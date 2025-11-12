"""
Dataclass Slots Codemod - Add slots=True to @dataclass decorators.

Guards: skip if multiple inheritance or existing __slots__.
"""

import libcst as cst
from libcst import matchers as m
from pathlib import Path
from typing import Optional

from ace.skills.python import EditPlan, Edit
from ace.uir import create_uir


class DataclassSlotsTransformer(cst.CSTTransformer):
    """Add slots=True to dataclass decorators."""

    def __init__(self):
        self.changes = []

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        """Add slots=True to @dataclass if safe."""
        # Guard: skip if multiple inheritance
        if len(updated_node.bases) > 1:
            return updated_node

        # Guard: skip if __slots__ already defined
        for stmt in updated_node.body.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                for s in stmt.body:
                    if isinstance(s, cst.Assign):
                        for target in s.targets:
                            if isinstance(target.target, cst.Name) and target.target.value == "__slots__":
                                return updated_node

        # Check for @dataclass decorator
        for decorator in updated_node.decorators:
            dec = decorator.decorator
            if m.matches(dec, m.Name("dataclass")) or m.matches(dec, m.Call(func=m.Name("dataclass"))):
                # Check if slots already present
                if isinstance(dec, cst.Call):
                    has_slots = any(
                        arg.keyword and arg.keyword.value == "slots"
                        for arg in dec.args
                        if isinstance(arg, cst.Arg) and arg.keyword
                    )
                    if has_slots:
                        continue

                    # Add slots=True
                    new_args = list(dec.args) + [
                        cst.Arg(
                            keyword=cst.Name("slots"),
                            value=cst.Name("True"),
                            equal=cst.AssignEqual(
                                whitespace_before=cst.SimpleWhitespace(""),
                                whitespace_after=cst.SimpleWhitespace("")
                            )
                        )
                    ]
                    new_dec = dec.with_changes(args=new_args)
                    new_decorator = decorator.with_changes(decorator=new_dec)

                    new_decorators = [
                        new_decorator if d == decorator else d
                        for d in updated_node.decorators
                    ]

                    self.changes.append(updated_node.name.value)
                    return updated_node.with_changes(decorators=new_decorators)

                elif isinstance(dec, cst.Name):
                    # @dataclass without parens -> @dataclass(slots=True)
                    new_dec = cst.Call(
                        func=cst.Name("dataclass"),
                        args=[
                            cst.Arg(
                                keyword=cst.Name("slots"),
                                value=cst.Name("True"),
                                equal=cst.AssignEqual(
                                    whitespace_before=cst.SimpleWhitespace(""),
                                    whitespace_after=cst.SimpleWhitespace("")
                                )
                            )
                        ]
                    )
                    new_decorator = decorator.with_changes(decorator=new_dec)

                    new_decorators = [
                        new_decorator if d == decorator else d
                        for d in updated_node.decorators
                    ]

                    self.changes.append(updated_node.name.value)
                    return updated_node.with_changes(decorators=new_decorators)

        return updated_node


class DataclassSlotsCodemod:
    """Codemod to add slots=True to dataclasses."""

    @staticmethod
    def plan(source_code: str, file_path: str) -> Optional[EditPlan]:
        """Generate edit plan."""
        try:
            tree = cst.parse_module(source_code)
        except Exception:
            return None

        transformer = DataclassSlotsTransformer()
        modified_tree = tree.visit(transformer)

        if not transformer.changes:
            return None

        new_code = modified_tree.code

        finding = create_uir(
            rule_id="PY_DATACLASS_SLOTS",
            severity="low",
            message=f"Add slots=True to dataclasses ({len(transformer.changes)} classes)",
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
            id=f"dataclass-slots-{Path(file_path).name}",
            findings=[finding],
            edits=[edit],
            invariants=["No multiple inheritance", "No existing __slots__"],
            estimated_risk=0.2
        )

        return plan

    @staticmethod
    def is_idempotent(source_code: str, file_path: str) -> bool:
        """Check idempotence."""
        plan1 = DataclassSlotsCodemod.plan(source_code, file_path)
        if plan1 is None:
            return True

        new_code = plan1.edits[0].payload
        plan2 = DataclassSlotsCodemod.plan(new_code, file_path)

        return plan2 is None
