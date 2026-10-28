#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
DEST_DIR="${HOME}/.local/bin"
DEST="${DEST_DIR}/lsplain"

mkdir -p "$DEST_DIR"
cp "$SCRIPT_DIR/lsplain" "$DEST"
chmod 755 "$DEST"
printf 'Installed lsplain to %s\n' "$DEST"
case ":${PATH}:" in
  *":${DEST_DIR}:"*) ;;
  *) printf 'Add this to ~/.zshrc if the command is not found:\n  export PATH="$HOME/.local/bin:$PATH"\n' ;;
esac
printf 'Try: lsplain --help\n'
