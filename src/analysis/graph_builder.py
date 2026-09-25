"""Builds the CodeGraph from repository ingestion and AST analysis."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Optional

from analysis.cycles import detect_cycles
from analysis.graph_models import (
    CircularDependency,
    CodeGraph,
    GraphNode,
    GraphStatistics,
    InheritanceRelation,
    NodeType,
    RelationshipEdge,
    RelationshipType,
)
from analysis.models import ClassInfo, FileAnalysis, FunctionInfo, RepositoryCodeIndex
from ingestion.models import RepositoryManifest
from utils.logger import setup_logger

logger = setup_logger(__name__)


class CodeGraphBuilder:
    """Constructs a CodeGraph from a RepositoryCodeIndex."""

    def __init__(self) -> None:
        self.nodes: list[GraphNode] = []
        self.edges: list[RelationshipEdge] = []
        self._node_ids: set[str] = set()

        # Indexes for fast resolution
        self._classes_by_name: dict[str, list[tuple[str, ClassInfo]]] = {}  # class_name -> [(file, class)]
        self._functions_by_name: dict[str, list[tuple[str, FunctionInfo]]] = {}  # fn_name -> [(file, fn)]
        self._file_to_module: dict[str, str] = {}  # file_rel_path -> dotted_module
        self._module_to_file: dict[str, str] = {}  # dotted_module / stem -> file_rel_path
        self._imports_by_file: dict[str, dict[str, str]] = {}  # file -> {alias/name: full_module}

    def build_graph(self, code_index: RepositoryCodeIndex) -> CodeGraph:
        """Main entry point to construct the complete CodeGraph."""
        logger.info("Building CodeGraph for repository: %s", code_index.manifest.name)

        self._reset()
        manifest = code_index.manifest
        file_analyses = code_index.file_analyses

        # 1. Pre-index entities for name and call resolution
        self._build_indexes(code_index)

        # 2. Build hierarchical nodes
        self._build_structural_nodes(manifest)
        self._build_code_nodes(file_analyses)

        # 3. Build relationship edges
        self._build_hierarchy_edges(manifest)
        self._build_definitions_and_contains_edges(file_analyses)
        self._build_import_and_dependency_edges(file_analyses)
        self._build_inheritance_edges(file_analyses)
        self._build_call_edges(file_analyses)
        self._build_test_edges(manifest, file_analyses)

        # 4. Compute circular dependencies & architecture metrics
        stats = self._compute_statistics()

        logger.info(
            "CodeGraph built: %d nodes, %d edges, %d cycles detected",
            len(self.nodes),
            len(self.edges),
            len(stats.circular_dependencies),
        )

        return CodeGraph(
            nodes=self.nodes,
            edges=self.edges,
            statistics=stats,
        )

    def _reset(self) -> None:
        self.nodes.clear()
        self.edges.clear()
        self._node_ids.clear()
        self._classes_by_name.clear()
        self._functions_by_name.clear()
        self._file_to_module.clear()
        self._module_to_file.clear()
        self._imports_by_file.clear()

    # ------------------------------------------------------------------
    # Indexing Helpers
    # ------------------------------------------------------------------

    def _build_indexes(self, code_index: RepositoryCodeIndex) -> None:
        for f in code_index.manifest.files:
            rel = f.relative_path
            if rel.endswith(".py"):
                dotted = PurePosixPath(rel).with_suffix("").as_posix().replace("/", ".")
                self._file_to_module[rel] = dotted
                self._module_to_file[dotted] = rel
                # Also index stem (e.g. 'models' for 'src/models.py')
                stem = PurePosixPath(rel).stem
                self._module_to_file[stem] = rel

        for fa in code_index.file_analyses:
            fp = fa.file_path
            self._imports_by_file[fp] = {}

            # Map imports in this file
            for imp in fa.imports:
                target_sym = imp.alias or imp.name or imp.module.split(".")[-1]
                full_target = f"{imp.module}.{imp.name}" if (imp.is_from_import and imp.name) else imp.module
                self._imports_by_file[fp][target_sym] = full_target

            # Index classes
            for cls in fa.classes:
                self._classes_by_name.setdefault(cls.name, []).append((fp, cls))

            # Index functions & methods
            for fn in fa.functions:
                self._functions_by_name.setdefault(fn.name, []).append((fp, fn))
            for cls in fa.classes:
                for m in cls.methods:
                    self._functions_by_name.setdefault(m.name, []).append((fp, m))

    def _add_node(self, node: GraphNode) -> None:
        if node.id not in self._node_ids:
            self._node_ids.add(node.id)
            self.nodes.append(node)

    def _add_edge(self, edge: RelationshipEdge) -> None:
        self.edges.append(edge)

    # ------------------------------------------------------------------
    # Node Construction
    # ------------------------------------------------------------------

    def _build_structural_nodes(self, manifest: RepositoryManifest) -> None:
        # Repository root node
        self._add_node(
            GraphNode(
                id=f"repo:{manifest.name}",
                name=manifest.name,
                type=NodeType.REPOSITORY,
                file="",
            )
        )

        # Directory nodes
        for d in manifest.directories:
            self._add_node(
                GraphNode(
                    id=f"dir:{d.relative_path}",
                    name=d.name,
                    type=NodeType.DIRECTORY,
                    file=d.relative_path,
                )
            )

        # File and Module nodes
        for f in manifest.files:
            self._add_node(
                GraphNode(
                    id=f"file:{f.relative_path}",
                    name=f.file_name,
                    type=NodeType.FILE,
                    file=f.relative_path,
                    start_line=1,
                    end_line=f.metadata.line_count,
                    metadata={
                        "language": f.language.value,
                        "size_bytes": f.metadata.size_bytes,
                        "is_test_file": f.is_test_file,
                        "is_documentation": f.is_documentation,
                        "is_configuration": f.is_configuration,
                    },
                )
            )
            # Dotted Python module
            if f.relative_path in self._file_to_module:
                mod_name = self._file_to_module[f.relative_path]
                self._add_node(
                    GraphNode(
                        id=f"module:{mod_name}",
                        name=mod_name,
                        type=NodeType.MODULE,
                        file=f.relative_path,
                        start_line=1,
                        end_line=f.metadata.line_count,
                    )
                )

    def _build_code_nodes(self, file_analyses: list[FileAnalysis]) -> None:
        for fa in file_analyses:
            fp = fa.file_path
            for cls in fa.classes:
                self._add_node(
                    GraphNode(
                        id=f"class:{fp}:{cls.name}",
                        name=cls.name,
                        type=NodeType.CLASS,
                        file=fp,
                        start_line=cls.start_line,
                        end_line=cls.end_line,
                        metadata={"base_classes": cls.base_classes, "docstring": cls.docstring},
                    )
                )
                for m in cls.methods:
                    self._add_node(
                        GraphNode(
                            id=f"method:{fp}:{cls.name}.{m.name}",
                            name=f"{cls.name}.{m.name}",
                            type=NodeType.METHOD,
                            file=fp,
                            start_line=m.start_line,
                            end_line=m.end_line,
                            metadata={"docstring": m.docstring, "parameters": [p.name for p in m.parameters]},
                        )
                    )

            for fn in fa.functions:
                self._add_node(
                    GraphNode(
                        id=f"func:{fp}:{fn.name}",
                        name=fn.name,
                        type=NodeType.FUNCTION,
                        file=fp,
                        start_line=fn.start_line,
                        end_line=fn.end_line,
                        metadata={"docstring": fn.docstring, "parameters": [p.name for p in fn.parameters]},
                    )
                )
                for sub in fn.nested_functions:
                    self._add_node(
                        GraphNode(
                            id=f"func:{fp}:{fn.name}.{sub.name}",
                            name=f"{fn.name}.{sub.name}",
                            type=NodeType.FUNCTION,
                            file=fp,
                            start_line=sub.start_line,
                            end_line=sub.end_line,
                            metadata={"parent": fn.name},
                        )
                    )

    # ------------------------------------------------------------------
    # Edge Construction
    # ------------------------------------------------------------------

    def _build_hierarchy_edges(self, manifest: RepositoryManifest) -> None:
        repo_id = f"repo:{manifest.name}"

        # Connect repo to top-level directories and top-level files
        for d in manifest.directories:
            p = PurePosixPath(d.relative_path)
            if len(p.parts) == 1:
                self._add_edge(
                    RelationshipEdge(
                        source=repo_id,
                        target=f"dir:{d.relative_path}",
                        type=RelationshipType.CONTAINS,
                    )
                )
            else:
                parent_dir = p.parent.as_posix()
                self._add_edge(
                    RelationshipEdge(
                        source=f"dir:{parent_dir}",
                        target=f"dir:{d.relative_path}",
                        type=RelationshipType.CONTAINS,
                    )
                )

        for f in manifest.files:
            p = PurePosixPath(f.relative_path)
            if len(p.parts) == 1:
                self._add_edge(
                    RelationshipEdge(
                        source=repo_id,
                        target=f"file:{f.relative_path}",
                        type=RelationshipType.CONTAINS,
                    )
                )
            else:
                parent_dir = p.parent.as_posix()
                self._add_edge(
                    RelationshipEdge(
                        source=f"dir:{parent_dir}",
                        target=f"file:{f.relative_path}",
                        type=RelationshipType.CONTAINS,
                    )
                )

    def _build_definitions_and_contains_edges(self, file_analyses: list[FileAnalysis]) -> None:
        for fa in file_analyses:
            fp = fa.file_path
            file_id = f"file:{fp}"

            for cls in fa.classes:
                cls_id = f"class:{fp}:{cls.name}"
                # File DEFINES class
                self._add_edge(
                    RelationshipEdge(
                        source=file_id,
                        target=cls_id,
                        type=RelationshipType.DEFINES,
                        file=fp,
                        line=cls.start_line,
                    )
                )
                # Class CONTAINS methods
                for m in cls.methods:
                    m_id = f"method:{fp}:{cls.name}.{m.name}"
                    self._add_edge(
                        RelationshipEdge(
                            source=cls_id,
                            target=m_id,
                            type=RelationshipType.CONTAINS,
                            file=fp,
                            line=m.start_line,
                        )
                    )

            for fn in fa.functions:
                fn_id = f"func:{fp}:{fn.name}"
                # File DEFINES function
                self._add_edge(
                    RelationshipEdge(
                        source=file_id,
                        target=fn_id,
                        type=RelationshipType.DEFINES,
                        file=fp,
                        line=fn.start_line,
                    )
                )
                # Function CONTAINS nested functions
                for sub in fn.nested_functions:
                    sub_id = f"func:{fp}:{fn.name}.{sub.name}"
                    self._add_edge(
                        RelationshipEdge(
                            source=fn_id,
                            target=sub_id,
                            type=RelationshipType.CONTAINS,
                            file=fp,
                            line=sub.start_line,
                        )
                    )

    def _build_import_and_dependency_edges(self, file_analyses: list[FileAnalysis]) -> None:
        seen_deps: set[tuple[str, str]] = set()

        for fa in file_analyses:
            fp = fa.file_path
            file_id = f"file:{fp}"
            mod_id = f"module:{self._file_to_module.get(fp, fp)}"

            for imp in fa.imports:
                raw_mod = imp.module
                target_ident = f"module:{raw_mod}" if raw_mod else (imp.name or "unknown")

                # Resolve if this import points to a local repository file
                target_file: Optional[str] = None

                # Direct match in module_to_file
                if raw_mod in self._module_to_file:
                    target_file = self._module_to_file[raw_mod]
                elif imp.is_from_import and f"{raw_mod}.{imp.name}" in self._module_to_file:
                    target_file = self._module_to_file[f"{raw_mod}.{imp.name}"]
                elif imp.category == "local":
                    # Check relative import or stem
                    stem = raw_mod.split(".")[-1]
                    if stem in self._module_to_file:
                        target_file = self._module_to_file[stem]

                resolved = target_file is not None or imp.category == "stdlib"
                confidence = 1.0 if target_file else (0.9 if imp.category == "stdlib" else 0.7)

                if target_file:
                    target_ident = f"file:{target_file}"

                # 1. IMPORTS relationship
                self._add_edge(
                    RelationshipEdge(
                        source=file_id,
                        target=target_ident,
                        type=RelationshipType.IMPORTS,
                        file=fp,
                        line=imp.line,
                        resolved=resolved,
                        confidence=confidence,
                        metadata={"is_from_import": imp.is_from_import, "name": imp.name},
                    )
                )

                # 2. DEPENDS_ON relationship (local module-to-module dependencies only)
                if target_file and target_file != fp:
                    dep_key = (fp, target_file)
                    if dep_key not in seen_deps:
                        seen_deps.add(dep_key)
                        target_mod = self._file_to_module.get(target_file, target_file)
                        self._add_edge(
                            RelationshipEdge(
                                source=mod_id,
                                target=f"module:{target_mod}",
                                type=RelationshipType.DEPENDS_ON,
                                file=fp,
                                line=imp.line,
                                resolved=True,
                                confidence=1.0,
                            )
                        )

    def _build_inheritance_edges(self, file_analyses: list[FileAnalysis]) -> None:
        for fa in file_analyses:
            fp = fa.file_path
            for cls in fa.classes:
                cls_id = f"class:{fp}:{cls.name}"
                for base in cls.base_classes:
                    base_name = base.split(".")[-1]

                    target_id = base
                    resolved = False
                    confidence = 0.7

                    # Look up base class in repository
                    if base_name in self._classes_by_name:
                        candidates = self._classes_by_name[base_name]
                        # Prefer candidate imported in this file or defined in the same file
                        target_fp, _ = candidates[0]
                        for c_fp, _ in candidates:
                            if c_fp == fp or c_fp in self._imports_by_file.get(fp, {}).values():
                                target_fp = c_fp
                                break
                        target_id = f"class:{target_fp}:{base_name}"
                        resolved = True
                        confidence = 1.0

                    self._add_edge(
                        RelationshipEdge(
                            source=cls_id,
                            target=target_id,
                            type=RelationshipType.INHERITS,
                            file=fp,
                            line=cls.start_line,
                            resolved=resolved,
                            confidence=confidence,
                            metadata={"base_class": base},
                        )
                    )

    def _build_call_edges(self, file_analyses: list[FileAnalysis]) -> None:
        for fa in file_analyses:
            fp = fa.file_path

            # Function calls
            for fn in fa.functions:
                caller_id = f"func:{fp}:{fn.name}"
                for call in fn.calls:
                    target_id, resolved, conf = self._resolve_call_target(call.target, fp)
                    self._add_edge(
                        RelationshipEdge(
                            source=caller_id,
                            target=target_id,
                            type=RelationshipType.CALLS,
                            file=fp,
                            line=call.line,
                            resolved=resolved,
                            confidence=conf,
                        )
                    )

            # Method calls
            for cls in fa.classes:
                for m in cls.methods:
                    caller_id = f"method:{fp}:{cls.name}.{m.name}"
                    for call in m.calls:
                        target_id, resolved, conf = self._resolve_call_target(call.target, fp, current_class=cls.name)
                        self._add_edge(
                            RelationshipEdge(
                                source=caller_id,
                                target=target_id,
                                type=RelationshipType.CALLS,
                                file=fp,
                                line=call.line,
                                resolved=resolved,
                                confidence=conf,
                            )
                        )

            # Module-level calls
            for call in fa.calls:
                target_id, resolved, conf = self._resolve_call_target(call.target, fp)
                self._add_edge(
                    RelationshipEdge(
                        source=f"file:{fp}",
                        target=target_id,
                        type=RelationshipType.CALLS,
                        file=fp,
                        line=call.line,
                        resolved=resolved,
                        confidence=conf,
                    )
                )

    def _resolve_call_target(
        self,
        call_target: str,
        current_file: str,
        current_class: Optional[str] = None,
    ) -> tuple[str, bool, float]:
        """Attempt to resolve a call target (e.g. 'hash_file', 'self.db.save', 'utils.hash_file')."""
        # Case 1: 'self.method_name()'
        if call_target.startswith("self.") and current_class:
            method_name = call_target[5:]
            if method_name in self._functions_by_name:
                for c_fp, fn in self._functions_by_name[method_name]:
                    if c_fp == current_file and getattr(fn, "is_method", False):
                        return f"method:{current_file}:{current_class}.{method_name}", True, 0.95

        # Case 2: Simple function name, e.g. 'create_app()' or 'hash_file()'
        if "." not in call_target:
            if call_target in self._functions_by_name:
                candidates = self._functions_by_name[call_target]
                # Check same file first
                for c_fp, _ in candidates:
                    if c_fp == current_file:
                        return f"func:{current_file}:{call_target}", True, 1.0

                # Check if imported into current file
                file_imports = self._imports_by_file.get(current_file, {})
                if call_target in file_imports:
                    imported_mod = file_imports[call_target]
                    for c_fp, _ in candidates:
                        if self._file_to_module.get(c_fp) == imported_mod or c_fp in imported_mod:
                            return f"func:{c_fp}:{call_target}", True, 0.95

                # Unique function across entire repo
                if len(candidates) == 1:
                    return f"func:{candidates[0][0]}:{call_target}", True, 0.85

            # Built-in or unresolvable
            return call_target, False, 0.2

        # Case 3: Qualified name, e.g. 'module.func' or 'obj.method'
        parts = call_target.split(".")
        prefix, name = parts[0], parts[-1]

        # Check if prefix was imported (e.g. `import utils` -> `utils.hash_file()`)
        file_imports = self._imports_by_file.get(current_file, {})
        if prefix in file_imports:
            mod_target = file_imports[prefix]
            if name in self._functions_by_name:
                for c_fp, _ in self._functions_by_name[name]:
                    if self._file_to_module.get(c_fp) == mod_target or mod_target in c_fp:
                        return f"func:{c_fp}:{name}", True, 0.95

        return call_target, False, 0.4

    def _build_test_edges(
        self,
        manifest: RepositoryManifest,
        file_analyses: list[FileAnalysis],
    ) -> None:
        """Link test files and test functions to the code under test."""
        # Map source stems to their file paths
        source_stems: dict[str, str] = {}
        for f in manifest.files:
            if not f.is_test_file and f.relative_path.endswith(".py"):
                stem = PurePosixPath(f.relative_path).stem
                source_stems[stem] = f.relative_path

        test_files = [f for f in manifest.files if f.is_test_file]

        for tf in test_files:
            test_fp = tf.relative_path
            test_stem = PurePosixPath(test_fp).stem

            # Extract target stem from test name: test_app -> app, test_utils -> utils
            target_stem = test_stem
            if target_stem.startswith("test_"):
                target_stem = target_stem[5:]
            elif target_stem.endswith("_test"):
                target_stem = target_stem[:-5]

            tested_file = source_stems.get(target_stem)
            confidence = 0.8

            # Check if test file explicitly imports the tested file
            test_imports = self._imports_by_file.get(test_fp, {})
            imported_files = set()
            for full_mod in test_imports.values():
                if full_mod in self._module_to_file:
                    imported_files.add(self._module_to_file[full_mod])

            if tested_file and tested_file in imported_files:
                confidence = 0.95
            elif not tested_file and imported_files:
                # Fallback: test file imports one primary source file
                tested_file = next(iter(imported_files))
                confidence = 0.7

            if tested_file:
                # 1. File-level TESTS edge
                self._add_edge(
                    RelationshipEdge(
                        source=f"file:{test_fp}",
                        target=f"file:{tested_file}",
                        type=RelationshipType.TESTS,
                        file=test_fp,
                        line=1,
                        resolved=True,
                        confidence=confidence,
                    )
                )

                # 2. Function-level TESTS edges
                # Find matching test functions, e.g. test_hash_file -> hash_file
                tf_analysis = next((fa for fa in file_analyses if fa.file_path == test_fp), None)
                if tf_analysis:
                    for t_fn in tf_analysis.functions:
                        if t_fn.name.startswith("test_"):
                            target_fn_name = t_fn.name[5:]
                            if target_fn_name in self._functions_by_name:
                                for c_fp, _ in self._functions_by_name[target_fn_name]:
                                    if c_fp == tested_file:
                                        self._add_edge(
                                            RelationshipEdge(
                                                source=f"func:{test_fp}:{t_fn.name}",
                                                target=f"func:{tested_file}:{target_fn_name}",
                                                type=RelationshipType.TESTS,
                                                file=test_fp,
                                                line=t_fn.start_line,
                                                resolved=True,
                                                confidence=0.9,
                                            )
                                        )

    # ------------------------------------------------------------------
    # Metrics & Cycle Detection
    # ------------------------------------------------------------------

    def _compute_statistics(self) -> GraphStatistics:
        nodes_by_type: dict[str, int] = {}
        for n in self.nodes:
            nodes_by_type[n.type.value] = nodes_by_type.get(n.type.value, 0) + 1

        rel_by_type: dict[str, int] = {}
        for e in self.edges:
            rel_by_type[e.type.value] = rel_by_type.get(e.type.value, 0) + 1

        # Build adjacency graph of DEPENDS_ON edges for cycle detection
        adj_edges: dict[str, list[tuple[str, RelationshipEdge]]] = {}
        in_degrees: dict[str, int] = {}
        out_degrees: dict[str, int] = {}

        for e in self.edges:
            if e.type == RelationshipType.DEPENDS_ON:
                adj_edges.setdefault(e.source, []).append((e.target, e))
                out_degrees[e.source] = out_degrees.get(e.source, 0) + 1
                in_degrees[e.target] = in_degrees.get(e.target, 0) + 1

        # Detect cycles
        cycles = detect_cycles(adj_edges)

        # Most imported / depended-on modules
        most_depended_on = sorted(
            [(k.replace("module:", ""), v) for k, v in in_degrees.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        modules_with_many_deps = sorted(
            [(k.replace("module:", ""), v) for k, v in out_degrees.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # Import counts
        import_counts: dict[str, int] = {}
        for e in self.edges:
            if e.type == RelationshipType.IMPORTS:
                raw_tgt = e.target.replace("file:", "").replace("module:", "")
                import_counts[raw_tgt] = import_counts.get(raw_tgt, 0) + 1

        most_imported = sorted(
            list(import_counts.items()),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # Inheritance relationships
        inheritance_rels: list[InheritanceRelation] = []
        for e in self.edges:
            if e.type == RelationshipType.INHERITS:
                sub_name = e.source.split(":")[-1]
                base_name = e.target.split(":")[-1]
                inheritance_rels.append(
                    InheritanceRelation(
                        subclass=sub_name,
                        base_class=base_name,
                        file=e.file,
                        line=e.line,
                    )
                )

        return GraphStatistics(
            total_nodes=len(self.nodes),
            total_edges=len(self.edges),
            nodes_by_type=nodes_by_type,
            relationships_by_type=rel_by_type,
            most_imported_modules=most_imported,
            most_depended_on_modules=most_depended_on,
            modules_with_many_dependencies=modules_with_many_deps,
            circular_dependencies=cycles,
            inheritance_relationships=inheritance_rels,
        )
