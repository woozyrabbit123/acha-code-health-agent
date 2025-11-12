"""Python skill - LibCST-based analysis and refactoring."""

from dataclasses import dataclass
from pathlib import Path

import libcst as cst

from ace.uir import create_uir

# Rule: PY-S101-UNSAFE-HTTP
RULE_ID = "PY-S101-UNSAFE-HTTP"
RULE_SEVERITY = "high"
REQUESTS_METHODS = {"get", "post", "put", "delete", "head", "request"}


@dataclass
class Finding:
    """Represents a code finding."""

    file: str
    line: int
    column: int
    rule: str
    severity: str
    message: str
    evidence: str
    snippet: str


@dataclass
class EditPlan:
    """Represents a refactoring plan."""

    file: str
    rule: str
    before: str
    after: str
    estimated_risk: float
    description: str


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


def analyze_py(text: str, path: str) -> list[Finding]:
    """
    Analyze Python source for HTTP timeout issues.

    Args:
        text: Python source code
        path: File path (for error reporting)

    Returns:
        List of Finding objects
    """
    try:
        # Parse with LibCST
        module = cst.parse_module(text)

        # Create metadata wrapper for position tracking
        wrapper = cst.MetadataWrapper(module)

        # Visit and collect findings
        visitor = HttpTimeoutVisitor(text)
        wrapper.visit(visitor)

        # Set file path on all findings
        for finding in visitor.findings:
            finding.file = path

        return visitor.findings

    except Exception:
        # If parsing fails, return empty list
        return []


def refactor_py_timeout(text: str, path: str, findings: list[Finding]) -> tuple[str, EditPlan]:
    """
    Refactor Python code to add timeout parameters.

    Args:
        text: Original Python source code
        path: File path
        findings: List of findings to fix

    Returns:
        Tuple of (refactored_code, edit_plan)
    """
    try:
        # Parse with LibCST
        module = cst.parse_module(text)

        # Collect lines to fix from findings
        lines_to_fix = {f.line for f in findings if f.rule == RULE_ID}

        if not lines_to_fix:
            # No findings to fix
            return text, EditPlan(
                file=path,
                rule=RULE_ID,
                before=text,
                after=text,
                estimated_risk=0.0,
                description="No changes needed",
            )

        # Create metadata wrapper for position tracking
        wrapper = cst.MetadataWrapper(module)

        # Apply transformation
        transformer = HttpTimeoutTransformer(lines_to_fix)
        modified_tree = wrapper.visit(transformer)

        # Generate modified code
        after_code = modified_tree.code

        # Calculate estimated risk (high because network calls)
        estimated_risk = 0.8

        plan = EditPlan(
            file=path,
            rule=RULE_ID,
            before=text,
            after=after_code,
            estimated_risk=estimated_risk,
            description=f"Add timeout=10 to {len(lines_to_fix)} requests call(s)",
        )

        return after_code, plan

    except Exception as e:
        # If transformation fails, return original
        return text, EditPlan(
            file=path,
            rule=RULE_ID,
            before=text,
            after=text,
            estimated_risk=0.0,
            description=f"Transform failed: {e}",
        )


def analyze_python(file_path: str) -> list:
    """
    Analyze Python file for issues.

    Args:
        file_path: Path to Python file

    Returns:
        List of UIR findings
    """
    path = Path(file_path)
    if not path.exists():
        return []

    try:
        text = path.read_text(encoding="utf-8")
        findings = analyze_py(text, str(path))

        # Convert to UIR format
        uir_findings = []
        for f in findings:
            uir = create_uir(
                file=f.file,
                line=f.line,
                rule=f.rule,
                severity=f.severity,
                message=f.message,
                suggestion="Add timeout=10 parameter",
                snippet=f.snippet,
            )
            uir_findings.append(uir)

        return uir_findings

    except Exception:
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
    path = Path(file_path)
    if not path.exists():
        return ""

    try:
        text = path.read_text(encoding="utf-8")

        # Convert UIR findings to Finding objects
        internal_findings = []
        for uir in findings:
            uir_dict = uir.to_dict() if hasattr(uir, "to_dict") else uir
            finding = Finding(
                file=uir_dict.get("file", ""),
                line=uir_dict.get("line", 0),
                column=0,
                rule=uir_dict.get("rule", ""),
                severity=uir_dict.get("severity", ""),
                message=uir_dict.get("message", ""),
                evidence=uir_dict.get("snippet", ""),
                snippet=uir_dict.get("snippet", ""),
            )
            internal_findings.append(finding)

        refactored, plan = refactor_py_timeout(text, str(path), internal_findings)
        return refactored

    except Exception:
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
