"""Python AST analysis engine.

Uses Python's built-in ``ast`` module to extract structural information
from Python source files **without executing them**.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional, Union

from analysis.import_classifier import classify_import
from analysis.models import (
    CallInfo,
    ClassInfo,
    DecoratorInfo,
    ExceptionInfo,
    FileAnalysis,
    FunctionInfo,
    ImportInfo,
    ParameterInfo,
    VariableInfo,
)
from ingestion.reader import read_file_text
from utils.logger import setup_logger

logger = setup_logger(__name__)

_FuncNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]


class PythonASTAnalyzer:
    """Analyse Python source code using the built-in ``ast`` module.

    This analyser **never** executes or imports target code.
    """

    def __init__(self, local_modules: Optional[set[str]] = None) -> None:
        self.local_modules: set[str] = local_modules or set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_source(
        self,
        source: str,
        file_path: str,
        local_modules: Optional[set[str]] = None,
    ) -> FileAnalysis:
        """Parse *source* and return a :class:`FileAnalysis`.

        Args:
            source: Python source code as a string.
            file_path: Relative path used for citation metadata.
            local_modules: Optional set of local module names for import classification.
        """
        if not source or not source.strip():
            return FileAnalysis(file_path=file_path, status="ok")

        effective_local = local_modules if local_modules is not None else self.local_modules

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as exc:
            logger.warning("Syntax error in %s: %s", file_path, exc)
            return FileAnalysis(
                file_path=file_path,
                status="parse_error",
                error_message=exc.msg if exc.msg else str(exc),
                error_line=exc.lineno,
            )
        except Exception as exc:
            logger.warning("Unexpected error parsing %s: %s", file_path, exc)
            return FileAnalysis(
                file_path=file_path,
                status="parse_error",
                error_message=str(exc),
            )

        return FileAnalysis(
            file_path=file_path,
            status="ok",
            imports=self._extract_imports(tree, file_path, effective_local),
            classes=self._extract_classes(tree, file_path),
            functions=self._extract_top_level_functions(tree, file_path),
            variables=self._extract_module_variables(tree, file_path),
            calls=self._extract_module_calls(tree, file_path),
            docstring=ast.get_docstring(tree),
        )

    def analyze_file(
        self,
        file_path: Path,
        relative_path: str,
        local_modules: Optional[set[str]] = None,
    ) -> FileAnalysis:
        """Read a Python file from disk and analyse it.

        Args:
            file_path: Absolute path on disk.
            relative_path: Path relative to repo root (for citations).
            local_modules: Optional set of local module names.
        """
        source = read_file_text(file_path)
        if source is None:
            return FileAnalysis(
                file_path=relative_path,
                status="read_error",
                error_message=f"Could not read file: {file_path}",
            )
        return self.analyze_source(source, relative_path, local_modules)

    # ------------------------------------------------------------------
    # Imports
    # ------------------------------------------------------------------

    def _extract_imports(
        self,
        tree: ast.Module,
        fp: str,
        local_modules: Optional[set[str]] = None,
    ) -> list[ImportInfo]:
        imports: list[ImportInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    cat = classify_import(
                        alias.name, local_modules=local_modules, is_relative=False
                    )
                    imports.append(
                        ImportInfo(
                            module=alias.name,
                            name=None,
                            alias=alias.asname,
                            is_from_import=False,
                            is_relative=False,
                            category=cat,
                            file=fp,
                            line=node.lineno,
                            start_line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                is_rel = (node.level or 0) > 0
                cat = classify_import(
                    module, local_modules=local_modules, is_relative=is_rel
                )
                for alias in node.names:
                    imports.append(
                        ImportInfo(
                            module=module,
                            name=alias.name,
                            alias=alias.asname,
                            is_from_import=True,
                            is_relative=is_rel,
                            category=cat,
                            file=fp,
                            line=node.lineno,
                            start_line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                        )
                    )
        imports.sort(key=lambda imp: (imp.line, imp.module, imp.name or ""))
        return imports

    # ------------------------------------------------------------------
    # Classes
    # ------------------------------------------------------------------

    def _extract_classes(
        self, tree: ast.Module, fp: str
    ) -> list[ClassInfo]:
        classes: list[ClassInfo] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(self._build_class_info(node, fp))
        return classes

    def _build_class_info(self, node: ast.ClassDef, fp: str) -> ClassInfo:
        bases = [_unparse_safe(b) for b in node.bases]
        decorators = [
            DecoratorInfo(
                name=_get_decorator_name(d),
                file=fp,
                line=d.lineno,
                start_line=d.lineno,
                end_line=getattr(d, "end_lineno", d.lineno),
            )
            for d in node.decorator_list
        ]
        methods = [
            self._build_function_info(child, fp, is_method=True)
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        attributes = self._extract_class_attributes(node, fp)

        return ClassInfo(
            name=node.name,
            file=fp,
            line=node.lineno,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            base_classes=bases,
            decorators=decorators,
            docstring=ast.get_docstring(node),
            methods=methods,
            attributes=attributes,
        )

    def _extract_class_attributes(
        self, node: ast.ClassDef, fp: str
    ) -> list[VariableInfo]:
        attributes: list[VariableInfo] = []
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        attributes.append(
                            VariableInfo(
                                name=target.id,
                                file=fp,
                                line=stmt.lineno,
                                start_line=stmt.lineno,
                                end_line=getattr(stmt, "end_lineno", stmt.lineno),
                                value=_unparse_safe(stmt.value),
                            )
                        )
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                val = _unparse_safe(stmt.value) if stmt.value is not None else None
                attributes.append(
                    VariableInfo(
                        name=stmt.target.id,
                        file=fp,
                        line=stmt.lineno,
                        start_line=stmt.lineno,
                        end_line=getattr(stmt, "end_lineno", stmt.lineno),
                        annotation=_get_annotation(stmt.annotation),
                        value=val,
                    )
                )
        return attributes

    # ------------------------------------------------------------------
    # Functions / methods
    # ------------------------------------------------------------------

    def _extract_top_level_functions(
        self, tree: ast.Module, fp: str
    ) -> list[FunctionInfo]:
        functions: list[FunctionInfo] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._build_function_info(node, fp, is_method=False))
        return functions

    def _build_function_info(
        self, node: _FuncNode, fp: str, *, is_method: bool = False
    ) -> FunctionInfo:
        params = self._extract_parameters(node.args)
        decorators = [
            DecoratorInfo(
                name=_get_decorator_name(d),
                file=fp,
                line=d.lineno,
                start_line=d.lineno,
                end_line=getattr(d, "end_lineno", d.lineno),
            )
            for d in node.decorator_list
        ]

        # Extract nested functions within this function
        nested_functions = [
            self._build_function_info(child, fp, is_method=False)
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        # Extract direct calls and exceptions within this function
        calls, exceptions = _collect_calls_and_exceptions(node.body, fp)

        return FunctionInfo(
            name=node.name,
            file=fp,
            line=node.lineno,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", node.lineno),
            parameters=params,
            return_annotation=_get_annotation(node.returns),
            decorators=decorators,
            docstring=ast.get_docstring(node),
            calls=calls,
            exceptions_raised=exceptions,
            nested_functions=nested_functions,
            is_method=is_method,
            is_async=isinstance(node, ast.AsyncFunctionDef),
        )

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------

    def _extract_parameters(self, args: ast.arguments) -> list[ParameterInfo]:
        params: list[ParameterInfo] = []

        all_positional = list(args.posonlyargs) + list(args.args)
        n_pos = len(all_positional)
        n_def = len(args.defaults)

        for i, arg in enumerate(all_positional):
            di = i - (n_pos - n_def)
            default = _unparse_safe(args.defaults[di]) if di >= 0 else None
            kind = (
                "positional_only"
                if i < len(args.posonlyargs)
                else "positional_or_keyword"
            )
            params.append(
                ParameterInfo(
                    name=arg.arg,
                    annotation=_get_annotation(arg.annotation),
                    default=default,
                    kind=kind,
                )
            )

        if args.vararg:
            params.append(
                ParameterInfo(
                    name=args.vararg.arg,
                    annotation=_get_annotation(args.vararg.annotation),
                    kind="var_positional",
                )
            )

        for i, arg in enumerate(args.kwonlyargs):
            default = None
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                default = _unparse_safe(args.kw_defaults[i])
            params.append(
                ParameterInfo(
                    name=arg.arg,
                    annotation=_get_annotation(arg.annotation),
                    default=default,
                    kind="keyword_only",
                )
            )

        if args.kwarg:
            params.append(
                ParameterInfo(
                    name=args.kwarg.arg,
                    annotation=_get_annotation(args.kwarg.annotation),
                    kind="var_keyword",
                )
            )

        return params

    # ------------------------------------------------------------------
    # Module-level variables
    # ------------------------------------------------------------------

    def _extract_module_variables(
        self, tree: ast.Module, fp: str
    ) -> list[VariableInfo]:
        variables: list[VariableInfo] = []
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        variables.append(
                            VariableInfo(
                                name=target.id,
                                file=fp,
                                line=stmt.lineno,
                                start_line=stmt.lineno,
                                end_line=getattr(stmt, "end_lineno", stmt.lineno),
                                value=_unparse_safe(stmt.value),
                            )
                        )
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                val = _unparse_safe(stmt.value) if stmt.value is not None else None
                variables.append(
                    VariableInfo(
                        name=stmt.target.id,
                        file=fp,
                        line=stmt.lineno,
                        start_line=stmt.lineno,
                        end_line=getattr(stmt, "end_lineno", stmt.lineno),
                        annotation=_get_annotation(stmt.annotation),
                        value=val,
                    )
                )
        return variables

    # ------------------------------------------------------------------
    # Module-level calls (outside functions / classes)
    # ------------------------------------------------------------------

    def _extract_module_calls(
        self, tree: ast.Module, fp: str
    ) -> list[CallInfo]:
        calls: list[CallInfo] = []
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for node in ast.walk(stmt):
                if isinstance(node, ast.Call):
                    target = _get_call_target(node)
                    if target:
                        calls.append(
                            CallInfo(
                                target=target,
                                file=fp,
                                line=node.lineno,
                                start_line=node.lineno,
                                end_line=getattr(node, "end_lineno", node.lineno),
                            )
                        )
        calls.sort(key=lambda c: (c.line, c.target))
        return calls


# ======================================================================
# Helpers
# ======================================================================


def _collect_calls_and_exceptions(
    stmts: list[ast.stmt], fp: str
) -> tuple[list[CallInfo], list[ExceptionInfo]]:
    """Collect call sites and raise statements without descending into nested functions or classes."""
    calls: list[CallInfo] = []
    exceptions: list[ExceptionInfo] = []

    stack: list[ast.AST] = list(stmts)
    while stack:
        curr = stack.pop()
        # Skip nested functions and classes so their internal calls stay scoped to them
        if isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        if isinstance(curr, ast.Call):
            target = _get_call_target(curr)
            if target:
                calls.append(
                    CallInfo(
                        target=target,
                        file=fp,
                        line=curr.lineno,
                        start_line=curr.lineno,
                        end_line=getattr(curr, "end_lineno", curr.lineno),
                    )
                )
        elif isinstance(curr, ast.Raise):
            exc_type: Optional[str] = None
            if curr.exc is not None:
                if isinstance(curr.exc, ast.Call):
                    exc_type = _get_call_target(curr.exc)
                elif isinstance(curr.exc, ast.Name):
                    exc_type = curr.exc.id
                elif isinstance(curr.exc, ast.Attribute):
                    exc_type = _unparse_safe(curr.exc)
                else:
                    exc_type = _unparse_safe(curr.exc)
            exceptions.append(
                ExceptionInfo(
                    exception_type=exc_type,
                    file=fp,
                    line=curr.lineno,
                    start_line=curr.lineno,
                    end_line=getattr(curr, "end_lineno", curr.lineno),
                )
            )

        for child in ast.iter_child_nodes(curr):
            stack.append(child)

    calls.sort(key=lambda c: (c.line, c.target))
    exceptions.sort(key=lambda e: (e.line, e.exception_type or ""))
    return calls, exceptions


def _get_annotation(node: Optional[ast.AST]) -> Optional[str]:
    """Safely convert an annotation node to its source representation."""
    if node is None:
        return None
    return _unparse_safe(node)


def _unparse_safe(node: ast.AST) -> str:
    """``ast.unparse`` with a fallback for edge cases."""
    try:
        return ast.unparse(node)
    except Exception:
        return "<unknown>"


def _get_call_target(node: ast.Call) -> Optional[str]:
    """Extract the textual call target from a :class:`ast.Call` node."""
    return _resolve_name(node.func)


def _resolve_name(node: ast.AST) -> Optional[str]:
    """Resolve a ``Name``, ``Attribute``, or ``Call`` node to a dotted string."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        value = _resolve_name(node.value)
        if value:
            return f"{value}.{node.attr}"
        return node.attr
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _get_decorator_name(node: ast.AST) -> str:
    """Extract a human-readable decorator name."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _resolve_name(node) or "<unknown>"
    if isinstance(node, ast.Call):
        return _get_decorator_name(node.func)
    return _unparse_safe(node)
