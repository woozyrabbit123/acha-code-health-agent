"""Refactor Agent - applies safe transformations"""
import ast
import json
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from utils.patcher import Patcher


class RefactorAgent:
    """Agent for refactoring code based on analysis findings"""

    def __init__(self):
        self.patcher = Patcher()
        self.modifications = {}
        self.notes = []

    def apply(self, target_dir: str, analysis_json_path: str) -> Dict[str, Any]:
        """
        Apply refactoring based on analysis findings.

        Args:
            target_dir: Directory containing source code
            analysis_json_path: Path to analysis.json file

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
        with open(analysis_path, 'r', encoding='utf-8') as f:
            analysis = json.load(f)

        findings = analysis.get('findings', [])

        # Filter for dup_immutable_const findings
        dup_const_findings = [
            f for f in findings if f.get('finding') == 'dup_immutable_const'
        ]

        self.modifications = {}
        self.notes = []

        # Prepare workdir
        self.patcher.prepare_workdir(target_dir)

        # Process each finding
        for finding in dup_const_findings:
            self._process_dup_const_finding(finding, target_path)

        # Generate and write diff
        all_diffs = []
        for file_path, new_content in self.modifications.items():
            original_file = target_path / file_path
            with open(original_file, 'r', encoding='utf-8') as f:
                original_content = f.read()

            diff = self.patcher.generate_diff(original_content, new_content, file_path)
            if diff:
                all_diffs.append(diff)

        combined_diff = '\n'.join(all_diffs)
        self.patcher.write_patch(combined_diff)

        # Apply modifications to workdir
        self.patcher.apply_modifications(self.modifications)

        # Count diff stats
        lines_added, lines_removed = self.patcher.count_diff_stats(combined_diff)

        # Generate patch summary
        patch_summary = {
            'patch_id': str(uuid.uuid4()),
            'files_touched': list(self.modifications.keys()),
            'lines_added': lines_added,
            'lines_removed': lines_removed,
            'notes': self.notes
        }

        return patch_summary

    def _process_dup_const_finding(self, finding: Dict[str, Any], target_path: Path):
        """Process a single dup_immutable_const finding"""
        file_path = finding.get('file')
        start_line = finding.get('start_line')

        if not file_path or not start_line:
            self.notes.append(f"Skipping finding {finding.get('id')}: missing file or line info")
            return

        source_file = target_path / file_path

        if not source_file.exists():
            self.notes.append(f"Skipping {file_path}: file not found")
            return

        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
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

        const_name = const_info['name']
        const_value = const_info['value']

        # Inline the constant
        modified_content = self._inline_constant(
            content, lines, tree, const_name, const_value, start_line
        )

        if modified_content != content:
            self.modifications[file_path] = modified_content
            self.notes.append(f"Inlined constant '{const_name}' in {file_path}")
        else:
            self.notes.append(f"No changes for constant '{const_name}' in {file_path}")

    def _find_constant_at_line(self, tree: ast.AST, line_num: int) -> Optional[Dict[str, Any]]:
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
                                    return {
                                        'name': target.id,
                                        'value': value,
                                        'line': line_num
                                    }
        return None

    def _inline_constant(
        self,
        content: str,
        lines: List[str],
        tree: ast.AST,
        const_name: str,
        const_value: Any,
        def_line: int
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
                    references.append({
                        'line': node.lineno,
                        'col': node.col_offset,
                        'end_col': node.end_col_offset
                    })

        if not references:
            return content

        # Sort references in reverse order (bottom to top) to preserve line numbers
        references.sort(key=lambda x: (x['line'], x['col']), reverse=True)

        # Convert content to list of lines for easier manipulation
        modified_lines = lines[:]

        # Generate literal representation
        if isinstance(const_value, str):
            literal = repr(const_value)
        else:
            literal = str(const_value)

        # Replace each reference
        for ref in references:
            line_idx = ref['line'] - 1
            if line_idx >= len(modified_lines):
                continue

            line = modified_lines[line_idx]
            col_start = ref['col']
            col_end = ref['end_col'] if ref['end_col'] else col_start + len(const_name)

            # Replace the constant name with its literal value
            new_line = line[:col_start] + literal + line[col_end:]
            modified_lines[line_idx] = new_line

        return '\n'.join(modified_lines)
