"""Scalar production-cost formulas mirroring cost_sect1.cpp and cost_sect2.cpp.

C++ reference: basecode/short_functions/dsk_cost_sect1.cpp, dsk_cost_sect2.cpp.
"""
from __future__ import annotations

import math


def cost_sect1(
    wage_net: float,
    process_prod: float,
    elec_demand_per_unit: float,
    elec_price: float,
    fossil_demand_per_unit: float,
    fossil_price: float,
    ff2em: float,
    env_filthiness: float,
    carbon_tax_s1: float = 0.0,
    elfrac_deficit: float = 0.0,
    fine: float = 0.0,
    rule: int = 1,
) -> float:
    """Unit production cost for a capital-good firm (machine building cost).

    C++ dsk_cost_sect1.cpp:
      procost1 = (w/a + eld*cel + ffd*cff + f2e*ffd*tax + ef*tax) * (1 + fine_multiplier)

    Parameters
    ----------
    wage_net       : w - Subwage  (= wage in baseline where Subwage=0)
    process_prod   : A1p(1,i) * a  (process labour productivity * scale)
    elec_demand_per_unit : eld — electricity demand per unit of output
    elec_price     : c_en(2)  (electricity price, previous period)
    fossil_demand_per_unit : ffd — fossil fuel demand per unit of output
    fossil_price   : pf
    ff2em          : emissions per unit of fossil fuel (ff2em = 1100)
    env_filthiness : A1p_ef  (process emission intensity; 0 in baseline)
    carbon_tax_s1  : t_CO2_I1  (0 in baseline)
    elfrac_deficit : max(0, elfrac_reg_now - A1p_el)  (0 pre-M5)
    fine           : elfrac_reg_fine  (0 pre-M5)
    rule           : flag_fuel_to_elec  (1 in baseline)
    """
    if process_prod <= 0.0:
        return 0.0

    base = (
        wage_net / process_prod
        + elec_demand_per_unit * elec_price
        + fossil_demand_per_unit * fossil_price
        + ff2em * fossil_demand_per_unit * carbon_tax_s1
        + env_filthiness * carbon_tax_s1
    )

    if fine == 0.0 or elfrac_deficit <= 0.0:
        return base

    dummy_lin = elfrac_deficit
    if rule == 2:
        mult = (dummy_lin + math.sqrt(math.sqrt(dummy_lin)) * 0.3 + 0.01) * fine
    else:
        mult = dummy_lin * fine
    return base * (1.0 + mult)


def cost_sect2(
    wage_net: float,
    machine_labour_prod: float,
    machine_energy_need: float,
    elec_price: float,
    machine_env_filthiness: float = 0.0,
    carbon_tax_s2: float = 0.0,
) -> float:
    """Unit production cost for a consumption-good firm using a specific machine.

    C++ dsk_cost_sect2.cpp:
      procost2 = w/a + eld*cel + ef*tax

    Parameters
    ----------
    wage_net              : w - Subwage  (= wage in baseline)
    machine_labour_prod   : A(tt, i) — labour productivity of this machine
    machine_energy_need   : A_en(tt, i) — electricity demand per unit of output
    elec_price            : c_en(2)  (electricity price, previous period)
    machine_env_filthiness: A_ef(tt, i)  (= 0 in baseline)
    carbon_tax_s2         : t_CO2_I2  (= 0 in baseline)
    """
    if machine_labour_prod <= 0.0:
        return 0.0

    return (
        wage_net / machine_labour_prod
        + machine_energy_need * elec_price
        + machine_env_filthiness * carbon_tax_s2
    )
