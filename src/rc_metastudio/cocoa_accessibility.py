"""Fail-closed traversal of the native Cocoa accessibility object tree."""

from collections import deque
from collections.abc import Callable, Iterable
from typing import Hashable


def find_accessibility_element(
    roots: Iterable[Hashable],
    *,
    expected_label: str,
    observe: Callable[[Hashable], dict[str, object]],
    children: Callable[[Hashable], Iterable[Hashable]],
    max_nodes: int = 256,
) -> dict[str, object]:
    """Find the exact labeled, exposed element without trusting the backing NSView."""
    queue = deque(roots)
    seen: set[Hashable] = set()
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        if len(seen) > max_nodes:
            raise RuntimeError("Cocoa accessibility traversal exceeded its node bound")
        observation = observe(current)
        if (
            observation.get("label") == expected_label
            and bool(observation.get("role"))
            and observation.get("is_element") is True
        ):
            return {**observation, "source": "accessibility-tree"}
        queue.extend(children(current))
    return {
        "role": "",
        "label": "",
        "is_element": False,
        "source": "accessibility-tree",
        "visited_nodes": len(seen),
    }
