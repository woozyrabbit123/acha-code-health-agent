"""
Pathlib Modernization Codemod - Transform os.path.* to Path(...).

Safely modernizes file path operations to use pathlib.Path.
Guards: skips dynamic string operations, template strings.
"""

import libcst as cst
from libcst import matchers as m
from pathlib import Path
from typing import Optional

from ace.skills.python import EditPlan, Edit
from ace.uir import UnifiedIssue, create_uir


class PathlibModernizeTransformer(cst.CSTTransformer):
    """LibCST transformer to modernize os.path calls to Path."""

    def __init__(self):
        self.changes = []
        self.needs_path_import = False
        self.has_path_import = False
        self.has_os_import = False

    def visit_Import(self, node: cst.Import) -> None:
        """Track imports."""
        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                if m.matches(name.name, m.Name("os")):
                    self.has_os_import = True
                elif m.matches(name.name, m.Attribute(value=m.Name("pathlib"), attr=m.Name("Path"))):
                    self.has_path_import = True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        """Track from imports."""
        if node.module and m.matches(node.module, m.Name("pathlib")):
            if isinstance(node.names, cst.ImportStar):
                self.has_path_import = True
            elif not isinstance(node.names, cst.ImportStar):
                for name in node.names:
                    if isinstance(name, cst.ImportAlias) and m.matches(name.name, m.Name("Path")):
                        self.has_path_import = True

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform os.path.join, os.path.exists, etc. to Path equivalents."""
        # Match os.path.join(...)
        if m.matches(
            updated_node.func,
            m.Attribute(
                value=m.Attribute(value=m.Name("os"), attr=m.Name("path")),
                attr=m.Name()
            )
        ):
            func_attr = updated_node.func
            method_name = func_attr.attr.value

            # Guard: Only transform simple cases
            if self._is_safe_to_transform(updated_node):
                if method_name == "join":
                    # os.path.join(a, b, c) -> Path(a) / b / c
                    self.needs_path_import = True
                    if len(updated_node.args) >= 1:
                        # Build Path(first) / second / third ...
                        result = cst.Call(
                            func=cst.Name("Path"),
                            args=[updated_node.args[0]]
                        )
                        for arg in updated_node.args[1:]:
                            result = cst.BinaryOperation(
                                left=result,
                                operator=cst.Divide(),
                                right=arg.value
                            )
                        self.changes.append(("os.path.join", "Path"))
                        return result

                elif method_name == "exists":
                    # os.path.exists(path) -> Path(path).exists()
                    self.needs_path_import = True
                    if len(updated_node.args) == 1:
                        result = cst.Call(
                            func=cst.Attribute(
                                value=cst.Call(
                                    func=cst.Name("Path"),
                                    args=[updated_node.args[0]]
                                ),
                                attr=cst.Name("exists")
                            ),
                            args=[]
                        )
                        self.changes.append(("os.path.exists", "Path.exists"))
                        return result

                elif method_name == "isfile":
                    # os.path.isfile(path) -> Path(path).is_file()
                    self.needs_path_import = True
                    if len(updated_node.args) == 1:
                        result = cst.Call(
                            func=cst.Attribute(
                                value=cst.Call(
                                    func=cst.Name("Path"),
                                    args=[updated_node.args[0]]
                                ),
                                attr=cst.Name("is_file")
                            ),
                            args=[]
                        )
                        self.changes.append(("os.path.isfile", "Path.is_file"))
                        return result

                elif method_name == "isdir":
                    # os.path.isdir(path) -> Path(path).is_dir()
                    self.needs_path_import = True
                    if len(updated_node.args) == 1:
                        result = cst.Call(
                            func=cst.Attribute(
                                value=cst.Call(
                                    func=cst.Name("Path"),
                                    args=[updated_node.args[0]]
                                ),
                                attr=cst.Name("is_dir")
                            ),
                            args=[]
                        )
                        self.changes.append(("os.path.isdir", "Path.is_dir"))
                        return result

                elif method_name == "basename":
                    # os.path.basename(path) -> Path(path).name
                    self.needs_path_import = True
                    if len(updated_node.args) == 1:
                        result = cst.Attribute(
                            value=cst.Call(
                                func=cst.Name("Path"),
                                args=[updated_node.args[0]]
                            ),
                            attr=cst.Name("name")
                        )
                        self.changes.append(("os.path.basename", "Path.name"))
                        return result

                elif method_name == "dirname":
                    # os.path.dirname(path) -> Path(path).parent
                    self.needs_path_import = True
                    if len(updated_node.args) == 1:
                        result = cst.Attribute(
                            value=cst.Call(
                                func=cst.Name("Path"),
                                args=[updated_node.args[0]]
                            ),
                            attr=cst.Name("parent")
                        )
                        self.changes.append(("os.path.dirname", "Path.parent"))
                        return result

        return updated_node

    def _is_safe_to_transform(self, node: cst.Call) -> bool:
        """Check if it's safe to transform this call."""
        # Guard: Skip if arguments contain complex expressions
        for arg in node.args:
            if isinstance(arg.value, cst.FormattedString):
                # Skip f-strings
                return False
            if isinstance(arg.value, cst.Call):
                # Skip nested calls (too complex)
                # Allow simple calls like str(x)
                if not m.matches(arg.value.func, m.Name("str")):
                    return False

        return True


