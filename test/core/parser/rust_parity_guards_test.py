"""Fast, deterministic parity guards distilled from the differential audits.

These are the permanent CI companions to the exploration tooling in
``utils/parity_audit`` - each one pins a bug class that was actually found
(and fixed) by that tooling, driven through SQL and a selected dialect.
"""

import pytest

try:
    from sqlfluff.core.parser.rust_parser import _HAS_RUST_PARSER, RustParser
except ImportError:  # pragma: no cover
    _HAS_RUST_PARSER = False


# ---------------------------------------------------------------------------
# RsMatchResult structural invariants.
#
# A malformed match result (out-of-bounds slice, overlapping/unsorted
# children, zero-length node carrying a class or children) is a rust-core bug
# by definition: MatchResult.apply raises its internal "Segment skip ahead"
# ValueError on overlap instead of a parse error, and silent shapes would
# corrupt trees. Corpus mutation fuzzing (~43k cases) found overlap emissions
# from exasol script-content and materialize bracketed-recovery grammars -
# minimized below. The valid battery must stay violation-free.
# ---------------------------------------------------------------------------


def _match_result_violations(rs_match, n_tokens, path="root"):
    start, stop = rs_match.matched_slice
    if start > stop:
        yield (path, f"inverted slice ({start},{stop})")
    if stop > n_tokens:
        yield (path, f"slice out of bounds ({start},{stop}) n={n_tokens}")
    if start == stop:
        if rs_match.matched_class:
            yield (path, f"zero-length with class {rs_match.matched_class}")
        if rs_match.child_matches:
            yield (path, "zero-length with children")
    prev_end = start
    prev_start = None
    for i, child in enumerate(rs_match.child_matches):
        cs, ce = child.matched_slice
        if cs < start or ce > stop:
            yield (
                f"{path}[{i}]",
                f"child ({cs},{ce}) outside parent ({start},{stop})",
            )
        if prev_start is not None and cs < prev_start:
            yield (f"{path}[{i}]", f"children unsorted ({cs} after {prev_start})")
        if cs < prev_end:
            yield (
                f"{path}[{i}]",
                f"overlap: child starts {cs} before prev end {prev_end}",
            )
        prev_end = max(prev_end, ce)
        prev_start = cs
        yield from _match_result_violations(
            child, n_tokens, f"{path}>{child.matched_class or '?'}[{i}]"
        )
    for idx, _seg_type, _impl in rs_match.insert_segments or []:
        if idx < start or idx > stop:
            yield (path, f"insert @{idx} outside ({start},{stop})")


def _raw_match_violations(sql, dialect):
    from sqlfluff.core import FluffConfig
    from sqlfluff.core.parser import Lexer

    config = FluffConfig(overrides={"dialect": dialect})
    segments, _ = Lexer(config=config).lex(sql)
    parser = RustParser(config=config)
    start = 0
    for start in range(len(segments)):
        if segments[start].is_code:
            break
    end = len(segments)
    for end in range(len(segments), start - 1, -1):
        if segments[end - 1].is_code:
            break
    if start == end:
        return []
    tokens = parser._extract_tokens_from_segments(segments[start:end])
    try:
        rs_match = parser._rs_parser.parse_match_result_from_tokens(tokens)
    except BaseException:
        # Raising a parse error is fine; we only audit *returned* results.
        return []
    return list(_match_result_violations(rs_match, len(tokens)))


@pytest.mark.skipif(not _HAS_RUST_PARSER, reason="Rust parser not available")
@pytest.mark.parametrize(
    "dialect,sql",
    [
        ("ansi", "SELECT a, b FROM t WHERE x = 1"),
        ("ansi", "SELECT CASE"),
        ("ansi", "SELECT 1) FROM t"),
        ("ansi", "SELECT a FROM t WHERE a IN (1, )"),
        ("ansi", "SELECT 1; !!!! ; SELECT 2"),
        ("snowflake", "SELECT 1 -} FROM t"),
        ("tsql", "GO GO GO"),
        ("postgres", "SELECT straße(1)"),
    ],
    ids=lambda v: repr(v)[:40],
)
def test__rust_parser__match_results_satisfy_invariants(dialect, sql):
    """Returned RsMatchResults must be structurally well-formed."""
    assert _raw_match_violations(sql, dialect) == []


@pytest.mark.skipif(not _HAS_RUST_PARSER, reason="Rust parser not available")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known rust-core bug: bracketed/script-content error recovery emits "
        "OVERLAPPING child matches (the same token claimed as both the "
        "opening and closing bracket child) for these minimized inputs, "
        "found by invariant-fuzzing ~43k corpus mutations. Downstream this "
        "surfaces as MatchResult.apply's 'Segment skip ahead error' "
        "ValueError instead of a parse error."
    ),
)
@pytest.mark.parametrize(
    "dialect,sql",
    [
        (
            "materialize",
            "(\n ) ( );\nCREATE SOURCE s IN CLUSTER c FROM WEBHOOK\n "
            "BODY FORMAT JSON\n (\n",
        ),
        ("exasol", "CREATE SCRIPT s AS\n(\n"),
    ],
    ids=["materialize-webhook", "exasol-script"],
)
def test__rust_parser__known_overlap_emissions(dialect, sql):
    """Minimized inputs where the rust core still emits overlapping matches."""
    assert _raw_match_violations(sql, dialect) == []


# ---------------------------------------------------------------------------
# Dangling grammar references.
#
# A Ref to a name the dialect can't resolve raises RuntimeError in Python the
# moment the branch is attempted, while the generated Rust tables silently
# treat it as Empty - identical SQL then crashes one engine and quietly fails
# a branch on the other. An audit found ~600 such refs across 27 dialects
# (unregistered keywords plus outright typos); all were fixed. This guard
# keeps every dialect's expanded grammar fully resolvable.
# ---------------------------------------------------------------------------


def _iter_grammar(g, seen):
    if id(g) in seen:
        return
    seen.add(id(g))
    yield g
    for attr in ("_elements", "terminators"):
        for child in getattr(g, attr, ()) or ():
            yield from _iter_grammar(child, seen)
    for attr in ("exclude", "delimiter"):
        child = getattr(g, attr, None)
        if child is not None:
            yield from _iter_grammar(child, seen)


def _dangling_refs(dialect_label):
    from sqlfluff.core.dialects import dialect_selector
    from sqlfluff.core.parser import Ref
    from sqlfluff.core.parser.segments import BaseSegment

    dialect = dialect_selector(dialect_label)
    lib = dialect._library
    seen = set()
    missing = set()
    for entry in lib.values():
        grammar = entry
        if isinstance(grammar, type) and issubclass(grammar, BaseSegment):
            grammar = getattr(grammar, "match_grammar", None)
            if grammar is None:
                continue
        for node in _iter_grammar(grammar, seen):
            if node.__class__ is Ref and node._ref not in lib:
                missing.add(node._ref)
    return missing


def _all_dialect_labels():
    from sqlfluff.core.dialects import dialect_readout

    return [r.label for r in dialect_readout()]


@pytest.mark.parametrize("dialect_label", _all_dialect_labels())
def test__dialect__no_dangling_grammar_refs(dialect_label):
    """Every Ref in every dialect's expanded grammar must resolve."""
    assert _dangling_refs(dialect_label) == set()
