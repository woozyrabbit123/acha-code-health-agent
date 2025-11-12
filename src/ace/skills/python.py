"""Python skill - LibCST-based analysis and refactoring."""

from dataclasses import dataclass

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from ace.uir import UnifiedIssue, create_uir, stable_id

# ============================================================================
# Dataclasses for refactoring plans
# ============================================================================


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
# Legacy dataclasses for Sprint 3 compatibility
# ============================================================================


@dataclass
class Finding:
    """Legacy Finding class for Sprint 3 HTTP timeout rule."""

    file: str
    line: int
    column: int
    rule: str
    severity: str
    message: str
    evidence: str
    snippet: str


# Rule: PY-S101-UNSAFE-HTTP
RULE_ID = "PY-S101-UNSAFE-HTTP"
RULE_SEVERITY = "high"
REQUESTS_METHODS = {"get", "post", "put", "delete", "head", "request"}

class HttpTimeoutVisitor(cst.CSTVisitor):
    """Visitor to find requests.* calls without timeout parameter."""

    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

    def __init__(self, source_code: str):
        self.findings: list[Finding] = []
        self.source_lines = source_code.splitlines()

    def visit_Call(self, node: cst.Call) -> None:
        """Visit function calls and check for requests.* without timeout."""
        # Check if this is a requests.{method} call
        if not isinstance(node.func, cst.Attribute):
            return

        # Check if attribute is one of the requests methods
        method_name = node.func.attr.value
        if method_name not in REQUESTS_METHODS:
            return

        # Check if the base is "requests"
        if isinstance(node.func.value, cst.Name) and node.func.value.value == "requests":
            # Check if timeout kwarg exists
            has_timeout = any(
                isinstance(arg.keyword, cst.Name) and arg.keyword.value == "timeout"
                for arg in node.args
                if isinstance(arg, cst.Arg) and arg.keyword is not None
            )

            if not has_timeout:
                # Found a requests call without timeout
                pos = self.get_metadata(cst.metadata.PositionProvider, node)
                line = pos.start.line
                column = pos.start.column

                # Get evidence (code snippet)
                evidence = ""
                if 0 <= line - 1 < len(self.source_lines):
                    evidence = self.source_lines[line - 1].strip()
                    if len(evidence) > 120:
                        evidence = evidence[:117] + "..."

                snippet = evidence

                finding = Finding(
                    file="",  # Will be set by caller
                    line=line,
                    column=column,
                    rule=RULE_ID,
                    severity=RULE_SEVERITY,
                    message=f"requests.{method_name} call without 'timeout'",
                    evidence=evidence,
                    snippet=snippet,
                )
                self.findings.append(finding)


class HttpTimeoutTransformer(cst.CSTTransformer):
    """Transformer to add timeout=10 to requests.* calls."""

    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

    def __init__(self, lines_to_fix: set[int]):
        """
        Initialize transformer.

        Args:
            lines_to_fix: Set of line numbers to fix
        """
        self.lines_to_fix = lines_to_fix
        self.modified = False

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform requests.* calls by adding timeout=10."""
        # Check if this is a requests.{method} call
        if not isinstance(updated_node.func, cst.Attribute):
            return updated_node

        method_name = updated_node.func.attr.value
        if method_name not in REQUESTS_METHODS:
            return updated_node

        # Check if the base is "requests"
        if not (
            isinstance(updated_node.func.value, cst.Name)
            and updated_node.func.value.value == "requests"
        ):
            return updated_node

        # Check if this call is on a line we want to fix
        pos = self.get_metadata(cst.metadata.PositionProvider, original_node)
        if pos.start.line not in self.lines_to_fix:
            return updated_node

        # Check if timeout already exists
        has_timeout = any(
            isinstance(arg.keyword, cst.Name) and arg.keyword.value == "timeout"
            for arg in updated_node.args
            if isinstance(arg, cst.Arg) and arg.keyword is not None
        )

        if has_timeout:
            return updated_node

        # Add timeout=10 as keyword argument
        timeout_arg = cst.Arg(
            keyword=cst.Name("timeout"),
            value=cst.Integer("10"),
            equal=cst.AssignEqual(
                whitespace_before=cst.SimpleWhitespace(""),
                whitespace_after=cst.SimpleWhitespace(""),
            ),
        )

        # Insert timeout argument after other arguments
        new_args = list(updated_node.args) + [timeout_arg]

        self.modified = True
        return updated_node.with_changes(args=new_args)


def analyze_py(text: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze Python source for HTTP timeout issues.

    Args:
        text: Python source code
        path: File path (for error reporting)

    Returns:
        List of UnifiedIssue objects
    """
    try:
        # Parse with LibCST
        module = cst.parse_module(text)

        # Create metadata wrapper for position tracking
        wrapper = cst.MetadataWrapper(module)

        # Visit and collect findings
        visitor = HttpTimeoutVisitor(text)
        wrapper.visit(visitor)

        # Convert legacy Finding objects to UnifiedIssue for Sprint 4 compatibility
        uir_findings = []
        for finding in visitor.findings:
            uir = create_uir(
                file=path,
                line=finding.line,
                rule=finding.rule,
                severity=finding.severity,
                message=finding.message,
                suggestion="Add timeout=10 parameter to requests call",
                snippet=finding.snippet,
            )
            uir_findings.append(uir)

        return uir_findings

    except Exception:
        # If parsing fails, return empty list
        return []


