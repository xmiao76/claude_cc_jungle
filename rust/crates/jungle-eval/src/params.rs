//! Evaluation weights and tables, ported verbatim from `config.py`.
//!
//! These are the *shipped* Python values, warts included, so the port can be
//! checked against the engine it replaces score for score. Tuning them is a later
//! phase and a separate, measured change; changing them here would make the
//! differential test meaningless.

use jungle_core::types::{COLS, ROWS};

/// Material by rank, index 0 unused. The linear `100 * rank` table.
///
/// This misprices Jungle -- rank order is not value order, since the Rat kills
/// the Elephant, swims, and blocks leaps -- but a Rat-premium alternative was
/// tried and measured, inconclusively, worse. Retuning belongs to the tuning
/// phase, with an instrument that can actually resolve the difference.
pub const PIECE_VALUES: [i32; 9] = [0, 100, 200, 300, 400, 500, 600, 700, 800];

pub const ADVANCEMENT_PER_ROW: i32 = 10;
pub const ADVANCEMENT_ACCELERATION: i32 = 6;
pub const DEN_PROXIMITY_MAX_DIST: i32 = 3;
pub const DEN_PROXIMITY_PER_STEP: i32 = 30;
pub const DEN_DEFENDER: i32 = 25;
pub const RAT_IN_WATER: i32 = 40;
pub const RAT_BLOCKS_RIVER: i32 = 35;
pub const RAT_ADJACENT_TO_ENEMY_ELEPHANT: i32 = 60;
/// Named "trap_control" in config.py but applied as a penalty for standing in
/// enemy traps. Kept at the same magnitude and sign as the original.
pub const TRAP_PENALTY: i32 = 80;
pub const JUMP_READY: i32 = 20;
pub const MOBILITY: i32 = 2;
pub const DEN_THREAT: i32 = 45;
pub const TEMPO: i32 = 10;
pub const PST_WEIGHT: i32 = 1;

/// Row index of the midline; advancement past it accelerates.
pub const MIDLINE: i32 = (ROWS / 2) as i32;

const fn build_pst() -> [[i32; COLS]; ROWS] {
    let col_weight = [0i32, 5, 9, 12, 9, 5, 0];
    let mut table = [[0i32; COLS]; ROWS];
    let mut adv = 0usize;
    while adv < ROWS {
        let mut c = 0usize;
        while c < COLS {
            let mut v = col_weight[c];
            if adv > ROWS / 2 {
                v += (adv as i32 - (ROWS / 2) as i32) * (col_weight[c] / 6);
            }
            table[adv][c] = v;
            c += 1;
        }
        adv += 1;
    }
    table
}

/// Indexed `[advancement][col]`, where advancement is measured from the piece's
/// *own* back rank. Column-symmetric, so the symmetric start position evaluates
/// to zero apart from the side-to-move bonus.
pub static PST: [[i32; COLS]; ROWS] = build_pst();

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pst_matches_the_python_table() {
        // Materialised values from config.py's _build_pst().
        assert_eq!(PST[0], [0, 5, 9, 12, 9, 5, 0]);
        assert_eq!(PST[4], [0, 5, 9, 12, 9, 5, 0]);
        assert_eq!(PST[5], [0, 5, 10, 14, 10, 5, 0]);
        assert_eq!(PST[6], [0, 5, 11, 16, 11, 5, 0]);
        assert_eq!(PST[7], [0, 5, 12, 18, 12, 5, 0]);
        assert_eq!(PST[8], [0, 5, 13, 20, 13, 5, 0]);
    }

    #[test]
    fn pst_is_column_symmetric() {
        // This is what makes the symmetric starting position evaluate to 0.
        for row in PST.iter() {
            for c in 0..COLS {
                assert_eq!(row[c], row[COLS - 1 - c]);
            }
        }
    }
}
