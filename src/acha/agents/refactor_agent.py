"""Refactor Agent - applies safe transformations"""

import ast
import json
import re
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

from acha.utils.import_analyzer import classify_import
from acha.utils.patcher import Patcher


class RefactorType(Enum):
    """Types of refactorings available"""

    INLINE_CONST = "inline_const"
    REMOVE_UNUSED_IMPORT = "remove_unused_import"
    ORGANIZE_IMPORTS = "organize_imports"
    HARDEN_SUBPROCESS = "harden_subprocess"


class RefactorAgent:
    """Agent for refactoring code based on analysis findings"""

    def __init__(self, refactor_types: list[str] | None = None):
        """
        Initialize RefactorAgent.

        Args:
            refactor_types: List of refactor type strings to apply.
                           Defaults to ["inline_const", "remove_unused_import"]
        """
        self.patcher = Patcher(dist_dir="reports")  # Write patches to reports/ directory
        self.modifications = {}
        self.notes = []

        # Parse refactor types
        if refactor_types is None:
            refactor_types = ["inline_const", "remove_unused_import"]

        self.enabled_refactors: set[RefactorType] = set()
        for rt in refactor_types:
            try:
                self.enabled_refactors.add(RefactorType(rt))
            except ValueError:
                self.notes.append(f"Unknown refactor type: {rt}")

    def apply(
        self, target_dir: str, analysis_json_path: str, plan_only: bool = False
    ) -> dict[str, Any]:
        """
        Apply refactoring based on analysis findings.

        Args:
            target_dir: Directory containing source code
            analysis_json_path: Path to analysis.json file
            plan_only: If True, generate plan (diff) only without applying changes

        Returns:
            PatchSummary dictionary
        """
        target_path = Path(target_dir)
        if not target_path.exists():
            raise ValueError(f"Target directory does not exist: {target_dir}")

        analysis_path = Path(analysis_json_path)
        if not analysis_path.exists():
            raise ValueError(f"Analysis file does not exist: {analysis_json_path}")

        # Load analysis findings
        with open(analysis_path, encoding="utf-8") as f:
            analysis = json.load(f)

        findings = analysis.get("findings", [])

        self.modifications = {}
        self.notes = []
        refactor_types_applied = []

        # Prepare workdir
        self.patcher.prepare_workdir(target_dir)

        # Process findings based on enabled refactor types
        if RefactorType.INLINE_CONST in self.enabled_refactors:
            dup_const_findings = [f for f in findings if f.get("finding") == "dup_immutable_const"]
            for finding in dup_const_findings:
                self._process_dup_const_finding(finding, target_path)
            if dup_const_findings:
                refactor_types_applied.append("inline_const")

        if RefactorType.REMOVE_UNUSED_IMPORT in self.enabled_refactors:
            unused_import_findings = [f for f in findings if f.get("finding") == "unused_import"]
            self._process_unused_imports(unused_import_findings, target_path)
            if unused_import_findings:
                refactor_types_applied.append("remove_unused_import")

        if RefactorType.ORGANIZE_IMPORTS in self.enabled_refactors:
            self._organize_all_imports(target_path)
            refactor_types_applied.append("organize_imports")

        if RefactorType.HARDEN_SUBPROCESS in self.enabled_refactors:
            subprocess_findings = [
                f for f in findings if f.get("finding") == "broad_subprocess_shell"
            ]
            self._process_subprocess_hardening(subprocess_findings, target_path)
            if subprocess_findings:
                refactor_types_applied.append("harden_subprocess")

        # Generate and write diff
        all_diffs = []
        for file_path, new_content in self.modifications.items():
            original_file = target_path / file_path
            with open(original_file, encoding="utf-8") as f:
                original_content = f.read()

            diff = self.patcher.generate_diff(original_content, new_content, file_path)
            if diff:
                all_diffs.append(diff)

        combined_diff = "\n".join(all_diffs)
        self.patcher.write_patch(combined_diff)

        # Apply modifications to workdir (unless plan_only)
        if not plan_only:
            self.patcher.apply_modifications(self.modifications)

        # Count diff stats
        lines_added, lines_removed = self.patcher.count_diff_stats(combined_diff)

        # Generate patch summary
        patch_summary = {
            "patch_id": str(uuid.uuid4()),
            "files_touched": list(self.modifications.keys()),
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "notes": self.notes,
            "refactor_types_applied": refactor_types_applied,
        }

        return patch_summary

    def _process_dup_const_finding(self, finding: dict[str, Any], target_path: Path):
        """Process a single dup_immutable_const finding"""
        file_path = finding.get("file")
        start_line = finding.get("start_line")

        if not file_path or not start_line:
            self.notes.append(f"Skipping finding {finding.get('id')}: missing file or line info")
            return

        source_file = target_path / file_path

        if not source_file.exists():
            self.notes.append(f"Skipping {file_path}: file not found")
            return

        try:
            with open(source_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")
        except Exception as e:
            self.notes.append(f"Skipping {file_path}: cannot read file - {e}")
            return

        try:
            tree = ast.parse(content, filename=str(source_file))
        except SyntaxError as e:
            self.notes.append(f"Skipping {file_path}: syntax error - {e}")
            return

        # Find the constant at the specified line
        const_info = self._find_constant_at_line(tree, start_line)
        if not const_info:
            self.notes.append(f"Skipping {file_path}:{start_line}: cannot identify constant")
            return

        const_name = const_info["name"]
        const_value = const_info["value"]

        # Inline the constant
        modified_content = self._inline_constant(
            content, lines, tree, const_name, const_value, start_line
        )

        if modified_content != content:
            self.modifications[file_path] = modified_content
            self.notes.append(f"Inlined constant '{const_name}' in {file_path}")
        else:
            self.notes.append(f"No changes for constant '{const_name}' in {file_path}")

    def _process_unused_imports(self, findings: list[dict[str, Any]], target_path: Path):
        """Remove unused imports from files"""
        # Group findings by file
        files_with_unused = {}
        for finding in findings:
            file_path = finding.get("file")
            line = finding.get("start_line")
            if file_path and line:
                if file_path not in files_with_unused:
                    files_with_unused[file_path] = []
                files_with_unused[file_path].append(line)

        for file_path, unused_lines in files_with_unused.items():
            self._remove_unused_imports_from_file(file_path, set(unused_lines), target_path)

    def _remove_unused_imports_from_file(
        self, file_path: str, unused_lines: set[int], target_path: Path
    ):
        """Remove unused imports from a single file, handling multi-import statements"""
        source_file = target_path / file_path

        if not source_file.exists():
            return

        try:
            with open(source_file, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # If we can't parse, fall back to simple line removal
            lines = content.split("\n")
            modified_lines = []
            for i, line in enumerate(lines, start=1):
                if i not in unused_lines:
                    modified_lines.append(line)
            modified_content = "\n".join(modified_lines)
            if modified_content != content:
                self.modifications[file_path] = modified_content
                self.notes.append(f"Removed {len(unused_lines)} unused import(s) from {file_path}")
            return

        # For proper handling, we remove entire import lines
        # Multi-import analysis would require tracking which specific name is unused,
        # which is beyond the current analyzer's capability
        lines = content.split("\n")
        modified_lines = []
        for i, line in enumerate(lines, start=1):
            if i not in unused_lines:
                modified_lines.append(line)

        modified_content = "\n".join(modified_lines)

        if modified_content != content:
            self.modifications[file_path] = modified_content
            self.notes.append(f"Removed {len(unused_lines)} unused import(s) from {file_path}")

    def _organize_all_imports(self, target_path: Path):
        """Organize imports in all Python files"""
        python_files = list(target_path.rglob("*.py"))

        for py_file in python_files:
            relative_path = str(py_file.relative_to(target_path))
            self._organize_imports_in_file(relative_path, target_path)

    def _organize_imports_in_file(self, file_path: str, target_path: Path):
        """Organize imports in a single file, respecting __future__ import rules"""
        source_file = target_path / file_path

        if not source_file.exists():
            return

        try:
            with open(source_file, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        # Find all imports at module level
        future_imports = []
        imports = {"stdlib": [], "third_party": [], "local": []}
        non_import_start = 0

        for i, node in enumerate(tree.body):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Check for __future__ imports - these MUST come first
                if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                    future_imports.append(ast.unparse(node))
                else:
                    # Classify and store regular imports
                    if isinstance(node, ast.Import):
                        module = node.names[0].name
                    else:
                        module = node.module or ""

                    classification = classify_import(module)
                    imports[classification].append(ast.unparse(node))
            else:
                # First non-import node
                non_import_start = i
                break

        # If no imports to organize, skip
        if not any(imports.values()) and not future_imports:
            return

        # Build organized import section
        organized_imports = []

        # __future__ imports MUST be first (Python requirement)
        if future_imports:
            organized_imports.extend(sorted(set(future_imports)))
            organized_imports.append("")  # Blank line after __future__

        # Sort within each group and deduplicate
        for group in ["stdlib", "third_party", "local"]:
            group_imports = sorted(set(imports[group]))
            if group_imports:
                organized_imports.extend(group_imports)
                organized_imports.append("")  # Blank line between groups

        # Remove trailing blank line
        while organized_imports and organized_imports[-1] == "":
            organized_imports.pop()

        # Reconstruct file
        lines = content.split("\n")

        # Find the line where imports end
        import_end_line = 0
        for node in tree.body[:non_import_start]:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_end_line = max(import_end_line, node.end_lineno or node.lineno)

        # Keep module docstring if present
        docstring_lines = []
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, (ast.Str, ast.Constant))
        ):
            # Has docstring
            docstring_node = tree.body[0]
            docstring_end = docstring_node.end_lineno or docstring_node.lineno
            docstring_lines = lines[:docstring_end]
            docstring_lines.append("")  # Blank line after docstring

        # Rest of the code (after imports)
        rest_of_code = lines[import_end_line:] if import_end_line < len(lines) else []

        # Remove leading blank lines from rest of code
        while rest_of_code and not rest_of_code[0].strip():
            rest_of_code.pop(0)

        # Combine
        if docstring_lines:
            modified_lines = docstring_lines + organized_imports + ["", ""] + rest_of_code
        else:
            modified_lines = organized_imports + ["", ""] + rest_of_code

        modified_content = "\n".join(modified_lines)

        if modified_content != content:
            self.modifications[file_path] = modified_content
            self.notes.append(f"Organized imports in {file_path}")

    def _process_subprocess_hardening(self, findings: list[dict[str, Any]], target_path: Path):
        """Harden subprocess calls by removing shell=True"""
        files_with_subprocess = {}
        for finding in findings:
            file_path = finding.get("file")
            line = finding.get("start_line")
            if file_path and line:
                if file_path not in files_with_subprocess:
                    files_with_subprocess[file_path] = []
                files_with_subprocess[file_path].append(line)

        for file_path, lines_to_fix in files_with_subprocess.items():
            self._harden_subprocess_in_file(file_path, set(lines_to_fix), target_path)

    def _harden_subprocess_in_file(self, file_path: str, lines_to_fix: set[int], target_path: Path):
        """Harden subprocess calls in a single file using AST manipulation"""
        source_file = target_path / file_path

        if not source_file.exists():
            return

        try:
            with open(source_file, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Fall back to regex-based approach for unparseable code
            self._harden_subprocess_regex_fallback(file_path, lines_to_fix, content)
            return

        # Use AST visitor to properly modify subprocess calls
        class SubprocessHardener(ast.NodeTransformer):
            def __init__(self, lines_to_fix: set[int]):
                self.lines_to_fix = lines_to_fix
                self.modified = False

            def visit_Call(self, node):
                # Check if this call is on a line we need to fix
                if not hasattr(node, "lineno") or node.lineno not in self.lines_to_fix:
                    return node

                # Check if it's a subprocess call
                is_subprocess = False
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                        is_subprocess = True

                if not is_subprocess:
                    return node

                # Remove shell=True from keywords
                new_keywords = []
                has_check = False
                for kw in node.keywords:
                    if kw.arg == "shell":
                        # Skip shell=True
                        self.modified = True
                        continue
                    if kw.arg == "check":
                        has_check = True
                    new_keywords.append(kw)

                # Add check=False if not present
                if not has_check:
                    new_keywords.append(ast.keyword(arg="check", value=ast.Constant(value=False)))
                    self.modified = True

                node.keywords = new_keywords
                return node

        hardener = SubprocessHardener(lines_to_fix)
        new_tree = hardener.visit(tree)

        if hardener.modified:
            try:
                modified_content = ast.unparse(new_tree)
                self.modifications[file_path] = modified_content
                self.notes.append(f"Hardened subprocess calls in {file_path}")
            except Exception:
                # If unparsing fails, fall back to regex
                self._harden_subprocess_regex_fallback(file_path, lines_to_fix, content)

    def _harden_subprocess_regex_fallback(
        self, file_path: str, lines_to_fix: set[int], content: str
    ):
        """Fallback regex-based subprocess hardening with improved comma handling"""
        lines = content.split("\n")
        modified = False
        modified_lines = lines[:]

        for line_num in lines_to_fix:
            if 0 < line_num <= len(modified_lines):
                idx = line_num - 1
                line = modified_lines[idx]

                # More careful regex to preserve comma structure
                # Match shell=True with optional surrounding whitespace and commas
                new_line = line

                # Remove , shell=True, -> ,
                new_line = re.sub(r",\s*shell\s*=\s*True\s*,", ",", new_line)
                # Remove , shell=True) -> )
                new_line = re.sub(r",\s*shell\s*=\s*True\s*\)", ")", new_line)
                # Remove (shell=True, -> (
                new_line = re.sub(r"\(\s*shell\s*=\s*True\s*,", "(", new_line)
                # Remove (shell=True) -> ()
                new_line = re.sub(r"\(\s*shell\s*=\s*True\s*\)", "()", new_line)

                # Add check=False if not present and if there's a subprocess call
                if "check=" not in new_line and "subprocess." in new_line:
                    # Add check=False before the closing paren
                    new_line = re.sub(r"\)(\s*)$", r", check=False)\1", new_line)

                if new_line != line:
                    modified_lines[idx] = new_line
                    modified = True

        if modified:
            modified_content = "\n".join(modified_lines)
            self.modifications[file_path] = modified_content
            self.notes.append(f"Hardened subprocess calls in {file_path}")

    def _find_constant_at_line(self, tree: ast.AST, line_num: int) -> dict[str, Any] | None:
        """Find the constant definition at the specified line"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Module):
                for item in node.body:
                    if isinstance(item, ast.Assign) and item.lineno == line_num:
                        # Check if it's a constant assignment
                        if isinstance(item.value, (ast.Constant, ast.Str, ast.Num)):
                            # Get the constant value
                            if isinstance(item.value, ast.Constant):
                                value = item.value.value
                            elif isinstance(item.value, ast.Str):
                                value = item.value.s
                            elif isinstance(item.value, ast.Num):
                                value = item.value.n
                            else:
                                continue

                            # Get target name
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    return {"name": target.id, "value": value, "line": line_num}
        return None

    def _inline_constant(
        self,
        content: str,
        lines: list[str],
        tree: ast.AST,
        const_name: str,
        const_value: Any,
        def_line: int,
    ) -> str:
        """
        Inline a constant by replacing usages with literal value.
        Keep the original definition.
        """
        # Find all references to the constant (excluding the definition line)
        references = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == const_name:
                # Skip the definition line
                if node.lineno != def_line:
                    references.append(
                        {
                            "line": node.lineno,
                            "col": node.col_offset,
                            "end_col": node.end_col_offset,
                        }
                    )

        if not references:
            return content

        # Sort references in reverse order (bottom to top) to preserve line numbers
        references.sort(key=lambda x: (x["line"], x["col"]), reverse=True)

        # Convert content to list of lines for easier manipulation
        modified_lines = lines[:]

        # Generate literal representation
        if isinstance(const_value, str):
            literal = repr(const_value)
        else:
            literal = str(const_value)

        # Replace each reference
        for ref in references:
            line_idx = ref["line"] - 1
            if line_idx >= len(modified_lines):
                continue

            line = modified_lines[line_idx]
            col_start = ref["col"]
            col_end = ref["end_col"] if ref["end_col"] else col_start + len(const_name)

            # Replace the constant name with its literal value
            new_line = line[:col_start] + literal + line[col_end:]
            modified_lines[line_idx] = new_line

        return "\n".join(modified_lines)
