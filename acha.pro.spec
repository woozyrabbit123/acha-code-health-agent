# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ACHA Pro single-file executable.

Build with: pyinstaller --clean --onefile acha.pro.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Determine platform-specific name
platform = sys.platform
if platform.startswith('linux'):
    exe_name = 'acha'
elif platform == 'darwin':
    exe_name = 'acha'
elif platform == 'win32':
    exe_name = 'acha.exe'
else:
    exe_name = 'acha'

# Get version from pyproject.toml
import tomllib  # Python 3.11+
version = "1.0.0"
try:
    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
        version = pyproject["project"]["version"]
except Exception:
    pass

a = Analysis(
    ['src/acha/cli.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/acha/schemas/*.json', 'acha/schemas'),
        ('src/acha/templates/*.html', 'acha/templates'),
    ],
    hiddenimports=[
        'acha.agents.analysis_agent',
        'acha.agents.refactor_agent',
        'acha.agents.validation_agent',
        'acha.baseline',
        'acha.precommit',
        'acha.pro_license',
        'acha.utils.ast_cache',
        'acha.utils.checkpoint',
        'acha.utils.exporter',
        'acha.utils.html_reporter',
        'acha.utils.import_analyzer',
        'acha.utils.logger',
        'acha.utils.parallel_executor',
        'acha.utils.patcher',
        'acha.utils.policy',
        'acha.utils.sarif_reporter',
        'nacl.signing',
        'nacl.encoding',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'black',
        'ruff',
        'mypy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon file path if desired
)
