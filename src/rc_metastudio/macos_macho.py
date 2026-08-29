# SPDX-FileCopyrightText: 2026 Ali Salman and RC MetaStudio contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure Mach-O architecture and Java ClassFile collision detection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO, Literal


class MachOError(ValueError):
    """Raised when a Mach-O payload is malformed or unsupported."""


MAX_ARCHITECTURES = 16
CPU_ARCHITECTURES = {
    0x01000007: "x86_64",
    0x0100000C: "arm64",
}
CPU_SUBTYPE_MASK = 0xFF000000
CPU_SUBTYPES = {
    0x01000007: {3: {0, 0x80000000}},
    0x0100000C: {0: {0}},
}
THIN_MAGICS: dict[bytes, tuple[Literal["big", "little"], int, bool]] = {
    b"\xfe\xed\xfa\xce": ("big", 28, False),
    b"\xce\xfa\xed\xfe": ("little", 28, False),
    b"\xfe\xed\xfa\xcf": ("big", 32, True),
    b"\xcf\xfa\xed\xfe": ("little", 32, True),
}
FAT_MAGICS: dict[bytes, tuple[Literal["big", "little"], int]] = {
    b"\xca\xfe\xba\xbe": ("big", 20),
    b"\xbe\xba\xfe\xca": ("little", 20),
    b"\xca\xfe\xba\xbf": ("big", 32),
    b"\xbf\xba\xfe\xca": ("little", 32),
}
MACHO_MAGICS = frozenset((*THIN_MAGICS, *FAT_MAGICS))
JAVA_CLASS_MAGIC = b"\xca\xfe\xba\xbe"


class _NotJavaClass(ValueError):
    pass


def _read_java_bytes(stream: BinaryIO, size: int, label: str) -> bytes:
    remaining = os.fstat(stream.fileno()).st_size - stream.tell()
    if size < 0 or size > remaining:
        raise _NotJavaClass(f"truncated Java {label}")
    value = stream.read(size)
    if len(value) != size:
        raise _NotJavaClass(f"truncated Java {label}")
    return value


def _skip_java_bytes(stream: BinaryIO, size: int, label: str) -> None:
    remaining = os.fstat(stream.fileno()).st_size - stream.tell()
    if size < 0 or size > remaining:
        raise _NotJavaClass(f"truncated Java {label}")
    stream.seek(size, os.SEEK_CUR)


def _valid_modified_utf8(value: bytes) -> bool:
    index = 0
    while index < len(value):
        first = value[index]
        if 0x01 <= first <= 0x7F:
            index += 1
            continue
        if 0xC0 <= first <= 0xDF:
            if index + 1 >= len(value):
                return False
            second = value[index + 1]
            if second & 0xC0 != 0x80:
                return False
            code_unit = ((first & 0x1F) << 6) | (second & 0x3F)
            if code_unit == 0:
                if first != 0xC0 or second != 0x80:
                    return False
            elif code_unit < 0x80:
                return False
            index += 2
            continue
        if 0xE0 <= first <= 0xEF:
            if index + 2 >= len(value):
                return False
            second, third = value[index + 1 : index + 3]
            if second & 0xC0 != 0x80 or third & 0xC0 != 0x80:
                return False
            code_unit = ((first & 0x0F) << 12) | ((second & 0x3F) << 6) | (third & 0x3F)
            if code_unit < 0x800:
                return False
            index += 3
            continue
        return False
    return True


def _valid_java_version(major: int, minor: int) -> bool:
    if major == 45:
        return 0 <= minor <= 3
    if 46 <= major <= 55:
        return minor == 0
    return 56 <= major <= 100 and minor in {0, 0xFFFF}


def _read_java_u1(stream: BinaryIO, label: str) -> int:
    return _read_java_bytes(stream, 1, label)[0]


def _read_java_u2(stream: BinaryIO, label: str) -> int:
    return int.from_bytes(_read_java_bytes(stream, 2, label), "big")


def _read_java_u4(stream: BinaryIO, label: str) -> int:
    return int.from_bytes(_read_java_bytes(stream, 4, label), "big")


def _java_cp_tag(tags: list[int | None], index: int, allowed: set[int]) -> bool:
    return 0 < index < len(tags) and tags[index] in allowed


def _skip_java_attributes(stream: BinaryIO, tags: list[int | None], count: int) -> None:
    for _ in range(count):
        name_index = _read_java_u2(stream, "attribute name")
        if not _java_cp_tag(tags, name_index, {1}):
            raise _NotJavaClass("invalid Java attribute name")
        length = _read_java_u4(stream, "attribute length")
        _skip_java_bytes(stream, length, "attribute body")


