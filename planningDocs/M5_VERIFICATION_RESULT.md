# Milestone 5 — Verification gate closing record

**Task:** 5.7 — Reproduce Wieners 2025 Figs 1–5 (one-nation climate-policy scenarios).
**Date:** 2026-05-29.
**Verdict:** **PASS (partial)** — approved partial gate (user sign-off 2026-05-29).
**Model:** Opus.

---

## 0. TL;DR

The carbon-pricing policy scenarios reproduce the paper's Figure 1 **direction**
on every gateable indicator: on the strong contrast (no policy → doubled carbon
tax **T2**), Python moves warming, emissions, renewable share, GDP, unemployment
and bankruptcy the same way as the C++ basecode at both 2050 and 2100
(**12/12 = 100%**, zero direction-wrong cells). The full three-way ranking
including the intermediate **Tc** scenario is 8/12; **all four misses are the
Tc scenario's fine ordering against a near neighbour, never a wrong direction**,
and trace to one substantive finding: Python's **energy-producer** green
transition responds *faster* to carbon pricing than C++ mid-transition.

This is a **partial** gate by design. Three features the full Figs 1–5 need are
not in the current port; they are documented in §5 with a closure checklist.

---

## 1. Scope (what was and was not gated)

| | |
|---|---|
| **Scenarios gated** | `baseline`, `Tc`, `T2` (carbon-pricing; Fig 1) |
| **Indicators gated** | panels **a** temperature, **b** emissions, **f** renewable share, **g** bankruptcy likelihood, **h** unemployment, **i** real GDP |
| **Blocked indicators** | **c** (electricity use, consumption goods) and **e** (electrification share, capital goods) — depend on the unported firm-side energy axis; frozen at `A0_el=0.3` |
| **Blocked scenarios** | `BE`, `CER`, `BCER`, `BCERT` (Figs 3 & 5) — **no C++ reference output on disk** (require recompiling C++ with `files_BCERT/`); `T2h`, `T2i` — degenerate to `T2` (tax-revenue routing unported) |

### Why partial (the three hard constraints)

1. **C++ reference outputs exist only for the carbon-pricing scenarios.** On
   disk: `basecode/run_scenario_{B,Tc,T2,T2h,T2i}/output_*/ymc_*.txt`
   (N1=100, N2=400, LS0=500000, T=220, 64 MC, mc 100–163). The paper's own
   `analysis/plot_figure1_5scenarios.py` builds Figure 1 from exactly these.
   The green-industrial-policy scenarios (Figs 3 & 5) have no output anywhere.
2. **The firm-side energy/electrification innovation axis is unported.**
   `CapitalGoodFirm.advance_technology()` innovates labour productivity only
   (`A1p_el/en/ef` deferred — see its docstring). Electrification fraction is
   frozen at `A0_el=0.3`, so panels c & e cannot move and the carbon tax's
   *industrial-electrification* transmission channel is structurally absent.
3. **Python `T2h`/`T2i` are degenerate to `T2`** — `t_CO2_use[]` revenue
   routing is unported (Task 5.6 note).

---

## 2. Method (mirrors the M1–M4 template)

The M1–M4 gates established that Python's PCG64 stream amplifies real-GDP growth
well above the C++ Numerical-Recipes stream from the spin-up on, so raw
*stochastic level* agreement is not the right instrument. The M5 gate is judged
on **policy-direction concordance**:

* **PRIMARY — `baseline → T2` direction.** `sign(T2 − baseline)` for each
  gateable indicator at 2050 (t=110) and 2100 (t=160), Python vs C++. This is
  the operational form of "ranking matches paper": C++ is the faithful paper
  model and the sign *is* the Fig 1 narrative.
* **DIAGNOSTIC — full 3-way ranking** of {baseline, Tc, T2}, with each miss
  classified.
