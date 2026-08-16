//! Negamax principal-variation search for Jungle.

pub mod ordering;
pub mod score;
pub mod search;
pub mod see;
pub mod tt;

pub use score::{mate_distance, mate_in, mated_in, is_mate_score, INF, MATE, MAX_PLY};
pub use search::{Limits, SearchResult, Searcher};
pub use see::see;
pub use tt::TranspositionTable;
