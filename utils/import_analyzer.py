"""Import analysis and classification utilities"""
import ast
import sys
from typing import Dict, List, Set, Tuple


# Standard library modules (Python 3.11+)
STDLIB_MODULES = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins', 'bz2',
    'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs', 'codeop',
    'collections', 'colorsys', 'compileall', 'concurrent', 'configparser', 'contextlib',
    'contextvars', 'copy', 'copyreg', 'crypt', 'csv', 'ctypes', 'curses', 'dataclasses',
    'datetime', 'dbm', 'decimal', 'difflib', 'dis', 'distutils', 'doctest', 'email',
    'encodings', 'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput',
    'fnmatch', 'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext',
    'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http',
    'imaplib', 'imghdr', 'imp', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools',
    'json', 'keyword', 'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'mailcap',
    'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'multiprocessing', 'netrc',
    'nis', 'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev', 'parser',
    'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib',
    'poplib', 'posix', 'posixpath', 'pprint', 'profile', 'pstats', 'pty', 'pwd', 'py_compile',
    'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're', 'readline', 'reprlib', 'resource',
    'rlcompleter', 'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex',
    'shutil', 'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver',
    'spwd', 'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct',
    'subprocess', 'sunau', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile',
    'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading', 'time', 'timeit',
    'tkinter', 'token', 'tokenize', 'tomllib', 'trace', 'traceback', 'tracemalloc', 'tty',
    'turtle', 'turtledemo', 'types', 'typing', 'unicodedata', 'unittest', 'urllib', 'uu',
    'uuid', 'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound',
    'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib',
    '_thread',
}


def classify_import(name: str) -> str:
    """
    Classify an import as 'stdlib', 'third_party', or 'local'.

    Args:
        name: Module name (e.g., 'os', 'numpy', 'mypackage.utils')

    Returns:
        'stdlib', 'third_party', or 'local'
    """
    # Get root module name
    root_name = name.split('.')[0]

    # Check if it's stdlib
    if root_name in STDLIB_MODULES:
        return 'stdlib'

    # Local imports start with '.' or are single-word without common patterns
    if name.startswith('.'):
        return 'local'

    # Heuristic: if it contains no dots and is lowercase, might be local
    # But popular packages are third-party
    common_third_party = {
        'numpy', 'pandas', 'scipy', 'matplotlib', 'requests', 'flask', 'django',
        'pytest', 'setuptools', 'wheel', 'pip', 'jsonschema', 'yaml', 'click',
        'sqlalchemy', 'redis', 'celery', 'boto3', 'aws', 'google', 'azure',
    }

    if root_name in common_third_party:
        return 'third_party'

    # Default to third_party for most imports
    # Local imports are typically relative or in same package
    return 'third_party'


def get_import_groups(tree: ast.AST) -> Dict[str, List[Tuple[ast.Import | ast.ImportFrom, int]]]:
    """
    Group imports by classification (stdlib, third_party, local).

    Args:
        tree: AST tree to analyze

    Returns:
        Dict mapping classification to list of (import_node, lineno) tuples
    """
    groups: Dict[str, List[Tuple[ast.Import | ast.ImportFrom, int]]] = {
        'stdlib': [],
        'third_party': [],
        'local': [],
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                classification = classify_import(alias.name)
                groups[classification].append((node, node.lineno))
                break  # Only classify once per Import node
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ''
            classification = classify_import(module_name)
            groups[classification].append((node, node.lineno))

    return groups


def collect_import_usage(tree: ast.AST) -> Tuple[Dict[str, List[int]], Set[str]]:
    """
    Collect imported names and their usage.

    Args:
        tree: AST tree to analyze

    Returns:
        Tuple of (imported_names_to_lines, referenced_names)
    """
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


def get_unused_imports(tree: ast.AST) -> List[int]:
    """
    Get line numbers of unused imports.

    Args:
        tree: AST tree to analyze

    Returns:
        List of line numbers with unused imports
    """
    imported, referenced = collect_import_usage(tree)
    unused_lines = []

    for name, lines in imported.items():
        if name not in referenced:
            unused_lines.extend(lines)

    return sorted(set(unused_lines))
