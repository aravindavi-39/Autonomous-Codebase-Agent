"""Programming language detection from file extensions and names."""

from __future__ import annotations

from ingestion.models import Language

# Extension → Language mapping
EXTENSION_MAP: dict[str, Language] = {
    # Python
    ".py": Language.PYTHON, ".pyi": Language.PYTHON, ".pyw": Language.PYTHON,
    # JavaScript
    ".js": Language.JAVASCRIPT, ".jsx": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT, ".cjs": Language.JAVASCRIPT,
    # TypeScript
    ".ts": Language.TYPESCRIPT, ".tsx": Language.TYPESCRIPT,
    # Java
    ".java": Language.JAVA,
    # C
    ".c": Language.C, ".h": Language.C,
    # C++
    ".cpp": Language.CPP, ".cxx": Language.CPP, ".cc": Language.CPP,
    ".hpp": Language.CPP, ".hxx": Language.CPP,
    # C#
    ".cs": Language.CSHARP,
    # Go
    ".go": Language.GO,
    # Rust
    ".rs": Language.RUST,
    # HTML
    ".html": Language.HTML, ".htm": Language.HTML,
    # CSS
    ".css": Language.CSS, ".scss": Language.CSS, ".sass": Language.CSS, ".less": Language.CSS,
    # JSON
    ".json": Language.JSON,
    # YAML
    ".yaml": Language.YAML, ".yml": Language.YAML,
    # Markdown
    ".md": Language.MARKDOWN, ".markdown": Language.MARKDOWN, ".rst": Language.MARKDOWN,
    # SQL
    ".sql": Language.SQL,
    # Shell
    ".sh": Language.SHELL, ".bash": Language.SHELL, ".zsh": Language.SHELL,
    ".bat": Language.SHELL, ".cmd": Language.SHELL, ".ps1": Language.SHELL,
    # TOML
    ".toml": Language.TOML,
    # XML
    ".xml": Language.XML, ".xsl": Language.XML, ".xslt": Language.XML,
}

# Special filename → Language
FILENAME_MAP: dict[str, Language] = {
    "Dockerfile": Language.DOCKERFILE,
    "Makefile": Language.SHELL,
    "Jenkinsfile": Language.UNKNOWN,
}


def detect_language(file_name: str, extension: str) -> Language:
    """Detect programming language from file name and extension.

    Checks special filenames first, then falls back to extension mapping.
    """
    if file_name in FILENAME_MAP:
        return FILENAME_MAP[file_name]
    ext_lower = extension.lower()
    return EXTENSION_MAP.get(ext_lower, Language.UNKNOWN)
