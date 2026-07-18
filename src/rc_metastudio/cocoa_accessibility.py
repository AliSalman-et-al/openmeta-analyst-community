"""Fail-closed traversal of the native Cocoa accessibility object tree."""

from collections import deque
from collections.abc import Callable, Iterable
from typing import Hashable


def find_accessibility_element(
    roots: Iterable[Hashable],
    *,
    expected_role: str,
    expected_title: str,
    expected_description: str,
    observe: Callable[[Hashable], dict[str, object]],
    children: Callable[[Hashable], Iterable[Hashable]],
    max_nodes: int = 256,
) -> dict[str, object]:
    """Find the exact named, described element without trusting its backing NSView."""
    queue = deque(roots)
    seen: set[Hashable] = set()
    observed_states = {
        "with_role": 0,
        "with_title": 0,
        "with_description": 0,
        "accessibility_elements": 0,
    }
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        if len(seen) > max_nodes:
            raise RuntimeError("Cocoa accessibility traversal exceeded its node bound")
        observation = observe(current)
        observed_states["with_role"] += bool(observation.get("role"))
        observed_states["with_title"] += bool(observation.get("title"))
        observed_states["with_description"] += bool(
            observation.get("description")
        )
        observed_states["accessibility_elements"] += (
            observation.get("is_element") is True
        )
        if (
            observation.get("role") == expected_role
            and observation.get("title") == expected_title
            and observation.get("description") == expected_description
            and observation.get("is_element") is True
        ):
            return {
                **observation,
                "source": "accessibility-tree",
                "visited_nodes": len(seen),
                "observed_states": observed_states,
            }
        queue.extend(children(current))
    return {
        "role": "",
        "title": "",
        "description": "",
        "is_element": False,
        "source": "accessibility-tree",
        "visited_nodes": len(seen),
        "observed_states": observed_states,
    }


def bounded_error_message(error: Exception, *, max_chars: int = 240) -> str:
    """Return one bounded printable line for retained native-probe diagnostics."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    printable = "".join(
        character if character.isprintable() else " " for character in str(error)
    )
    return " ".join(printable.split())[:max_chars]
