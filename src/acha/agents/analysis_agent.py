"""Analysis Agent - detects code quality issues"""
import ast
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set, Optional
from acha.utils.ast_cache import ASTCache
from acha.utils.parallel_executor import ParallelExecutor


# Severity mapping for rules
RULE_SEVERITY = {
    "dup_immutable_const": "warning",
    "risky_construct": "critical",
    "risky_imports": "error",
    "risky_subprocess": "error",
    "long_function": "warning",
    "missing_docstring": "info",
    # new:
    "unused_import": "warning",
    "magic_number": "warning",
    "high_complexity": "warning",
    "broad_exception": "error",
    "broad_subprocess_shell": "error",
}


def _has_docstring(node: ast.AST) -> bool:
    try:
        return ast.get_docstring(node) is not None
    except Exception:
        return False


def _is_broad_exception(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
        return True
    if isinstance(handler.type, ast.Attribute) and handler.type.attr == "Exception":
        return True
    return False


def _compute_cyclomatic_complexity(fn) -> int:
    count = 1
    for node in ast.walk(fn):
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.IfExp, ast.Match)):
            count += 1
        if isinstance(node, ast.BoolOp):
            # add for each boolean operation beyond the first
            count += max(0, len(getattr(node, "values", [])) - 1)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            count += 1
        if isinstance(node, ast.ExceptHandler):
            count += 1
    return count


def _file_wide_suppressions(source_lines: List[str]) -> Set[str]:
    kinds: Set[str] = set()
    for line in source_lines:
        if "# acha: file-disable-all" in line:
            kinds.add("*")
        if "# acha: file-disable=" in line:
            # parse single rule
            try:
                frag = line.split("# acha: file-disable=")[1].strip()
                rule = frag.split()[0].strip()
                kinds.add(rule)
            except Exception:
                pass
    return kinds


def _is_suppressed(rule: str, lineno: int, source_lines: List[str], file_sups: Set[str]) -> bool:
    if "*" in file_sups or rule in file_sups:
        return True
    if 1 <= lineno <= len(source_lines):
        line = source_lines[lineno - 1]
        if "# acha: disable-all" in line:
            return True
        tag = f"# acha: disable={rule}"
        if tag in line:
            return True
    return False


def _collect_import_usage(tree: ast.AST) -> Tuple[Dict[str, List[int]], Set[str]]:
    # map imported names -> line numbers declared; and names referenced
    imported: Dict[str, List[int]] = {}
    referenced: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                imported.setdefault(name, []).append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                imported.setdefault(name, []).append(node.lineno)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            referenced.add(node.id)
    return imported, referenced


