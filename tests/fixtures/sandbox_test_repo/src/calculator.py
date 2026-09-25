"""Calculator implementation with intentional patterns for refactoring testing."""

import sys


def add_entry(val, history=[]):
    """Function with a mutable default argument and unused import sys."""
    history.append(val)
    return sum(history)


def multiply_numbers(a, b):
    """Pure multiplication."""
    return a * b
