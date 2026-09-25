"""Classify imports as standard-library, third-party, or local.

Uses ``sys.stdlib_module_names`` (Python 3.10+) with a comprehensive fallback
set for stdlib detection, and repository file structure for local-module detection.
No network requests are ever made.
"""

from __future__ import annotations

import sys
from typing import Optional

# Comprehensive stdlib module list for fallback or older python environments
_FALLBACK_STDLIB: frozenset[str] = frozenset({
    "abc", "argparse", "array", "ast", "asyncio", "atexit", "base64", "bdb",
    "binascii", "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb",
    "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections",
    "colorsys", "compileall", "concurrent", "configparser", "contextlib",
    "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv", "ctypes",
    "curses", "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis",
    "distutils", "doctest", "email", "encodings", "ensurepip", "enum", "errno",
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch", "fractions",
    "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob",
    "graphlib", "gzip", "hashlib", "heapq", "hmac", "html", "http", "idlelib",
    "imaplib", "imghdr", "imp", "importlib", "inspect", "io", "ipaddress",
    "itertools", "json", "keyword", "lib2to3", "linecache", "locale", "logging",
    "lzma", "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "msilib", "msvcrt", "multiprocessing", "netrc", "nis",
    "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev", "pathlib",
    "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform", "plistlib",
    "poplib", "posix", "posixpath", "pprint", "profile", "pstats", "pty",
    "pwd", "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random",
    "re", "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched",
    "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal",
    "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd",
    "sqlite3", "sre", "sre_compile", "sre_constants", "sre_parse", "ssl",
    "stat", "statistics", "string", "stringprep", "struct", "subprocess",
    "sunau", "symbol", "symtable", "sys", "sysconfig", "syslog", "tabnanny",
    "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap", "threading",
    "time", "timeit", "tkinter", "token", "tokenize", "tomllib", "trace",
    "traceback", "tracemalloc", "tty", "turtle", "turtledemo", "types",
    "typing", "unicodedata", "unittest", "urllib", "uu", "uuid", "venv",
    "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
    "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    "zoneinfo",
})

_SYS_STDLIB = getattr(sys, "stdlib_module_names", None)
_STDLIB_MODULES: frozenset[str] = (
    frozenset(_SYS_STDLIB) if _SYS_STDLIB else _FALLBACK_STDLIB
)


def classify_import(
    module: str,
    local_modules: Optional[set[str]] = None,
    is_relative: bool = False,
) -> str:
    """Classify an import as ``'stdlib'``, ``'third_party'``, or ``'local'``.

    Args:
        module: Dotted module path (e.g. ``'os.path'`` or ``'src.app'``).
        local_modules: Top-level module/package names belonging to the target repo.
        is_relative: Whether the import is a relative from-import (e.g. ``from . import foo``).

    Returns:
        One of ``'stdlib'``, ``'local'``, ``'third_party'``.
    """
    if is_relative or not module:
        return "local"

    top_level = module.split(".")[0]

    # Check local modules first in case project shadows a name or has local packages
    if local_modules and top_level in local_modules:
        return "local"

    if top_level in _STDLIB_MODULES:
        return "stdlib"

    return "third_party"