def _subprocess_shell_calls(tree: ast.AST) -> List[Tuple[int, int]]:
    hits: List[Tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # func is subprocess.<x>
            is_subprocess = False
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "subprocess":
                    is_subprocess = True
            if not is_subprocess:
                continue
            for kw in node.keywords or []:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    hits.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
    return hits


def _find_broad_excepts(tree: ast.AST) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and _is_broad_exception(node):
            out.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
    return out


def _find_magic_numbers(tree: ast.AST, source_lines: List[str]) -> List[Tuple[int, int, str]]:
    hits: List[Tuple[int, int, str]] = []
    def is_exempt(n: ast.AST) -> bool:
        # 0/1/-1 common sentinels
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            if n.value in (0, 1, -1):
                return True
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not is_exempt(node):
            # heuristic: ignore if in assignment to ALL_CAPS name or default arg
            parent = getattr(node, "parent", None)
            if isinstance(parent, ast.keyword):  # default kw
                continue
            ln = node.lineno
            hits.append((ln, getattr(node, "end_lineno", ln), repr(node.value)))
    # post-filter: require repeats (same literal 2+ times in file)
    counts: Dict[str, int] = {}
    for _, _, lit in hits:
        counts[lit] = counts.get(lit, 0) + 1
    return [(ln, end, lit) for (ln, end, lit) in hits if counts.get(lit, 0) >= 2]


def _attach_parents(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node  # type: ignore[attr-defined]


def _read_lines(p: Path) -> List[str]:
    try:
        return p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []


class AnalysisAgent:
    """Agent for analyzing code quality"""

    def __init__(self, dup_threshold: int = 3, cache: Optional[ASTCache] = None,
                 parallel: bool = False, max_workers: int = 4):
        """
        Initialize the analysis agent.

        Args:
            dup_threshold: Minimum references to flag a duplicated constant (default: 3)
            cache: AST cache for improved performance (default: None)
            parallel: Enable parallel file analysis (default: False)
            max_workers: Number of worker threads for parallel analysis (default: 4)
        """
        self.dup_threshold = dup_threshold
        self.findings = []
        self.finding_counter = 0
        self.cache = cache
        self.parallel = parallel
        self.max_workers = max_workers

    def _generate_finding_id(self) -> str:
        """Generate a unique finding ID"""
        self.finding_counter += 1
        return f"ANL-{self.finding_counter:03d}"

    def _severity_to_numeric(self, severity) -> float:
        """Convert severity string to numeric value for schema compatibility"""
        if isinstance(severity, (int, float)):
            return float(severity)

        severity_map = {
            "info": 0.1,
            "warning": 0.4,
            "error": 0.7,
            "critical": 0.9
        }
        return severity_map.get(str(severity).lower(), 0.5)

    def _add_finding(self, finding: Dict[str, Any]) -> None:
        """Add a finding with automatic severity assignment"""
        rule = finding.get("rule", finding.get("finding", ""))
        severity_str = RULE_SEVERITY.get(rule, "info")

        # Always convert to numeric for schema compatibility
        if "severity" not in finding:
            finding["severity"] = self._severity_to_numeric(severity_str)
        else:
            finding["severity"] = self._severity_to_numeric(finding["severity"])

        self.findings.append(finding)

    def _add_issue(self, rule: str, file_path: str, start: int, end: int, rationale: str, test_hints: List[str] = None):
        """Add an issue with standard fields"""
        severity_str = RULE_SEVERITY.get(rule, "info")
        self._add_finding({
            "id": self._generate_finding_id(),
            "rule": rule,
            "finding": rule,
            "severity": severity_str,  # Will be converted to numeric by _add_finding
            "file": file_path,
            "start_line": start,
            "end_line": end,
            "rationale": rationale,
            "test_hints": test_hints or [],
            "fix_type": "manual"
        })

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

        if self.parallel and len(python_files) > 1:
            # Use parallel analysis
            self._analyze_parallel(python_files, target_path)
        else:
            # Sequential analysis
            for py_file in python_files:
                self._analyze_file(py_file, target_path)

        return {"findings": self.findings}

    def analyze_batch(self, target_dirs: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyze multiple directories in batch.

        Args:
            target_dirs: List of directory paths

        Returns:
            Dictionary mapping target directory to its findings
        """
        results = {}

        for target_dir in target_dirs:
            # Reset findings for each directory
            self.findings = []
            self.finding_counter = 0

            target_path = Path(target_dir)
            if not target_path.exists():
                results[target_dir] = []
                continue

            python_files = list(target_path.rglob("*.py"))

            if self.parallel and len(python_files) > 1:
                self._analyze_parallel(python_files, target_path)
            else:
                for py_file in python_files:
                    self._analyze_file(py_file, target_path)

            results[target_dir] = self.findings

        return results

    def _analyze_parallel(self, python_files: List[Path], base_path: Path):
        """Analyze files in parallel"""
        executor = ParallelExecutor(max_workers=self.max_workers, verbose=False)

        def analyze_single(py_file: Path) -> List[Dict]:
            # Create a temporary findings list for this file
            original_findings = self.findings
            original_counter = self.finding_counter

            self.findings = []

            self._analyze_file(py_file, base_path)

            # Capture findings from this file
            file_findings = self.findings

            # Restore original state
            self.findings = original_findings
            self.finding_counter = original_counter

            return file_findings

        # Analyze files in parallel
        all_file_findings = executor.map_parallel(analyze_single, python_files)

        # Combine findings
        for file_findings in all_file_findings:
            if file_findings:
                self.findings.extend(file_findings)
                # Update counter based on findings added
                for finding in file_findings:
                    if 'id' in finding:
                        # Extract counter from id like "ANL-001"
                        try:
                            counter = int(finding['id'].split('-')[1])
                            self.finding_counter = max(self.finding_counter, counter)
                        except Exception:
                            pass

    def _analyze_file(self, file_path: Path, base_path: Path):
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            # Skip files that can't be read
            return

        # Try to get AST from cache
        tree = None
        if self.cache:
            tree = self.cache.get_ast(file_path)

        # Parse if not in cache
        if tree is None:
            try:
                tree = ast.parse(content, filename=str(file_path))
                # Store in cache for future use
                if self.cache:
                    self.cache.put_ast(file_path, tree)
            except SyntaxError:
                # Skip files with syntax errors
                return
        else:
            # Got from cache, but still need to parse for line content
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError:
                return

        relative_path = str(file_path.relative_to(base_path))

        # Get file-wide suppressions
        file_sups = _file_wide_suppressions(lines)
        _attach_parents(tree)

        # NEW RULES FIRST

        # --- unused_import
        imported, referenced = _collect_import_usage(tree)
        for name, import_lines in imported.items():
            if name not in referenced:
                for ln in import_lines:
                    if not _is_suppressed("unused_import", ln, lines, file_sups):
                        self._add_issue("unused_import", relative_path, ln, ln, f"Imported '{name}' is never used")

        # --- magic_number
        for ln, end, lit in _find_magic_numbers(tree, lines):
            if not _is_suppressed("magic_number", ln, lines, file_sups):
                self._add_issue("magic_number", relative_path, ln, end, f"Repeated literal {lit} without named constant")

        # --- high_complexity + missing_docstring
        from acha.utils.policy import PolicyConfig
        max_complexity_threshold = PolicyConfig().max_complexity

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ln = node.lineno
                if not _has_docstring(node) and not _is_suppressed("missing_docstring", ln, lines, file_sups):
                    self._add_issue("missing_docstring", relative_path, ln, ln, f"Function '{node.name}' missing docstring")
                cplx = _compute_cyclomatic_complexity(node)
                if cplx > max_complexity_threshold:
                    if not _is_suppressed("high_complexity", ln, lines, file_sups):
                        self._add_issue("high_complexity", relative_path, ln, ln, f"Function '{node.name}' complexity {cplx} exceeds threshold {max_complexity_threshold}")

        # --- broad_exception
        for ln, end in _find_broad_excepts(tree):
            if not _is_suppressed("broad_exception", ln, lines, file_sups):
                self._add_issue("broad_exception", relative_path, ln, end, "Catching broad Exception or bare except")

        # --- subprocess shell=True
        for ln, end in _subprocess_shell_calls(tree):
            if not _is_suppressed("broad_subprocess_shell", ln, lines, file_sups):
                self._add_issue("broad_subprocess_shell", relative_path, ln, end, "subprocess called with shell=True")

        # EXISTING RULES (keep unchanged)

        # Detect duplicated immutable constants
        self._detect_duplicated_constants(tree, relative_path, lines, file_sups)

        # Detect risky constructs
        self._detect_risky_constructs(tree, relative_path, lines, file_sups)

        # Detect long functions
        self._detect_long_functions(tree, relative_path, lines, file_sups)

    def _detect_duplicated_constants(self, tree: ast.AST, file_path: str, lines: List[str], file_sups: Set[str]):
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
                ln = const_info['line']
                if not _is_suppressed("dup_immutable_const", ln, lines, file_sups):
                    self._add_finding({
                        'id': self._generate_finding_id(),
                        'file': file_path,
                        'start_line': const_info['line'],
                        'end_line': const_info['line'],
                        'finding': 'dup_immutable_const',
                        'rule': 'dup_immutable_const',
                        'severity': 0.4,
                        'fix_type': 'inline_const',
                        'rationale': f"Constant '{const_name}' with value {repr(const_info['value'])} is referenced {ref_count} times. Consider inlining or using a more descriptive pattern.",
                        'test_hints': [
                            f"Verify all {ref_count} usages of '{const_name}' still work after refactoring",
                            "Ensure the constant value is correctly inlined in all locations"
                        ]
                    })

    def _detect_risky_constructs(self, tree: ast.AST, file_path: str, lines: List[str], file_sups: Set[str]):
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
                        ln = node.lineno
                        if not _is_suppressed("risky_construct", ln, lines, file_sups):
                            self._add_finding({
                                'id': self._generate_finding_id(),
                                'file': file_path,
                                'start_line': node.lineno,
                                'end_line': node.lineno,
                                'finding': 'risky_construct',
                                'rule': 'risky_construct',
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
                ln = node.lineno
                if not _is_suppressed("risky_construct", ln, lines, file_sups):
                    self._add_finding({
                        'id': self._generate_finding_id(),
                        'file': file_path,
                        'start_line': node.lineno,
                        'end_line': node.lineno,
                        'finding': 'risky_construct',
                        'rule': 'risky_construct',
                        'severity': 0.9,
                        'fix_type': 'remove_or_wrap',
                        'rationale': f"Use of '{risky_call}' detected. This is a dangerous construct that can execute arbitrary code.",
                        'test_hints': [
                            f"Remove '{risky_call}' and use safer alternatives",
                            "If necessary, wrap with strict input validation",
                            "Consider using ast.literal_eval for safe evaluation"
                        ]
                    })

    def _detect_long_functions(self, tree: ast.AST, file_path: str, lines: List[str], file_sups: Set[str]):
        """Detect functions that are too long (>60 lines)"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start_line = node.lineno
                end_line = node.end_lineno or start_line
                length = end_line - start_line + 1

                if length > 60:
                    if not _is_suppressed("long_function", start_line, lines, file_sups):
                        self._add_finding({
                            'id': self._generate_finding_id(),
                            'file': file_path,
                            'start_line': start_line,
                            'end_line': end_line,
                            'finding': 'long_function',
                            'rule': 'long_function',
                            'severity': 0.5,
                            'fix_type': 'extract_helper',
                            'rationale': f"Function '{node.name}' is {length} lines long. Consider breaking it into smaller helper functions.",
                            'test_hints': [
                                f"Extract logical sections of '{node.name}' into separate helper functions",
                                "Ensure all tests pass after refactoring",
                                "Verify the function's interface remains unchanged"
                            ]
                        })
