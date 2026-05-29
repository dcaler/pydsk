"""Global parameters dataclass — G-scope constants and flags from NAME_MAP §1–§8."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=False)
class GlobalParameters:
    # --- §1 Simulation Dimensions ---
    n1_capital_good_firms: int = 100
    n2_consumption_good_firms: int = 400
    total_steps: int = 220
    mc_runs: int = 5
    observation_lag: int = 1
    t_energy_retune: int = 60
    t_spinup_energy: int = 5
    spin_up_steps: int = 60
    climate_start_step: int = 80          # = spin_up_steps + 20
    experiment_id: int = 0

    # --- §2 dskQE ---
    bonds_share_of_credit: float = 0.0
    solvency_weight_in_spread_1: float = 0.5
    solvency_weight_in_spread_2: float = 0.5

    # --- §3 KS-Core Behavioral Parameters ---
    rd_budget_fraction: float = 0.04
    innovation_imitation_split: float = 0.5
    innovation_sector1_share_initial: float = 0.07
    innovation_sector1_share_scaling: float = 0.0
    innovation_sector1_share_limit: float = 5.0
    innov_imit_probability_scale: float = 1.0
    rd_productivity_energy: float = 0.6
    rd_productivity_labour: float = 0.15
    rd_productivity_innovation_legacy: float = 0.3
    rd_productivity_imitation: float = 0.3
    frontier_growth_machine_prod: float = 0.03
    frontier_growth_process_prod: float = 0.03
    machine_prod_change_lower: float = -0.06
    machine_prod_change_upper: float = 0.06
    labour_prod_s2_innov_lower: float = -0.13
    labour_prod_s2_innov_upper: float = 0.13
    labour_prod_s1_innov_lower: float = -0.13
    labour_prod_s1_innov_upper: float = 0.13
    entry_support_upper_endogenous: float = 0.30
    n1_foreign_firms: int = 100           # = n1_capital_good_firms
    frontier_innov_unif_lower: float = -0.15
    frontier_innov_unif_upper: float = 0.15
    beta_innov_alpha: float = 3.0
    beta_innov_beta: float = 3.0
    beta_univ_alpha: float = 3.0
    beta_univ_beta: float = 3.0
    beta_entry_alpha: float = 2.0
    beta_entry_beta: float = 4.0
    beta_frontier_alpha: float = 3.0
    beta_frontier_beta: float = 3.0
    patent_duration: float = 12.0
    patent_breadth: float = 0.01
    credit_max_rule: float = 2.0
    s1_markup: float = 0.04
    brochure_growth_factor: float = 0.5
    s1_antitrust_cap: float = 1.0
    replicator_strength: float = -1.0
    competitiveness_price_weight: float = 1.0
    competitiveness_demand_weight: float = 1.0
    wage_productivity_response: float = 0.9
    s2_exit_market_share_floor: float = 0.00001
    wage_subsistence: float = 1.0
    firm_price_floor: float = 0.01
    inventory_target_fraction: float = 0.1
    capacity_utilization: float = 0.75
    investment_trigger: float = 0.0
    investment_trigger_upper: float = 0.5
    machine_size_units: float = 40.0
    labour_supply_growth: float = 0.0
    machine_max_age: float = 19.0
    payback_threshold: float = 200.0      # = 5 * machine_size_units
    s1_productivity_scale: float = 0.1
    productivity_init: float = 1.0
    s1_initial_prod_scale: float = 1.0
    labour_supply_init: float = 500000.0
    s1_net_worth_init: float = 1000.0
    s2_net_worth_init: float = 1000.0
    wage_init: float = 1.0
    capital_init: float = 800.0

    # --- §4 Credit-Market Parameters ---
    credit_max_relative_networth: float = 0.5
    r_sterilize_bank_failure: float = 0.0
    bank_deposit_markdown: float = 1.0
    cb_reserves_markdown: float = 0.33
    bank_extra_reserve_ratio: float = 1.0
    bank_debt_remit_reinvest_rate: float = 0.0
    bailout_toxicap_share: float = 1.0
    bailout_toxicap_share_govt: float = 1.0
    credit_homogeneous_share: float = 0.0
    dividend_rate_s1: float = 0.0
    dividend_rate_s2: float = 0.0
    dividend_rate_bank: float = 0.0
    gdrift_const: float = 42000.0
    gpar_const: float = 1.01
    tech_progress_exogenous_growth: float = 0.005
    process_innov_unif_lower_exog: float = 0.04
    product_innov_unif_upper_exog: float = 0.04
    myopic_expect_t1: float = 0.4
    myopic_expect_t2: float = 0.4
    myopic_expect_t3: float = 0.0
    myopic_expect_t4: float = 0.0
    expect_accel_gd: float = 0.5
    expect_extrap_a: float = 0.3
    expect_extrap_b: float = 0.3
    bank_equity_init_multiplier: float = 1.0
    debt_repayment_fraction: float = 0.33
    bonds_repayment_share: float = 0.025
    # varphi — fraction of each bank's Basel credit pre-allocated to bonds when
    # flag_portfolioallocation==1 (BONDS_DEMAND). 0 at baseline. dsk_constant.h:35.
    bonds_share_of_credit: float = 0.0
    deposit_insurance_tax_rate: float = 0.0
    deposit_recovery_share: float = 1.0
    pareto_alpha: float = 0.8
    pareto_k: float = 2.0
    pareto_p: float = 400.0
    inflation_target: float = 0.005       # = 0.02 / 4
    unemployment_target: float = 0.05
    s1_entrant_networth_upper: float = 0.9
    s1_entrant_networth_lower: float = 0.1
    s2_entrant_networth_upper: float = 0.9
    s2_entrant_networth_lower: float = 0.1
    s2_entrant_capital_upper: float = 0.9
    s2_entrant_capital_lower: float = 0.1
    bank_markup_init: float = 0.3
    k_const: float = 0.1
    unemployment_benefit_low: float = 0.20
    unemployment_benefit_high: float = 0.60
    aliq_low: float = 0.05
    aliq_high: float = 0.15
    keynes_rule_unemployment_threshold: float = 0.1
    rdeb_floor: float = 0.02
    beta_r: float = 0.0
    entry_random_copy_fraction: float = 0.8
    wage_change_floor: float = 0.0
    wage_staggering_period: float = 12.0
    wage_tax_rate: float = 0.1
    beta_bonds: float = 0.04
    taylor3: float = 1.0
    bonds_markdown: float = 0.0
    # Bailout random-multiplier bounds for recapitalisation (b1inf/sup, b2inf/sup in C++)
    bailout_equity_multiplier_lower: float = 0.1   # b1inf — flagbailout=0, max_equity>0 case
    bailout_equity_multiplier_upper: float = 0.9   # b1sup
    bailout_fallback_multiplier_lower: float = 0.1 # b2inf — all-banks-negative fallback
    bailout_fallback_multiplier_upper: float = 0.9 # b2sup
    # Rate markdowns used by TAYLOR to derive r_depo, r_cbreserves, r_bonds from policy_rate.
    # bankmarkdown=1 → r_depo = 0 (no deposit interest paid by banks in baseline).
    deposit_markdown: float = 1.0             # bankmarkdown — dsk_constant.h:170
    cb_reserve_markdown: float = 0.33         # centralbankmarkdown — dsk_constant.h:174
    # flag_bonds=1 → r_bonds = r*(1-bondsmarkdown); flag_bonds=2 → r_bonds = 0.01 fixed
    bonds_rate_rule: int = 1                  # flag_bonds — dsk_flag.h:182
    # flag_mtm=0 → spread_marktomarket = 0 always (no mark-to-market premium)
    mark_to_market_rule: int = 0              # flag_mtm — dsk_flag.h:21
    gamma_bd: float = 1.0
    beta_basel: float = 1.0           # leverage coefficient in buffer rule (experiment_setting.cpp:127)
    wage_max_change: float = 0.5
    credit_max_for_investment: float = 2.0
    s1_entrant_capital_upper: float = 0.9
    s1_entrant_capital_lower: float = 0.1
    s2_entrant_capital_upper_alt: float = 0.9
    s2_entrant_capital_lower_alt: float = 0.1
    inv_channel_uu5a: float = -0.15
    inv_channel_uu6a: float = 0.15
    inv_channel_uu5b: float = -0.15
    inv_channel_uu6b: float = 0.15
    staggered_price_prob: float = 0.25
    weak_trend_rule_param: float = 0.4
    strong_trend_rule_param: float = 1.3
    laa_rule_param: float = 1.0
    adaptive_expect_param: float = 0.65
    laa_weight: float = 0.5
    switch_memory_param: float = 0.7
    switch_intensity_of_choice: float = 0.4
    switch_inertia: float = 0.7
    n_expectation_rules: int = 5

    # --- §5 DSK Energy & Climate Constants ---
    fuel_to_emissions_factor: float = 1100.0
    fuel_to_electricity_equivalence: float = 0.3
    carbon_tax_sector1_scale: float = 0.0
    carbon_tax_sector2_scale: float = 0.0
    carbon_tax_energy_scale: float = 0.0
    # carbon_tax_revenue_allocation: fractions going to [gov budget, unemployment, RnD elec, RnD S1]
    carbon_tax_revenue_allocation: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 1.0])
    energy_rd_share_of_revenue: float = 0.01
    dirty_rd_share_init: float = 0.6
    green_plant_payback_threshold: int = 40
    plant_lifetime_years: int = 60
    green_expansion_quota: float = 0.2
    green_replacement_quota: float = 0.1
    dirty_replacement_quota: float = 0.1
    n_plants_no_hurrycost_min: float = 1500.0
    n_plants_replace_min: float = 1500.0
    energy_demand_history_factor: float = 1.03
    rd_coefficient_dirty_energy: float = 0.02
    rd_coefficient_clean_energy: float = 0.02
    rd_coefficient_univ_green: float = 6.666666666666667e-4  # = 0.02 / 30
    dirty_fuel_eff_innov_lower: float = -0.08
    dirty_fuel_eff_innov_upper: float = 0.08
    dirty_emission_innov_lower: float = -0.20
    dirty_emission_innov_upper: float = 0.20
    dirty_buildcost_innov_lower: float = -0.08
    dirty_buildcost_innov_upper: float = 0.08
    green_buildcost_innov_lower_init: float = -0.24
    green_buildcost_innov_upper_init: float = 0.24
    s2_energy_eff_innov_lower: float = -0.15
    s2_energy_eff_innov_upper: float = 0.15
    s1_energy_eff_innov_lower: float = -0.15
    s1_energy_eff_innov_upper: float = 0.15
    s2_proc_emission_innov_lower: float = -0.05
    s2_proc_emission_innov_upper: float = 0.05
    s1_proc_emission_innov_lower: float = -0.05
    s1_proc_emission_innov_upper: float = 0.05
    s1_elfrac_innov_lower: float = -0.15
    s1_elfrac_innov_upper: float = 0.15
    disaster_a0: float = 1.0
    disaster_b0: float = 100.0
    time_shock_start: int = 200

    # --- §6 C-ROADS Climate Box ---
    climate_call_frequency: int = 1
    dt_economy_years: float = 1.0
    dt_climate_years: float = 1.0         # = climate_call_frequency * dt_economy_years
    n_climate_iterations: int = 5
    n_ocean_layers: int = 5
    # depth of ocean layers in metres, top first: [100, 300, 300, 1300, 1800]
    ocean_layer_depths_m: list = field(default_factory=lambda: [100, 300, 300, 1300, 1800])
    ocean_carbon_pre_ind_per_m: float = 10.2373
    reveille_factor_default: float = 9.7
    reveille_concentration_sensitivity: float = 3.92
    ocean_carbon_upper_ref: float = 1023.73       # = Con00 * laydep[0]
    ocean_carbon_upper_ref_T_sensitivity: float = 0.003
    eddy_diffusion_m2_per_year: float = 4400.0
    atmos_carbon_pre_ind: float = 590.0
    npp_reference: float = 85.1771
    fertilization_effect: float = 0.42
    heatstress_effect_on_npp: float = -0.01
    humus_fraction_of_decay: float = 0.428
    biosphere_decay_time_years: float = 10.6
    humus_decay_time_years: float = 27.8
    biosphere_pre_ind_stock: float = 902.877      # = NPP0 * biotime
    humus_pre_ind_stock: float = 1013.47          # = humfrac * biom0 * humtime / biotime
    climate_sensitivity_K_per_doubling: float = 3.015
    radiative_forcing_co2_w_per_m2: float = 5.35
    outgoing_radiation_w_per_m2_per_k: float = 1.23  # = 1.23 * 3.015 / climsens
    non_co2_forcing_factor: float = 1.12
    sea_surface_fraction: float = 0.708
    water_heat_capacity_j_per_m3: float = 4.23e6
    seconds_per_year: float = 31557600.0          # = 365.25 * 24 * 3600
    # 2010 initial conditions (flag_nonCO2_force=0 branch)
    atmos_carbon_init_2010: float = 809.9168
    ocean_carbon_init_2010: list = field(
        default_factory=lambda: [1051.0, 3126.0, 3103.0, 13329.0, 18429.0]
    )
    ocean_heat_init_2010: list = field(
        default_factory=lambda: [3.3841e8, 6.5175e8, 3.7094e8, 2.2604e8, 0.1719e8]
    )
    ocean_temp_init_2010: list = field(
        default_factory=lambda: [0.8000, 0.5136, 0.2923, 0.0411, 0.0023]
    )
    t_mixed_init_2010: float = 0.8000
    biosphere_carbon_init_2010: float = 996.7183
    humus_carbon_init_2010: float = 1080.7
    # 2020 initial conditions (active default)
    atmos_carbon_init_2020: float = 864.6616
    ocean_carbon_init_2020: list = field(
        default_factory=lambda: [1056.0, 3136.0, 3110.0, 13334.0, 18429.0]
    )
    ocean_heat_init_2020: list = field(
        default_factory=lambda: [4.5922e8, 8.9026e8, 5.1279e8, 3.2073e8, 0.2518e8]
    )
    ocean_temp_init_2020: list = field(
        default_factory=lambda: [1.0856, 0.7015, 0.4041, 0.0583, 0.0033]
    )
    t_mixed_init_2020: float = 1.0856
    biosphere_carbon_init_2020: float = 1014.7
    humus_carbon_init_2020: float = 1095.0
    emissions_first_year_gtc: float = 12.0
    temp_pre_industrial_global_mean: float = 14.0
    shock_beta_a: float = 1.0          # a_0 — alpha of disaster beta distribution
    shock_beta_b: float = 100.0        # b_0 — beta of disaster beta distribution
    nordhaus_damage_coefficient: float = 0.00236  # a2_nord — Nordhaus damage scale
    nordhaus_damage_exponent: float = 2.0          # a3_nord — Nordhaus damage exponent
    cumulative_emissions_init_gtc: float = 493.0
    temp_cum_emissions_intercept: float = -0.2674
    temp_cum_emissions_slope: float = 0.0018

    # --- §7 DSK Initialization Constants ---
    energy_need_init: float = 0.13333333333333333  # = 0.2 / 1.5
    s1_energy_need_init_factor: float = 2000.0      # = 1000.0 * 2.0
    env_filthiness_init: float = 300000.0
    electrification_fraction_init_s1: float = 0.3
    energy_cost_init_box_off: float = 0.001
    green_capacity_share_init: float = 0.0
    fossil_fuel_price_init: float = 0.02            # = 0.03 / 1.5
    electricity_price_max_step_change: float = 2.0
    energy_markup_init: float = 0.1                 # = fossil_fuel_price_init * 5
    dirty_plant_one_over_eff_init: float = 2.5
    energy_emissivity_ratio_init: float = 1.0
    dirty_plant_build_cost_init: float = 2.0        # = A_de0 * pf0 * life_plant * 2/3
    green_plant_build_cost_init: float = 10.0       # = A_de0 * pf0 * life_plant * 5/3 * 2
    fuel_labour_cost_fraction: float = 0.6
    elfrac_floor: float = 0.0
    elfrac_ceil: float = 1.0
    s1_energy_need_floor: float = 133.33333333333334  # = energy_need_init * s1_energy_need_init_factor / 2
    s2_energy_need_floor: float = 0.03333333333333333  # = energy_need_init / 4
    s1_proc_emission_floor: float = 0.0
    s2_proc_emission_floor: float = 0.0
    dirty_plant_inv_eff_floor: float = 1.6
    dirty_plant_emission_floor: float = 550.0       # = fuel_to_emissions_factor * energy_emissivity_ratio_init / 2
    dirty_plant_emission_ceil: float = 1650.0       # = fuel_to_emissions_factor * energy_emissivity_ratio_init * 1.5
    dirty_plant_build_cost_floor_init: float = 1.0  # = dirty_plant_build_cost_init / 2
    green_plant_build_cost_floor_init: float = 1.0  # = dirty_plant_build_cost_init / 2
    green_plant_build_cost_state_rd_floor: float = 3.3333333333333335  # = green_plant_build_cost_init / 3
    green_plant_build_cost_govt_floor_init: float = 3.3333333333333335

    # --- §8 Flags (baseline values from dsk_flag.h) ---
    write_micro_max_mc: int = 10000
    use_dskqe: int = 1
    use_mark_to_market: int = 0
    mtm_spread_type: int = 0
    bonds_portfolio_allocation: int = 0
    enable_climate_tech: int = 1
    allow_proc_emissions_s2: int = 0
    allow_proc_emissions_s1: int = 0
    dirty_emissions_per_fuel_variable: int = 0
    fuel_to_elec_rule: int = 1
    fuel_to_elec_innovation_rule: int = 0
    energy_nominal_demand_lookback: int = 0
    green_expansion_constraint_mode: int = 1
    brown_quota_tolerant: int = 1
    energy_premature_replacement_mode: int = 2
    replaced_plants_scrapped: int = 0
    brown_can_replace_brown: int = 0
    electricity_bid_includes_fixed: int = 0
    imitation_distance_metric: int = 1
    use_user_emissions_scenario: int = 0
    include_non_co2_forcing: int = 1
    use_cumulative_emissions_simple: int = 0
    apply_carbon_tax_to_firm_costs: int = 1
    allow_energy_innovation_in_spinup: int = 0
    climate_shock_type: int = 0
    cap_shock_burden_carrier: int = 0
    endogenous_dirty_rd_share: int = 1
    enable_population_growth: int = 0
    disable_strong_trend_rule: int = 0
    entry_expectation_rule: int = 1
    enable_heterogeneous_expectations: int = 0
    expectation_rule: int = 0
    balanced_budget_rule: int = 0
    bonds_payment_rule: int = 1
    debt_crisis_only_some_vars_saved: int = 0
    bailout_rule: int = 0
    taylor_rule_variant: int = 2
    wage_rule: int = 3
    endogenous_capital_buffer: int = 1
    pareto_client_distribution: int = 1
    remunerate_negative_debt: int = 1
    lagged_productivity_for_cpi_am: int = 0
    deposit_distribution_rule: int = 0
    entrant_initialization_rule: int = 5
    total_credit_rule: int = 2
    bank_interest_rate_rule: int = 2
    banks_force_saved_first_100: int = 0
    deposit_insurance: int = 0
    loan_to_value_binding: int = 1
    tax_base_rule: int = 2
    check_new_credit_parts: int = 1
    record_exit_bad_debt: int = 1
    remunerate_bank_reserves: int = 1
    count_s1_interest_revenue: int = 0
    sterilize_bank_failure: int = 0
    credit_for_negative_cashflow: int = 0
    credit_allocation_rule: int = 0
    frontier_type: int = 2
    frontier_exogenous_mechanism: int = 3
    patent_mode: int = 0
    entry_random_copy_scope: int = 0
    write_debug_file: int = 0
    machine_firms_paid_if_client_dies: int = 1
    s1_firms_persist_with_negative_w: int = 1
    s1_production_unbound_by_finance: int = 1
    scrap_when_cost_above_price: int = 0
    consumption_rule: int = 2
    national_accounts_consumption_rule: int = 0
    gdp_weights_i_c: int = 0
    rd_real_vs_nominal: int = 1
    extra_labour_force: int = 0
    verbose: int = 0
    tech_change_type: int = 2
    exogenous_tech_change_kind: int = 1
    flag_def: int = 1
    bonds_allocation_rule: int = 1
    endogenous_bank_markup: int = 0
    staggered_pricing: int = 0
    keynes_rule_mode: int = 0
    downward_wage_rigidity: int = 0
