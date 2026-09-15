#!/usr/bin/env bash
# Download the OPA static binary that ACS uses to evaluate Rego policies, then
# print the ACS_OPA_PATH you should export.
#
# ACS fails closed (Rego evaluation errors) without OPA on PATH. The bundled
# dispatcher honors $ACS_OPA_PATH when set; a bad explicit path fails closed
# rather than falling back to another `opa` on PATH.
set -euo pipefail

DEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/bin"
mkdir -p "$DEST_DIR"
DEST="$DEST_DIR/opa"

os="$(uname -s)"
arch="$(uname -m)"

case "$os" in
  Linux)  os_tag="linux" ;;
  Darwin) os_tag="darwin" ;;
  *) echo "Unsupported OS: $os (download OPA manually from https://www.openpolicyagent.org/docs/latest/#running-opa)"; exit 1 ;;
esac

case "$arch" in
  x86_64|amd64) arch_tag="amd64" ;;
  arm64|aarch64) arch_tag="arm64" ;;
  *) echo "Unsupported arch: $arch"; exit 1 ;;
esac

# Static builds avoid glibc surprises in cloud/CI images.
asset="opa_${os_tag}_${arch_tag}_static"
url="https://openpolicyagent.org/downloads/latest/${asset}"

echo "Downloading ${asset} ..."
curl -fsSL -o "$DEST" "$url"
chmod +x "$DEST"

echo "OPA installed at: $DEST"
"$DEST" version
echo
echo "Now export this before running the cookbook:"
echo "  export ACS_OPA_PATH=\"$DEST\""
