"""CI smoke tests - quick verification that basic imports and version work."""

import sys


class TestCISmoke:
    """Smoke tests for CI to catch critical failures quickly."""

    def test_ace_imports(self):
        """Test that ace module can be imported."""
        try:
            import ace
            import ace.cli
            import ace.kernel
            import ace.uir
            import ace.policy
            import ace.guard
        except ImportError as e:
            raise AssertionError(f"Failed to import ace modules: {e}")

    def test_acha_imports(self):
        """Test that acha module can be imported."""
        try:
            import acha
            import acha.cli
        except ImportError as e:
            raise AssertionError(f"Failed to import acha modules: {e}")

    def test_ace_version_defined(self):
        """Test that ace.__version__ is defined."""
        import ace
        assert hasattr(ace, "__version__")
        assert isinstance(ace.__version__, str)
        assert len(ace.__version__) > 0

    def test_acha_version_defined(self):
        """Test that acha.__version__ is defined."""
        import acha
        assert hasattr(acha, "__version__")
        assert isinstance(acha.__version__, str)
        assert len(acha.__version__) > 0

    def test_python_version(self):
        """Test that Python version is 3.11+."""
        assert sys.version_info >= (3, 11), f"Python 3.11+ required, got {sys.version_info}"

    def test_ace_cli_main_exists(self):
        """Test that ace CLI main entry point exists."""
        from ace.cli import main
        assert callable(main)

    def test_acha_cli_main_exists(self):
        """Test that acha CLI main entry point exists."""
        from acha.cli import main
        assert callable(main)

    def test_ace_kernel_functions_exist(self):
        """Test that key ace.kernel functions exist."""
        from ace.kernel import run_analyze, run_refactor, run_apply
        assert callable(run_analyze)
        assert callable(run_refactor)
        assert callable(run_apply)

    def test_libcst_available(self):
        """Test that libcst is available (required for ace)."""
        try:
            import libcst
            assert hasattr(libcst, "parse_module")
        except ImportError:
            raise AssertionError("libcst not available - required for ace functionality")

    def test_no_syntax_errors(self):
        """Test that all main modules can be imported without syntax errors."""
        modules = [
            "ace.cli",
            "ace.kernel",
            "ace.skills.quick_detects",
            "ace.codemods.dead_imports",
            "ace.autopilot",
            "ace.repair",
            "acha.cli",
        ]
        
        for module_name in modules:
            try:
                __import__(module_name)
            except SyntaxError as e:
                raise AssertionError(f"Syntax error in {module_name}: {e}")
            except ImportError as e:
                # Optional dependencies are OK
                if "textual" in str(e) or "PyNaCl" in str(e):
                    continue
                raise AssertionError(f"Import error in {module_name}: {e}")
