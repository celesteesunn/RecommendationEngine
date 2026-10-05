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

# Spark (through Hadoop) sets file permissions when it writes. On the Windows drive that only
# works when the drive is mounted with the "metadata" option and owned by this user.
if ! (cd "$REPO_DIR" && touch .perm_check && chmod 644 .perm_check) 2>/dev/null; then
    rm -f "$REPO_DIR/.perm_check"
    cat >&2 <<'EOF'
Cannot change file permissions in the repository folder, so Spark cannot write Parquet here.
Enable Linux permissions on the Windows drive, then restart WSL:
    printf '\n[automount]\noptions = "metadata,uid=1000,gid=1000,umask=022"\n' | sudo tee -a /etc/wsl.conf
    wsl --shutdown        (in Windows PowerShell; then reopen Ubuntu)
EOF
    exit 1
fi
rm -f "$REPO_DIR/.perm_check"

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

# With an NVIDIA card, add the CUDA libraries TensorFlow needs to train on the GPU (~3 GB).
if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
    TF_VERSION="$(grep -E '^tensorflow==' "$REPO_DIR/requirements.txt" | cut -d= -f3)"
    echo "      NVIDIA GPU found: installing CUDA libraries for TensorFlow $TF_VERSION"
    VIRTUAL_ENV="$VENV_DIR" "$UV" pip install "tensorflow[and-cuda]==$TF_VERSION"
fi

if [ ! -f "$REPO_DIR/.env" ]; then
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
fi

JAVA_HOME_DIR="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
echo
echo "Done. Activate the environment with:"
echo "    source $VENV_DIR/bin/activate"
echo "Spark finds Java on the PATH; if it does not, add this to ~/.bashrc:"
echo "    export JAVA_HOME=$JAVA_HOME_DIR"
