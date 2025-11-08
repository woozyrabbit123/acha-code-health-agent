# Third-Party Notices

ACHA Pro v1.0.0 includes code from the following open-source projects. We are grateful to these communities for their contributions.

---

## Runtime Dependencies

### PyNaCl (v1.5.0+)
**License:** Apache License 2.0
**Purpose:** Ed25519 cryptographic signature verification for offline license validation
**Repository:** https://github.com/pyca/pynacl

Copyright 2013-2023 Donald Stufft and individual contributors

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at:

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

---

### jsonschema (v4.0.0+)
**License:** MIT License
**Purpose:** JSON Schema validation for analysis reports and configuration files
**Repository:** https://github.com/python-jsonschema/jsonschema

Copyright (c) 2013 Julian Berman

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

## Development & Build Dependencies

### pytest (v7.0.0+)
**License:** MIT License
**Purpose:** Testing framework
**Repository:** https://github.com/pytest-dev/pytest

Copyright (c) 2004 Holger Krekel and others

---

### pytest-timeout (v2.0.0+)
**License:** MIT License
**Purpose:** Timeout control for tests
**Repository:** https://github.com/pytest-dev/pytest-timeout

---

### pytest-cov (v4.0.0+)
**License:** MIT License
**Purpose:** Code coverage reporting
**Repository:** https://github.com/pytest-dev/pytest-cov

---

### Black (v23.0.0+)
**License:** MIT License
**Purpose:** Python code formatter
**Repository:** https://github.com/psf/black

Copyright © 2018 Łukasz Langa and contributors

---

### Ruff (v0.1.0+)
**License:** MIT License
**Purpose:** Fast Python linter (replaces flake8, isort, pyupgrade)
**Repository:** https://github.com/astral-sh/ruff

Copyright (c) 2022 Charlie Marsh

---

### mypy (v1.0.0+)
**License:** MIT License
**Purpose:** Static type checker for Python
**Repository:** https://github.com/python/mypy

Copyright (c) 2015-2023 Jukka Lehtosalo and contributors

---

### PyInstaller (v5.0.0+)
**License:** GPL v2 with exception for bundled applications
**Purpose:** Creating standalone executables
**Repository:** https://github.com/pyinstaller/pyinstaller

**Note:** PyInstaller is licensed under GPL v2, but includes an exception allowing bundled applications to be distributed under any license. ACHA Pro binaries created with PyInstaller are not subject to GPL requirements.

From PyInstaller's license:
> "In addition, as a special exception, the copyright holders give permission to link or embed the code of this Program with code licensed under the GNU General Public License version 2 only, and to distribute linked combinations including the two. You must obey the GNU General Public License in all respects for all of the code used other than code licensed under the GNU General Public License version 2 only."

---

## Python Standard Library

ACHA Pro uses the following Python 3.11+ standard library modules:
- `ast` - Abstract Syntax Tree parsing
- `argparse` - Command-line argument parsing
- `json` - JSON encoding/decoding
- `pathlib` - File system path operations
- `hashlib` - SHA256 hashing for baseline IDs
- `subprocess` - Running external commands (git, pytest)
- `tempfile` - Temporary file/directory creation
- `importlib.resources` - Package resource loading
- `tomllib` - TOML parsing (Python 3.11+)

Python itself is licensed under the PSF License Agreement, compatible with GPL and commercial use.

---

## Embedded Resources

### HTML Report Template
ACHA Pro's HTML reporter includes embedded CSS inspired by modern design systems but is original work. No third-party CSS frameworks (Bootstrap, Tailwind, etc.) are used.

### JavaScript
All JavaScript in HTML reports is original code written specifically for ACHA Pro. No third-party libraries (jQuery, React, etc.) are included.

---

## Exclusions

The following are **NOT** included in ACHA Pro distributions:
- Testing frameworks (pytest, pytest-timeout, pytest-cov) - development only
- Linters/formatters (ruff, black, mypy) - development only
- Build tools (PyInstaller) - build-time only

Only `jsonschema` and `PyNaCl` (when Pro features are used) are required at runtime.

---

## License File Locations

Full license texts for all dependencies can be found in their respective repositories linked above.

Python packages installed via pip include license files in:
```
<python-site-packages>/<package-name>-<version>.dist-info/LICENSE
```

---

## Attribution Requirements

Per the licenses above, we provide this notice to fulfill attribution requirements. If you redistribute ACHA Pro or include it in a larger work, please retain this THIRD_PARTY_NOTICES.md file.

---

## Updates

This file is accurate as of ACHA Pro v1.0.0 (2025-01-01). Dependency versions and licenses may change in future releases. Check the latest version of this file in the source repository.

---

## Questions

If you have questions about licensing or dependency usage:
- **GitHub Issues:** https://github.com/woozyrabbit123/acha-code-health-agent/issues
- **Email:** [SUPPORT EMAIL TO BE SPECIFIED]

---

**Thank you to all open-source maintainers whose work makes ACHA Pro possible!**

Last Updated: 2025-01-01
ACHA Pro Version: 1.0.0
