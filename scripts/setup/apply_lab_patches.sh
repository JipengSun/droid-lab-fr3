#!/usr/bin/env bash
# Apply lab patches inside the fairo submodule (run from repo root).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FAiro_INIT="$ROOT/droid/fairo/polymetis/polymetis/python/polymetis/__init__.py"
PATCH="$ROOT/scripts/setup/patches/polymetis_lazy_import.patch"

if [[ ! -f "$PATCH" ]]; then
  echo "Missing patch: $PATCH" >&2
  exit 1
fi

cd "$ROOT/droid/fairo"
git apply --check "$PATCH" 2>/dev/null && git apply "$PATCH" && echo "Applied polymetis lazy-import patch."
echo "Done."