def _skip_java_members(stream: BinaryIO, tags: list[int | None], count: int) -> None:
    for _ in range(count):
        _read_java_u2(stream, "member access flags")
        name_index = _read_java_u2(stream, "member name")
        descriptor_index = _read_java_u2(stream, "member descriptor")
        if not _java_cp_tag(tags, name_index, {1}) or not _java_cp_tag(
            tags, descriptor_index, {1}
        ):
            raise _NotJavaClass("invalid Java member identity")
        _skip_java_attributes(
            stream, tags, _read_java_u2(stream, "member attribute count")
        )


def is_valid_java_class(path: Path) -> bool:
    """Return true only for a structurally complete JVM ClassFile payload."""
    try:
        file_size = path.stat().st_size
        with path.open("rb") as stream:
            if _read_java_bytes(stream, 4, "magic") != JAVA_CLASS_MAGIC:
                return False
            minor = _read_java_u2(stream, "minor version")
            major = _read_java_u2(stream, "major version")
            if not _valid_java_version(major, minor):
                return False
            constant_pool_count = _read_java_u2(stream, "constant-pool count")
            if constant_pool_count < 1:
                return False
            tags: list[int | None] = [None] * constant_pool_count
            references: list[tuple[int, set[int]]] = []
            index = 1
            while index < constant_pool_count:
                tag = _read_java_u1(stream, "constant-pool tag")
                tags[index] = tag
                if tag == 1:
                    utf8_value = _read_java_bytes(
                        stream,
                        _read_java_u2(stream, "UTF-8 constant length"),
                        "UTF-8 constant",
                    )
                    if not _valid_modified_utf8(utf8_value):
                        return False
                elif tag in {3, 4}:
                    _read_java_bytes(stream, 4, "numeric constant")
                elif tag in {5, 6}:
                    _read_java_bytes(stream, 8, "wide numeric constant")
                    index += 1
                    if index >= constant_pool_count:
                        raise _NotJavaClass("wide Java constant has no reserved slot")
                elif tag in {7, 8, 16, 19, 20}:
                    references.append(
                        (_read_java_u2(stream, "constant reference"), {1})
                    )
                elif tag in {9, 10, 11}:
                    references.append((_read_java_u2(stream, "class reference"), {7}))
                    references.append(
                        (_read_java_u2(stream, "name/type reference"), {12})
                    )
                elif tag == 12:
                    references.append((_read_java_u2(stream, "name reference"), {1}))
                    references.append(
                        (_read_java_u2(stream, "descriptor reference"), {1})
                    )
                elif tag == 15:
                    kind = _read_java_u1(stream, "method-handle kind")
                    reference = _read_java_u2(stream, "method-handle reference")
                    allowed = {
                        1: {9},
                        2: {9},
                        3: {9},
                        4: {9},
                        5: {10},
                        6: {10, 11},
                        7: {10, 11},
                        8: {10},
                        9: {11},
                    }.get(kind)
                    if allowed is None:
                        raise _NotJavaClass("invalid Java method-handle kind")
                    references.append((reference, allowed))
                elif tag in {17, 18}:
                    _read_java_u2(stream, "bootstrap-method index")
                    references.append(
                        (_read_java_u2(stream, "name/type reference"), {12})
                    )
                else:
                    return False
                index += 1
            if not all(
                _java_cp_tag(tags, reference, allowed)
                for reference, allowed in references
            ):
                return False
            _read_java_u2(stream, "class access flags")
            this_class = _read_java_u2(stream, "this class")
            super_class = _read_java_u2(stream, "super class")
            if not _java_cp_tag(tags, this_class, {7}) or (
                super_class and not _java_cp_tag(tags, super_class, {7})
            ):
                return False
            for _ in range(_read_java_u2(stream, "interface count")):
                if not _java_cp_tag(tags, _read_java_u2(stream, "interface"), {7}):
                    return False
            _skip_java_members(stream, tags, _read_java_u2(stream, "field count"))
            _skip_java_members(stream, tags, _read_java_u2(stream, "method count"))
            _skip_java_attributes(
                stream, tags, _read_java_u2(stream, "class attribute count")
            )
            return stream.tell() == file_size
    except _NotJavaClass:
        return False


def is_macho_candidate(path: Path) -> bool:
    """Identify Mach-O magic while excluding structurally valid Java ClassFiles."""
    with path.open("rb") as stream:
        magic = stream.read(4)
    if magic not in MACHO_MAGICS:
        return False
    return magic != JAVA_CLASS_MAGIC or not is_valid_java_class(path)


def _macho_cpu_identity(
    cpu_type: int, raw_subtype: int, path: Path
) -> tuple[str, int, int]:
    architecture = CPU_ARCHITECTURES.get(cpu_type)
    if architecture is None:
        raise MachOError(
            f"Mach-O file {path} has unsupported CPU type 0x{cpu_type:08x}"
        )
    base_subtype = raw_subtype & ~CPU_SUBTYPE_MASK
    capabilities = raw_subtype & CPU_SUBTYPE_MASK
    supported_capabilities = CPU_SUBTYPES[cpu_type].get(base_subtype)
    if supported_capabilities is None or capabilities not in supported_capabilities:
        raise MachOError(
            f"Mach-O file {path} has unsupported {architecture} CPU subtype "
            f"0x{raw_subtype:08x}"
        )
    return architecture, base_subtype, capabilities


