"""Analysis Agent - detects code quality issues"""
import ast
import os
from pathlib import Path
from typing import Dict, List, Any


class AnalysisAgent:
    """Agent for analyzing code quality"""

    def __init__(self, dup_threshold: int = 3):
        """
        Initialize the analysis agent.

        Args:
            dup_threshold: Minimum references to flag a duplicated constant (default: 3)
        """
        self.dup_threshold = dup_threshold
        self.findings = []
        self.finding_counter = 0

    def _generate_finding_id(self) -> str:
        """Generate a unique finding ID"""
        self.finding_counter += 1
        return f"ANL-{self.finding_counter:03d}"

    def run(self, target_dir: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyze code at the given directory.

        Args:
            target_dir: Path to directory containing Python code

        Returns:
            Dictionary with 'findings' key containing list of findings
        """
        self.findings = []
        self.finding_counter = 0

        target_path = Path(target_dir)
        if not target_path.exists():
            raise ValueError(f"Target directory does not exist: {target_dir}")

        # Find all Python files
        python_files = list(target_path.rglob("*.py"))

        for py_file in python_files:
            self._analyze_file(py_file, target_path)

        return {"findings": self.findings}

    def _analyze_file(self, file_path: Path, base_path: Path):
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            # Skip files that can't be read
            return

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            # Skip files with syntax errors
            return

        relative_path = str(file_path.relative_to(base_path))

        # Detect duplicated immutable constants
        self._detect_duplicated_constants(tree, relative_path, lines)

        # Detect risky constructs
        self._detect_risky_constructs(tree, relative_path, lines)

        # Detect long functions
        self._detect_long_functions(tree, relative_path, lines)

    def _detect_duplicated_constants(self, tree: ast.AST, file_path: str, lines: List[str]):
        """Detect duplicated immutable constants at module level"""
        # Find module-level constant assignments
        constants = {}

        for node in ast.walk(tree):
            # Only look at module-level assignments
            if isinstance(node, ast.Module):
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        # Check if assigned value is a string or number constant
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

                            # Only track strings and numbers
                            if not isinstance(value, (str, int, float)):
                                continue

                            # Get target names
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    constants[target.id] = {
                                        'value': value,
                                        'line': item.lineno,
                                        'name': target.id
                                    }

        # Count references to these constants
        for const_name, const_info in constants.items():
            ref_count = 0

            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == const_name:
                    # Don't count the assignment itself
                    if node.lineno != const_info['line']:
                        ref_count += 1

            # Flag if referenced more than threshold
            if ref_count > self.dup_threshold:
                self.findings.append({
                    'id': self._generate_finding_id(),
                    'file': file_path,
                    'start_line': const_info['line'],
                    'end_line': const_info['line'],
                    'finding': 'dup_immutable_const',
                    'severity': 0.4,
                    'fix_type': 'inline_const',
                    'rationale': f"Constant '{const_name}' with value {repr(const_info['value'])} is referenced {ref_count} times. Consider inlining or using a more descriptive pattern.",
                    'test_hints': [
                        f"Verify all {ref_count} usages of '{const_name}' still work after refactoring",
                        "Ensure the constant value is correctly inlined in all locations"
                    ]
                })

    def _detect_risky_constructs(self, tree: ast.AST, file_path: str, lines: List[str]):
        """Detect risky constructs like eval, exec, __import__, subprocess"""
        risky_names = {'eval', 'exec', '__import__'}
        risky_attrs = {'subprocess'}

        for node in ast.walk(tree):
            risky_call = None

            # Check for direct calls to risky functions
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in risky_names:
                    risky_call = node.func.id
                # Check for subprocess module usage
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id in risky_attrs:
                        risky_call = f"{node.func.value.id}.{node.func.attr}"

            # Check for imports of subprocess
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'subprocess':
                        self.findings.append({
                            'id': self._generate_finding_id(),
                            'file': file_path,
                            'start_line': node.lineno,
                            'end_line': node.lineno,
                            'finding': 'risky_construct',
                            'severity': 0.8,
                            'fix_type': 'remove_or_wrap',
                            'rationale': f"Import of 'subprocess' module detected. This can be dangerous if used with untrusted input.",
                            'test_hints': [
                                "Review all subprocess calls for security issues",
                                "Ensure no user input is passed to subprocess without validation",
                                "Consider safer alternatives if possible"
                            ]
                        })

            if risky_call:
                self.findings.append({
                    'id': self._generate_finding_id(),
                    'file': file_path,
                    'start_line': node.lineno,
                    'end_line': node.lineno,
                    'finding': 'risky_construct',
                    'severity': 0.9,
                    'fix_type': 'remove_or_wrap',
                    'rationale': f"Use of '{risky_call}' detected. This is a dangerous construct that can execute arbitrary code.",
                    'test_hints': [
                        f"Remove '{risky_call}' and use safer alternatives",
                        "If necessary, wrap with strict input validation",
                        "Consider using ast.literal_eval for safe evaluation"
                    ]
                })

    def _detect_long_functions(self, tree: ast.AST, file_path: str, lines: List[str]):
        """Detect functions that are too long (>60 lines)"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start_line = node.lineno
                end_line = node.end_lineno or start_line
                length = end_line - start_line + 1

                if length > 60:
                    self.findings.append({
                        'id': self._generate_finding_id(),
                        'file': file_path,
                        'start_line': start_line,
                        'end_line': end_line,
                        'finding': 'long_function',
                        'severity': 0.5,
                        'fix_type': 'extract_helper',
                        'rationale': f"Function '{node.name}' is {length} lines long. Consider breaking it into smaller helper functions.",
                        'test_hints': [
                            f"Extract logical sections of '{node.name}' into separate helper functions",
                            "Ensure all tests pass after refactoring",
                            "Verify the function's interface remains unchanged"
                        ]
                    })
