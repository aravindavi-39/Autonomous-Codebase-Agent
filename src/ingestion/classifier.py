"""File classification — documentation, configuration, and test detection."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

# --- Documentation patterns ---
DOCUMENTATION_NAMES: set[str] = {
    "readme", "readme.md", "readme.txt", "readme.rst",
    "changelog", "changelog.md", "changes", "changes.md",
    "contributing", "contributing.md",
    "license", "license.md", "license.txt",
    "authors", "authors.md", "authors.txt",
    "history", "history.md",
    "code_of_conduct", "code_of_conduct.md",
    "security", "security.md",
}

DOCUMENTATION_EXTENSIONS: set[str] = {
    ".md", ".markdown", ".rst", ".adoc",
}

DOCUMENTATION_DIRS: set[str] = {
    "docs", "doc", "documentation", "wiki",
}

# --- Configuration patterns ---
CONFIGURATION_NAMES: set[str] = {
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "package-lock.json",
    "tsconfig.json", "jsconfig.json",
    "webpack.config.js", "babel.config.js", "rollup.config.js",
    ".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.yml",
    ".prettierrc", ".prettierrc.json",
    "tox.ini", "pytest.ini",
    "makefile", "cmakelist.txt",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".gitignore", ".gitattributes", ".editorconfig",
    "cargo.toml", "go.mod", "go.sum",
    "pom.xml", "build.gradle", "build.gradle.kts",
    "gemfile", "rakefile",
    "requirements.txt", "pipfile", "pipfile.lock",
    "renovate.json", ".renovaterc", ".babelrc",
}

CONFIGURATION_EXTENSIONS: set[str] = {
    ".toml", ".ini", ".cfg", ".conf", ".properties",
}

# --- Test file patterns ---
TEST_DIR_NAMES: set[str] = {
    "test", "tests", "__tests__", "spec", "specs",
    "test_suite", "testing",
}

TEST_FILE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^test_.*\.py$"),
    re.compile(r"^.*_test\.py$"),
    re.compile(r"^.*\.test\.[jt]sx?$"),
    re.compile(r"^.*\.spec\.[jt]sx?$"),
    re.compile(r"^test_.*\.[jt]sx?$"),
    re.compile(r"^.*Test\.java$"),
    re.compile(r"^.*_test\.go$"),
    re.compile(r"^.*_test\.rs$"),
    re.compile(r"^conftest\.py$"),
]


def classify_file(
    file_name: str,
    extension: str,
    relative_path: str,
) -> tuple[bool, bool, bool]:
    """Classify a file as documentation, configuration, and/or test.

    Args:
        file_name: The file's base name.
        extension: The file's extension (including dot).
        relative_path: Posix-style path relative to repo root.

    Returns:
        ``(is_documentation, is_configuration, is_test_file)``.
    """
    is_doc = _is_documentation(file_name, extension, relative_path)
    is_config = _is_configuration(file_name, extension)
    is_test = _is_test_file(file_name, relative_path)
    return is_doc, is_config, is_test


def _is_documentation(file_name: str, extension: str, relative_path: str) -> bool:
    if file_name.lower() in DOCUMENTATION_NAMES:
        return True
    # Doc-extension files inside a documentation directory
    parts = PurePosixPath(relative_path).parts
    for part in parts[:-1]:
        if part.lower() in DOCUMENTATION_DIRS:
            if extension.lower() in DOCUMENTATION_EXTENSIONS:
                return True
    return False


def _is_configuration(file_name: str, extension: str) -> bool:
    if file_name.lower() in CONFIGURATION_NAMES:
        return True
    # Dotfiles with config extensions
    if file_name.startswith(".") and extension.lower() in {
        ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini",
    }:
        return True
    if extension.lower() in CONFIGURATION_EXTENSIONS:
        return True
    return False


def _is_test_file(file_name: str, relative_path: str) -> bool:
    for pattern in TEST_FILE_PATTERNS:
        if pattern.match(file_name):
            return True
    parts = PurePosixPath(relative_path).parts
    for part in parts[:-1]:
        if part.lower() in TEST_DIR_NAMES:
            return True
    return False
