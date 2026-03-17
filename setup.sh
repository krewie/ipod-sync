#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel

pip install "pygpod[all] @ git+https://github.com/Bionded/pygpod.git"

pip freeze > requirements.txt

echo "Done."
echo "Activate with: source $VENV_DIR/bin/activate"