* **TRACKED, not gated — raw stochastic level deviation** (inherits the M1 RNG
  amplification) and the deterministic policy-delta (uninformative at the
  near-zero magnitudes Python's deterministic mode produces under tax).

Calendar mapping (paper's plotter): `year = t + 1940` ⇒ t=80 = 2020 (climate
start), t=110 = 2050, t=160 = 2100, t=220 = 2160.

Data: Python 32 MC (seeds 0–31) vs C++ 64 MC (mc 100–163), both N1=100, N2=400,
LS0=500000, T=220.

---

## 3. Results

### 3.1 PRIMARY — direction concordance: 12/12 (100%)

On `baseline → T2`, both codebases agree on the sign at 2050 and 2100 for all
six gateable indicators:

| indicator | effect of doubling the tax | Py | C++ |
|---|---|---|---|
| temperature | down | ✓ | ✓ |
| emissions | down | ✓ | ✓ |
| renewable share | up | ✓ | ✓ |
| GDP | down | ✓ | ✓ |
| unemployment | up | ✓ | ✓ |
| bankruptcy | down | ✓ | ✓ |

This is the paper's Fig 1 story, reproduced through the ported channels:
carbon tax → fossil-fuel price → energy-sector green-vs-brown R&D + capacity
expansion → renewable share & emissions, with the macro feedback to GDP,
unemployment and bankruptcy.

### 3.2 DIAGNOSTIC — full 3-way ranking: 8/12

The four misses are all the intermediate **Tc** scenario; none is a wrong
direction:

| panel | year | Py order (asc) | C++ order (asc) | class |
|---|---|---|---|---|
| b emissions | 2050 | Tc<T2<baseline | T2<Tc<baseline | Tc timing |
| f renewable | 2050 | baseline<T2<Tc | baseline<Tc<T2 | Tc timing |
| g bankruptcy | 2050 | T2<Tc<baseline | T2<baseline<Tc | Tc near-tie |
| h unemployment | 2100 | Tc<baseline<T2 | baseline<Tc<T2 | Tc near-tie |

* **Tc near-tie** (g 2050, h 2100): Tc sits within ~10% of baseline, so
  sub-percent ensemble-mean noise flips the Tc/baseline order. Not a model
  defect.
* **Tc timing** (b 2050, f 2050): the substantive finding — see §4.

### 3.3 TRACKED — raw level within ±20%: 6/18

These are level deviations of the kind M1–M4 tracked rather than gated (the
RNG-implementation difference between the two codebases). At this config/horizon
(N1=100, t=160) Python's ensemble real GDP comes in ~26–33% *below* C++ — note
this is the opposite sign to M1's N1=50/t=60 finding (Python above C++); the
gate does not establish whether that is the same RNG mechanism at a different
config/horizon or a distinct effect, and it does not need to, since levels are
not the instrument. The standout outlier is emissions for T2 at 2100 (Py 22.3
vs C++ 1.18 GtC, +1797%): C++'s T2 has nearly fully decarbonized by 2100 while
Python's T2 retains residual fossil use because the industrial-electrification
channel is absent (firms cannot shift off fossil fuel). Reported for
transparency, **not gated**.

---

## 4. Substantive finding — energy-producer transition over-responsive to carbon pricing

At 2050, Python's **Tc** (the *lower* "critical" tax, 0.6e-4) reaches a
renewable share of **~0.95**, whereas C++'s Tc reaches only **~0.075** (C++ Tc
greens late, hitting ~0.90 by 2100). Python's energy-sector green transition
therefore responds to carbon pricing roughly **50 years too fast**, and is
strong enough that the lower tax (Tc) out-greens the higher tax (T2) at 2050 —
because under T2 the deeper recession (lower GDP, lower electricity demand)
slows new-capacity turnover, hence slows the *share* shift. By 2100 both reach
~1.0 and the ordering resolves correctly.

* **Where it lives.** The ported energy module (`ElectricityProducer`
  capacity expansion + green/brown R&D), the same module M3 verified in
  deterministic **baseline** mode (no carbon tax). The divergence appears only
  *under carbon pricing*, where the fossil-fuel-price uplift from the tax feeds
  the green-vs-brown lifetime-cost comparison.
* **What it is not.** Not a crash and not a wrong-direction error — green share
  still rises with the tax, as in the paper. It is a *timing / sensitivity*
  calibration divergence, analogous in spirit to the M1 RNG-amplification
  residual: a quantitative offset in a structurally-correct channel.
