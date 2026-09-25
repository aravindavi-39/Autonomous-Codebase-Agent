"""Pydantic data models for AST analysis results.

Every entity preserves source-location information (file, start_line,
end_line) so that later phases can produce accurate citations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from ingestion.models import RepositoryManifest


# ------------------------------------------------------------------
# Import analysis
# ------------------------------------------------------------------

class ImportInfo(BaseModel):
    """A single import statement."""

    module: str = Field("", description="Module path, e.g. 'os' or 'pathlib'")
    name: Optional[str] = Field(None, description="Imported name for from-imports")
    alias: Optional[str] = Field(None, description="Import alias (as ...)")
    is_from_import: bool = False
    is_relative: bool = False
    category: str = Field(
        "unknown", description="'stdlib', 'third_party', or 'local'"
    )
    file: str = ""
    line: int = 0
    start_line: int = 0
    end_line: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def _sync_lines(cls, data: Any) -> Any:
        if isinstance(data, dict):
            line = data.get("line", 0)
            start = data.get("start_line", 0)
            if start and not line:
                data["line"] = start
            elif line and not start:
                data["start_line"] = line
            if data.get("end_line") is None:
                data["end_line"] = data.get("start_line", line)
        return data


# ------------------------------------------------------------------
# Function / method analysis
# ------------------------------------------------------------------

class ParameterInfo(BaseModel):
    """A single function parameter."""

    name: str
    annotation: Optional[str] = None
    default: Optional[str] = None
    kind: str = Field(
        "positional_or_keyword",
        description="positional_only | positional_or_keyword | var_positional | keyword_only | var_keyword",
    )


class DecoratorInfo(BaseModel):
    """A decorator applied to a function or class."""

    name: str
    file: str = ""
    line: int = 0
    start_line: int = 0
    end_line: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def _sync_lines(cls, data: Any) -> Any:
        if isinstance(data, dict):
            line = data.get("line", 0)
            start = data.get("start_line", 0)
            if start and not line:
                data["line"] = start
            elif line and not start:
                data["start_line"] = line
            if data.get("end_line") is None:
                data["end_line"] = data.get("start_line", line)
        return data


class CallInfo(BaseModel):
    """A function/method call site."""

    target: str = Field(..., description="Textual call target, e.g. 'db.save'")
    file: str = ""
    line: int = 0
    start_line: int = 0
    end_line: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def _sync_lines(cls, data: Any) -> Any:
        if isinstance(data, dict):
            line = data.get("line", 0)
            start = data.get("start_line", 0)
            if start and not line:
                data["line"] = start
            elif line and not start:
                data["start_line"] = line
            if data.get("end_line") is None:
                data["end_line"] = data.get("start_line", line)
        return data


class ExceptionInfo(BaseModel):
    """A ``raise`` statement."""

    exception_type: Optional[str] = None
    file: str = ""
    line: int = 0
    start_line: int = 0
    end_line: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def _sync_lines(cls, data: Any) -> Any:
        if isinstance(data, dict):
            line = data.get("line", 0)
            start = data.get("start_line", 0)
            if start and not line:
                data["line"] = start
            elif line and not start:
                data["start_line"] = line
            if data.get("end_line") is None:
                data["end_line"] = data.get("start_line", line)
        return data


class VariableInfo(BaseModel):
    """A variable assignment (module-level or class attribute)."""

    name: str
    file: str = ""
    line: int = 0
    start_line: int = 0
    end_line: Optional[int] = None
    annotation: Optional[str] = None
    value: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _sync_lines(cls, data: Any) -> Any:
        if isinstance(data, dict):
            line = data.get("line", 0)
            start = data.get("start_line", 0)
            if start and not line:
                data["line"] = start
            elif line and not start:
                data["start_line"] = line
            if data.get("end_line") is None:
                data["end_line"] = data.get("start_line", line)
        return data


class FunctionInfo(BaseModel):
    """Structural information about a function or method."""

    name: str
    file: str = ""
    line: int = 0
    start_line: int = 0
    end_line: Optional[int] = None
    parameters: list[ParameterInfo] = Field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: list[DecoratorInfo] = Field(default_factory=list)
    docstring: Optional[str] = None
    calls: list[CallInfo] = Field(default_factory=list)
    exceptions_raised: list[ExceptionInfo] = Field(default_factory=list)
    nested_functions: list[FunctionInfo] = Field(default_factory=list)
    is_method: bool = False
    is_async: bool = False

    @model_validator(mode="before")
    @classmethod
    def _sync_lines(cls, data: Any) -> Any:
        if isinstance(data, dict):
            line = data.get("line", 0)
            start = data.get("start_line", 0)
            if start and not line:
                data["line"] = start
            elif line and not start:
                data["start_line"] = line
            if data.get("end_line") is None and data.get("start_line"):
                data["end_line"] = data["start_line"]
        return data


# ------------------------------------------------------------------
# Class analysis
# ------------------------------------------------------------------

class ClassInfo(BaseModel):
    """Structural information about a class."""

    name: str
    file: str = ""
    line: int = 0
    start_line: int = 0
    end_line: Optional[int] = None
    base_classes: list[str] = Field(default_factory=list)
    decorators: list[DecoratorInfo] = Field(default_factory=list)
    docstring: Optional[str] = None
    methods: list[FunctionInfo] = Field(default_factory=list)
    attributes: list[VariableInfo] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _sync_lines(cls, data: Any) -> Any:
        if isinstance(data, dict):
            line = data.get("line", 0)
            start = data.get("start_line", 0)
            if start and not line:
                data["line"] = start
            elif line and not start:
                data["start_line"] = line
            if data.get("end_line") is None and data.get("start_line"):
                data["end_line"] = data["start_line"]
        return data


# ------------------------------------------------------------------
# File-level analysis
# ------------------------------------------------------------------

class FileAnalysis(BaseModel):
    """Complete AST analysis of a single Python source file."""

    file_path: str = Field(..., description="Path relative to repo root")
    status: str = Field("ok", description="'ok' | 'parse_error' | 'read_error'")
    error_message: Optional[str] = None
    error_line: Optional[int] = None

    imports: list[ImportInfo] = Field(default_factory=list)
    classes: list[ClassInfo] = Field(default_factory=list)
    functions: list[FunctionInfo] = Field(default_factory=list)
    variables: list[VariableInfo] = Field(default_factory=list)
    calls: list[CallInfo] = Field(default_factory=list)
    docstring: Optional[str] = None


# ------------------------------------------------------------------
# Repository-level code index
# ------------------------------------------------------------------

class AnalysisSummary(BaseModel):
    """Aggregate counts across all analysed files."""

    python_files_analyzed: int = 0
    parse_errors: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_methods: int = 0
    total_imports: int = 0
    total_calls: int = 0


class RepositoryCodeIndex(BaseModel):
    """Top-level container combining ingestion manifest with AST analyses."""

    manifest: RepositoryManifest
    file_analyses: list[FileAnalysis] = Field(default_factory=list)
    summary: AnalysisSummary = Field(default_factory=AnalysisSummary)

    def get_classes(self) -> list[ClassInfo]:
        """Return all classes across all analyzed files."""
        result: list[ClassInfo] = []
        for fa in self.file_analyses:
            result.extend(fa.classes)
        return result

    def get_functions(
        self,
        include_methods: bool = False,
        include_nested: bool = False,
    ) -> list[FunctionInfo]:
        """Return functions across all analyzed files."""
        result: list[FunctionInfo] = []
        for fa in self.file_analyses:
            for fn in fa.functions:
                result.append(fn)
                if include_nested:
                    result.extend(self._collect_nested_functions(fn))
            if include_methods:
                for cls in fa.classes:
                    for m in cls.methods:
                        result.append(m)
                        if include_nested:
                            result.extend(self._collect_nested_functions(m))
        return result

    def _collect_nested_functions(self, fn: FunctionInfo) -> list[FunctionInfo]:
        nested: list[FunctionInfo] = []
        for sub_fn in fn.nested_functions:
            nested.append(sub_fn)
            nested.extend(self._collect_nested_functions(sub_fn))
        return nested

    def find_function(self, name: str) -> list[FunctionInfo]:
        """Find functions or methods matching *name*."""
        matches: list[FunctionInfo] = []
        for fn in self.get_functions(include_methods=True, include_nested=True):
            if fn.name == name:
                matches.append(fn)
        return matches

    def find_class(self, name: str) -> list[ClassInfo]:
        """Find classes matching *name*."""
        return [cls for cls in self.get_classes() if cls.name == name]

    def get_calls_for_function(self, func_name: str) -> list[CallInfo]:
        """Return all calls made within function(s) or method(s) named *func_name*."""
        calls: list[CallInfo] = []
        for fn in self.find_function(func_name):
            calls.extend(fn.calls)
        return calls

    def get_modules_importing(self, module_name: str) -> list[str]:
        """Return file paths of files that import the given module name."""
        importers: set[str] = set()
        for fa in self.file_analyses:
            for imp in fa.imports:
                if imp.module == module_name or imp.module.startswith(f"{module_name}."):
                    importers.add(fa.file_path)
                    break
                elif imp.is_from_import and not imp.module and imp.name == module_name:
                    importers.add(fa.file_path)
                    break
        return sorted(list(importers))

    def get_subclasses(self, base_class_name: str) -> list[ClassInfo]:
        """Find classes that inherit from *base_class_name*."""
        subclasses: list[ClassInfo] = []
        for cls in self.get_classes():
            for base in cls.base_classes:
                if base == base_class_name or base.endswith(f".{base_class_name}"):
                    subclasses.append(cls)
                    break
        return subclasses

    def export_json(self, output_path: Optional[str | Path] = None) -> str:
        """Export the code index as deterministic formatted JSON."""
        json_str = self.model_dump_json(indent=2)
        if output_path is not None:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json_str, encoding="utf-8")
        return json_str
