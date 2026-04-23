from __future__ import annotations

from ai_friction_map.events import ParsedEvent

_boundary_clip_count: int = 0


def is_compact_boundary(event: ParsedEvent) -> bool:
    return event.type == "system" and event.subtype == "compact_boundary"


def window_events(
    events: list[ParsedEvent],
    center_idx: int,
    n: int,
) -> tuple[int, int]:
    """Return (lo, hi) inclusive indices around center_idx.

    Spans up to n events on each side, stopping just before any
    system/compact_boundary event. The boundary event itself is excluded
    from the returned range. Result is clamped to [0, len(events) - 1].

    Whenever a boundary truncates what would otherwise have been a full
    ±n span, the module-level clip counter increments. Use
    get_boundary_clip_count() / reset_boundary_clip_count() for the
    corpus checkpoint.
    """
    global _boundary_clip_count
    last = len(events) - 1
    if last < 0:
        return (0, -1)

    lo = max(0, center_idx - n)
    hi = min(last, center_idx + n)

    # Walk backward from center-1; stop at first boundary.
    walked_back = 0
    lo_final = center_idx
    for i in range(center_idx - 1, lo - 1, -1):
        if is_compact_boundary(events[i]):
            break
        lo_final = i
        walked_back += 1
    if walked_back < (center_idx - lo):
        # Loop exited early — the only way that happens is hitting a
        # boundary inside the clamped span. Count it. The corpus-edge
        # clamp is already baked into `lo`, so this fires only on true
        # boundary clips.
        _boundary_clip_count += 1

    walked_fwd = 0
    hi_final = center_idx
    for i in range(center_idx + 1, hi + 1):
        if is_compact_boundary(events[i]):
            break
        hi_final = i
        walked_fwd += 1
    if walked_fwd < (hi - center_idx):
        _boundary_clip_count += 1

    return (lo_final, hi_final)


def get_boundary_clip_count() -> int:
    return _boundary_clip_count


def reset_boundary_clip_count() -> None:
    global _boundary_clip_count
    _boundary_clip_count = 0
