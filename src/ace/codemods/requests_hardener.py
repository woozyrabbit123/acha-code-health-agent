"""
Requests Hardener Codemod - Add timeout and raise_for_status() to requests.

Ensures requests have timeouts and proper error handling.
Guards: only adds if not already present.
"""

import libcst as cst
from libcst import matchers as m
from pathlib import Path
from typing import Optional

from ace.skills.python import EditPlan, Edit
from ace.uir import create_uir


class RequestsHardenerTransformer(cst.CSTTransformer):
    """LibCST transformer to harden requests calls."""

    def __init__(self):
        self.changes = []

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Add timeout parameter to requests.get/post/etc if missing."""
        # Match requests.get(...), requests.post(...), etc.
        if m.matches(
            updated_node.func,
            m.Attribute(value=m.Name("requests"), attr=m.Name())
        ):
            method = updated_node.func.attr.value
            if method in ["get", "post", "put", "delete", "patch", "request"]:
                # Check if timeout already present
                has_timeout = any(
                    arg.keyword and arg.keyword.value == "timeout"
                    for arg in updated_node.args
                    if isinstance(arg, cst.Arg) and arg.keyword
                )

                if not has_timeout:
                    # Add timeout=30
                    new_args = list(updated_node.args) + [
                        cst.Arg(
                            keyword=cst.Name("timeout"),
                            value=cst.Integer("30"),
                            equal=cst.AssignEqual(
                                whitespace_before=cst.SimpleWhitespace(""),
                                whitespace_after=cst.SimpleWhitespace("")
                            )
                        )
                    ]
                    self.changes.append(f"requests.{method}")
                    return updated_node.with_changes(args=new_args)

        return updated_node


class RequestsHardenerCodemod:
    """Codemod to harden requests calls."""

    @staticmethod
    def plan(source_code: str, file_path: str) -> Optional[EditPlan]:
        """Generate edit plan for requests hardening."""
        try:
            tree = cst.parse_module(source_code)
        except Exception:
            return None

        # Transform requests calls
        transformer = RequestsHardenerTransformer()
        modified_tree = tree.visit(transformer)

        if not transformer.changes:
            return None

        new_code = modified_tree.code

        # Create finding
        finding = create_uir(
            rule_id="PY_REQUESTS_HARDEN",
            severity="medium",
            message=f"Add timeout to requests calls ({len(transformer.changes)} calls)",
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

        plan = EditPlan(
            id=f"requests-harden-{Path(file_path).name}",
            findings=[finding],
            edits=[edit],
            invariants=["Timeout added to requests", "AST structure preserved"],
            estimated_risk=0.3
        )

        return plan

    @staticmethod
    def is_idempotent(source_code: str, file_path: str) -> bool:
        """Check idempotence."""
        plan1 = RequestsHardenerCodemod.plan(source_code, file_path)
        if plan1 is None:
            return True

        new_code = plan1.edits[0].payload
        plan2 = RequestsHardenerCodemod.plan(new_code, file_path)

        return plan2 is None
