#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/syndra/masgent.git"
DIR="masgent"

echo "=========================================="
echo " Masgent - One-click Setup"
echo "=========================================="
echo ""

# 1. Clone
echo "[1/5] Cloning repository..."
if [ -d "$DIR" ]; then
    echo "  Directory $DIR exists, pulling latest..."
    cd "$DIR" && git pull && cd ..
else
    git clone --depth 1 "$REPO" "$DIR"
fi
cd "$DIR"

# 2. Python version check
echo "[2/5] Checking Python version..."
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  Python $PY_VER detected"
if [ "$(echo "$PY_VER < 3.11" | bc)" = "1" ] || [ "$(echo "$PY_VER >= 3.15" | bc)" = "1" ]; then
    echo "  ERROR: Python >= 3.11, < 3.15 required"
    exit 1
fi

# 3. Virtual environment
echo "[3/5] Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# 4. Install
echo "[4/5] Installing Masgent and dependencies..."
pip install -e .

# 5. Config
echo "[5/5] Setting up configuration..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "  Created .env from .env.example"
        echo "  >>> Edit .env with your API keys before running <<<"
    fi
fi

echo ""
echo "=========================================="
echo " Masgent installed successfully!"
echo "=========================================="
echo ""
echo "  cd $DIR"
echo "  source .venv/bin/activate"
echo "  masgent"
echo ""
