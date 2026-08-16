//! Python bindings for the Jungle engine.
//!
//! The boundary is deliberately narrow and speaks in plain integers rather than
//! in wrapped types. Move generation hands back `(fc, fr, tc, tr, captured)`
//! tuples in the Python engine's signed piece-id convention, so the Python side
//! can build its own `Move` namedtuple directly — whose *value equality* is
//! load-bearing in `controller.py`, where an AI result is validated with
//! `move not in gs.legal_moves()`.
//!
//! The search releases the GIL. That matters twice: the Pygame UI stays
//! responsive while the AI thinks, which is the whole point of the controller's
//! thread, and it is what will let the search use more than one core later.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use jungle_core::position::Position as CorePosition;
use jungle_core::types::{col_of, row_of, sq, Color, Move, Piece, NSQ};

/// Colour codes on the wire, matching `engine.pieces.Color`.
const BLUE: u8 = 0;
const BLACK: u8 = 1;

fn to_color(v: u8) -> PyResult<Color> {
    match v {
        BLUE => Ok(Color::Blue),
        BLACK => Ok(Color::Black),
        _ => Err(PyValueError::new_err(format!("bad colour {v}"))),
    }
}

fn from_color(c: Color) -> u8 {
    match c {
        Color::Blue => BLUE,
        Color::Black => BLACK,
    }
}

/// A move as the Python side wants it: coordinates plus the signed id of the
/// captured piece (0 when nothing is taken).
type PyMove = (usize, usize, usize, usize, i8);

fn encode_move(pos: &CorePosition, m: Move) -> PyMove {
    (
        col_of(m.from()),
        row_of(m.from()),
        col_of(m.to()),
        row_of(m.to()),
        pos.piece_at(m.to()).map_or(0, |p| p.to_signed()),
    )
}

fn check_square(col: usize, row: usize) -> PyResult<u8> {
    if col >= jungle_core::types::COLS || row >= jungle_core::types::ROWS {
        return Err(PyValueError::new_err(format!(
            "({col}, {row}) is off the board"
        )));
    }
    Ok(sq(col, row))
}

// `skip_from_py_object`: Position is only ever passed *into* Rust by
// reference, so the derived FromPyObject (which clones) is dead weight and
// deprecated in this pyo3 version.
#[pyclass(module = "jungle_native", skip_from_py_object)]
#[derive(Clone)]
pub struct Position {
    inner: CorePosition,
}

#[pymethods]
impl Position {
    /// The starting position, Blue to move.
    #[new]
    fn new() -> Position {
        Position {
            inner: CorePosition::startpos(),
        }
    }

    #[staticmethod]
    fn empty() -> Position {
        Position {
            inner: CorePosition::empty(),
        }
    }

    #[staticmethod]
    #[pyo3(signature = (board, side_to_move=BLUE, halfmove=0))]
    fn from_board(board: &str, side_to_move: u8, halfmove: u16) -> PyResult<Position> {
        let mut inner = CorePosition::from_board_string(board).map_err(PyValueError::new_err)?;
        inner.set_side_to_move(to_color(side_to_move)?);
        inner.set_halfmove_clock(halfmove);
        Ok(Position { inner })
    }

    fn reset(&mut self) {
        self.inner = CorePosition::startpos();
    }

    /// Put a piece on an empty square, by signed piece id.
    fn place(&mut self, col: usize, row: usize, pid: i8) -> PyResult<()> {
        let s = check_square(col, row)?;
        if pid == 0 || pid.unsigned_abs() > 8 {
            return Err(PyValueError::new_err(format!("bad piece id {pid}")));
        }
        if self.inner.piece_at(s).is_some() {
            return Err(PyValueError::new_err(format!(
                "({col}, {row}) is already occupied"
            )));
        }
        let piece = Piece::from_signed(pid);
        if self.inner.square_of(piece).is_some() {
            return Err(PyValueError::new_err(format!(
                "piece {pid} is already on the board"
            )));
        }
        self.inner.place(s, piece);
        Ok(())
    }

