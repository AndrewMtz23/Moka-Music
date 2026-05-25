from collections.abc import Iterable


def normalize_position(position: int, length: int) -> int:
    """Return a 1-based insertion position clamped to the playlist bounds."""
    try:
        numeric_position = int(position)
    except (TypeError, ValueError):
        numeric_position = 1
    return max(1, min(numeric_position, length + 1))


def unique_filenames(filenames: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for filename in filenames:
        if not filename or filename in seen:
            continue
        unique.append(filename)
        seen.add(filename)
    return unique


def insert_at_position(current_order: list[str], filenames: Iterable[str], position: int) -> list[str]:
    """Insert filenames as a block at a 1-based position.

    If any inserted filename already exists in the current order, it is moved
    instead of duplicated.
    """
    inserted = unique_filenames(filenames)
    if not inserted:
        return current_order.copy()

    moving = set(inserted)
    remaining_order = [filename for filename in current_order if filename not in moving]
    insertion_position = normalize_position(position, len(remaining_order))
    insertion_index = insertion_position - 1
    return remaining_order[:insertion_index] + inserted + remaining_order[insertion_index:]


def renumber_order(order: Iterable[str], start: int = 1) -> dict[str, int]:
    try:
        first_number = int(start)
    except (TypeError, ValueError):
        first_number = 0
    return {
        filename: index
        for index, filename in enumerate(order, start=max(0, first_number))
    }
