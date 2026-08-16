//! Developer front-end for the Jungle engine.
//!
//! Subcommands:
//!   `protocol`  line-based host, so another process can drive the engine
//!   `bench`     node/depth benchmark
//!   `perft`     move-generation fingerprint and speed
//!
//! The protocol exists so the Python strength harness can play this engine
//! against the Python one without either having to import the other. It is
//! deliberately tiny -- four commands -- because its only job is to let two
//! engines share a board.

use std::io::{self, BufRead, Write};

use jungle_core::position::Position;
use jungle_core::types::{col_of, row_of, Color, Move};
use jungle_core::{generate, perft, perft_divide};
use jungle_search::{Limits, Searcher};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("protocol") => protocol(),
        Some("perft") => {
            let depth = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(6);
            run_perft(depth, args.iter().any(|a| a == "--divide"));
        }
        Some("bench") => {
            let ms = args.get(1).and_then(|s| s.parse().ok()).unwrap_or(2000);
            run_bench(ms);
        }
        _ => {
            eprintln!("usage: jungle <protocol|bench [ms]|perft [depth] [--divide]>");
            std::process::exit(2);
        }
    }
}

fn parse_move(tok: &str) -> Option<Move> {
    let v: Vec<&str> = tok.split(',').collect();
    if v.len() != 4 {
        return None;
    }
    let fc: usize = v[0].parse().ok()?;
    let fr: usize = v[1].parse().ok()?;
    let tc: usize = v[2].parse().ok()?;
    let tr: usize = v[3].parse().ok()?;
    Some(Move::new(
        jungle_core::sq(fc, fr),
        jungle_core::sq(tc, tr),
    ))
}

fn format_move(m: Move) -> String {
    format!(
        "{},{},{},{}",
        col_of(m.from()),
        row_of(m.from()),
        col_of(m.to()),
        row_of(m.to())
    )
}

/// Line protocol.
///
/// ```text
/// newgame                                   forget the table and history
/// position startpos [moves fc,fr,tc,tr ...] replay a game, keeping repetition history
/// position board <63 chars> <B|K> <halfmove>
/// go nodes <n> | go movetime <ms> | go depth <d>
///   -> info depth <d> seldepth <d> score <cp|mate n> nodes <n> time <ms>
///   -> bestmove <fc,fr,tc,tr> | bestmove none
/// quit
/// ```
fn protocol() {
    let stdin = io::stdin();
    let mut out = io::stdout();
    let mut searcher = Searcher::new(128);
    let mut pos = Position::startpos();

    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        let tokens: Vec<&str> = line.split_whitespace().collect();
        let Some(&cmd) = tokens.first() else { continue };

        match cmd {
            "quit" => break,
            "isready" => {
                let _ = writeln!(out, "readyok");
                let _ = out.flush();
            }
            "newgame" => {
                searcher.reset();
                pos = Position::startpos();
            }
            "position" => {
                match tokens.get(1).copied() {
                    Some("startpos") => {
                        pos = Position::startpos();
                        if let Some(i) = tokens.iter().position(|&t| t == "moves") {
                            for tok in &tokens[i + 1..] {
                                match parse_move(tok) {
                                    Some(m) if generate(&pos).as_slice().contains(&m) => pos.make(m),
                                    _ => {
                                        let _ = writeln!(out, "error illegal move {tok}");
                                        let _ = out.flush();
                                        break;
                                    }
                                }
                            }
                        }
                    }
                    Some("board") => {
                        let Some(board) = tokens.get(2) else { continue };
                        match Position::from_board_string(board) {
                            Ok(p) => {
                                pos = p;
                                if tokens.get(3) == Some(&"K") {
                                    pos.set_side_to_move(Color::Black);
                                }
                                if let Some(h) = tokens.get(4).and_then(|s| s.parse().ok()) {
                                    pos.set_halfmove_clock(h);
                                }
                            }
                            Err(e) => {
                                let _ = writeln!(out, "error {e}");
                                let _ = out.flush();
                            }
                        }
                    }
                    _ => {}
                }
            }
            "go" => {
                let limits = match (tokens.get(1).copied(), tokens.get(2)) {
                    (Some("nodes"), Some(n)) => Limits::nodes(n.parse().unwrap_or(10_000)),
                    (Some("movetime"), Some(ms)) => Limits::movetime(ms.parse().unwrap_or(1000)),
                    (Some("depth"), Some(d)) => Limits::depth(d.parse().unwrap_or(6)),
                    _ => Limits::movetime(1000),
                };
                let r = searcher.think(&mut pos, &limits);
                let score = match jungle_search::mate_distance(r.score) {
                    Some(n) => format!("mate {n}"),
                    None => format!("cp {}", r.score),
                };
                let _ = writeln!(
                    out,
                    "info depth {} seldepth {} score {score} nodes {} time {}",
                    r.depth,
                    r.seldepth,
                    r.nodes,
                    r.elapsed.as_millis()
                );
                match r.best_move {
                    Some(m) => {
                        let _ = writeln!(out, "bestmove {}", format_move(m));
                    }
                    None => {
                        let _ = writeln!(out, "bestmove none");
                    }
                }
                let _ = out.flush();
            }
            _ => {}
        }
    }
}

fn run_perft(max_depth: u32, divide: bool) {
    use std::time::Instant;
    println!(
        "{:>5}  {:>16}  {:>8}  {:>14}",
        "depth", "leaves", "time_s", "leaves/s"
    );
    for depth in 1..=max_depth {
        let mut pos = Position::startpos();
        let t0 = Instant::now();
        let leaves = perft(&mut pos, depth);
        let dt = t0.elapsed().as_secs_f64();
        println!(
            "{depth:>5}  {leaves:>16}  {dt:>8.3}  {:>14.0}",
            leaves as f64 / dt.max(1e-9)
        );
    }
    if divide {
        let mut pos = Position::startpos();
        for (m, n) in perft_divide(&mut pos, max_depth) {
            println!("  {m}  {n}");
        }
    }
}

fn run_bench(budget_ms: u64) {
    use std::time::Instant;
    let mut total_nodes = 0u64;
    let mut total_time = 0.0;
    println!(
        "{:<12} {:>5} {:>7} {:>12} {:>12} {:>7}",
        "position", "depth", "seldep", "nodes", "nps", "time_s"
    );
    for (name, board) in [
        (
            "fixed-mid",
            "g.....f.......a.e.d.h.....................H.D.E.A.......F.....G",
        ),
        (
            "midgame-1",
            "g....b..c....fae...dh.....................H.D.E..B....CA..F...G",
        ),
        (
            "midgame-2",
            "g....f.c....bh..ed....a...................HD...EA.FB..C......G.",
        ),
    ] {
        let mut pos = Position::from_board_string(board).expect("bad bench position");
        let mut s = Searcher::new(64);
        let t0 = Instant::now();
        let r = s.think(&mut pos, &Limits::movetime(budget_ms));
        let dt = t0.elapsed().as_secs_f64();
        println!(
            "{name:<12} {:>5} {:>7} {:>12} {:>12.0} {:>7.2}",
            r.depth,
            r.seldepth,
            r.nodes,
            r.nodes as f64 / dt.max(1e-9),
            dt
        );
        total_nodes += r.nodes;
        total_time += dt;
    }
    println!(
        "\ntotal: {total_nodes} nodes in {total_time:.2}s = {:.0} nps",
        total_nodes as f64 / total_time.max(1e-9)
    );
}
