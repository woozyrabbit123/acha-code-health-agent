"""Python skill - LibCST-based analysis and refactoring."""

from dataclasses import dataclass

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from ace.uir import UnifiedIssue, create_uir, stable_id


@dataclass
class Edit:
    """Represents a single edit operation."""

    file: str
    start_line: int
    end_line: int
    op: str  # "replace", "insert", "delete"
    payload: str


@dataclass
class EditPlan:
    """Represents a refactoring plan."""

    id: str
    findings: list[UnifiedIssue]
    edits: list[Edit]
    invariants: list[str]
    estimated_risk: float

    def to_dict(self):
        """Convert EditPlan to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "findings": [f.to_dict() for f in self.findings],
            "edits": [
                {
                    "file": e.file,
                    "start_line": e.start_line,
                    "end_line": e.end_line,
                    "op": e.op,
                    "payload": e.payload,
                }
                for e in self.edits
            ],
            "invariants": self.invariants,
            "estimated_risk": self.estimated_risk,
        }


# ============================================================================
# PY-E201-BROAD-EXCEPT: Fix bare except: → except Exception:
# ============================================================================


class BroadExceptTransformer(cst.CSTTransformer):
    """Transform bare except: to except Exception:."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.modified = False

    def leave_ExceptHandler(
        self, original_node: cst.ExceptHandler, updated_node: cst.ExceptHandler
    ) -> cst.ExceptHandler:
        """Transform bare except clauses."""
        if original_node.type is None:  # bare except
            self.modified = True
            return updated_node.with_changes(
                type=cst.Name("Exception"),
                whitespace_after_except=cst.SimpleWhitespace(" "),
            )
        return updated_node


