@echo off
REM WebPilot Agent — Quick Setup (Windows)
REM Run this once after downloading the project folder.
REM
REM Usage:
REM   cd webpilot-agent
REM   setup.bat

echo ==============================
echo   WebPilot Agent — Setup
echo ==============================
echo.

REM 1. Create virtual environment
if not exist ".venv" (
    echo [1/5] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/5] Virtual environment already exists.
)

REM 2. Activate
echo [2/5] Activating virtual environment...
call .venv\Scripts\activate.bat

REM 3. Install dependencies
echo [3/5] Installing dependencies...
pip install -e ".[dev]" --quiet

REM 4. Install Playwright browser
echo [4/5] Installing Playwright Chromium browser...
playwright install chromium

REM 5. Run tests
echo [5/5] Running tests to verify everything works...
echo.
python -m pytest tests/ -v --tb=short

echo.
echo ==============================
echo   Setup Complete!
echo ==============================
echo.
echo Next steps:
echo.
echo   1. Copy .env.example to .env and add your Anthropic API key:
echo      copy .env.example .env
echo      REM Edit .env: set ANTHROPIC_API_KEY from https://console.anthropic.com/settings/keys
echo      REM Generate VAULT_ENCRYPTION_KEY with:
echo      REM   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
echo.
echo   2. Initialize git:
echo      git init
echo      git add .
echo      git commit -m "feat: Sprint 1+2 complete — 105 tests"
echo.
echo   3. Launch Claude Code to continue building:
echo      claude
echo      Then type: Continue building WebPilot Agent from Sprint 3. Read CLAUDE.md for full context.
echo.
