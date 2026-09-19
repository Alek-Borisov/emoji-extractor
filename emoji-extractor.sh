#!/bin/sh
# Emoji Extractor: sh emoji-extractor.sh
# Makes a temporary Python environment, installs what emoji-extractor.py needs, saves every
# emoji at 160 px into a fresh Emojis folder next to this script, then deletes the environment.

cd "$(dirname "$0")" || exit 1

if [ ! -f emoji-extractor.py ]; then
    echo "emoji-extractor.py has to be in the same folder as this script." >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Install Apple's Command Line Tools with: xcode-select --install" >&2
    exit 1
fi

WORK=$(mktemp -d "${TMPDIR:-/tmp}/emoji-extractor.XXXXXX") || exit 1
trap 'rm -rf "$WORK"; echo "Temporary environment removed."' EXIT
trap 'exit 130' INT TERM HUP

# Keep everything the setup writes inside $WORK: no pip cache, no temp files, no bytecode elsewhere.
mkdir "$WORK/tmp" || exit 1
export TMPDIR="$WORK/tmp" PYTHONDONTWRITEBYTECODE=1
venv_pip() { "$WORK/venv/bin/python" -m pip --quiet --no-cache-dir --disable-pip-version-check "$@"; }

echo "Setting up a temporary Python environment..."
python3 -m venv "$WORK/venv" || exit 1
venv_pip install --upgrade pip || exit 1
venv_pip install "pillow>=11.2" "fonttools>=4.57" rich pyfiglet || exit 1

"$WORK/venv/bin/python" emoji-extractor.py "$@"