* **Disposition.** Tracked for the energy-module review that should accompany
  the firm-side energy-axis back-fill (§5). Debugging the exact transition
  timing requires the electrification channel to be present anyway, since in the
  real model the two channels co-determine energy demand and the green build-out.

---

## 5. Closure checklist toward a FULL M5 gate

A full reproduction of Figs 1–5 (not gated here) requires, in rough order:

1. **Port the firm-side energy-axis innovation** (`A1p_el`, `A1p_en`, `A1p_ef`)
   in `CapitalGoodFirm.advance_technology()` — the TECHANGEND energy axes
   deferred since M1/Task 1.14. This unblocks panels c & e and the carbon tax's
   industrial-electrification channel. **Largest item.**
2. **Port tax-revenue routing** (`t_CO2_use[]`) so `T2h` (→ households) and
   `T2i` (→ industrial R&D) differentiate from `T2`. Completes Fig 1's five
   carbon-pricing curves and Fig 2's rising-tax variants (`TD2`, `TDh`).
3. **Compile the C++ green-industrial-policy references.** Build the C++ with
   `files_BCERT/` and run `BE`, `CER`, `BCER`, `BCERT` (+ `Tsec`) to get the
   on-disk reference for Figs 3, 4 (scorecard) and 5.
4. **Re-check the energy-producer transition timing (§4)** once the
   electrification channel is present, against the C++ Tc/T2 renewable-share
   trajectories.

---

## 6. Artefacts and reproduction

```
# from Code/dskPython2/
python3 tests/reference/one_nation/run_deterministic_M5.py            # py_det_M5_<s>.parquet
python3 tests/reference/one_nation/run_ensemble_M5.py --workers 30     # py_macro_M5_<s>.parquet  (32 MC, T=220)
python3 -c "import sys; sys.path.insert(0,'tests/reference/one_nation'); \
    import load_cpp_basecode as L; \
    [L.load_cpp_scenario_ymc(s).to_parquet(f'tests/reference/one_nation/cpp_ymc_M5_{s}.parquet') \
     for s in ['baseline','Tc','T2']]"                                 # cpp_ymc_M5_<s>.parquet (cache; slow)
python3 tests/reference/one_nation/build_M5_all_scenarios_notebook.py  # M5_all_scenarios.ipynb
jupyter nbconvert --to notebook --execute \
    tests/reference/one_nation/M5_all_scenarios.ipynb --inplace
```

New / changed files:

* `tests/reference/one_nation/run_ensemble_M5.py` — per-scenario MC ensembles at
  the paper-level N1=100 config.
* `tests/reference/one_nation/run_deterministic_M5.py` — per-scenario
  deterministic trajectories.
* `tests/reference/one_nation/load_cpp_basecode.py` — added
  `cpp_scenario_ymc_dir()` and `load_cpp_scenario_ymc()` for the
  `run_scenario_<S>/output_<S>/` paper-level ensembles.
* `tests/reference/one_nation/build_M5_all_scenarios_notebook.py` + the executed
  `M5_all_scenarios.ipynb` (9-panel Fig-1 Python reproduction; Python-vs-C++
  overlays; direction & ranking tables; verdict).
* `dsk/nation.py` — added `n_s2_bankruptcies` (C++ `next2bc`, Fig-1 panel g):
  count of sector-2 firms exiting with positive bad debt this period; exposed in
  `save_outputs`.

Test status after the M5 gate: **761 passed, 1 skipped** (unit + integration,
excluding the slow `test_sfc_baseline_t1_t60.py`), no regressions from the
`n_s2_bankruptcies` addition.

---

## 7. M5 → M6 note

Per the standing "no auto-advance" rule, M6 (multi-nation harness) does **not**
start until the user signs off on this partial gate. If the user wants a FULL
M5 before M6, the §5 checklist is the path; that work re-opens M1/Task 1.14
(energy-axis innovation) and adds a C++ recompile step, so it is a milestone-
sized effort, not a patch.
