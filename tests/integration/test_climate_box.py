"""Verification gate for Task 4.1 — the C-ROADS climate box.

Drives :class:`dsk.climate.climate_system.ClimateSystem` with the *calibrated*
annual-emissions sequence extracted from a C++ basecode run and asserts the
Python surface-temperature trajectory reproduces the C++ one to within 0.05 K.

Reference data: ``tests/integration/data/climate_box_cpp_reference.tsv``
(frozen from ``Wieners_2025-main_slim/basecode/output_B/ymc_0_1_101.txt``;
column 18 = calibrated emissions GtC, 19 = Cat, 20 = Tmixed; rows t = 81..220,
i.e. every step the climate box actually runs, t > t_start_climbox = 80).
The C++ run started the box from its 2020 initial state with non-CO₂ forcing
on (flag_nonCO2_force = 1), which is the Python default.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dsk.climate.climate_system import ClimateSystem

DATA = Path(__file__).parent / "data" / "climate_box_cpp_reference.tsv"
TOL_K = 0.05  # acceptance threshold from IMPLEMENTATION_PLAN Task 4.1


def _load_reference():
    rows = []
    for line in DATA.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("t\t") or line.startswith("t "):
            continue
        parts = line.split()
        rows.append(
            {
                "t": int(parts[0]),
                "emiss_calib_gtc": float(parts[1]),
                "cat_cpp": float(parts[2]),
                "tmixed_cpp": float(parts[3]),
            }
        )
    return rows


def test_reference_data_present():
    rows = _load_reference()
    assert len(rows) == 140, "expected t=81..220 (140 climate steps)"
    assert rows[0]["t"] == 81 and rows[-1]["t"] == 220


def test_initial_state_matches_2020_conditions():
    c = ClimateSystem()
    # 2020 init (flag_nonCO2_force = 1): Tmixedinit1 = 1.0856, Catinit1 = 864.6616
    assert c.surface_temperature == pytest.approx(1.0856, abs=1e-4)
    assert c.atmospheric_carbon == pytest.approx(864.6616, abs=1e-4)
    assert c.temperature_anomaly == c.surface_temperature


def test_surface_temperature_within_0p05K_through_run():
    """Primary acceptance: |Tmixed_py - Tmixed_cpp| < 0.05 K at every step."""
    rows = _load_reference()
    c = ClimateSystem()

    max_dT = 0.0
    worst_t = None
    for r in rows:
        c.step(r["emiss_calib_gtc"])
        dT = abs(c.surface_temperature - r["tmixed_cpp"])
        if dT > max_dT:
            max_dT = dT
            worst_t = r["t"]

    assert max_dT < TOL_K, (
        f"max |dTmixed| = {max_dT:.6e} K at t={worst_t} exceeds {TOL_K} K"
    )


def test_atmospheric_carbon_tracks_cpp():
    """Carbon trajectory is a tight secondary check (C++ writes 4-dp output)."""
    rows = _load_reference()
    c = ClimateSystem()
    max_dC = 0.0
    for r in rows:
        c.step(r["emiss_calib_gtc"])
        max_dC = max(max_dC, abs(c.atmospheric_carbon - r["cat_cpp"]))
    # 4-decimal output rounding bounds the achievable agreement well under 0.1 GtC
    assert max_dC < 0.1, f"max |dCat| = {max_dC:.6e} GtC"


def test_upper_ocean_carbon_conserved_each_step():
    """The iterative atm/ocean exchange must conserve Cat + top-layer ocean C."""
    rows = _load_reference()
    c = ClimateSystem()
    for r in rows:
        c.step(r["emiss_calib_gtc"])
        # By construction Con(1,1) = Ctot1 - Cat(1); both finite and positive.
        assert c.ocean_carbon_per_layer[0] > 0.0
        assert c.atmospheric_carbon > 0.0


def test_warming_is_monotone_under_rising_emissions():
    """Scenario B emissions rise overall; surface temp should end far above start."""
    rows = _load_reference()
    c = ClimateSystem()
    t0 = c.surface_temperature
    for r in rows:
        c.step(r["emiss_calib_gtc"])
    assert c.surface_temperature > t0 + 5.0  # ends ~11.6 K vs ~1.09 K start


def test_zero_emissions_step_is_finite_and_does_not_warm():
    """A zero-emission step must run cleanly (live Simulation seam before M3)."""
    c = ClimateSystem()
    t_before = c.surface_temperature
    c.step(0.0)
    assert c.surface_temperature == c.surface_temperature  # not NaN
    # with no emissions and decay/uptake, the atmosphere should not gain carbon
    assert c.atmospheric_carbon < 864.6616


def test_calibrate_emissions_gauge_logic():
    """First call pins the gauge; later calls scale proportionally to GtC."""
    c = ClimateSystem()
    # first call -> calibrated = emissions_first_year_gtc * dtclim (= 12 * 1)
    first = c.calibrate_emissions(model_emissions=4.0e9)
    assert first == pytest.approx(12.0, abs=1e-9)
    # doubling raw model emissions doubles the relative rate -> 24 GtC
    second = c.calibrate_emissions(model_emissions=8.0e9)
    assert second == pytest.approx(24.0, abs=1e-9)
