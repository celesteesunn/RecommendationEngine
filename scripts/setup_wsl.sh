#!/usr/bin/env bash
# Set up the project's Python environment inside WSL2 Ubuntu.
#
# Usage (from the repository root, inside Ubuntu):
#     sudo apt update && sudo apt install -y openjdk-17-jdk-headless python3-venv   # once
#     bash scripts/setup_wsl.sh
#     source ~/venvs/reco/bin/activate
#
# The environment lives in the Linux home folder, not in the repository: the repository is
# usually on the Windows drive (/mnt/c/...), where loading TensorFlow and Spark is much slower.
# Python 3.11 is installed with uv because Ubuntu's own Python is too new for TensorFlow 2.18.

set -euo pipefail

VENV_DIR="${VENV_DIR:-$HOME/venvs/reco}"
TOOLS_DIR="$HOME/venvs/tools"
PYTHON_VERSION="3.11"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v java >/dev/null; then
    echo "Java is missing. Run: sudo apt install -y openjdk-17-jdk-headless" >&2
    exit 1
fi

if [ ! -x "$TOOLS_DIR/bin/uv" ]; then
    echo "[1/3] Installing uv into $TOOLS_DIR"
    python3 -m venv "$TOOLS_DIR"
    "$TOOLS_DIR/bin/pip" install --quiet uv
fi
UV="$TOOLS_DIR/bin/uv"

echo "[2/3] Creating Python $PYTHON_VERSION environment at $VENV_DIR"
"$UV" python install "$PYTHON_VERSION"
if [ ! -x "$VENV_DIR/bin/python" ]; then
    "$UV" venv --python "$PYTHON_VERSION" "$VENV_DIR"
fi

echo "[3/3] Installing requirements-dev.txt"
VIRTUAL_ENV="$VENV_DIR" "$UV" pip install -r "$REPO_DIR/requirements-dev.txt"

if [ ! -f "$REPO_DIR/.env" ]; then
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
fi

JAVA_HOME_DIR="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
echo
echo "Done. Activate the environment with:"
echo "    source $VENV_DIR/bin/activate"
echo "Spark finds Java on the PATH; if it does not, add this to ~/.bashrc:"
echo "    export JAVA_HOME=$JAVA_HOME_DIR"