def _read_macho_bytes(
    stream: BinaryIO, path: Path, offset: int, size: int, label: str
) -> bytes:
    stream.seek(offset)
    value = stream.read(size)
    if len(value) != size:
        raise MachOError(f"Mach-O file {path} has a truncated {label}")
    return value


def _thin_macho_architecture(
    header: bytes, available_size: int, path: Path
) -> tuple[str, int, int]:
    if len(header) < 12:
        raise MachOError(f"Mach-O file {path} has a truncated thin header")
    thin_format = THIN_MAGICS.get(header[:4])
    if thin_format is None:
        raise MachOError(f"Mach-O file {path} has an unsupported thin magic")
    byte_order, minimum_header_size, is_64_bit = thin_format
    if available_size < minimum_header_size:
        raise MachOError(f"Mach-O file {path} has a truncated thin header")
    cpu_type = int.from_bytes(header[4:8], byte_order)
    if bool(cpu_type & 0x01000000) != is_64_bit:
        raise MachOError(
            f"Mach-O file {path} has a CPU type inconsistent with its thin class"
        )
    raw_subtype = int.from_bytes(header[8:12], byte_order)
    return _macho_cpu_identity(cpu_type, raw_subtype, path)


def architectures(path: Path) -> list[str]:
    """Return sorted native architectures after strict Mach-O validation."""
    try:
        file_size = path.stat().st_size
        with path.open("rb") as stream:
            header = _read_macho_bytes(stream, path, 0, 8, "header")
            fat_format = FAT_MAGICS.get(header[:4])
            if fat_format is None:
                thin_header = header + _read_macho_bytes(
                    stream, path, 8, 4, "thin header"
                )
                return [_thin_macho_architecture(thin_header, file_size, path)[0]]
            byte_order, entry_size = fat_format
            architecture_count = int.from_bytes(header[4:8], byte_order)
            if not 1 <= architecture_count <= MAX_ARCHITECTURES:
                raise MachOError(
                    f"Mach-O file {path} has an invalid fat architecture count"
                )
            table_end = 8 + architecture_count * entry_size
            if table_end > file_size:
                raise MachOError(
                    f"Mach-O file {path} has a truncated fat architecture table"
                )
            parsed: list[str] = []
            slice_ranges: list[tuple[int, int]] = []
            for index in range(architecture_count):
                entry = _read_macho_bytes(
                    stream,
                    path,
                    8 + index * entry_size,
                    entry_size,
                    "fat architecture entry",
                )
                declared = _macho_cpu_identity(
                    int.from_bytes(entry[0:4], byte_order),
                    int.from_bytes(entry[4:8], byte_order),
                    path,
                )
                field_size = 8 if entry_size == 32 else 4
                slice_offset = int.from_bytes(entry[8 : 8 + field_size], byte_order)
                slice_size = int.from_bytes(
                    entry[8 + field_size : 8 + 2 * field_size], byte_order
                )
                alignment_offset = 24 if entry_size == 32 else 16
                alignment = int.from_bytes(
                    entry[alignment_offset : alignment_offset + 4], byte_order
                )
                if entry_size == 32 and int.from_bytes(entry[28:32], byte_order) != 0:
                    raise MachOError(
                        f"Mach-O file {path} has a nonzero fat64 reserved field"
                    )
                if (
                    slice_offset < table_end
                    or slice_size < 8
                    or slice_offset > file_size
                    or slice_size > file_size - slice_offset
                    or alignment > 63
                    or slice_offset % (1 << alignment) != 0
                ):
                    raise MachOError(
                        f"Mach-O file {path} has an out-of-bounds fat slice"
                    )
                slice_end = slice_offset + slice_size
                if any(
                    slice_offset < existing_end and existing_start < slice_end
                    for existing_start, existing_end in slice_ranges
                ):
                    raise MachOError(f"Mach-O file {path} has overlapping fat slices")
                slice_ranges.append((slice_offset, slice_end))
                actual = _thin_macho_architecture(
                    _read_macho_bytes(
                        stream, path, slice_offset, 12, "fat slice header"
                    ),
                    slice_size,
                    path,
                )
                if actual != declared:
                    raise MachOError(
                        f"Mach-O file {path} has a mismatched fat slice CPU identity"
                    )
                architecture = actual[0]
                if architecture in parsed:
                    raise MachOError(
                        f"Mach-O file {path} has a duplicate fat architecture"
                    )
                parsed.append(architecture)
            return sorted(parsed)
    except MachOError:
        raise
    except OSError as error:
        raise MachOError(f"cannot read Mach-O file {path}: {error}") from error
