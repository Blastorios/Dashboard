"""
Flatten a list of lists into a single list.
"""
from typing import Any, Dict, Callable, List
from operator import itemgetter


def flatten(l: List[list]) -> list:
    """Flatten a 2D list into a 1D list."""
    return [item for sublist in l for item in sublist]


def find_max_dict(
    collection: List[Dict[str, Any]], key: str, func: Callable | None = None
) -> Any:
    """Find the highest value behind a `key` in a collection dictionaries.

    Args:
        collection: A list of dictionaries.
        key: The key to find the highest value behind.
        func: A function to apply to every value in the collection.

    Returns:
        The highest value behind the `key`.

    Raises:
        ValueError: If the collection is empty.
        TypeError: If the collection is not a list of dictionaries.

    Example:
        `>>> find_max_dict([{'a': 1, 'b': 2}, {'a': 3, 'b': 4}], 'a')`
    """
    return max(map(itemgetter(key), collection), key=func)
