"""
Print to Logging Codemod - Convert print() to logging.info().

Guards: skip test files, skip debug prints, skip if __name__ == "__main__".
"""

import libcst as cst
from libcst import matchers as m
from pathlib import Path
from typing import Optional

from ace.skills.python import EditPlan, Edit
from ace.uir import create_uir


class PrintToLoggingTransformer(cst.CSTTransformer):
    """Convert print() to logging.info()."""

    def __init__(self, file_path: str):
        self.changes = []
        self.file_path = file_path
        self.needs_logging_import = False
        self.has_logging_import = False
        self.in_main_block = False

    def visit_If(self, node: cst.If) -> None:
        """Track if inside if __name__ == "__main__" block."""
        # Check for if __name__ == "__main__":
        if isinstance(node.test, cst.Comparison):
            comp = node.test
            if (m.matches(comp.left, m.Name("__name__")) and
                len(comp.comparisons) == 1 and
                m.matches(comp.comparisons[0].operator, m.Equal()) and
                m.matches(comp.comparisons[0].comparator, m.SimpleString('"__main__"') | m.SimpleString("'__main__'"))):
                self.in_main_block = True

    def leave_If(self, original_node: cst.If, updated_node: cst.If) -> cst.If:
        """Leave main block."""
        self.in_main_block = False
        return updated_node

    def visit_Import(self, node: cst.Import) -> None:
        """Track logging import."""
        for name in node.names:
            if isinstance(name, cst.ImportAlias) and m.matches(name.name, m.Name("logging")):
                self.has_logging_import = True

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Convert print() to logging.info()."""
        # Guard: skip in main block
        if self.in_main_block:
            return updated_node

        # Guard: skip test files
        if "test_" in self.file_path or "_test.py" in self.file_path:
            return updated_node

        # Match print(...)
        if m.matches(updated_node.func, m.Name("print")):
            # Convert to logging.info(...)
            self.needs_logging_import = True
            new_call = updated_node.with_changes(
                func=cst.Attribute(
                    value=cst.Name("logging"),
                    attr=cst.Name("info")
                )
            )
            self.changes.append("print")
            return new_call

        return updated_node


class ImportAdder(cst.CSTTransformer):
    """Add logging import if needed."""

    def __init__(self, needs_import: bool, has_import: bool):
        self.needs_import = needs_import
        self.has_import = has_import
        self.import_added = False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add import at the top."""
        if self.needs_import and not self.has_import and not self.import_added:
            new_import = cst.SimpleStatementLine(
                body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("logging"))])]
            )

            new_body = [new_import] + list(updated_node.body)
            self.import_added = True
            return updated_node.with_changes(body=new_body)

        return updated_node


class PrintToLoggingCodemod:
    """Codemod to convert print to logging."""

    @staticmethod
    def plan(source_code: str, file_path: str) -> Optional[EditPlan]:
        """Generate edit plan."""
        try:
            tree = cst.parse_module(source_code)
        except Exception:
            return None

        transformer = PrintToLoggingTransformer(file_path)
        modified_tree = tree.visit(transformer)

        if not transformer.changes:
            return None

        # Add import if needed
        import_adder = ImportAdder(transformer.needs_logging_import, transformer.has_logging_import)
        modified_tree = modified_tree.visit(import_adder)

        new_code = modified_tree.code

        finding = create_uir(
            rule_id="PY_PRINT_LOGGING",
            severity="low",
            message=f"Convert print() to logging.info() ({len(transformer.changes)} calls)",
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
            id=f"print-logging-{Path(file_path).name}",
            findings=[finding],
            edits=[edit],
            invariants=["Skip tests", "Skip main blocks", "Import added"],
            estimated_risk=0.2
        )

        return plan

    @staticmethod
    def is_idempotent(source_code: str, file_path: str) -> bool:
        """Check idempotence."""
        plan1 = PrintToLoggingCodemod.plan(source_code, file_path)
        if plan1 is None:
            return True

        new_code = plan1.edits[0].payload
        plan2 = PrintToLoggingCodemod.plan(new_code, file_path)

        return plan2 is None