    /// The signed piece id on a square; 0 when empty.
    fn get(&self, col: usize, row: usize) -> PyResult<i8> {
        let s = check_square(col, row)?;
        Ok(self.inner.piece_at(s).map_or(0, |p| p.to_signed()))
    }

    #[getter]
    fn side_to_move(&self) -> u8 {
        from_color(self.inner.side_to_move())
    }

    #[setter]
    fn set_side_to_move(&mut self, c: u8) -> PyResult<()> {
        self.inner.set_side_to_move(to_color(c)?);
        Ok(())
    }

    #[getter]
    fn halfmove_clock(&self) -> u16 {
        self.inner.halfmove_clock()
    }

    #[setter]
    fn set_halfmove_clock(&mut self, v: u16) {
        self.inner.set_halfmove_clock(v);
    }

    fn legal_moves(&self) -> Vec<PyMove> {
        jungle_core::generate(&self.inner)
            .as_slice()
            .iter()
            .map(|&m| encode_move(&self.inner, m))
            .collect()
    }

    fn make(&mut self, fc: usize, fr: usize, tc: usize, tr: usize) -> PyResult<()> {
        let from = check_square(fc, fr)?;
        let to = check_square(tc, tr)?;
        let mv = Move::new(from, to);
        // Validated rather than trusted: an unchecked make would corrupt the
        // mailbox, the piece list and the hash together, and the corruption would
        // only surface much later as a wrong move.
        if !jungle_core::generate(&self.inner).as_slice().contains(&mv) {
            return Err(PyValueError::new_err(format!(
                "({fc},{fr}) -> ({tc},{tr}) is not legal here"
            )));
        }
        self.inner.make(mv);
        Ok(())
    }

    fn unmake(&mut self) -> PyResult<()> {
        if self.inner.ply() == 0 {
            return Err(PyRuntimeError::new_err("nothing to undo"));
        }
        self.inner.unmake();
        Ok(())
    }

    #[getter]
    fn ply(&self) -> usize {
        self.inner.ply()
    }

    #[getter]
    fn key(&self) -> u64 {
        self.inner.key()
    }

    fn alive_count(&self, color: u8) -> PyResult<u32> {
        Ok(self.inner.alive_count(to_color(color)?))
    }

    /// The decided winner, or None. Positional: den entry or capture-all.
    fn result(&self) -> Option<u8> {
        self.inner.result().map(from_color)
    }

    /// The winner including stalemate (a loss for the side to move) and the
    /// 50-move draw, matching `GameState.get_winner`.
    fn winner(&self) -> Option<u8> {
        self.inner.winner().map(from_color)
    }

    fn is_terminal(&self) -> bool {
        self.inner.is_terminal()
    }

    fn is_repetition(&self) -> bool {
        self.inner.is_repetition()
    }

    fn is_fifty_move_draw(&self) -> bool {
        self.inner.is_fifty_move_draw()
    }

    fn board_string(&self) -> String {
        self.inner.to_board_string()
    }

    fn copy(&self) -> Position {
        self.clone()
    }

    /// Assert the mailbox, piece list, occupancy and incremental hash all agree.
    fn assert_consistent(&self) {
        self.inner.assert_consistent();
    }

    fn __repr__(&self) -> String {
        format!(
            "<Position {} {}>",
            self.inner.to_board_string(),
            if self.inner.side_to_move() == Color::Blue {
                "B"
            } else {
                "K"
            }
        )
    }
}

/// What a search found.
#[pyclass(module = "jungle_native", get_all)]
pub struct SearchInfo {
    /// `(fc, fr, tc, tr, captured)` or None when there is no legal move.
    pub best_move: Option<PyMove>,
    pub score: i32,
    /// Moves to mate, signed; None for an ordinary score.
    pub mate: Option<i32>,
    pub depth: i32,
    pub seldepth: usize,
    pub nodes: u64,
    pub time_ms: u64,
}

