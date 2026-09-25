"""Intentionally smelly code fixture for test coverage."""


def long_and_complex_function(a, b, c, d, e, f, g):
    """A function that is too long, has too many parameters, deep nesting, and too many branches."""
    total = 0
    if a > 0:
        if b > 0:
            for i in range(10):
                while c > 0:
                    try:
                        total += a + b + c + d + e + f + g
                    except Exception:
                        pass
                    c -= 1
    # Adding lines to exceed 50-line threshold
    total += 1
    total += 2
    total += 3
    total += 4
    total += 5
    total += 6
    total += 7
    total += 8
    total += 9
    total += 10
    total += 11
    total += 12
    total += 13
    total += 14
    total += 15
    total += 16
    total += 17
    total += 18
    total += 19
    total += 20
    total += 21
    total += 22
    total += 23
    total += 24
    total += 25
    total += 26
    total += 27
    total += 28
    total += 29
    total += 30
    total += 31
    total += 32
    total += 33
    total += 34
    total += 35
    total += 36
    total += 37
    total += 38
    total += 39
    total += 40
    return total


class GodClassExample:
    """Class with too many methods."""

    def m1(self): pass
    def m2(self): pass
    def m3(self): pass
    def m4(self): pass
    def m5(self): pass
    def m6(self): pass
    def m7(self): pass
    def m8(self): pass
    def m9(self): pass
    def m10(self): pass
    def m11(self): pass
    def m12(self): pass
    def m13(self): pass
    def m14(self): pass
    def m15(self): pass
    def m16(self): pass


def unused_dead_function():
    # Never called anywhere
    return "dead"


def duplicate_task_alpha(val):
    x = val * 2
    y = x + 10
    z = y * 3
    w = z - 5
    return w


def duplicate_task_beta(other):
    x = other * 2
    y = x + 10
    z = y * 3
    w = z - 5
    return w


def function_with_bare_except():
    try:
        x = 1 / 0
    except:
        pass

