#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
python_bin="${DOCS_PYTHON:-python3}"
if [[ -z "${DOCS_PYTHON:-}" && -x "$root/.venv-docs/bin/python" ]]; then
  python_bin="$root/.venv-docs/bin/python"
fi
exec "$python_bin" "$root/scripts/build_docs_pdf.py" "$@"
