"""ACE quick detect rules (cheap AST/regex checks)."""

import logging
import os
from pathlib import Path

import libcst as cst
from libcst import ParserSyntaxError, CSTValidationError
from libcst.metadata import MetadataWrapper, PositionProvider

from ace.uir import UnifiedIssue, create_uir

logger = logging.getLogger(__name__)


def analyze_assert_in_nontest(src: str, path: str) -> list[UnifiedIssue]:
    """
    Detect assert statements outside test files (PY-Q201-ASSERT-IN-NONTEST).

    Args:
        src: Source code
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    # Normalize path for cross-platform compatibility
    norm_path = os.path.normpath(path).replace(os.sep, "/").lower()
    path_parts = norm_path.split("/")
    basename = path_parts[-1] if path_parts else ""

    # Check if this is a test file
    is_test_file = (
        "/tests/" in norm_path
        or "/test/" in norm_path
        or basename.endswith("_test.py")
        or basename.endswith("test_.py")
        or basename.startswith("test_")
    )

    if is_test_file:
        return []

    findings = []

    try:
        module = cst.parse_module(src)
        wrapper = MetadataWrapper(module)

        class AssertVisitor(cst.CSTVisitor):
            METADATA_DEPENDENCIES = (PositionProvider,)

            def visit_Assert(self, node: cst.Assert) -> None:
                pos = self.get_metadata(PositionProvider, node)
                line = pos.start.line

                finding = create_uir(
                    file=path,
                    line=line,
                    rule="PY-Q201-ASSERT-IN-NONTEST",
                    severity="medium",
                    message="assert statement in non-test code",
                    suggestion="Use proper error handling instead of assert",
                    snippet="assert",
                )
                findings.append(finding)

        wrapper.visit(AssertVisitor())

    except (ParserSyntaxError, CSTValidationError) as e:
        logger.warning(f"Failed to parse {path}: {e}")
    except (OSError, ValueError) as e:
        logger.warning(f"Error analyzing {path}: {e}")

    return findings


def analyze_print_in_src(src: str, path: str) -> list[UnifiedIssue]:
    """
    Detect print() calls in source code (PY-Q202-PRINT-IN-SRC).

    Args:
        src: Source code
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    # Normalize path for cross-platform compatibility
    norm_path = os.path.normpath(path).replace(os.sep, "/").lower()

    # Check if this is a src file
    is_src_file = "/src/" in norm_path

    if not is_src_file:
        return []

    findings = []

    try:
        module = cst.parse_module(src)
        wrapper = MetadataWrapper(module)

        class PrintVisitor(cst.CSTVisitor):
            METADATA_DEPENDENCIES = (PositionProvider,)

            def visit_Call(self, node: cst.Call) -> None:
                # Check if this is a print() call
                if isinstance(node.func, cst.Name) and node.func.value == "print":
                    pos = self.get_metadata(PositionProvider, node)
                    line = pos.start.line

                    finding = create_uir(
                        file=path,
                        line=line,
                        rule="PY-Q202-PRINT-IN-SRC",
                        severity="low",
                        message="print() call in source code",
                        suggestion="Use logging instead of print",
                        snippet="print()",
                    )
                    findings.append(finding)

        wrapper.visit(PrintVisitor())

    except (ParserSyntaxError, CSTValidationError) as e:
        logger.warning(f"Failed to parse {path}: {e}")
    except (OSError, ValueError) as e:
        logger.warning(f"Error analyzing {path}: {e}")

    return findings


def analyze_eval_exec(src: str, path: str) -> list[UnifiedIssue]:
    """
    Detect eval() and exec() calls (PY-Q203-EVAL-EXEC).

    Args:
        src: Source code
        path: File path

    Returns:
        List of UnifiedIssue findings
    """
    findings = []

    try:
        module = cst.parse_module(src)
        wrapper = MetadataWrapper(module)

        class EvalExecVisitor(cst.CSTVisitor):
            METADATA_DEPENDENCIES = (PositionProvider,)

            def visit_Call(self, node: cst.Call) -> None:
                # Check if this is eval() or exec() call
                if isinstance(node.func, cst.Name) and node.func.value in {
                    "eval",
                    "exec",
                }:
                    pos = self.get_metadata(PositionProvider, node)
                    line = pos.start.line
                    func_name = node.func.value

                    finding = create_uir(
                        file=path,
                        line=line,
                        rule="PY-Q203-EVAL-EXEC",
                        severity="high",
                        message=f"{func_name}() is dangerous and can execute arbitrary code",
                        suggestion=f"Avoid {func_name}(); use safer alternatives",
                        snippet=f"{func_name}()",
                    )
                    findings.append(finding)

        wrapper.visit(EvalExecVisitor())

    except (ParserSyntaxError, CSTValidationError) as e:
        logger.warning(f"Failed to parse {path}: {e}")
    except (OSError, ValueError) as e:
        logger.warning(f"Error analyzing {path}: {e}")

    return findings
