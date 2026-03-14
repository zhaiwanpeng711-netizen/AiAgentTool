"""Sorting algorithms library.

All functions return a new list and do not mutate the input iterable.
"""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")
K = TypeVar("K")


Decorated = Tuple[K, int, T]


def _decorate(items: Sequence[T], key: Optional[Callable[[T], K]]) -> List[Decorated]:
    if key is None:
        return [(item, idx, item) for idx, item in enumerate(items)]  # type: ignore[misc]
    return [(key(item), idx, item) for idx, item in enumerate(items)]


def _lt(a: Decorated, b: Decorated, reverse: bool) -> bool:
    return (a[0], a[1]) > (b[0], b[1]) if reverse else (a[0], a[1]) < (b[0], b[1])


def _le(a: Decorated, b: Decorated, reverse: bool) -> bool:
    return (a[0], a[1]) >= (b[0], b[1]) if reverse else (a[0], a[1]) <= (b[0], b[1])


def _gt(a: Decorated, b: Decorated, reverse: bool) -> bool:
    return (a[0], a[1]) < (b[0], b[1]) if reverse else (a[0], a[1]) > (b[0], b[1])


def bubble_sort(iterable: Iterable[T], *, key: Optional[Callable[[T], K]] = None, reverse: bool = False) -> List[T]:
    items = list(iterable)
    decorated = _decorate(items, key)
    n = len(decorated)
    for i in range(n):
        swapped = False
        for j in range(0, n - 1 - i):
            if _gt(decorated[j], decorated[j + 1], reverse):
                decorated[j], decorated[j + 1] = decorated[j + 1], decorated[j]
                swapped = True
        if not swapped:
            break
    return [value for _, _, value in decorated]


def insertion_sort(
    iterable: Iterable[T], *, key: Optional[Callable[[T], K]] = None, reverse: bool = False
) -> List[T]:
    items = list(iterable)
    decorated = _decorate(items, key)
    for i in range(1, len(decorated)):
        current = decorated[i]
        j = i - 1
        while j >= 0 and _gt(decorated[j], current, reverse):
            decorated[j + 1] = decorated[j]
            j -= 1
        decorated[j + 1] = current
    return [value for _, _, value in decorated]


def selection_sort(
    iterable: Iterable[T], *, key: Optional[Callable[[T], K]] = None, reverse: bool = False
) -> List[T]:
    items = list(iterable)
    decorated = _decorate(items, key)
    n = len(decorated)
    for i in range(n):
        best = i
        for j in range(i + 1, n):
            if _lt(decorated[j], decorated[best], reverse):
                best = j
        if best != i:
            decorated[i], decorated[best] = decorated[best], decorated[i]
    return [value for _, _, value in decorated]


def merge_sort(iterable: Iterable[T], *, key: Optional[Callable[[T], K]] = None, reverse: bool = False) -> List[T]:
    items = list(iterable)
    decorated = _decorate(items, key)

    def _merge(left: List[Decorated], right: List[Decorated]) -> List[Decorated]:
        merged: List[Decorated] = []
        i = 0
        j = 0
        while i < len(left) and j < len(right):
            if _le(left[i], right[j], reverse):
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
        if i < len(left):
            merged.extend(left[i:])
        if j < len(right):
            merged.extend(right[j:])
        return merged

    def _merge_sort(seq: List[Decorated]) -> List[Decorated]:
        if len(seq) <= 1:
            return seq
        mid = len(seq) // 2
        left = _merge_sort(seq[:mid])
        right = _merge_sort(seq[mid:])
        return _merge(left, right)

    result = _merge_sort(decorated)
    return [value for _, _, value in result]


def quick_sort(iterable: Iterable[T], *, key: Optional[Callable[[T], K]] = None, reverse: bool = False) -> List[T]:
    items = list(iterable)
    decorated = _decorate(items, key)

    def _partition(arr: List[Decorated], low: int, high: int) -> int:
        pivot = arr[high]
        i = low
        for j in range(low, high):
            if _le(arr[j], pivot, reverse):
                arr[i], arr[j] = arr[j], arr[i]
                i += 1
        arr[i], arr[high] = arr[high], arr[i]
        return i

    def _quick_sort(arr: List[Decorated], low: int, high: int) -> None:
        if low >= high:
            return
        pivot_index = _partition(arr, low, high)
        _quick_sort(arr, low, pivot_index - 1)
        _quick_sort(arr, pivot_index + 1, high)

    _quick_sort(decorated, 0, len(decorated) - 1)
    return [value for _, _, value in decorated]
