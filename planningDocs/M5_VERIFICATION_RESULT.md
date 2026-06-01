# Milestone 5 — Verification gate closing record

**Task:** 5.8 — FULL gate: reproduce Wieners 2025 Figs 1–5 (one-nation
climate-policy scenarios), extending the approved partial gate (Task 5.7).
**Date:** 2026-06-01.
**Verdict:** **PASS (full)** — on the M1–M4 gate instrument, with two documented
findings (a defective C++ reference for BE/CER, and the standing macro
RNG-amplification residual).
**Model:** Opus.

> Supersedes the **PASS (partial)** record (Task 5.7, 2026-05-29). The three
> enablers the partial gate flagged are now in place:
> **5.7.1** firm-side energy-axis innovation (`A1p_el/en/ef`) → panels c/d/e LIVE;
> **5.7.2** carbon-tax revenue routing (`t_CO2_use[]`) → T2h/T2i distinct from T2;
> **5.7.3** C++ green-industrial references compiled → BE/CER/BCER/BCERT on disk.

---

## 0. TL;DR

The carbon tax's **industrial-electrification channel** — structurally absent in
the partial gate (electrification frozen at `A0_el=0.3`) — is now LIVE and
reproduces the paper. On the four decarbonization indicators (temperature,
emissions, electrification, renewable share), **every** policy with a valid C++
reference moves **every** indicator the same direction as C++ at both 2050 and
2100: **48/48 = 100%**. The electrification *coefficient levels* (panels c/d/e),
now technical quantities rather than RNG-amplified aggregates, agree with C++
within ±20%: **36/42 = 86%**. The green-industrial-policy scenarios (Figs 3 & 5),
which had no reference at all before, reproduce the paper's transition.

Two findings are documented, not hidden:

1. **Task 5.7.3's C++ references for BE and CER are defective** — they show no
   transition (renewable share stays 0, electrification frozen), contradicting
   the paper; CER additionally crashes in ~half its MC runs. This is a 5.7.3
   *build/policy-switch* defect, **not** a Python error: the Python BE/CER runs
   reproduce the paper cleanly (BE: green→1.0, electrification→1.0, warming
   3.8→1.8 °C). BE/CER are therefore gated Python-vs-**paper** (8/8) and the C++
   references are flagged for a rebuild.
2. **The macro/financial channel** (GDP, unemployment, bankruptcy) carries the
   inherited M1 RNG amplification; its direction flips on weak contrasts
   (26/36). Tracked, not gated — exactly as M1–M4 established.

---

## 1. Scope

| | |
|---|---|
| **Fig 1 — carbon-pricing** (valid C++ ref, 9 panels) | `baseline, Tc, T2, T2h, T2i` |
| **Fig 3 — green-industrial** (valid C++ ref, 9 panels) | `baseline, BCER, BCERT` |
| **Fig 3 — green-industrial** (C++ ref DEFECTIVE → vs paper) | `BE, CER` |
| **Fig 2 — increasing tax** (partial: TD2/TDh reference-less) | `Tc, T2` shown |
| **Fig 5 — tax vs green-industrial** (partial: Tsec/BCR ref-less) | `baseline, T2, BCER` shown |
| **Fig 4 — scorecard** | built for the 9 scenarios with refs (warming / unemployment / bankruptcy) |
| **Reference-less, not gated** | `TD2, TDh, Tsec, ET2, RT2, BCR` — exponential / sector-specific tax variants are commented out in the current C++ source, so 5.7.3 could not build them |

Calendar mapping (paper plotter `analysis/plot_figure1_5scenarios.py`):
`year = t + 1940`, so t=110 = 2050, t=160 = 2100.

Data: Python 64 MC (seeds 0–63) vs C++ 64 MC (mc 100–163), both N1=100, N2=400,
LS0=500000, T=220.

---

## 2. Method (the M1–M4 / partial-gate template)

