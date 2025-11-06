.PHONY: setup test demo clean

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

# Clean generated files and directories
clean:
	@echo "Cleaning generated files..."
	rm -rf workdir/ .checkpoints/ dist/ reports/
	rm -f *.pyc
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned"
