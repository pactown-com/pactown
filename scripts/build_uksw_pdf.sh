#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$root/scripts/build_docs_pdf.sh" --config "$root/docs/pdf-uksw-config.json" "$@"
