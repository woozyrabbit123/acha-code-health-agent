.PHONY: setup test demo clean benchmark clean-cache package-pro clean-build

# Detect version from pyproject.toml
VERSION := $(shell python -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d['project']['version'])")

# Detect OS for release naming
ifeq ($(OS),Windows_NT)
    DETECTED_OS := windows
    PLATFORM := win-amd64
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Linux)
        DETECTED_OS := linux
        PLATFORM := linux-x86_64
    endif
    ifeq ($(UNAME_S),Darwin)
        DETECTED_OS := macos
        PLATFORM := macos-universal2
    endif
endif

# Install dependencies
setup:
	@echo "Installing dependencies..."
	pip install -q jsonschema pytest pytest-timeout
	@echo "✓ Dependencies installed"

# Run all tests
test:
	@echo "Running tests..."
	python -m pytest tests/ -v

# Run demo pipeline on sample_project
demo:
	@echo "Running ACHA demo on sample_project..."
	python cli.py run --target ./sample_project

# Run performance benchmark
benchmark:
	@echo "Running performance benchmark..."
	python -m pytest tests/test_performance.py::test_benchmark_100_files -v -s

# Clean AST cache
clean-cache:
	@echo "Cleaning AST cache..."
	rm -rf .acha_cache/
	@echo "✓ Cache cleaned"

# Clean generated files and directories
clean:
	@echo "Cleaning generated files..."
	rm -rf workdir/ .checkpoints/ dist/ reports/ .acha_cache/
	rm -f *.pyc
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned"

# Clean build artifacts
clean-build:
	@echo "Cleaning build artifacts..."
	rm -rf build/ dist/ *.spec
	rm -rf dist/release/
	@echo "✓ Build artifacts cleaned"

# Package ACHA Pro as single-file executable (requires PyInstaller + PyNaCl)
package-pro:
	@echo "============================================="
	@echo "  ACHA Pro v$(VERSION) - Packaging"
	@echo "  Platform: $(DETECTED_OS) ($(PLATFORM))"
	@echo "============================================="
	@echo ""
	@echo "[1/5] Installing build dependencies..."
	@pip install -q pyinstaller PyNaCl
	@echo "✓ Build dependencies installed"
	@echo ""
	@echo "[2/5] Running tests..."
	@python -m pytest tests/ -q --tb=line
	@echo "✓ Tests passed"
	@echo ""
	@echo "[3/5] Building single-file executable with PyInstaller..."
	@pyinstaller --clean --onefile acha.pro.spec
	@echo "✓ Executable built"
	@echo ""
	@echo "[4/5] Creating release package..."
	@mkdir -p dist/release
	@if [ "$(DETECTED_OS)" = "windows" ]; then \
		cd dist && zip -q ../dist/release/ACHA-Pro-$(VERSION)-$(DETECTED_OS).zip acha.exe; \
	else \
		cd dist && tar -czf ../dist/release/ACHA-Pro-$(VERSION)-$(DETECTED_OS).tar.gz acha; \
	fi
	@echo "✓ Release package created"
	@echo ""
	@echo "[5/5] Generating checksums..."
	@cd dist/release && sha256sum ACHA-Pro-$(VERSION)-$(DETECTED_OS).* > SHA256SUMS-$(DETECTED_OS).txt
	@echo "✓ Checksums generated"
	@echo ""
	@echo "============================================="
	@echo "  ✅ ACHA Pro v$(VERSION) packaged successfully!"
	@echo ""
	@echo "  📦 Release artifacts:"
	@ls -lh dist/release/
	@echo "============================================="