Raw *macro* level agreement is not the instrument (Python's PCG64 stream
amplifies GDP growth above C++'s Numerical-Recipes stream from the spin-up on).
The gate is judged on:

* **PRIMARY — transition-indicator direction concordance.** For the four
  decarbonization indicators (a temperature, b emissions, e electrification,
  f renewable share), `sign(policy − baseline)` at 2050 and 2100, Python vs C++
  (valid refs). Near-zero deltas (within 2% of the baseline magnitude) count as a
  concordant "flat". This is the operational form of "ranking of scenarios on
  each indicator matches the paper", on the indicators whose policy signal is
  unambiguous.
* **NEW quantitative — electrification panel levels.** Panels c/d/e are technical
  coefficients (`A2_en`, `A1p_en`, `A1p_el`), so their ensemble-mean levels are
  directly comparable; gated within ±20%.
* **DEFECT handling.** A green policy whose C++ renewable share never leaves ~0
  is auto-detected and gated Python-vs-paper instead.
* **TRACKED, not gated.** Macro/financial direction (g/h/i) and raw level
  deviation (M1 RNG amplification).

The C++ panel-c/d/e values are firm-means of the per-firm micro files
`A2all_en` / `A1all_en` / `A1all_el` (the paper plotter's `.mean(axis=1)`); the
Python values are the matching firm-means added to `save_outputs` in this task.

---

## 3. Results

### 3.1 PRIMARY — transition-indicator direction: 48/48 (100%)

Over valid refs `{Tc, T2, T2h, T2i, BCER, BCERT}`, both codebases agree on
`sign(policy − baseline)` for temperature, emissions, electrification and
renewable share at 2050 and 2100 — zero mismatches. This is the paper's Fig-1/3
decarbonization narrative, now reproduced **through the industrial-electrification
channel** that was absent in the partial gate.

### 3.2 NEW — electrification panel levels within ±20%: 36/42 (86%)

The c/d/e coefficients track C++ quantitatively. Example (T2 @ 2100):
panel c (cons-good electricity/output) Py 0.117 vs C++ 0.101; panel d (cap-good
energy/output) Py 231 vs C++ 190; panel e (cap-good electrification) Py 0.99 vs
C++ 0.95. The handful of >20% cells are early-transition (2050) points where one
side leads the other by a few years.

### 3.3 BE/CER — Python vs paper: 8/8 (100%)

With the C++ reference defective (§4), the Python BE/CER runs are checked against
the paper's qualitative expectations (green ↑, electrification ↑, warming ↓,
emissions ↓ vs baseline at 2100) — all 8 cells match. Python BE: green 0→1.0,
electrification 0.36→1.0, warming 3.77→1.81 °C; Python CER: green 0→0.985,
warming →2.34 °C. This is the paper's Fig-3 story.

### 3.4 TRACKED (not gated) — macro/financial channel: 26/36

Direction on GDP / unemployment / bankruptcy flips on weak contrasts: the
inherited M1 RNG amplification (Python GDP runs above C++) plus a noisy
bankruptcy *count* near a low base (~0.03 likelihood). Fig-4 peak metrics over
the policy era agree on sign vs baseline for 8/8 (warming), 8/8 (unemployment)
and 7/8 (bankruptcy) policies, so the *qualitative* macro picture is right; only
the per-point direction on small contrasts is noisy. Not gated, per M1–M4.

### 3.5 DIAGNOSTIC — full 5-way ranking: 1/18 per figure group

Exact ordering of 5 ensemble means (several near-tied, all RNG-amplified) almost
never matches — this is a deliberately over-strict diagnostic, not a gate. The
PRIMARY instrument (§3.1) certifies no decarbonization-indicator direction is
wrong.

---

## 4. Finding — Task 5.7.3 C++ references for BE and CER are defective

| C++ scenario | runs reaching t=220 | renewable @2100 | electrification @2100 | status |
|---|---|---|---|---|
| B / Tc / T2 / T2h / T2i | 64/64 | matches paper | rises under tax | **valid** |
| **BE** | 64/64 | **0.000** | **0.31** (≈frozen) | **DEFECTIVE** |
| **CER** | **30/64** | **0.000** | 0.32 | **DEFECTIVE** + unstable |
| BCER | 63/64 | 1.000 | 1.000 | valid |
| BCERT | 63/64 | 1.000 | 1.000 | valid |

The BCERT-overlay (`files_BCERT/0_dsk_main.cpp`) compiled in 5.7.3 used
compile-time `#ifndef` switches (`NO_SUB`, `NO_BROWN_BAN`) to derive the
ban-only (BE) and subsidy-only (CER) mixes. Those two mixes did **not** trigger a
green transition in the C++ output, contradicting the paper (BE greens to ~90%
by 2050). The ymc column layout is byte-identical to the standard build (verified
against `dsk_main.cpp:8825+`), so this is a genuine model-output defect, not a
parsing artefact.

**Disposition.** Not a Python defect — Python reproduces the paper's BE/CER
transition. The C++ BE/CER references are flagged for a 5.7.3 rebuild (likely the
brown-ban start-time / subsidy-zeroing logic in the overlay's policy switches).
BCER/BCERT references are valid and are gated normally. A rebuild would convert
BE/CER from "gated vs paper" to "gated vs C++"; it does not change the verdict.

---

## 5. Energy-transition timing (carried from the partial gate, §4 there)

The partial gate's one substantive finding — Python's energy-producer green
transition responds *faster* to carbon pricing than C++ mid-transition — persists
but is no longer prominent now that the electrification channel is present: it
surfaces only as a few >20% cells in §3.2 at 2050 and the 6% full-ranking
diagnostic. Direction is never wrong. With the industrial-electrification channel
now co-determining energy demand, the remaining timing offset is a quantitative
calibration item for the energy-module review, not a structural error.

---

## 6. Artefacts and reproduction

```
# from Code/dskPython2/
python3 tests/reference/one_nation/run_deterministic_M5.py             # py_det_M5_<s>.parquet (baseline/Tc/T2)
python3 tests/reference/one_nation/run_ensemble_M5.py --workers 32      # 9 scenarios, 32 MC, T=220 -> py_macro_M5_<s>.parquet
python3 tests/reference/one_nation/cache_cpp_M5.py                      # cpp_ymc_M5_<s>.parquet + cpp_micro_M5_<s>.parquet (9 scenarios)
python3 tests/reference/one_nation/build_M5_all_scenarios_notebook.py   # M5_all_scenarios.ipynb
jupyter nbconvert --to notebook --execute \
    tests/reference/one_nation/M5_all_scenarios.ipynb --inplace
```

New / changed for Task 5.8:

* `dsk/nation.py` — `save_outputs` now records the three firm-mean transition
  coefficients matching the paper's Fig-1/3 panels c/d/e:
  `mean_elec_use_s2` (A2_en), `mean_energy_use_s1` (A1p_en), `mean_elfrac_s1`
  (A1p_el). (Simple means over alive firms, matching the paper's `.mean(axis=1)`.)
* `tests/reference/one_nation/load_cpp_basecode.py` — added
  `load_cpp_scenario_micro()` + `_load_micro_firmmean()` to read the per-firm
  `A1all_el/A1all_en/A2all_en` C++ micro files into firm-mean frames.
* `tests/reference/one_nation/run_ensemble_M5.py` — extended to all 9 scenarios
  with C++ references (`baseline, Tc, T2, T2h, T2i, BE, CER, BCER, BCERT`).
* `tests/reference/one_nation/cache_cpp_M5.py` — NEW: caches the C++ ymc + micro
  references to parquet (the raw text ensembles are slow to read on NFS).
* `tests/reference/one_nation/build_M5_all_scenarios_notebook.py` + executed
  `M5_all_scenarios.ipynb` — extended to all of Figs 1–5: full 9-panel Py-vs-C++
  reproductions for Figs 1 & 3, partial Figs 2/5, Fig-4 scorecard, defect
  detection, the transition-direction / electrification-level / BE/CER-vs-paper
  gate, and the verdict.

Test status after the gate: see build_log.md Task 5.8 entry (full unit +
integration suite, excluding the slow `test_sfc_baseline_t1_t60.py`).

---

## 7. M5 → M6 note

Per the standing **no-auto-advance** rule, M6 (multi-nation harness) does **not**
start until the user signs off on this FULL gate. Open follow-ups (none blocking
the verdict):

1. **Rebuild the C++ BE/CER references** (5.7.3) so they transition, converting
   BE/CER from "gated vs paper" to "gated vs C++".
2. **Energy-module transition-timing review** (§5) — quantitative calibration,
   not a structural bug.
3. The macro RNG-amplification residual is the same standing M1 item, not M5-specific.
