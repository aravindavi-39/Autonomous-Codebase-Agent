"""Data models for the repository ingestion pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Language(str, Enum):
    """Supported programming language identifiers."""
    PYTHON = "Python"
    JAVASCRIPT = "JavaScript"
    TYPESCRIPT = "TypeScript"
    JAVA = "Java"
    C = "C"
    CPP = "C++"
    CSHARP = "C#"
    GO = "Go"
    RUST = "Rust"
    HTML = "HTML"
    CSS = "CSS"
    JSON = "JSON"
    YAML = "YAML"
    MARKDOWN = "Markdown"
    SQL = "SQL"
    SHELL = "Shell"
    TOML = "TOML"
    XML = "XML"
    DOCKERFILE = "Dockerfile"
    UNKNOWN = "Unknown"


class FileMetadata(BaseModel):
    """Technical metadata for a single file."""
    size_bytes: int = Field(..., description="File size in bytes")
    line_count: int = Field(0, description="Number of lines")
    is_binary: bool = Field(False, description="Whether the file is binary")


class FileRecord(BaseModel):
    """Complete record for a discovered file."""
    relative_path: str = Field(..., description="Path relative to repo root (posix-style)")
    file_name: str = Field(..., description="File name with extension")
    extension: str = Field("", description="File extension including dot")
    language: Language = Field(Language.UNKNOWN)
    metadata: FileMetadata
    is_documentation: bool = Field(False)
    is_configuration: bool = Field(False)
    is_test_file: bool = Field(False)


class DirectoryInfo(BaseModel):
    """Information about a directory in the repository."""
    relative_path: str
    name: str
    file_count: int = 0
    subdirectory_count: int = 0


class RepositoryStatistics(BaseModel):
    """Aggregate statistics about the repository."""
    total_files: int = 0
    total_directories: int = 0
    total_lines: int = 0
    files_by_language: dict[str, int] = Field(default_factory=dict)
    largest_files: list[FileRecord] = Field(default_factory=list)
    test_files: list[FileRecord] = Field(default_factory=list)
    documentation_files: list[FileRecord] = Field(default_factory=list)
    configuration_files: list[FileRecord] = Field(default_factory=list)


class RepositoryManifest(BaseModel):
    """Complete manifest of an ingested repository."""
    name: str
    root_path: str
    files: list[FileRecord] = Field(default_factory=list)
    directories: list[DirectoryInfo] = Field(default_factory=list)
    statistics: RepositoryStatistics = Field(default_factory=RepositoryStatistics)
    ingested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
