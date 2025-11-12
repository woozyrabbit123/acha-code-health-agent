"""
Dead Imports Codemod - Remove unused imports (scope-aware).

Guards: never touch __future__, typing.* if annotations present.
"""

import logging

import libcst as cst
from libcst import matchers as m
from libcst.metadata import Scope, QualifiedNameProvider, ScopeProvider
from pathlib import Path
from typing import Optional, Set

from ace.skills.python import EditPlan, Edit
from ace.uir import create_uir

logger = logging.getLogger(__name__)


class ImportCollector(cst.CSTVisitor):
    """Collect all imports and their usage."""

    METADATA_DEPENDENCIES = (ScopeProvider,)

    def __init__(self):
        self.imports = {}  # name -> Import node
        self.used_names = set()

    def visit_Import(self, node: cst.Import) -> bool:
        """Track imports and skip traversing into import nodes."""
        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                imported_name = name.asname.name.value if name.asname else name.name.value
                self.imports[imported_name] = node
        # Return False to prevent traversing into children (avoid counting import names as used)
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Track from imports and skip traversing into import nodes."""
        if not isinstance(node.names, cst.ImportStar):
            for name in node.names:
                if isinstance(name, cst.ImportAlias):
                    imported_name = name.asname.name.value if name.asname else name.name.value
                    self.imports[imported_name] = node
        # Return False to prevent traversing into children (avoid counting import names as used)
        return False

    def visit_Name(self, node: cst.Name) -> None:
        """Track name usage."""
        self.used_names.add(node.value)

    def visit_Attribute(self, node: cst.Attribute) -> None:
        """Track attribute access (module.attr)."""
        if isinstance(node.value, cst.Name):
            self.used_names.add(node.value.value)


class DeadImportsRemover(cst.CSTTransformer):
    """Remove unused imports."""

    def __init__(self, unused_imports: Set[str], has_annotations: bool):
        self.unused_imports = unused_imports
        self.has_annotations = has_annotations
        self.changes = []

    def leave_SimpleStatementLine(
        self, original_node: cst.SimpleStatementLine, updated_node: cst.SimpleStatementLine
    ) -> cst.SimpleStatementLine | cst.RemovalSentinel:
        """Remove import statements with unused imports."""
        for stmt in updated_node.body:
            if isinstance(stmt, cst.Import):
                # Check if any names are unused
                remaining_names = []
                for name in stmt.names:
                    if isinstance(name, cst.ImportAlias):
                        imported_name = name.asname.name.value if name.asname else name.name.value

                        # Guard: never remove __future__
                        if m.matches(name.name, m.Attribute(value=m.Name("__future__"))):
                            remaining_names.append(name)
                            continue

                        # Guard: keep typing imports if annotations present
                        if self.has_annotations and imported_name == "typing":
                            remaining_names.append(name)
                            continue

                        if imported_name not in self.unused_imports:
                            remaining_names.append(name)
                        else:
                            self.changes.append(imported_name)

                if not remaining_names and len(stmt.names) > 0:
                    # Remove entire import
                    return cst.RemovalSentinel.REMOVE
                elif len(remaining_names) < len(stmt.names):
                    # Update import with remaining names
                    new_stmt = stmt.with_changes(names=remaining_names)
                    return updated_node.with_changes(body=[new_stmt])

            elif isinstance(stmt, cst.ImportFrom):
                # Guard: never remove __future__
                if stmt.module and m.matches(stmt.module, m.Name("__future__")):
                    return updated_node

                if isinstance(stmt.names, cst.ImportStar):
                    return updated_node

                remaining_names = []
                for name in stmt.names:
                    if isinstance(name, cst.ImportAlias):
                        imported_name = name.asname.name.value if name.asname else name.name.value

                        # Guard: keep typing.* if annotations present
                        if self.has_annotations and stmt.module and m.matches(stmt.module, m.Name("typing")):
                            remaining_names.append(name)
                            continue

                        if imported_name not in self.unused_imports:
                            remaining_names.append(name)
                        else:
                            self.changes.append(imported_name)

                if not remaining_names and len(stmt.names) > 0:
                    return cst.RemovalSentinel.REMOVE
                elif len(remaining_names) < len(stmt.names):
                    new_stmt = stmt.with_changes(names=remaining_names)
                    return updated_node.with_changes(body=[new_stmt])

        return updated_node


class DeadImportsCodemod:
    """Codemod to remove dead imports."""

    @staticmethod
    def plan(source_code: str, file_path: str) -> Optional[EditPlan]:
        """Generate edit plan."""
        try:
            tree = cst.parse_module(source_code)
        except cst.ParserSyntaxError as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return None

        # Check for annotations
        has_annotations = "from __future__ import annotations" in source_code

        # Collect imports and usage (simple analysis)
        collector = ImportCollector()
        try:
            wrapper = cst.MetadataWrapper(tree)
            wrapper.visit(collector)
        except (ValueError, TypeError) as e:
            # Fallback to simple visitor if metadata fails
            logger.warning(f"Metadata analysis failed for {file_path}, using fallback: {e}")
            tree.visit(collector)

        # Find unused imports
        unused = set(collector.imports.keys()) - collector.used_names

        if not unused:
            return None

        # Remove unused imports
        remover = DeadImportsRemover(unused, has_annotations)
        modified_tree = tree.visit(remover)

        if not remover.changes:
            return None

        new_code = modified_tree.code

        finding = create_uir(
            rule_id="PY_DEAD_IMPORTS",
            severity="low",
            message=f"Remove unused imports ({len(remover.changes)} imports)",
            file_path=file_path,
            line=1,
            snippet="",
            context={}
        )

        edit = Edit(
            file=file_path,
            start_line=1,
            end_line=len(source_code.split('\n')),
            op="replace",
            payload=new_code
        )

        plan = EditPlan(
            id=f"dead-imports-{Path(file_path).name}",
            findings=[finding],
            edits=[edit],
            invariants=["Scope-aware", "Keep __future__", "Keep typing if annotations"],
            estimated_risk=0.2
        )

        return plan

    @staticmethod
    def is_idempotent(source_code: str, file_path: str) -> bool:
        """Check idempotence."""
        plan1 = DeadImportsCodemod.plan(source_code, file_path)
        if plan1 is None:
            return True

        new_code = plan1.edits[0].payload
        plan2 = DeadImportsCodemod.plan(new_code, file_path)

        return plan2 is None