def refactor_py_timeout(text: str, path: str, findings: list[UnifiedIssue]) -> tuple[str, EditPlan]:
    """
    Refactor Python code to add timeout parameters.

    Args:
        text: Original Python source code
        path: File path
        findings: List of UnifiedIssue findings to fix

    Returns:
        Tuple of (refactored_code, edit_plan)
    """
    try:
        # Parse with LibCST
        module = cst.parse_module(text)

        # Collect lines to fix from findings
        lines_to_fix = {f.line for f in findings if f.rule == RULE_ID}

        if not lines_to_fix:
            # No findings to fix - return empty plan
            return text, EditPlan(
                id=stable_id(path, RULE_ID, "plan"),
                findings=[],
                edits=[],
                invariants=[],
                estimated_risk=0.0,
            )

        # Create metadata wrapper for position tracking
        wrapper = cst.MetadataWrapper(module)

        # Apply transformation
        transformer = HttpTimeoutTransformer(lines_to_fix)
        modified_tree = wrapper.visit(transformer)

        # Generate modified code
        after_code = modified_tree.code

        # Create Edit object
        edit = Edit(
            file=path,
            start_line=1,
            end_line=len(text.splitlines()),
            op="replace",
            payload=after_code,
        )

        # Calculate estimated risk (high because network calls)
        estimated_risk = 0.8

        plan = EditPlan(
            id=stable_id(path, RULE_ID, "plan"),
            findings=findings,
            edits=[edit],
            invariants=["must_parse"],
            estimated_risk=estimated_risk,
        )

        return after_code, plan

    except Exception:
        # If transformation fails, return original with empty plan
        return text, EditPlan(
            id=stable_id(path, RULE_ID, "plan"),
            findings=[],
            edits=[],
            invariants=[],
            estimated_risk=0.0,
        )



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
# PY-S201-SUBPROCESS-CHECK: Add check=True to subprocess.run()
# ============================================================================


