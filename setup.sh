#!/bin/bash
# MANI Pattern Engine — setup script
set -e

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .

echo "Running tests..."
python -m pytest --tb=short -q

echo ""
echo "Setup complete. To activate:"
echo "  source venv/bin/activate"
echo ""
echo "To run the web app:"
echo "  python -m uvicorn web.app:app --host 0.0.0.0 --port 8000"
echo ""
echo "To run the CLI:"
echo "  python -m agentic_pattern_engine.cli --chest 91.5 --waist 73.5 --hip 98.0 --shoulder-width 40.0 --torso-length 42.5 --verbose"