class ImportAdder(cst.CSTTransformer):
    """Add Path import if needed."""

    def __init__(self, needs_import: bool, has_import: bool):
        self.needs_import = needs_import
        self.has_import = has_import
        self.import_added = False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add import at the top of the module."""
        if self.needs_import and not self.has_import and not self.import_added:
            # Add: from pathlib import Path
            new_import = cst.SimpleStatementLine(
                body=[
                    cst.ImportFrom(
                        module=cst.Name("pathlib"),
                        names=[cst.ImportAlias(name=cst.Name("Path"))]
                    )
                ]
            )

            # Insert after any __future__ imports
            future_count = 0
            for stmt in updated_node.body:
                if isinstance(stmt, cst.SimpleStatementLine):
                    for s in stmt.body:
                        if isinstance(s, cst.ImportFrom) and s.module and m.matches(s.module, m.Name("__future__")):
                            future_count += 1
                            break

            new_body = list(updated_node.body)
            new_body.insert(future_count, new_import)

            self.import_added = True
            return updated_node.with_changes(body=new_body)

        return updated_node


class PathlibModernizeCodemod:
    """Codemod to modernize os.path to pathlib.Path."""

    @staticmethod
    def plan(source_code: str, file_path: str) -> Optional[EditPlan]:
        """
        Generate edit plan for pathlib modernization.

        Args:
            source_code: Python source code
            file_path: File path for tracking

        Returns:
            EditPlan if changes needed, None otherwise
        """
        try:
            tree = cst.parse_module(source_code)
        except Exception:
            return None

        # First pass: transform os.path calls
        transformer = PathlibModernizeTransformer()
        modified_tree = tree.visit(transformer)

        if not transformer.changes:
            return None

        # Second pass: add import if needed
        import_adder = ImportAdder(transformer.needs_path_import, transformer.has_path_import)
        modified_tree = modified_tree.visit(import_adder)

        # Generate edit
        new_code = modified_tree.code

        # Create finding
        finding = create_uir(
            rule_id="PY_PATHLIB",
            severity="low",
            message=f"Modernize os.path to pathlib.Path ({len(transformer.changes)} transformations)",
            file_path=file_path,
            line=1,
            snippet="",
            context={}
        )

        # Create edit
        edit = Edit(
            file=file_path,
            start_line=1,
            end_line=len(source_code.split('\n')),
            op="replace",
            payload=new_code
        )

        # Create plan
        plan = EditPlan(
            id=f"pathlib-{Path(file_path).name}",
            findings=[finding],
            edits=[edit],
            invariants=[
                "AST structure preserved",
                "Import added if needed",
                "Only simple cases transformed"
            ],
            estimated_risk=0.2
        )

        return plan

    @staticmethod
    def is_idempotent(source_code: str, file_path: str) -> bool:
        """
        Check if applying the codemod twice yields the same result.

        Args:
            source_code: Python source code
            file_path: File path

        Returns:
            True if idempotent
        """
        plan1 = PathlibModernizeCodemod.plan(source_code, file_path)
        if plan1 is None:
            return True

        new_code = plan1.edits[0].payload
        plan2 = PathlibModernizeCodemod.plan(new_code, file_path)

        return plan2 is None  # No further changes = idempotent