/// The search engine.
///
/// The searcher sits behind a `Mutex` so that every method here can take `&self`
/// rather than `&mut self`. That is not a style choice: pyo3 tracks borrows at
/// runtime, and a `&mut self` search would hold an exclusive borrow for its whole
/// duration, so `stop()` from the UI thread would fail with "Already mutably
/// borrowed" instead of stopping anything. Escape, undo and new-game all go
/// through that path, so the abort would have been silently dead.
#[pyclass(module = "jungle_native")]
pub struct Engine {
    searcher: Mutex<jungle_search::Searcher>,
    stop: Arc<AtomicBool>,
}

#[pymethods]
impl Engine {
    #[new]
    #[pyo3(signature = (tt_megabytes=64))]
    fn new(tt_megabytes: usize) -> Engine {
        let searcher = jungle_search::Searcher::new(tt_megabytes);
        let stop = searcher.stop_handle();
        Engine {
            searcher: Mutex::new(searcher),
            stop,
        }
    }

    /// Forget the transposition table and history heuristics. For a new game
    /// only: within one game they are worth carrying across moves.
    fn reset(&self) {
        self.searcher.lock().expect("engine mutex poisoned").reset();
    }

    /// Ask a running search to stop. Safe to call from another thread, which is
    /// exactly what the controller does on Escape, undo and new game.
    fn stop(&self) {
        self.stop.store(true, Ordering::Relaxed);
    }

    /// Search `position` and return the best move.
    ///
    /// The position is cloned and searched on this thread with the GIL released,
    /// so the caller's copy is untouched and the UI keeps running.
    #[pyo3(signature = (position, movetime_ms=None, nodes=None, depth=None))]
    fn think(
        &self,
        py: Python<'_>,
        position: &Position,
        movetime_ms: Option<u64>,
        nodes: Option<u64>,
        depth: Option<i32>,
    ) -> SearchInfo {
        let limits = jungle_search::Limits {
            depth,
            nodes,
            movetime: movetime_ms.map(std::time::Duration::from_millis),
        };
        let mut pos = position.inner.clone();

        let result = py.detach(|| {
            let mut searcher = self.searcher.lock().expect("engine mutex poisoned");
            searcher.think(&mut pos, &limits)
        });

        SearchInfo {
            best_move: result.best_move.map(|m| encode_move(&pos, m)),
            score: result.score,
            mate: jungle_search::mate_distance(result.score),
            depth: result.depth,
            seldepth: result.seldepth,
            nodes: result.nodes,
            time_ms: result.elapsed.as_millis() as u64,
        }
    }

    #[getter]
    fn hashfull(&self) -> usize {
        self.searcher.lock().expect("engine mutex poisoned").hashfull()
    }
}

/// Static evaluation from `color`'s point of view.
#[pyfunction]
fn evaluate(position: &Position, color: u8) -> PyResult<i32> {
    Ok(jungle_eval::evaluate(&position.inner, to_color(color)?))
}

/// Static exchange evaluation for a capture.
#[pyfunction]
fn see(position: &Position, fc: usize, fr: usize, tc: usize, tr: usize) -> PyResult<i32> {
    let from = check_square(fc, fr)?;
    let to = check_square(tc, tr)?;
    Ok(jungle_search::see(&position.inner, Move::new(from, to)))
}

/// Exhaustive leaf count, for verifying move generation.
#[pyfunction]
fn perft(py: Python<'_>, position: &Position, depth: u32) -> u64 {
    let mut pos = position.inner.clone();
    py.detach(|| jungle_core::perft(&mut pos, depth))
}

#[pymodule]
fn jungle_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Position>()?;
    m.add_class::<Engine>()?;
    m.add_class::<SearchInfo>()?;
    m.add_function(wrap_pyfunction!(evaluate, m)?)?;
    m.add_function(wrap_pyfunction!(see, m)?)?;
    m.add_function(wrap_pyfunction!(perft, m)?)?;
    m.add("COLS", jungle_core::types::COLS)?;
    m.add("ROWS", jungle_core::types::ROWS)?;
    m.add("NSQ", NSQ)?;
    m.add("MATE", jungle_search::MATE)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
