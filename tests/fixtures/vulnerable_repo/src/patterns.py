"""Intentionally problematic coding patterns fixture for test coverage."""

from math import *
import sys


def parse_something(value):
    try:
        return int(value)
    except Exception:
        pass


def append_to_list(val, items=[]):
    items.append(val)
    return items


def query_item(id, type):
    result = f"{id}:{type}"
    return result
    print("unreachable debug message")
