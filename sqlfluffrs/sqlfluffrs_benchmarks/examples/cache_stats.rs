//! Print per-variant frame-cache gets/hits over both TPC suites.
use sqlfluffrs_benchmarks::{tpc_fixture, TPCDS_N, TPCH_N};
use sqlfluffrs_dialects::dialect::ansi::matcher::ANSI_LEXERS;
use sqlfluffrs_dialects::Dialect;
use sqlfluffrs_lexer::{LexInput, Lexer};
use sqlfluffrs_parser::parser::Parser;

fn main() {
    let mut totals: std::collections::BTreeMap<String, usize> = Default::default();
    for (sub, count) in [("tpc-h", TPCH_N), ("tpc-ds", TPCDS_N)] {
        for n in 1..=count {
            let sql = std::fs::read_to_string(tpc_fixture(sub, n)).expect("fixture");
            let (tokens, _) = Lexer::new(None, ANSI_LEXERS.to_vec()).lex(LexInput::String(sql), false);
            let mut p = Parser::new(&tokens, Dialect::Ansi, hashbrown::HashMap::new());
            p.call_rule_as_root().expect("parse failed");
            for (k, v) in p.diagnostics() {
                *totals.entry(k).or_default() += v;
            }
        }
    }
    for (k, v) in &totals {
        if k.starts_with("cache_") {
            println!("{k:24} {v:>10}");
        }
    }
}
