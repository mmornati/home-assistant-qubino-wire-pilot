.PHONY: help clean lint format check zip install-dev validate

# Default target
help:
	@echo "Qubino Wire Pilot - Development Tasks"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  help        Show this help message"
	@echo "  clean       Remove build artifacts and cache files"
	@echo "  lint        Run pylint on the custom component"
	@echo "  format      Format code with black"
	@echo "  check       Check code formatting with black (no changes)"
	@echo "  validate    Validate JSON files (translations, manifest)"
	@echo "  zip         Create production-ready zip for Home Assistant"
	@echo "  install-dev Install development dependencies"
	@echo ""

# Component paths
COMPONENT_DIR := custom_components/qubino_wire_pilot
ZIP_NAME := qubino_wire_pilot.zip
DIST_DIR := dist

# Development dependencies
install-dev:
	@echo "Installing development dependencies..."
	pip install black pylint homeassistant voluptuous

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(DIST_DIR)
	rm -f $(COMPONENT_DIR)/$(ZIP_NAME)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "Clean complete!"

# Lint with pylint
lint:
	@echo "Running pylint..."
	pylint $(COMPONENT_DIR) --disable=R,C || true

# Format code with black
format:
	@echo "Formatting code with black..."
	black $(COMPONENT_DIR)

# Check formatting without making changes
check:
	@echo "Checking code formatting..."
	black --check --diff $(COMPONENT_DIR)

# Validate JSON files
validate:
	@echo "Validating JSON files..."
	@python3 -c "import json; \
		json.load(open('$(COMPONENT_DIR)/manifest.json')); \
		json.load(open('$(COMPONENT_DIR)/translations/en.json')); \
		json.load(open('$(COMPONENT_DIR)/translations/fr.json')); \
		print('✅ All JSON files are valid')"

# Create production-ready zip for Home Assistant
# This zip can be extracted directly to custom_components/
zip: clean validate
	@echo "Creating production-ready zip..."
	@mkdir -p $(DIST_DIR)
	@cd custom_components && zip -r ../$(DIST_DIR)/$(ZIP_NAME) qubino_wire_pilot \
		-x "*.git*" \
		-x "*__pycache__*" \
		-x "*.pyc" \
		-x "*.pyo" \
		-x "*.DS_Store" \
		-x "*.pytest_cache*" \
		-x "*.mypy_cache*"
	@echo ""
	@echo "✅ Created $(DIST_DIR)/$(ZIP_NAME)"
	@echo ""
	@echo "To install on Home Assistant:"
	@echo "  1. Copy $(DIST_DIR)/$(ZIP_NAME) to your Home Assistant server"
	@echo "  2. Extract to /config/custom_components/"
	@echo "     unzip $(ZIP_NAME) -d /config/custom_components/"
	@echo "  3. Restart Home Assistant"
	@echo ""
	@zipinfo $(DIST_DIR)/$(ZIP_NAME) | head -20
