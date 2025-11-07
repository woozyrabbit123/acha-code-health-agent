.PHONY: setup test demo clean benchmark clean-cache

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