class SubprocessCheckVisitor(cst.CSTVisitor):
    """Visitor to find subprocess.run() calls without check= parameter."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, source_code: str, file_path: str):
        self.findings: list[UnifiedIssue] = []
        self.source_lines = source_code.splitlines()
        self.file_path = file_path

    def visit_Call(self, node: cst.Call) -> None:
        """Visit function calls and check for subprocess.run() without check=."""
        # Check if this is a subprocess.run() call
        if not isinstance(node.func, cst.Attribute):
            return

        # Check if attribute is "run"
        if node.func.attr.value != "run":
            return

        # Check if the base is "subprocess"
        if isinstance(node.func.value, cst.Name) and node.func.value.value == "subprocess":
            # Check if check kwarg exists
            has_check = any(
                isinstance(arg.keyword, cst.Name) and arg.keyword.value == "check"
                for arg in node.args
                if isinstance(arg, cst.Arg) and arg.keyword is not None
            )

            if not has_check:
                # Found subprocess.run() without check parameter
                pos = self.get_metadata(PositionProvider, node)
                line = pos.start.line

                # Get evidence (code snippet)
                evidence = ""
                if 0 <= line - 1 < len(self.source_lines):
                    evidence = self.source_lines[line - 1].strip()
                    if len(evidence) > 120:
                        evidence = evidence[:117] + "..."

                finding = create_uir(
                    file=self.file_path,
                    line=line,
                    rule="PY-S201-SUBPROCESS-CHECK",
                    severity="medium",
                    message="subprocess.run() without 'check=' parameter",
                    suggestion="Add check=True to fail on non-zero exit codes",
                    snippet=evidence,
                )
                self.findings.append(finding)


class SubprocessCheckTransformer(cst.CSTTransformer):
    """Transformer to add check=True to subprocess.run() calls."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, lines_to_fix: set[int]):
        """
        Initialize transformer.

        Args:
            lines_to_fix: Set of line numbers to fix
        """
        self.lines_to_fix = lines_to_fix
        self.modified = False

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform subprocess.run() calls by adding check=True."""
        # Check if this is a subprocess.run() call
        if not isinstance(updated_node.func, cst.Attribute):
            return updated_node

        if updated_node.func.attr.value != "run":
            return updated_node

        # Check if the base is "subprocess"
        if not (
            isinstance(updated_node.func.value, cst.Name)
            and updated_node.func.value.value == "subprocess"
        ):
            return updated_node

        # Check if this call is on a line we want to fix
        pos = self.get_metadata(PositionProvider, original_node)
        if pos.start.line not in self.lines_to_fix:
            return updated_node

        # Check if check already exists
        has_check = any(
            isinstance(arg.keyword, cst.Name) and arg.keyword.value == "check"
            for arg in updated_node.args
            if isinstance(arg, cst.Arg) and arg.keyword is not None
        )

        if has_check:
            return updated_node

        # Add check=True as keyword argument
        check_arg = cst.Arg(
            keyword=cst.Name("check"),
            value=cst.Name("True"),
            equal=cst.AssignEqual(
                whitespace_before=cst.SimpleWhitespace(""),
                whitespace_after=cst.SimpleWhitespace(""),
            ),
        )

        # Insert check argument after other arguments
        new_args = list(updated_node.args) + [check_arg]

        self.modified = True
        return updated_node.with_changes(args=new_args)


def analyze_subprocess_check(src: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze Python source for subprocess.run() without check= parameter.

    Args:
        src: Python source code
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    try:
        module = cst.parse_module(src)
        wrapper = MetadataWrapper(module)
        visitor = SubprocessCheckVisitor(src, path)
        wrapper.visit(visitor)
        return visitor.findings

    except Exception:
        # If parsing fails, return empty list
        return []


def refactor_subprocess_check(
    src: str, path: str, findings: list[UnifiedIssue]
) -> tuple[str, EditPlan]:
    """
    Refactor Python code to add check=True to subprocess.run() calls.

    Args:
        src: Original Python source code
        path: File path
        findings: List of findings to fix

    Returns:
        Tuple of (refactored_code, edit_plan)
    """
    try:
        module = cst.parse_module(src)

        # Collect lines to fix from findings
        lines_to_fix = {f.line for f in findings if f.rule == "PY-S201-SUBPROCESS-CHECK"}

        if not lines_to_fix:
            return src, EditPlan(
                id=stable_id(path, "PY-S201-SUBPROCESS-CHECK", "plan"),
                findings=[],
                edits=[],
                invariants=[],
                estimated_risk=0.0,
            )

        wrapper = MetadataWrapper(module)
        transformer = SubprocessCheckTransformer(lines_to_fix)
        modified_tree = wrapper.visit(transformer)
        new_code = modified_tree.code

        edit = Edit(
            file=path,
            start_line=1,
            end_line=len(src.splitlines()),
            op="replace",
            payload=new_code,
        )
        plan = EditPlan(
            id=stable_id(path, "PY-S201-SUBPROCESS-CHECK", "plan"),
            findings=findings,
            edits=[edit],
            invariants=["must_parse"],
            estimated_risk=0.6,
        )
        return new_code, plan

    except Exception:
        # If refactoring fails, return original
        return src, EditPlan(
            id=stable_id(path, "PY-S201-SUBPROCESS-CHECK", "plan"),
            findings=findings,
            edits=[],
            invariants=[],
            estimated_risk=0.0,
        )


# ============================================================================
# PY-S202-SUBPROCESS-SHELL: Detect shell=True in subprocess calls
# ============================================================================


def analyze_subprocess_shell(src: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze Python source for subprocess calls with shell=True.

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

        class SubprocessShellVisitor(cst.CSTVisitor):
            METADATA_DEPENDENCIES = (PositionProvider,)

            def visit_Call(self, node: cst.Call) -> None:
                """Visit function calls and check for shell=True."""
                # Check if this is a subprocess.* call
                is_subprocess_call = False

                if isinstance(node.func, cst.Attribute):
                    # subprocess.run(), subprocess.call(), etc.
                    if isinstance(node.func.value, cst.Name) and node.func.value.value == "subprocess":
                        is_subprocess_call = True
                elif isinstance(node.func, cst.Name):
                    # Direct subprocess function calls (if imported)
                    if node.func.value in {"run", "call", "check_call", "check_output", "Popen"}:
                        is_subprocess_call = True

                if not is_subprocess_call:
                    return

                # Check if shell=True exists
                for arg in node.args:
                    if not isinstance(arg, cst.Arg) or arg.keyword is None:
                        continue
                    if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "shell":
                        # Check if value is True
                        if isinstance(arg.value, cst.Name) and arg.value.value == "True":
                            pos = self.get_metadata(PositionProvider, node)
                            line = pos.start.line

                            finding = create_uir(
                                file=path,
                                line=line,
                                rule="PY-S202-SUBPROCESS-SHELL",
                                severity="high",
                                message="subprocess call with shell=True is dangerous",
                                suggestion="Avoid shell=True; use list args to prevent shell injection",
                                snippet="shell=True",
                            )
                            findings.append(finding)
                            break

        wrapper.visit(SubprocessShellVisitor())
        return findings

    except Exception:
        # If parsing fails, return empty list
        return []


# ============================================================================
# PY-S203-SUBPROCESS-STRING-CMD: Detect string commands in subprocess
# ============================================================================


def analyze_subprocess_string_cmd(src: str, path: str) -> list[UnifiedIssue]:
    """
    Analyze Python source for subprocess calls with string commands.

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

        class SubprocessStringCmdVisitor(cst.CSTVisitor):
            METADATA_DEPENDENCIES = (PositionProvider,)

            def visit_Call(self, node: cst.Call) -> None:
                """Visit function calls and check for string commands."""
                # Check if this is a subprocess.run/call/etc. call
                is_subprocess_call = False

                if isinstance(node.func, cst.Attribute):
                    # subprocess.run(), subprocess.call(), etc.
                    if isinstance(node.func.value, cst.Name) and node.func.value.value == "subprocess":
                        is_subprocess_call = True
                elif isinstance(node.func, cst.Name):
                    # Direct subprocess function calls (if imported)
                    if node.func.value in {"run", "call", "check_call", "check_output", "Popen"}:
                        is_subprocess_call = True

                if not is_subprocess_call:
                    return

                # Check first positional argument (command)
                if node.args:
                    first_arg = node.args[0]
                    if isinstance(first_arg, cst.Arg) and first_arg.keyword is None:
                        # Check if it's a string (not a list)
                        if isinstance(first_arg.value, (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString)):
                            pos = self.get_metadata(PositionProvider, node)
                            line = pos.start.line

                            finding = create_uir(
                                file=path,
                                line=line,
                                rule="PY-S203-SUBPROCESS-STRING-CMD",
                                severity="medium",
                                message="subprocess call with string command",
                                suggestion="Use list args instead of string for safer command execution",
                                snippet="cmd string",
                            )
                            findings.append(finding)

        wrapper.visit(SubprocessStringCmdVisitor())
        return findings

    except Exception:
        # If parsing fails, return empty list
        return []


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