def analyze_broad_except(src: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze Python source for bare except clauses.

    Args:
        src: Python source code
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    try:
        module = cst.parse_module(src)
        wrapper = MetadataWrapper(module)
        findings = []

        class BroadExceptVisitor(cst.CSTVisitor):
            METADATA_DEPENDENCIES = (PositionProvider,)

            def visit_ExceptHandler(self, node: cst.ExceptHandler) -> None:
                if node.type is None:  # bare except
                    pos = self.get_metadata(PositionProvider, node)
                    line = pos.start.line
                    snippet = "except:"

                    finding = create_uir(
                        file=path,
                        line=line,
                        rule="PY-E201-BROAD-EXCEPT",
                        severity="medium",
                        message="bare except; use 'except Exception:'",
                        suggestion="Replace with 'except Exception:'",
                        snippet=snippet,
                    )
                    findings.append(finding)

        wrapper.visit(BroadExceptVisitor())
        return findings

    except Exception:
        # If parsing fails, return empty list
        return []


def refactor_broad_except(
    src: str, path: str, findings: list[UnifiedIssue]
) -> tuple[str, EditPlan]:
    """
    Refactor Python code to fix bare except clauses.

    Args:
        src: Original Python source code
        path: File path
        findings: List of findings to fix

    Returns:
        Tuple of (refactored_code, edit_plan)
    """
    try:
        module = cst.parse_module(src)
        transformer = BroadExceptTransformer()
        new_module = module.visit(transformer)
        new_code = new_module.code

        edit = Edit(
            file=path,
            start_line=1,
            end_line=len(src.splitlines()),
            op="replace",
            payload=new_code,
        )
        plan = EditPlan(
            id=stable_id(path, "PY-E201-BROAD-EXCEPT", "plan"),
            findings=findings,
            edits=[edit],
            invariants=["must_parse"],
            estimated_risk=0.7,
        )
        return new_code, plan

    except Exception:
        # If refactoring fails, return original
        return src, EditPlan(
            id=stable_id(path, "PY-E201-BROAD-EXCEPT", "plan"),
            findings=findings,
            edits=[],
            invariants=[],
            estimated_risk=0.0,
        )


# ============================================================================
# PY-I101-IMPORT-SORT: Sort imports alphabetically
# ============================================================================


class ImportSorter(cst.CSTTransformer):
    """Sort import statements alphabetically."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self):
        self.modified = False

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        """Sort imports at the top of the module."""
        body = list(updated_node.body)

        # Find the import block at the top of the file
        i = 0
        import_statements = []
        while i < len(body):
            stmt = body[i]
            if isinstance(stmt, cst.SimpleStatementLine):
                # Check if this line contains import statements
                has_import = any(
                    isinstance(el, (cst.Import, cst.ImportFrom)) for el in stmt.body
                )
                if has_import:
                    import_statements.append(stmt)
                    i += 1
                    continue
            # Stop at first non-import statement
            if import_statements:
                break
            i += 1

        if not import_statements:
            return updated_node

        # Get the rest of the body
        rest = body[i:]

        # Sort import statements by their code representation
        # Generate code for each statement for comparison
        def get_code(stmt):
            # Create a temporary module with just this statement to get its code
            temp_module = cst.Module(body=[stmt])
            return temp_module.code

        sorted_imports = sorted(import_statements, key=get_code)

        # Check if sorting changed anything
        if [get_code(s) for s in import_statements] != [get_code(s) for s in sorted_imports]:
            self.modified = True

        # Reconstruct the module
        return updated_node.with_changes(body=sorted_imports + rest)


def analyze_import_sort(src: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze Python source for unsorted imports.

    Args:
        src: Python source code
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    try:
        module = cst.parse_module(src)

        # Collect import lines at the top
        import_lines = []
        for stmt in module.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                has_import = any(
                    isinstance(el, (cst.Import, cst.ImportFrom)) for el in stmt.body
                )
                if has_import:
                    import_lines.append(module.code_for_node(stmt))
                else:
                    # Stop at first non-import
                    if import_lines:
                        break
            else:
                # Stop at first non-simple-statement
                if import_lines:
                    break

        # Check if imports are sorted
        if import_lines and import_lines != sorted(import_lines):
            evidence = "\n".join(import_lines[:3])
            if len(import_lines) > 3:
                evidence += "\n..."

            finding = create_uir(
                file=path,
                line=1,
                rule="PY-I101-IMPORT-SORT",
                severity="low",
                message="imports not sorted",
                suggestion="Sort imports alphabetically",
                snippet=evidence[:100],  # Truncate for stable_id
            )
            return [finding]

        return []

    except Exception:
        # If parsing fails, return empty list
        return []


def refactor_import_sort(
    src: str, path: str, findings: list[UnifiedIssue]
) -> tuple[str, EditPlan]:
    """
    Refactor Python code to sort imports.

    Args:
        src: Original Python source code
        path: File path
        findings: List of findings to fix

    Returns:
        Tuple of (refactored_code, edit_plan)
    """
    try:
        module = cst.parse_module(src)
        sorter = ImportSorter()
        new_module = module.visit(sorter)
        new_code = new_module.code

        edit = Edit(
            file=path,
            start_line=1,
            end_line=len(src.splitlines()),
            op="replace",
            payload=new_code,
        )
        plan = EditPlan(
            id=stable_id(path, "PY-I101-IMPORT-SORT", "plan"),
            findings=findings,
            edits=[edit],
            invariants=["must_parse"],
            estimated_risk=0.6,
        )
        return new_code, plan

    except Exception:
        # If refactoring fails, return original
        return src, EditPlan(
            id=stable_id(path, "PY-I101-IMPORT-SORT", "plan"),
            findings=findings,
            edits=[],
            invariants=[],
            estimated_risk=0.0,
        )


# ============================================================================
# Legacy stub functions (kept for compatibility)
# ============================================================================


def analyze_python(file_path: str) -> list:
    """
    Analyze Python file for issues.

    Args:
        file_path: Path to Python file

    Returns:
        List of UIR findings
    """
    return []


def refactor_python(file_path: str, findings: list) -> str:
    """
    Apply LibCST-based refactorings to Python file.

    Args:
        file_path: Path to Python file
        findings: List of findings to fix

    Returns:
        Refactored source code
    """
    return ""


def validate_python_syntax(source: str) -> bool:
    """
    Validate Python syntax after refactoring.

    Args:
        source: Python source code

    Returns:
        True if valid syntax
    """
    try:
        cst.parse_module(source)
        return True
    except Exception:
        return False
