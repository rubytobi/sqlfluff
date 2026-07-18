#!/usr/bin/env bash
# Two-phase PGO build of the sqlfluffrs extension wheel.
#
# Usage: ./build_pgo.sh [workload.py]
#
# Phase 1 builds an instrumented wheel, installs it, and runs the workload
# (default: a TPC-H/TPC-DS parse pass via test/.cache/tpc fixtures - see
# PERF_LOG.md "Wall-time halving pass" for fixture provenance). Phase 2
# rebuilds with the merged profile. The committed release profile is
# unchanged; PGO is opt-in via this script.
#
# Requires: maturin, the rustup `llvm-tools` component for the pinned
# toolchain (rustup component add llvm-tools), and a Python env where the
# local sqlfluff checkout is importable.
set -euo pipefail

cd "$(dirname "$0")"
PGO_DIR="${PGO_DIR:-$HOME/pgo-data}"
WORKLOAD="${1:-}"
TOOLCHAIN_BIN="$(rustc --print sysroot)/lib/rustlib/x86_64-unknown-linux-gnu/bin"

rm -rf "$PGO_DIR" && mkdir -p "$PGO_DIR"

echo "== Phase 1: instrumented build =="
RUSTFLAGS="-Cprofile-generate=$PGO_DIR" maturin build --release
WHEEL=$(ls -t target/wheels/sqlfluffrs-*.whl | head -1)
pip install --force-reinstall --no-deps "$WHEEL"

echo "== Running workload =="
if [ -n "$WORKLOAD" ]; then
    python "$WORKLOAD"
else
    python - <<'EOF'
import pathlib
from sqlfluff.core import Linter
from sqlfluff.core.config import FluffConfig
from sqlfluff.core.parser import rust_parser

cache = pathlib.Path(__file__ or ".").parent
root = pathlib.Path.cwd().parent / "test" / ".cache" / "tpc"
suites = []
for sub, n in (("tpc-h", 22), ("tpc-ds", 99)):
    d = root / sub
    if d.is_dir():
        suites.append([(d / f"{i}.sql").read_text() for i in range(1, n + 1)])
assert suites, f"No TPC fixtures under {root}; see PERF_LOG.md to fetch them"
cfg = FluffConfig(overrides={"dialect": "ansi", "use_rust_parser": True},
                  ignore_local_config=True)
linter = Linter(config=cfg)
for native in (False, True):
    rust_parser.set_native_ast(native)
    for qs in suites:
        for q in qs:
            linter.parse_string(q)
rust_parser.set_native_ast(False)
print("PGO workload complete")
EOF
fi

echo "== Merging profiles =="
"$TOOLCHAIN_BIN/llvm-profdata" merge -o "$PGO_DIR/merged.profdata" "$PGO_DIR"/*.profraw

echo "== Phase 2: optimized build =="
RUSTFLAGS="-Cprofile-use=$PGO_DIR/merged.profdata" maturin build --release
echo "PGO wheel: $(ls -t target/wheels/sqlfluffrs-*.whl | head -1)"
