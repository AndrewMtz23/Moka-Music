"""Pure numbering plans; file I/O and manual-lock persistence belong to the controller."""


def plan_gap_closure(tracks: list[tuple[str, int, bool]], removed_number: int | None) -> list[tuple[str, int]]:
    """Close one removed slot through the contiguous block, reserving locked numbers.

    Input rows are (filename, track_number, is_track_locked). Preexisting gaps
    terminate the block so unrelated, distant assignments remain unchanged.
    """
    if (
        removed_number is None
        or removed_number < 0
        or any(number == removed_number for _name, number, _manual in tracks)
    ):
        return []
    reserved = {number for _name, number, manual in tracks if manual or number < removed_number}
    next_number = removed_number
    previous = removed_number
    plan = []
    for filename, number, manual in sorted(tracks, key=lambda item: (item[1], item[0])):
        if number <= removed_number:
            continue
        if number > previous + 1:
            break
        previous = number
        if manual:
            continue
        while next_number in reserved:
            next_number += 1
        if next_number < number:
            plan.append((filename, next_number))
        next_number += 1
    return plan
