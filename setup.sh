#!/usr/bin/env bash
# WebPilot Agent — Quick Setup
# Run this once after downloading the project folder.
#
# Usage:
#   cd webpilot-agent
#   chmod +x setup.sh
#   ./setup.sh

set -e

echo "=============================="
echo "  WebPilot Agent — Setup"
echo "=============================="
echo ""

# 1. Create virtual environment
if [ ! -d ".venv" ]; then
    echo "[1/5] Creating virtual environment..."
    python3 -m venv .venv
else
    echo "[1/5] Virtual environment already exists."
fi

# 2. Activate
echo "[2/5] Activating virtual environment..."
source .venv/bin/activate

# 3. Install dependencies
echo "[3/5] Installing dependencies..."
pip install -e ".[dev]" --quiet

# 4. Install Playwright browser
echo "[4/5] Installing Playwright Chromium browser..."
playwright install chromium

# 5. Run tests to verify
echo "[5/5] Running tests to verify everything works..."
echo ""
python -m pytest tests/ -v --tb=short

echo ""
echo "=============================="
echo "  Setup Complete!"
echo "=============================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Copy .env.example to .env and add your Anthropic API key:"
echo "     cp .env.example .env"
echo "     # Edit .env → set ANTHROPIC_API_KEY from https://console.anthropic.com/settings/keys"
echo "     # Generate VAULT_ENCRYPTION_KEY with:"
echo "     #   python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
echo ""
echo "  2. Initialize git:"
echo "     git init && git add . && git commit -m 'feat: Sprint 1+2 complete — 105 tests'"
echo ""
echo "  3. Launch Claude Code to continue building:"
echo "     claude"
echo "     > Continue building WebPilot Agent from Sprint 3. Read CLAUDE.md for full context."
echo ""
