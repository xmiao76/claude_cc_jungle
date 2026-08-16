//! Tunable search parameters and feature toggles.
//!
//! Every heuristic is switchable and every margin is a number here rather than a
//! constant in the search, so any of them can be measured head-to-head against
//! its own absence. That is the repository's central convention, and until now it
//! was expensive to obey: the Python engine's A/B runs took long enough that most
//! of its recorded per-flag results are, on inspection, statistically
//! inconclusive. A search three orders of magnitude faster makes a properly
//! powered match minutes rather than an overnight job.
//!
//! Defaults reproduce the Python engine's shipped tuning, so `SearchParams::default()`
//! is the control to measure changes against.

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SearchParams {
    // --- null-move pruning ---
    pub use_nmp: bool,
    pub nmp_reduction: i32,
    pub nmp_min_depth: i32,
    /// Withheld when the side to move is this short of pieces: passing is a
    /// materially different proposition in a near-empty position.
    pub nmp_min_pieces: u32,

    // --- shallow-depth pruning ---
    pub use_rfp: bool,
    pub rfp_margin: i32,
    pub rfp_max_depth: i32,
    pub use_razoring: bool,
    pub razor_margin: i32,
    pub razor_max_depth: i32,
    pub use_futility: bool,
    pub futility_margin: i32,
    pub futility_max_depth: i32,
    pub use_lmp: bool,
    pub lmp_base: usize,

    // --- late-move reductions ---
    pub use_lmr: bool,
    pub lmr_min_depth: i32,
    pub lmr_moves_before: usize,
    /// Whether a killer may be reduced. Measured at about -56 Elo when true,
    /// at fixed depth 5 against the engine this one replaces.
    pub lmr_reduce_killers: bool,

    // --- iterative deepening ---
    pub aspiration_delta: i32,
    pub aspiration_min_depth: i32,

    // --- quiescence ---
    pub delta_margin: i32,
    pub quiescence_max_ply: i32,
}

impl Default for SearchParams {
    fn default() -> SearchParams {
        SearchParams {
            use_nmp: true,
            nmp_reduction: 2,
            nmp_min_depth: 3,
            nmp_min_pieces: 3,

            use_rfp: true,
            rfp_margin: 120,
            rfp_max_depth: 4,
            use_razoring: true,
            razor_margin: 300,
            razor_max_depth: 2,
            use_futility: true,
            futility_margin: 150,
            futility_max_depth: 2,
            use_lmp: true,
            lmp_base: 6,

            use_lmr: true,
            lmr_min_depth: 3,
            lmr_moves_before: 4,
            lmr_reduce_killers: false,

            aspiration_delta: 50,
            aspiration_min_depth: 4,

            delta_margin: 200,
            quiescence_max_ply: 4,
        }
    }
}

impl SearchParams {
    /// Everything optional switched off: plain alpha-beta with a transposition
    /// table, move ordering and quiescence. The control for measuring the
    /// pruning heuristics as a group.
    pub fn baseline() -> SearchParams {
        SearchParams {
            use_nmp: false,
            use_rfp: false,
            use_razoring: false,
            use_futility: false,
            use_lmp: false,
            use_lmr: false,
            ..SearchParams::default()
        }
    }

    /// Parse `name=value` overrides, e.g. `"use_lmr=false,rfp_margin=90"`.
    /// Returns the offending token on a bad name or value.
    pub fn apply_overrides(&mut self, spec: &str) -> Result<(), String> {
        for token in spec.split(',').map(str::trim).filter(|t| !t.is_empty()) {
            let (name, value) = token
                .split_once('=')
                .ok_or_else(|| format!("expected name=value, got {token:?}"))?;
            let bad = || format!("bad value {value:?} for {name}");
            match name {
                "use_nmp" => self.use_nmp = value.parse().map_err(|_| bad())?,
                "nmp_reduction" => self.nmp_reduction = value.parse().map_err(|_| bad())?,
                "nmp_min_depth" => self.nmp_min_depth = value.parse().map_err(|_| bad())?,
                "nmp_min_pieces" => self.nmp_min_pieces = value.parse().map_err(|_| bad())?,
                "use_rfp" => self.use_rfp = value.parse().map_err(|_| bad())?,
                "rfp_margin" => self.rfp_margin = value.parse().map_err(|_| bad())?,
                "rfp_max_depth" => self.rfp_max_depth = value.parse().map_err(|_| bad())?,
                "use_razoring" => self.use_razoring = value.parse().map_err(|_| bad())?,
                "razor_margin" => self.razor_margin = value.parse().map_err(|_| bad())?,
                "razor_max_depth" => self.razor_max_depth = value.parse().map_err(|_| bad())?,
                "use_futility" => self.use_futility = value.parse().map_err(|_| bad())?,
                "futility_margin" => self.futility_margin = value.parse().map_err(|_| bad())?,
                "futility_max_depth" => {
                    self.futility_max_depth = value.parse().map_err(|_| bad())?
                }
                "use_lmp" => self.use_lmp = value.parse().map_err(|_| bad())?,
                "lmp_base" => self.lmp_base = value.parse().map_err(|_| bad())?,
                "use_lmr" => self.use_lmr = value.parse().map_err(|_| bad())?,
                "lmr_min_depth" => self.lmr_min_depth = value.parse().map_err(|_| bad())?,
                "lmr_moves_before" => self.lmr_moves_before = value.parse().map_err(|_| bad())?,
                "lmr_reduce_killers" => {
                    self.lmr_reduce_killers = value.parse().map_err(|_| bad())?
                }
                "aspiration_delta" => self.aspiration_delta = value.parse().map_err(|_| bad())?,
                "aspiration_min_depth" => {
                    self.aspiration_min_depth = value.parse().map_err(|_| bad())?
                }
                "delta_margin" => self.delta_margin = value.parse().map_err(|_| bad())?,
                "quiescence_max_ply" => {
                    self.quiescence_max_ply = value.parse().map_err(|_| bad())?
                }
                other => return Err(format!("unknown parameter {other:?}")),
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn overrides_apply_and_reject() {
        let mut p = SearchParams::default();
        p.apply_overrides("use_lmr=false, rfp_margin=90").unwrap();
        assert!(!p.use_lmr);
        assert_eq!(p.rfp_margin, 90);

        assert!(p.apply_overrides("nonsense=1").is_err());
        assert!(p.apply_overrides("use_lmr=maybe").is_err());
        assert!(p.apply_overrides("use_lmr").is_err());
    }

    #[test]
    fn baseline_disables_every_optional_heuristic() {
        let b = SearchParams::baseline();
        assert!(!b.use_nmp && !b.use_rfp && !b.use_razoring);
        assert!(!b.use_futility && !b.use_lmp && !b.use_lmr);
        // ...without touching the margins, so turning one back on gives the
        // shipped behaviour for that heuristic rather than a stale tuning.
        assert_eq!(b.rfp_margin, SearchParams::default().rfp_margin);
    }

    #[test]
    fn killers_are_not_reduced_by_default() {
        assert!(!SearchParams::default().lmr_reduce_killers);
    }
}
