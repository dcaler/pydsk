# NAME_MAP — Canonical C++ → Python Translation Table

This document is the **canonical reference** for translating every meaningful symbol in the Wieners 2025 DSK C++ codebase to its Python name in `dskPython2/`. It extends Appendix A of `PORT_PLAN_v3.md` to **every** constant, flag, and `extern` declaration in the four header files:

- `Code/Wieners_2025-main_slim/basecode/dsk_constant.h` — all `const` definitions
- `Code/Wieners_2025-main_slim/basecode/dsk_flag.h` — all `const int flag*` switches
- `Code/Wieners_2025-main_slim/basecode/dsk_globalvar.h` — all globals (defining declarations)
- `Code/Wieners_2025-main_slim/basecode/modules/module_{energy,finance,macro,climate}.h` — all `extern` declarations

Pure scratch dummies (`dummy1`, `dummy2`, `norm_dummy`, `intdummy*`, `cost1_dummy*`, `d1_*_dummy*`, `elfrac_diff*`, `dummy_replace_*`, `dummy_G_ge`) and pure loop indices (`i`, `j`, `t`, `tt`, `ii`, `jj`, `iii`, `jjj`, `kkk`, `lll`, `ttt`, `n`, `step`, `stepbis`, `cont`, `imax`, `tmax`, `jmax`, `ind_i`, `ind_tt`, `indforn`, `nextmax1`, `nextmax2`, `rni`, `rnf`, `flag`, `t00`, `nsize`, `newbroch`) are skipped.

## Scope tags

| Tag | Meaning |
|---|---|
| **G** | **Global** — single value shared by the whole simulation regardless of nation count (physics constants, behavioral knobs, dimensions, RNG, default fossil-fuel price). Lives on `GlobalParameters` or the `Simulation`. |
| **N** | **Nation** — varies per `Nation` instance (macro aggregates, fiscal/monetary policy, climate policy instruments, taxes, government accounts, labor market state, climate state when `flag_shared_climate=False`). Lives on `Nation` or a nation-owned object. |
| **A** | **Agent** — heterogeneous per agent (firm, bank, plant). Lives on `CapitalGoodFirm`, `ConsumptionGoodFirm`, `Bank`, `PowerPlant`, or in numpy arrays inside their owning `AgentSet`. |

For climate state we follow v3 Appendix B item 3: shared global atmosphere is the **default** (G), per-nation atmosphere survives only as a verification toggle.

For fossil-fuel price we follow v3 Appendix B item 7: global default (G), per-nation YAML override.

---

## 1. Constants — Simulation Dimensions & Time (`dsk_constant.h`)

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `N1` | `n1_capital_good_firms` | G | Number of capital good (machine-tool) firms |
| `N2` | `n2_consumption_good_firms` | G | Number of consumption-good firms |
| `T` | `total_steps` | G | Total simulation steps (annual) |
| `MC_RUNS` (macro) | `mc_runs` | G | Monte Carlo replicate count |
| `MC` | `mc_runs` | G | Alias of MC_RUNS as a long const |
| `forgoneobs` | `observation_lag` | G | Lag/frequency at which stuff is observed |
| `t_tune` | `t_energy_retune` | G | Step at which energy sector is re-tuned |
| `t_spinup_energy` | `t_spinup_energy` | G | Step until which nr of plants = demand automatically |
| `t_spinup` | `spin_up_steps` | G | Steps until no policy or climate modelling happens |
| `t_start_climbox` | `climate_start_step` | G | Step at which climate box starts (= `t_spinup + 20`) |
| `EXPERIMENT` (macro) | `experiment_id` | G | Experiment type identifier |
| `experiment` | `experiment_id` | G | Same as EXPERIMENT — type of experiment (0=baseline, 1=ψ3 wage, 2=ψ1 wage, ..., 9=aliq+wu) |

## 2. Constants — dskQE (financial extensions)

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `varphi` | `bonds_share_of_credit` | G | Fraction of total credit invested in bonds |
| `varpi1` | `solvency_weight_in_spread_1` | G | Weight of solvency in mark-to-market spread (component 1) |
| `varpi2` | `solvency_weight_in_spread_2` | G | Weight of solvency in mark-to-market spread (component 2) |

## 3. Constants — KS-Core Behavioral Parameters

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `nu` | `rd_budget_fraction` | G | R&D spending as fraction of sales — "Parametro spesa R&D" |
| `xi` | `innovation_imitation_split` | G | Allocates R&D between innovation and imitation (=1 → all innovation) |
| `xin0` | `innovation_sector1_share_initial` | G | Initial share of innov. R&D going to "sector 1 properties" (vs sector 2) |
| `xin1` | `innovation_sector1_share_scaling` | G | Scales change of the sector-1-properties share |
| `xinlim` | `innovation_sector1_share_limit` | G | Limit preventing the shift from becoming too big |
| `probinim` | `innov_imit_probability_scale` | G | 0..1; probability of innov/imit multiplier |
| `o11` | `rd_productivity_energy` | G | R&D productivity, innovation — energy properties |
| `o12` | `rd_productivity_labour` | G | R&D productivity, innovation — labour properties |
| `o1` | `rd_productivity_innovation_legacy` | G | R&D productivity innovation (outdated; only with non-default climate flags) |
| `o2` | `rd_productivity_imitation` | G | R&D productivity for imitation |
| `uu3` | `frontier_growth_machine_prod` | G | Exogenous growth rate of machine productivity frontier |
| `uu4` | `frontier_growth_process_prod` | G | Exogenous growth rate of process productivity frontier |
| `uu5` | `machine_prod_change_lower` | G | Lower bound of variation in machine productivity (outdated unless flag_clim_tech=0) |
| `uu6` | `machine_prod_change_upper` | G | Upper bound of variation in machine productivity |
| `uu1_a` | `labour_prod_s2_innov_lower` | G | Min rate of labour productivity change (sector 2) via innovation |
| `uu2_a` | `labour_prod_s2_innov_upper` | G | Max rate of labour productivity change (sector 2) via innovation |
| `uu1_ap` | `labour_prod_s1_innov_lower` | G | Min rate of labour productivity change (sector 1) via innovation |
| `uu2_ap` | `labour_prod_s1_innov_upper` | G | Max rate of labour productivity change (sector 1) via innovation |
| `uu7` | `entry_support_upper_endogenous` | G | Max support for entry of endogenous frontier |
| `N1f` | `n1_foreign_firms` | G | Number of foreign firms (= N1) — see v3 §6 for N≥2 handling |
| `uinf` | `frontier_innov_unif_lower` | G | Lower bound of uniform innovation on exogenous frontier |
| `usup` | `frontier_innov_unif_upper` | G | Upper bound of uniform innovation on exogenous frontier |
| `b_a1` | `beta_innov_alpha` | G | Beta α for innovation distribution |
| `b_b1` | `beta_innov_beta` | G | Beta β for innovation distribution |
| `b_a1_univ` | `beta_univ_alpha` | G | Beta α for government fundamental green ("university") research |
| `b_b1_univ` | `beta_univ_beta` | G | Beta β for government fundamental green research |
| `b_a2` | `beta_entry_alpha` | G | Beta α for entry distribution |
| `b_b2` | `beta_entry_beta` | G | Beta β for entry distribution |
| `b_a3` | `beta_frontier_alpha` | G | Beta α for exogenous frontier innovation |
| `b_b3` | `beta_frontier_beta` | G | Beta β for exogenous frontier innovation |
| `patdur` | `patent_duration` | G | Patent duration |
| `patbre` | `patent_breadth` | G | Patent breadth |
| `phi1` | `credit_max_rule` | G | Rule for max credit |
| `mi1` | `s1_markup` | G | Mark-up rate for sector 1 (machine-tool industry) |
| `Gamma` | `brochure_growth_factor` | G | New brochures sent = old matches × Γ (higher Γ → less turbulence) |
| `f1max` | `s1_antitrust_cap` | G | Antitrust ceiling for sector-1 market share (≥1 → off) |
| `chi` | `replicator_strength` | G | Replicator-dynamics strength for consumption-good industry |
| `omega1` | `competitiveness_price_weight` | G | Price weight in manufacturing competitiveness |
| `omega2` | `competitiveness_demand_weight` | G | Unsatisfied-demand weight in manufacturing competitiveness |
| `psi2` | `wage_productivity_response` | G | Wage response to productivity |
| `exit2` | `s2_exit_market_share_floor` | G | Market-share floor for sector-2 firm exit |
| `w_min` | `wage_subsistence` | G | Subsistence wage |
| `pmin` | `firm_price_floor` | G | Lower bound on firm prices |
| `theta` | `inventory_target_fraction` | G | Expected stock as fraction of demand |
| `u` | `capacity_utilization` | G | Capacity utilization rate |
| `alfa` | `investment_trigger` | G | Lower trigger threshold for investment |
| `alfasup` | `investment_trigger_upper` | G | Upper bound on investment trigger |
| `dim_mach` | `machine_size_units` | G | Size of one machine in output/value units |
| `eta` | `labour_supply_growth` | G | Labour-supply growth rate |
| `agemax` | `machine_max_age` | G | Max age (vintage) of a machine |
| `b` | `payback_threshold` | G | Payback threshold (= `5 * dim_mach` baseline) |
| `a` | `s1_productivity_scale` | G | Sector-1 productivity multiplier (1 sector-1 unit > 1 sector-2 unit) |
| `A0` | `productivity_init` | G | Initial productivity |
| `A0_sect1_scale` | `s1_initial_prod_scale` | G | Scale factor for initial sector-1 labour productivity |
| `LS0` | `labour_supply_init` | G | Initial total labour supply |
| `W10` | `s1_net_worth_init` | G | Initial sector-1 net worth |
| `W20` | `s2_net_worth_init` | G | Initial sector-2 net worth |
| `w0` | `wage_init` | G | Initial wage |
| `K0` | `capital_init` | G | Initial capital stock per firm |

## 4. Constants — Credit-Market Parameters

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `phi_b` | `credit_max_relative_networth` | G | Max credit as a function of firm relative net worth (∈ [0,1]) |
| `r_sterilizebankfailure` | `r_sterilize_bank_failure` | G | Rate avoiding bank failure with low rate (debug only) |
| `bankmarkdown` | `bank_deposit_markdown` | G | Mark-down on deposits relative to base rate |
| `centralbankmarkdown` | `cb_reserves_markdown` | G | Mark-down on CB-held reserves |
| `bank_saving_rate` | `bank_extra_reserve_ratio` | G | Bank reserves above the obligatory requirement |
| `bank_debtremittances_investment_rate` | `bank_debt_remit_reinvest_rate` | G | Fraction of debt remittances re-injected into credit |
| `toxicap` | `bailout_toxicap_share` | G | Share of bad debt bought during incumbent bail-out |
| `toxicap_G` | `bailout_toxicap_share_govt` | G | Share of bad debt bought during government bail-out |
| `basiccreditrate` | `credit_homogeneous_share` | G | Coefficient setting fraction of total credit allocated homogeneously to all firms |
| `d1` | `dividend_rate_s1` | G | Dividend rate for sector 1 |
| `d2` | `dividend_rate_s2` | G | Dividend rate for sector 2 |
| `db` | `dividend_rate_bank` | G | Dividend rate for banks |
| `gdrift` | `gdrift_const` | G | Drift parameter (used in govt-spending generators) |
| `gpar` | `gpar_const` | G | Companion parameter to gdrift |
| `uu` | `tech_progress_exogenous_growth` | G | Exogenous constant rate of technological progress |
| `uu1` | `process_innov_unif_lower_exog` | G | Lower bound for exogenous process-innovation uniform draw |
| `uu2` | `product_innov_unif_upper_exog` | G | Upper bound for exogenous product-innovation uniform draw |
| `beta1` | `myopic_expect_t1` | G | Weight on t-1 in myopic expectations |
| `beta2` | `myopic_expect_t2` | G | Weight on t-2 in myopic expectations |
| `beta3` | `myopic_expect_t3` | G | Weight on t-3 in myopic expectations |
| `beta4` | `myopic_expect_t4` | G | Weight on t-4 in myopic expectations |
| `beta` | `expect_accel_gd` | G | Accelerative GD expectations parameter |
| `delta5` | `expect_extrap_a` | G | Extrapolative expectations parameter A |
| `delta6` | `expect_extrap_b` | G | Extrapolative expectations parameter B |
| `initialbankequitymultiplier` | `bank_equity_init_multiplier` | G | Initial bank equity as a multiple of firm initial capital |
| `repayment_share` | `debt_repayment_fraction` | G | Fraction of net worth used to repay debt |
| `bonds_share` | `bonds_repayment_share` | G | Repayment share for bonds |
| `dep_rule` | `deposit_insurance_tax_rate` | G | Tax on bank profits funding deposit insurance |
| `share_rule` | `deposit_recovery_share` | G | Share of deposits recovered when bank fails |
| `pareto_a` | `pareto_alpha` | G | Pareto α value (for bank-client distribution) |
| `pareto_k` | `pareto_k` | G | Pareto k value |
| `pareto_p` | `pareto_p` | G | Pareto p value (= N2 doubled) |
| `d_cpi_target` | `inflation_target` | G | Target inflation per step (= 0.02/4 quarterly) |
| `ustar` | `unemployment_target` | G | Natural rate of unemployment |
| `w1sup` | `s1_entrant_networth_upper` | G | Upper bound for entrant net worth share (sector 1) |
| `w1inf` | `s1_entrant_networth_lower` | G | Lower bound for entrant net worth share (sector 1) |
| `w2sup` | `s2_entrant_networth_upper` | G | Upper bound for entrant net worth share (sector 2) |
| `w2inf` | `s2_entrant_networth_lower` | G | Lower bound for entrant net worth share (sector 2) |
| `ksup` | `s2_entrant_capital_upper` | G | Max capital share for entrant firms (sector 2) |
| `kinf` | `s2_entrant_capital_lower` | G | Min capital share for entrant firms (sector 2) |
| `bankmarkup_init` | `bank_markup_init` | G | Initialization of bank markup on loans |
| `k_const` | `k_const` | G | Generic financial-rule constant (used in TOTCREDIT) |
| `wu_low` | `unemployment_benefit_low` | G | Low unemployment-benefit rate (Keynes rule) |
| `wu_high` | `unemployment_benefit_high` | G | High unemployment-benefit rate (Keynes rule) |
| `aliq_low` | `aliq_low` | G | Low income-tax rate (Keynes rule) |
| `aliq_high` | `aliq_high` | G | High income-tax rate (Keynes rule) |
| `U_threshold` | `keynes_rule_unemployment_threshold` | G | Unemployment threshold for switching rules (flag_Keynes_Rule=1) |
| `rmin` | `rdeb_floor` | G | Min interest rate (when flagSPREAD=1) |
| `beta_r` | `beta_r` | G | Spread parameter (when flagSPREAD=1) |
| `alpha_entry` | `entry_random_copy_fraction` | G | Fraction of random-copy at entry (flagENTRY2=4) |
| `min_dw` | `wage_change_floor` | G | Minimum change in wages (flagWAGE2=1) |
| `nw` | `wage_staggering_period` | G | Periods between wage adjustments (flagWAGE=4) |
| `aliqw` | `wage_tax_rate` | G | Tax rate on wages |
| `beta_bonds` | `beta_bonds` | G | GOV_BUDGET coefficient when flag_bonds=3 |
| `taylor3` | `taylor3` | G | Taylor-rule coefficient 3 |
| `bondsmarkdown` | `bonds_markdown` | G | Bonds rate markdown |
| `gamma_BD` | `gamma_bd` | G | Bonds/dividend computation parameter |
| `mdw` | `wage_max_change` | G | Max wage variation |
| `phi2` | `credit_max_for_investment` | G | Max credit multiplier for investments |
| `b1sup` | `s1_entrant_capital_upper` | G | Upper bound — sector-1 entrant capital |
| `b1inf` | `s1_entrant_capital_lower` | G | Lower bound — sector-1 entrant capital |
| `b2sup` | `s2_entrant_capital_upper_alt` | G | Upper bound — sector-2 entrant capital (alt) |
| `b2inf` | `s2_entrant_capital_lower_alt` | G | Lower bound — sector-2 entrant capital (alt) |
| `uu5a` | `inv_channel_uu5a` | G | Possibly unused inv-channel variant lower a |
| `uu6a` | `inv_channel_uu6a` | G | Possibly unused inv-channel variant upper a |
| `uu5b` | `inv_channel_uu5b` | G | Possibly unused inv-channel variant lower b |
| `uu6b` | `inv_channel_uu6b` | G | Possibly unused inv-channel variant upper b |
| `p_stag` | `staggered_price_prob` | G | Per-step price-change probability (flagSTAG=1) |
| `w3` | `weak_trend_rule_param` | G | WTR rule weight (baseline 0.4) |
| `w4` | `strong_trend_rule_param` | G | STR rule weight (baseline 1.3) |
| `w5` | `laa_rule_param` | G | LAA rule weight (baseline 1) |
| `delta1` | `adaptive_expect_param` | G | ADA adaptive expectations parameter (0.65 from Hommes 2011) |
| `laa` | `laa_weight` | G | Weight between aggregate and idiosyncratic growth in LAA (0=idiosync, 1=aggregate) |
| `eta_switch` | `switch_memory_param` | G | Memory parameter for expectation-rule switching |
| `beta_switch` | `switch_intensity_of_choice` | G | Intensity-of-choice parameter for switching |
| `delta_switch` | `switch_inertia` | G | Inertia parameter for switching |
| `nb_rules` | `n_expectation_rules` | G | Number of expectation rules to choose from |

## 5. Constants — DSK Energy & Climate (`dsk_constant.h`)

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `ff2em` | `fuel_to_emissions_factor` | G | Emissions per unit of fossil fuel in the industry (× EM0 in energy firm) |
| `elconv` | `fuel_to_electricity_equivalence` | G | 1 unit of fuel ≈ `elconv` units of electricity in sector 1 |
| `t_CO2_I10` | `carbon_tax_sector1_scale` | G | Carbon tax scaling factor for sector 1 |
| `t_CO2_I20` | `carbon_tax_sector2_scale` | G | Carbon tax scaling factor for sector 2 |
| `t_CO2_en0` | `carbon_tax_energy_scale` | G | Carbon tax scaling factor for energy sector |
| `TCO2_1..4` (macro) | `t_co2_use_default` | G | Allocation of CO2 tax revenue (gov budget / unemployment / RnD electricity / RnD sector 1) |
| `t_CO2_use_0[4]` | `carbon_tax_revenue_allocation` | G | Default fractional split of CO2 tax revenue across 4 destinations |
| `share_RD_en` | `energy_rd_share_of_revenue` | G | Share of energy-firm revenue spent on R&D |
| `share_de_0` | `dirty_rd_share_init` | G | Initial share of energy R&D in dirty research (1 − share = green) |
| `payback_en` | `green_plant_payback_threshold` | G | Payback parameter for green plants |
| `life_plant` | `plant_lifetime_years` | G | Lifetime of energy plants |
| `exp_quota` | `green_expansion_quota` | G | Max expansion of green plants (fraction of K_ge) per period |
| `repl_quota_ge` | `green_replacement_quota` | G | Max expansion of green by replacement (fraction of K_ge) |
| `repl_quota_de` | `dirty_replacement_quota` | G | Max expansion of brown by replacement (fraction of K_de) |
| `N_hurrycost_min` | `n_plants_no_hurrycost_min` | G | Plants always buildable for expansion regardless of K_ge×exp_quota |
| `N_replace_min` | `n_plants_replace_min` | G | Plants always buildable for replacement regardless of quotas |
| `D_en_build_fac` | `energy_demand_history_factor` | G | Factor for historic demand expectation (energy build plan) |
| `o1_en_de` | `rd_coefficient_dirty_energy` | G | Innovation coefficient: dirty energy (P_success = 1 − exp(−o1·workers)) |
| `o1_en_ge` | `rd_coefficient_clean_energy` | G | Innovation coefficient: clean energy |
| `o1_univ_ge` | `rd_coefficient_univ_green` | G | Innovation coefficient for govt's fundamental green research |
| `uu1_eede` | `dirty_fuel_eff_innov_lower` | G | Lower limit, fuel-efficiency innovation gain (dirty energy) |
| `uu2_eede` | `dirty_fuel_eff_innov_upper` | G | Upper limit, fuel-efficiency innovation gain (dirty energy) |
| `uu1_efde` | `dirty_emission_innov_lower` | G | Lower limit, emission/fuel innovation gain (dirty energy) |
| `uu2_efde` | `dirty_emission_innov_upper` | G | Upper limit, emission/fuel innovation gain (dirty energy) |
| `uu1_cfde` | `dirty_buildcost_innov_lower` | G | Lower limit, building-cost innovation gain (dirty energy) |
| `uu2_cfde` | `dirty_buildcost_innov_upper` | G | Upper limit, building-cost innovation gain (dirty energy) |
| `uu1_ge0` | `green_buildcost_innov_lower_init` | G | Initial lower limit, green-plant-cost innovation gain (can shift via university research) |
| `uu2_ge0` | `green_buildcost_innov_upper_init` | G | Initial upper limit, green-plant-cost innovation gain |
| `uu1_ee` | `s2_energy_eff_innov_lower` | G | Lower limit, energy-efficiency innovation gain — consumption-good firm |
| `uu2_ee` | `s2_energy_eff_innov_upper` | G | Upper limit, energy-efficiency innovation gain — consumption-good firm |
| `uu1_eep` | `s1_energy_eff_innov_lower` | G | Lower limit, energy-efficiency innovation gain — tool firm |
| `uu2_eep` | `s1_energy_eff_innov_upper` | G | Upper limit, energy-efficiency innovation gain — tool firm |
| `uu1_ef` | `s2_proc_emission_innov_lower` | G | Lower limit, process-emission innovation gain — consumption-good firm |
| `uu2_ef` | `s2_proc_emission_innov_upper` | G | Upper limit, process-emission innovation gain — consumption-good firm |
| `uu1_efp` | `s1_proc_emission_innov_lower` | G | Lower limit, process-emission innovation gain — tool firm |
| `uu2_efp` | `s1_proc_emission_innov_upper` | G | Upper limit, process-emission innovation gain — tool firm |
| `uu1_elp` | `s1_elfrac_innov_lower` | G | Lower limit, electrification-fraction innovation gain — tool firm |
| `uu2_elp` | `s1_elfrac_innov_upper` | G | Upper limit, electrification-fraction innovation gain — tool firm |
| `a_0` | `disaster_a0` | G | Parameter in disaster generating function |
| `b_0` | `disaster_b0` | G | Parameter in disaster generating function |
| `time_shock` | `time_shock_start` | G | Period at which shocks start |

## 6. Constants — C-ROADS Climate Box

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `freqclim` | `climate_call_frequency` | G | Climate box called every `freqclim`-th step |
| `dtecon` | `dt_economy_years` | G | Length of economic time step (years; 1.0 = annual, 0.25 = quarterly) |
| `dtclim` | `dt_climate_years` | G | Time interval (years) between climate-box calls |
| `niterclim` | `n_climate_iterations` | G | Iterations for ocean–atmosphere carbon exchange |
| `ndep` | `n_ocean_layers` | G | Number of ocean layers |
| `laydep[ndep]` | `ocean_layer_depths_m` | G | Depth of ocean layers in metres (top first) |
| `Con00` | `ocean_carbon_pre_ind_per_m` | G | Pre-industrial ocean carbon content per metre depth |
| `rev0` | `reveille_factor_default` | G | Standard Reveille (buffer) factor |
| `revC` | `reveille_concentration_sensitivity` | G | Impact of C concentration on Reveille factor |
| `Conref` | `ocean_carbon_upper_ref` | G | Reference (pre-ind.) carbon in upper layer for atm.-ocean exchange |
| `ConrefT` | `ocean_carbon_upper_ref_T_sensitivity` | G | Temperature influence on Conref |
| `eddydif` | `eddy_diffusion_m2_per_year` | G | Eddy diffusion coefficient (m²/year) |
| `Cat0` | `atmos_carbon_pre_ind` | G | Pre-industrial atmospheric carbon (GtC) |
| `NPP0` | `npp_reference` | G | Reference net primary production (GtC/yr) |
| `fertil` | `fertilization_effect` | G | CO2 fertilization on NPP |
| `heatstress` | `heatstress_effect_on_npp` | G | Heat-stress effect of warming on NPP |
| `humfrac` | `humus_fraction_of_decay` | G | Fraction of decaying bio carbon entering humus |
| `biotime` | `biosphere_decay_time_years` | G | Carbon decay time in biosphere (years) |
| `humtime` | `humus_decay_time_years` | G | Carbon decay time in humus (years) |
| `biom0` | `biosphere_pre_ind_stock` | G | Pre-industrial stock of biospheric carbon (GtC) |
| `humm0` | `humus_pre_ind_stock` | G | Pre-industrial stock of humus carbon (GtC) |
| `climsens` | `climate_sensitivity_K_per_doubling` | G | Equilibrium warming per CO2 doubling (K) |
| `forCO2` | `radiative_forcing_co2_w_per_m2` | G | Radiative forcing from e-folding CO2 (W/m²) |
| `outrad` | `outgoing_radiation_w_per_m2_per_k` | G | Outgoing radiation per 1 K surface warming |
| `otherforcefac` | `non_co2_forcing_factor` | G | Multiplier on CO2 forcing accounting for non-CO2 |
| `seasurf` | `sea_surface_fraction` | G | Fraction of planet's surface covered by sea |
| `heatcap` | `water_heat_capacity_j_per_m3` | G | Heat capacity of water (J/m³) |
| `secyr` | `seconds_per_year` | G | Seconds per year |
| `Catinit0` | `atmos_carbon_init_2010` | G | Initial atmospheric carbon (2010 init) |
| `Coninit0[ndep]` | `ocean_carbon_init_2010` | G | Initial oceanic carbon per layer (GtC, 2010 init) |
| `Honinit0[ndep]` | `ocean_heat_init_2010` | G | Initial ocean heat content per layer (J/m², 2010 init) |
| `Toninit0[ndep]` | `ocean_temp_init_2010` | G | Initial ocean temperatures (above pre-ind, 2010 init) |
| `Tmixedinit0` | `t_mixed_init_2010` | G | Initial mixed-layer temperature (= `Toninit0[0]`) |
| `biominit0` | `biosphere_carbon_init_2010` | G | Initial carbon stock of biosphere (2010 init) |
| `humminit0` | `humus_carbon_init_2010` | G | Initial carbon stock of humus (2010 init) |
| `Catinit1` | `atmos_carbon_init_2020` | G | Initial atmospheric carbon (2020 init) |
| `Coninit1[ndep]` | `ocean_carbon_init_2020` | G | Initial oceanic carbon per layer (2020 init) |
| `Honinit1[ndep]` | `ocean_heat_init_2020` | G | Initial ocean heat content per layer (2020 init) |
| `Toninit1[ndep]` | `ocean_temp_init_2020` | G | Initial ocean temperatures (2020 init) |
| `Tmixedinit1` | `t_mixed_init_2020` | G | Initial mixed-layer temperature (2020 init) |
| `biominit1` | `biosphere_carbon_init_2020` | G | Initial carbon stock of biosphere (2020 init) |
| `humminit1` | `humus_carbon_init_2020` | G | Initial carbon stock of humus (2020 init) |
| `Emiss_yearly_0` | `emissions_first_year_gtc` | G | Emissions in first climate-box year (GtC) |
| `T_pre` | `temp_pre_industrial_global_mean` | G | Pre-industrial global mean surface temperature |
| `Cum_emissions_0` | `cumulative_emissions_init_gtc` | G | Initial cumulative emissions |
| `intercept_temp` | `temp_cum_emissions_intercept` | G | Intercept of cum-emissions vs temp relation |
| `slope_temp` | `temp_cum_emissions_slope` | G | Slope of cum-emissions vs temp relation |

## 7. Constants — DSK Initialization

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `A0_en` | `energy_need_init` | G | Initial energy need (= 1 / energy productivity) |
| `A0_en_sect1fac` | `s1_energy_need_init_factor` | G | Initial energy need for sector 1 = `A0_en × A0_en_sect1fac` |
| `A0_ef` | `env_filthiness_init` | G | Initial environmental filthiness (process emissions per unit) |
| `A0_el` | `electrification_fraction_init_s1` | G | Initial electrification fraction in sector 1 |
| `c0_en` | `energy_cost_init_box_off` | G | Initial energy cost (used when energy box turned OFF) |
| `K_ge0_perc` | `green_capacity_share_init` | G | Initial fraction of green plant capacity |
| `pf0` | `fossil_fuel_price_init` | G | Initial price of fossil fuel (see §7 below for runtime `pf` scope = N) |
| `delcen` | `electricity_price_max_step_change` | G | Max factor by which electricity price may change per step (often inactive) |
| `mi_en0` | `energy_markup_init` | G | Initial mark-up of energy producer (largely unused with fixed-cost bidding) |
| `A_de0` | `dirty_plant_one_over_eff_init` | G | 1/(initial thermal efficiency) for dirty plants |
| `EM0` | `energy_emissivity_ratio_init` | G | Ratio of energy-sector emissivity vs industry |
| `CF_de0` | `dirty_plant_build_cost_init` | G | Initial brown-plant build cost |
| `CF_ge0` | `green_plant_build_cost_init` | G | Initial green-plant build cost |
| `LDff_frac` | `fuel_labour_cost_fraction` | G | Fraction of fuel costs related to labour |
| `A1p_el_limlow` | `elfrac_floor` | G | Minimum electrification fraction (0) |
| `A1p_el_limupp` | `elfrac_ceil` | G | Maximum electrification fraction (1) |
| `A1p_en_limlow` | `s1_energy_need_floor` | G | Min energy needs in sector 1 |
| `A1_en_limlow` | `s2_energy_need_floor` | G | Min energy needs in sector 2 |
| `A1p_ef_limlow` | `s1_proc_emission_floor` | G | Min process emissions sector 1 |
| `A1_ef_limlow` | `s2_proc_emission_floor` | G | Min process emissions sector 2 |
| `A_de_limlow` | `dirty_plant_inv_eff_floor` | G | Lower limit on dirty-plant inverse efficiency |
| `EM_de_limlow` | `dirty_plant_emission_floor` | G | Minimum emissions per fuel unit (energy sector) |
| `EM_de_limupp` | `dirty_plant_emission_ceil` | G | Maximum emissions per fuel unit (energy sector) |
| `CF_de_limlow0` | `dirty_plant_build_cost_floor_init` | G | Minimum brown-plant build cost (uninflated) |
| `CF_ge_limlow0` | `green_plant_build_cost_floor_init` | G | Minimum green-plant build cost (uninflated) |
| `CF_ge_RDstate` | `green_plant_build_cost_state_rd_floor` | G | Lowest CF_ge achievable by state-funded RnD |
| `CF_ge_gov_limlow0` | `green_plant_build_cost_govt_floor_init` | G | Lowest CF_ge achievable by govt's own research (uninflated) |

---

## 8. Flags (`dsk_flag.h`)

All flags are global (G). Baseline values listed in the comment.

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `flag_writemicro` | `write_micro_max_mc` | G | If >0, write micro variables for the first `k` MC members |
| `flag_dskQE` | `use_dskqe` | G | dskQE switch (1=ON baseline). Per v3 Appendix B item 2 |
| `flag_mtm` | `use_mark_to_market` | G | Mark-to-market evaluation (0=off baseline) |
| `flag_spread_mtm` | `mtm_spread_type` | G | 0=share of bonds bought by CB (baseline); 1=unsatisfied supply |
| `flag_portfolioallocation` | `bonds_portfolio_allocation` | G | 0=KS15 (baseline); 1=allocate totcredit between bonds and loans by weights |
| `flag_clim_tech` | `enable_climate_tech` | G | 0=KS2013; 1=DSK with energy & climate (baseline) |
| `flag_EF_sector2` | `allow_proc_emissions_s2` | G | 0=zero process emissions in S2 (baseline); 1=allow |
| `flag_EF_sector1` | `allow_proc_emissions_s1` | G | 0=zero process emissions in S1 (baseline); 1=allow |
| `flag_ff2em_en` | `dirty_emissions_per_fuel_variable` | G | 0=fixed emissions/fuel (baseline); 1=allow variation |
| `flag_fuel_to_elec` | `fuel_to_elec_rule` | G | 0/1/2 substitution rules (1=baseline-recommended) |
| `flag_fuel_to_elec_inn` | `fuel_to_elec_innovation_rule` | G | 0=linear elfrac increment (baseline); 1=multiplicative |
| `flag_demand_energy` | `energy_nominal_demand_lookback` | G | n-period max demand lookback for plant building (0=baseline) |
| `flag_energy_exp` | `green_expansion_constraint_mode` | G | 0=no, 1=soft (baseline), 2=hard |
| `flag_brown_late` | `brown_quota_tolerant` | G | 1=tolerate late-brown precaution (baseline); 0=strict |
| `flag_early_plants` | `energy_premature_replacement_mode` | G | 0=demand>supply only; 1=cost-based; 2=cost-based with net-worth cap (baseline) |
| `flag_early_plants2` | `replaced_plants_scrapped` | G | 0=replaced plants become reserve (baseline); 1=scrapped |
| `flag_early_brown` | `brown_can_replace_brown` | G | 0=only green can replace (baseline); 1=brown can replace brown |
| `flag_electricity_bidding` | `electricity_bid_includes_fixed` | G | 0=operational-only + markup (baseline); 1=operational + fixed |
| `flag_techdist` | `imitation_distance_metric` | G | 0=cost-based; 1=norm-based (baseline if flag_clim_tech=1) |
| `flag_cheat_emiss` | `use_user_emissions_scenario` | G | 0=use DSK emissions (baseline); 1=user-defined scenario for climate testing |
| `flag_nonCO2_force` | `include_non_co2_forcing` | G | 0=no; 1=include non-CO2 forcing factor (baseline) |
| `flag_cum_emissions` | `use_cumulative_emissions_simple` | G | 0=standard C-ROADS (baseline); 1=simple cumulative-emissions/temp |
| `flag_tax_CO2` | `apply_carbon_tax_to_firm_costs` | G | 0=no firm-cost effect; 1=yes (baseline) |
| `flag_spinup_innov` | `allow_energy_innovation_in_spinup` | G | 0=no spin-up innovation (baseline); 1=allow |
| `flag_shocks` | `climate_shock_type` | G | 0=no shocks (baseline); 1..11 various shock targets |
| `flag_capshocks` | `cap_shock_burden_carrier` | G | 0=none (baseline); 1=cons-good firms; 2=cap-good firms |
| `flag_share_END` | `endogenous_dirty_rd_share` | G | 0=exogenous = share_de_0; 1=endogenous (baseline; TRANSITION paper) |
| `flag_pop_growth` | `enable_population_growth` | G | 0=no (baseline); 1=from t=101 |
| `flag_STR` | `disable_strong_trend_rule` | G | 0=STR included (baseline, nb_rules=5); 1=excluded (nb_rules=4) |
| `flagEXP_entry` | `entry_expectation_rule` | G | 0=uniform; 1=copy incumbent (baseline) |
| `flagEXP_switch` | `enable_heterogeneous_expectations` | G | 0=uniform rule (baseline); 1=heterogeneous + switching |
| `flagEXP` | `expectation_rule` | G | 0=naive (baseline); 1..7 myopic/ADA/extrap/WTR/STR/LAA |
| `flag_balancedbudget` | `balanced_budget_rule` | G | 0=none (baseline); 1..4 SGP / fiscal compact variants |
| `flag_bonds` | `bonds_payment_rule` | G | 0=no payment; 1=baseline; 2=fixed-rate (QE-like); 3=risk premium |
| `flag_debtcrisis` | `debt_crisis_only_some_vars_saved` | G | 0=baseline; 1=limited output during exploding-debt runs |
| `flagbailout` | `bailout_rule` | G | 0=full govt bailout (baseline); 1=none; 2=biggest-bank; 3=all surviving |
| `flagTAYLOR` | `taylor_rule_variant` | G | 1=inflation gap; 2=inflation+unemployment (baseline; taylor2=0); 3=Oeffner smoothing; 4=r_min + r(t) |
| `flagWAGE` | `wage_rule` | G | 0=Δunemployment; 1=level-ustar; 2=π-target; 3=π-target+gap (baseline); 4=staggered |
| `flagBUFFER` | `endogenous_capital_buffer` | G | 1=endogenous buffer in TOTCREDIT (baseline) |
| `flag_pareto` | `pareto_client_distribution` | G | 1=Pareto for clients-per-bank (baseline) |
| `flagDEBTREMUN` | `remunerate_negative_debt` | G | 1=negative debt remunerated at r_cbreserves (baseline) |
| `flagPRODLAG` | `lagged_productivity_for_cpi_am` | G | 0=baseline; 1=lagged values for cpi and Am(1) |
| `flagDEPOSITS` | `deposit_distribution_rule` | G | 0=baseline; 1=equal share; 2=proportional to bank market share |
| `flagENTRY2` | `entrant_initialization_rule` | G | 1..5 various entrant W/A/K rules; 6=baseline; default code value 5 |
| `flagtotalcredit` | `total_credit_rule` | G | 0=deposit multiplier; 1=min(mult, Basel); 2=Basel II only (baseline) |
| `flag_interest_rate` | `bank_interest_rate_rule` | G | 1=risk-premium ranking; 2=credit-class quartiles (baseline) |
| `flagtest` | `banks_force_saved_first_100` | G | 0=baseline; 1=banks saved first 100 periods |
| `flag_insurance` | `deposit_insurance` | G | 0=no insurance (baseline); 1=insurance based on share_rule |
| `flag_loantovalue` | `loan_to_value_binding` | G | 1=LTV is binding (baseline) |
| `flagTAX` | `tax_base_rule` | G | 2=firm+bank profits (baseline); 1=firm profits+wages; 0=firms+wages+banks |
| `flagchecknewparts` | `check_new_credit_parts` | G | Internal credit-mechanism validation flag |
| `flagturbulence` | `record_exit_bad_debt` | G | 1=track bad debt from exiting firms (baseline) |
| `flagreservesremuneration` | `remunerate_bank_reserves` | G | 1=baseline |
| `flagbankmachtoolrevenues` | `count_s1_interest_revenue` | G | 0=baseline; 1=count S1 interest revenue |
| `flagsterilizebankfailure` | `sterilize_bank_failure` | G | 0=baseline; 1=prevent failure with zero rate (debug) |
| `flagcreditforcf` | `credit_for_negative_cashflow` | G | 0=baseline |
| `flagallocatecredit` | `credit_allocation_rule` | G | 0=by NW/sales rating (baseline); 1=by NW+size |
| `flagFRONT` | `frontier_type` | G | 1=exogenous; 2=endogenous (baseline) |
| `flagFRONTEX` | `frontier_exogenous_mechanism` | G | 0..3 entry/innovation modes (3=baseline) |
| `flagPAT` | `patent_mode` | G | 0=off (baseline); 1=on; 2=on+breadth |
| `flagENTRY` | `entry_random_copy_scope` | G | 0=both sectors (baseline); 1=S2 only; 2=S1 only; 3=never |
| `flagbug` | `write_debug_file` | G | 0=baseline; 1=write debug file |
| `flagdie` | `machine_firms_paid_if_client_dies` | G | 1=baseline (always paid) |
| `flagdieW` | `s1_firms_persist_with_negative_w` | G | 1=baseline (don't die from finance) |
| `flagdieP` | `s1_production_unbound_by_finance` | G | 1=baseline (production not constrained) |
| `flagPC` | `scrap_when_cost_above_price` | G | 0=baseline; 1=scrap if c2(t)>p2(t-1) |
| `flagC` | `consumption_rule` | G | 0=work-or-die; 1=public spending; 2=unemployment subsidy (baseline) |
| `flagCN` | `national_accounts_consumption_rule` | G | 0=C≥Q2+N; 1=C=Q2+N (baseline) |
| `flagGDP` | `gdp_weights_i_c` | G | 0=baseline; 1=GDP weights I and C |
| `flagRD` | `rd_real_vs_nominal` | G | 0=nominal; 1=real (baseline) |
| `flagEXTRA` | `extra_labour_force` | G | 0=baseline; 1=extra workforce |
| `echo` | `verbose` | G | 0=quiet (baseline); 1=print messages |
| `flagTCGEN` | `tech_change_type` | G | 1=exogenous; 2=endogenous (baseline) |
| `flagTC` | `exogenous_tech_change_kind` | G | 1=stochastic (baseline); 2=deterministic |
| `flag_DEF` | `flag_def` | G | DFNRT12b correction flag |
| `bonds_rule` | `bonds_allocation_rule` | G | 0=by market share; 1=by profit share (baseline) |
| `flagSPREAD` | `endogenous_bank_markup` | G | 0=baseline; 1=endogenous in TOTCREDIT |
| `flagSTAG` | `staggered_pricing` | G | 0=baseline; 1=stagger price changes in MACH with prob `p_stag` |
| `flag_Keynes_Rule` | `keynes_rule_mode` | G | 0=off; 1=flexible wu_low/high; 2=flexible aliq_low/high |
| `flagWAGE2` | `downward_wage_rigidity` | G | 0=baseline; 1=downward rigidity |

---

## 9. Sector-1 (Capital-Good / Machine-Tool) Firm State

All variables in this section are **A (Agent)** — they live on `CapitalGoodFirm` instances managed by `CapitalGoodSector` (an `AgentSet`).

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `W1(2,N1)` | `cap_firm.net_worth` (current & prev) | A | Net worth |
| `S1(2,N1)` | `cap_firm.sales` | A | Sales |
| `NetWorthToSales1(N1)` | `cap_firm.net_worth_to_sales_ratio` | A | NW/Sales |
| `Deb1(2,N1)` | `cap_firm.debt` | A | Debt stock |
| `p1(2,N1)` | `cap_firm.price` | A | Machine price |
| `RD(2,N1)` | `cap_firm.rd_spending` | A | R&D budget |
| `size1(2,N1)` | `cap_firm.size` | A | Firm size |
| `f1(2,N1)` | `cap_firm.market_share` | A | Market share |
| `Q1(N1)` | `cap_firm.production` | A | Production (in machines) |
| `D1(N1)` | `cap_firm.demand` | A | Demand (in machines, not size-adjusted) |
| `tao(N1)` | `cap_firm.machine_vintage_index` | A | "Generazione macchinario" → vintage index |
| `A1(N1)` | `cap_firm.machine_productivity` | A | Productivity of machine sold (current technology) |
| `Anew(N1)` | `cap_firm.new_machine_productivity` | A | Productivity of new candidate machine |
| `A1inn(N1)` | `cap_firm.machine_productivity_innov` | A | Innovation outcome — machine productivity |
| `A1pinn(N1)` | `cap_firm.process_productivity_innov` | A | Innovation outcome — own process productivity |
| `A1imm(N1)` | `cap_firm.machine_productivity_imit` | A | Imitation outcome — machine productivity |
| `A1pimm(N1)` | `cap_firm.process_productivity_imit` | A | Imitation outcome — own process productivity |
| `Pi1(N1)` | `cap_firm.profit` | A | Profit |
| `Ld1(2,N1)` | `cap_firm.labour_demand` | A | Labour demand for production |
| `Ld1rd(N1)` | `cap_firm.labour_demand_rd` | A | Labour demand for R&D |
| `ee1(N1)` | `cap_firm.entry_flag` | A | Entry-flag vector |
| `ind_ee1(N1)` | `cap_firm.entry_index` | A | Entry-index vector |
| `nclient(N1)` | `cap_firm.n_clients` | A | Number of clients |
| `Debmax1(N1)` | `cap_firm.debt_max` | A | Maximum allowable debt |
| `debres1(N1)` | `cap_firm.debt_residual_line` | A | Residual credit line |
| `DebtInterests1(N1)` | `cap_firm.debt_interest_paid` | A | Interest paid to bank |
| `div1(N1)` | `cap_firm.dividends` | A | Dividends paid |
| `die(N1)` | `cap_firm.death_flag` | A | Death indicator |
| `c1(N1)` | `cap_firm.unit_production_cost` | A | Cost to produce one machine unit |
| `A1p(2,N1)` | `cap_firm.process_productivity` | A | Process (own labour) productivity |
| `RDin(N1)` | `cap_firm.rd_spend_innovation` | A | R&D spending on innovation |
| `RDin1(N1)` | `cap_firm.rd_spend_innov_s1_props` | A | R&D spend on sector-1 properties (labour productivity) |
| `RDin2(N1)` | `cap_firm.rd_spend_innov_s2_props` | A | R&D spend on sector-2 properties (machine quality) |
| `RDim(N1)` | `cap_firm.rd_spend_imitation` | A | R&D spending on imitation |
| `RDsucc1(N1)` | `cap_firm.rd_success_s1_props` | A | Machine-lifetime cost reduction from innovation, S1 props |
| `RDsucc2(N1)` | `cap_firm.rd_success_s2_props` | A | Machine-lifetime cost reduction from innovation, S2 props |
| `xin(N1)` | `cap_firm.innov_s1_share` | A | Per-firm fraction of innov RnD on S1 properties |
| `Inn1(N1)` | `cap_firm.innovated_s1` | A | Flag — innovated S1 props this step |
| `Inn2(N1)` | `cap_firm.innovated_s2` | A | Flag — innovated S2 props this step |
| `Inn(N1)` | `cap_firm.innovated` | A | Legacy flag — firm innovated this step |
| `Imm(N1)` | `cap_firm.imitated` | A | Flag — firm imitated this step |
| `Pat(N1)` | `cap_firm.patent_years_left` | A | Years remaining on patent |
| `flagA1(N1)` | `cap_firm.productivity_persistence_flag` | A | Flag for productivity-persistence output file |
| `A1f(N1)` | `foreign_firm.machine_productivity` | A | Foreign firms' machine productivity (v3 Appendix B item 6) |
| `A1pf(N1)` | `foreign_firm.process_productivity` | A | Foreign firms' production technology |
| `A1w(N1+N1f)` | `world_machine_productivity` | A | World (exogenous frontier) machine productivity |
| `A1pw(N1+N1f)` | `world_process_productivity` | A | World process productivity |
| `Patw(N1+N1f)` | `world_patent_remaining_duration` | A | Patent remaining duration including world firms |
| `Td(N1+1)` | `tech_distance` | A | Per-firm technological-distance vector (imitation) |
| `Tdw(N1+N1f+1)` | `tech_distance_world` | A | Per-firm tech-distance including world firms |
| `A(T,N1)` | `cap_firm.machine_vintage_productivity` | A | Productivity of machines existing across vintages (matrix per firm) |
| `C(T,N1)` | `cap_firm.machine_vintage_cost` | A | Cost of machines across vintages |
| `Match(N2,N1)` | `cap_firm.client_matching` | A | Brochure matching (firm i sends brochure to j) |
| `mat2d(T,N1)` | `cap_firm.vintage_aux` | A | Auxiliary matrix in technology rolls |
| `A_en(T,N1)` | `cap_firm.machine_energy_efficiency_vintage` | A | Energy efficiency of machines across vintages |
| `A_ef(T,N1)` | `cap_firm.machine_env_filthiness_vintage` | A | Environmental filthiness of machines across vintages |
| `A1_en(N1)` | `cap_firm.machine_energy_efficiency` | A | EE of machine when used in cons-good firm |
| `A1_ef(N1)` | `cap_firm.machine_env_filthiness` | A | EF of machine (process emissions per unit) |
| `A1p_en(N1)` | `cap_firm.process_energy_efficiency` | A | EE of own production technique |
| `A1p_ef(N1)` | `cap_firm.process_env_filthiness` | A | EF of own production technique |
| `A1p_el(N1)` | `cap_firm.process_electrification_fraction` | A | Electrification fraction of own production |
| `EE_inn(N1)` | `cap_firm.ee_innovation` | A | Energy-efficiency innovation outcome — machine |
| `EEp_inn(N1)` | `cap_firm.eep_innovation` | A | EE innovation — process |
| `EE_imm(N1)` | `cap_firm.ee_imitation` | A | EE imitation — machine |
| `EEp_imm(N1)` | `cap_firm.eep_imitation` | A | EE imitation — process |
| `EF_inn(N1)` | `cap_firm.ef_innovation` | A | EF innovation — machine |
| `EFp_inn(N1)` | `cap_firm.efp_innovation` | A | EF innovation — process |
| `EF_imm(N1)` | `cap_firm.ef_imitation` | A | EF imitation — machine |
| `EFp_imm(N1)` | `cap_firm.efp_imitation` | A | EF imitation — process |
| `ELp_inn(N1)` | `cap_firm.elfrac_innovation` | A | Electrification innov outcome (process) |
| `ELp_imm(N1)` | `cap_firm.elfrac_imitation` | A | Electrification imit outcome (process) |
| `D1_en(2,N1)` | `cap_firm.electricity_demand` | A | Electricity demand (sector-1 firms) |
| `D1_ff(2,N1)` | `cap_firm.fossil_fuel_demand` | A | Fossil-fuel demand (sector-1 firms) |
| `D1_en_act(N1)` | `cap_firm.electricity_demand_actual` | A | Realised electricity demand (current step) |
| `D1_ff_act(N1)` | `cap_firm.fossil_fuel_demand_actual` | A | Realised fossil-fuel demand (current step) |
| `Emiss1(N1)` | `cap_firm.emissions` | A | Total emissions per cap-good firm |
| `Emiss1FF(N1)` | `cap_firm.emissions_fossil` | A | Emissions from fuel use only |
| `Emiss1EF(N1)` | `cap_firm.emissions_process` | A | Emissions from process (env. filthiness) |
| `shocks_machprod(N1)` | `cap_firm.shock_machine_productivity` | A | Climate shock — machine productivity |
| `shocks_techprod(N1)` | `cap_firm.shock_tech_productivity` | A | Climate shock — process productivity |

## 10. Sector-2 (Consumption-Good) Firm State

All **A (Agent)** — on `ConsumptionGoodFirm` inside `ConsumptionGoodSector`.

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `D2(5,N2)` | `cons_firm.demand_history` | A | Demand history (5 lags) |
| `De(3,N2)` | `cons_firm.expected_demand` | A | Expected demand |
| `f2(3,N2)` | `cons_firm.market_share` | A | Market share |
| `E2(2,N2)` | `cons_firm.competitiveness` | A | Competitiveness |
| `c2(2,N2)` | `cons_firm.unit_cost` | A | Unit production cost |
| `Q2(2,N2)` | `cons_firm.production` | A | Production |
| `N(2,N2)` | `cons_firm.inventory` | A | Inventory of consumption goods ("scorte") |
| `Nm(2,N2)` | `cons_firm.inventory_money` | A | Inventory in money terms |
| `W2(2,N2)` | `cons_firm.net_worth` | A | Net worth (effectively liquid assets) |
| `NetWorthToSales2(N2)` | `cons_firm.net_worth_to_sales_ratio` | A | NW/Sales |
| `size2(2,N2)` | `cons_firm.size` | A | Firm size |
| `I(2,N2)` | `cons_firm.investment_total` | A | Total investment (size-units, not #machines) |
| `EI(2,N2)` | `cons_firm.investment_expansion` | A | Realised expansion investment |
| `SI(2,N2)` | `cons_firm.investment_substitution` | A | Realised substitution investment |
| `S2(2,N2)` | `cons_firm.sales` | A | Sales/turnover |
| `Deb2(2,N2)` | `cons_firm.debt` | A | Debt stock |
| `CreditDemand(1,N2)` | `cons_firm.credit_demand` | A | Credit demand this period |
| `p2(2,N2)` | `cons_firm.price` | A | Price |
| `mu2(2,N2)` | `cons_firm.markup` | A | Markup vector |
| `DebtInterests2(N2)` | `cons_firm.debt_interest_paid` | A | Interest paid to bank |
| `DebtRemittances2(N2)` | `cons_firm.debt_repaid` | A | Principal repaid to bank |
| `DebtService(N2)` | `cons_firm.debt_service` | A | Total interest + repayment |
| `baddebt(N2)` | `cons_firm.bad_debt` | A | Bad debt left for the bank |
| `Em2(2)` | `cons_sector.mean_competitiveness` | N | Sector-level mean competitiveness (consumption industry) |
| `EId(N2)` | `cons_firm.desired_expansion_investment` | A | Desired expansion investment |
| `SId(N2)` | `cons_firm.desired_substitution_investment` | A | Desired substitution investment |
| `SIp(N2)` | `cons_firm.demanded_substitution_prudential` | A | Substitution investment after prudential limits |
| `EIp(N2)` | `cons_firm.demanded_expansion_prudential` | A | Expansion investment after prudential limits |
| `Ip(N2)` | `cons_firm.demanded_investment_prudential` | A | Total demanded investment after prudential limits |
| `A2(N2)` | `cons_firm.mean_productivity` | A | Average productivity over machine stock |
| `A2e(2,N2)` | `cons_firm.effective_productivity` | A | Effective productivity used in production |
| `A2temp(N2)` | `cons_firm.mean_productivity_temp` | A | Temp for flagPRODLAG=1 |
| `Ktemp(N2)` | `cons_firm.capital_temp` | A | Temp capital if flagPRODLAG=1 |
| `c2e(N2)` | `cons_firm.unit_cost_effective` | A | Effective unit cost |
| `Ld2(2,N2)` | `cons_firm.labour_demand_for_production` | A | Labour demand for production |
| `l2(N2)` | `cons_firm.unsatisfied_demand` | A | Demand the firm could not satisfy |
| `n_mach(N2)` | `cons_firm.n_machines` | A | Number of machines firm j owns |
| `n_mach_temp(N2)` | `cons_firm.n_machines_temp` | A | Temp for flagPRODLAG=1 |
| `Qd(N2)` | `cons_firm.production_desired` | A | Desired production |
| `K(N2)` | `cons_firm.capital_stock` | A | Capital (in machine-size units) |
| `Kd(N2)` | `cons_firm.capital_desired` | A | Desired capital |
| `Ktrig(N2)` | `cons_firm.capital_trigger_threshold` | A | Investment-trigger threshold |
| `Ktop(N2)` | `cons_firm.capital_ceiling` | A | Max capital |
| `Ke(N2)` | `cons_firm.capital_at_entry` | A | Capital of entrant firm (0 if incumbent) |
| `Pi2(N2)` | `cons_firm.profit` | A | Profit |
| `ueff(N2)` | `cons_firm.utilization_rate` | A | Capacity utilization rate |
| `ee2(N2)` | `cons_firm.entry_flag` | A | Entry flag vector |
| `ind_ee2(N2)` | `cons_firm.entry_index` | A | Entry index |
| `Q2temp(N2)` | `cons_firm.production_temp` | A | Auxiliary production |
| `f_temp2(N2)` | `cons_firm.market_share_temp` | A | Auxiliary market share |
| `D_temp2(N2)` | `cons_firm.demand_temp` | A | Auxiliary demand |
| `dN(N2)` | `cons_firm.inventory_change` | A | Change in inventory |
| `dNm(N2)` | `cons_firm.inventory_change_money` | A | Change in inventory (money) |
| `Debmax2(N2)` | `cons_firm.debt_max` | A | Maximum allowable debt |
| `debres2(N2)` | `cons_firm.debt_residual_line` | A | Residual credit line |
| `fornit(N2)` | `cons_firm.supplier_index` | A | Index of current supplier (capital-good firm) |
| `Cmach(N2)` | `cons_firm.machine_total_cost` | A | Cost paid for new machines |
| `CmachEI(N2)` | `cons_firm.machine_cost_expansion` | A | Machine cost for expansion only |
| `CmachSI(N2)` | `cons_firm.machine_cost_substitution` | A | Machine cost for scrapping only |
| `Ne(N2)` | `cons_firm.inventory_expected_post_sale` | A | Expected post-sale inventory |
| `mol(N2)` | `cons_firm.gross_operating_margin` | A | Gross operating margin |
| `CF(N2)` | `cons_firm.cash_flow` | A | Cash flow |
| `dt(N2)` | `cons_firm.cash_flow_aux` | A | Auxiliary cash-flow vector |
| `div2(N2)` | `cons_firm.dividends` | A | Dividends paid |
| `flagA2(N2)` | `cons_firm.productivity_persistence_flag` | A | Flag for productivity output file |
| `Kexp(N2)` | `cons_firm.entrant_capital_expectation_flag` | A | Flag — entrant K variable, sector 2 |
| `p_change(N2)` | `cons_firm.price_change_event` | A | Per-firm price-change event (flagSTAG=1) |
| `D2_en(3,N2)` | `cons_firm.electricity_demand` | A | Electricity demand history |
| `D2_en_act(N2)` | `cons_firm.electricity_demand_actual` | A | Realised electricity demand |
| `A2e_en(N2)` | `cons_firm.effective_energy_efficiency` | A | Effective EE of machines |
| `A2e_ef(N2)` | `cons_firm.effective_env_filthiness` | A | Effective EF of machines |
| `A2_en(N2)` | `cons_firm.mean_energy_efficiency` | A | Mean energy efficiency |
| `A2_ef(N2)` | `cons_firm.mean_env_filthiness` | A | Mean environmental filthiness |
| `Emiss2(N2)` | `cons_firm.emissions` | A | Emissions per cons-good firm |
| `shocks_capstock(N2)` | `cons_firm.shock_capital_stock` | A | Climate shock — capital stock |
| `shocks_invent(N2)` | `cons_firm.shock_inventories` | A | Climate shock — inventories |

### MachineStock tensor (per-firm in Python)
| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `g[T][N1][N2]` | `cons_firm.machines.count[vintage, supplier]` | A | Machine count, per firm — see v3 §3.2-3.3 |
| `g_pb[T][N1][N2]` | `cons_firm.machines.count_payback_candidates` | A | Scrapping candidate counts |
| `C_pb[T][N1][N2]` | `cons_firm.machines.cost_payback_candidates` | A | Scrapping candidate costs |
| `g_c[T][N1][N2]` | `cons_firm.machines.count_for_cost` | A | Counts used in production-cost calc |
| `gtemp[T][N1][N2]` | `cons_firm.machines.count_temp` | A | Temporary scratch (Python: avoid persistence) |
| `age[T][N1][N2]` | `cons_firm.machines.age` | A | Machine ages (integer matrix) |

---

## 11. Banking-Sector State

All **A (Agent)** for per-bank vectors, **N (Nation)** for aggregates. Lives on `Bank` instances inside `BankingSector`.

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `NB` | `n_banks` | N | Number of banks per nation (per-experiment double) |
| `NBtemp` | `n_banks_temp` | N | Temp value during initialization |
| `NB_long` | `n_banks_long` | N | Long-int version of NB |
| `NL(NB)` | `bank.n_links_target` | A | Target number of clients (symmetric init) |
| `bonds_dem(NB)` | `bank.bonds_demand` | A | Per-bank bonds demand |
| `bonds_dem_share(NB)` | `bank.bonds_demand_share` | A | Per-bank share of bonds demand |
| `bonds_NO_marktomarket(NB)` | `bank.bonds_not_marked` | A | Bonds not valued mark-to-market |
| `bonds_dem_tot` | `bonds_demand_total` | N | Total bonds demanded |
| `bonds_sup` | `bonds_supply` | N | Bonds supply |
| `bonds_sup_tot` | `bonds_supply_total` | N | Total bonds supply |
| `spread_marktomarket` | `mtm_spread` | N | Mark-to-market spread |
| `r_marktomarket` | `mtm_rate` | N | Mark-to-market discount rate |
| `bankreserve_requirement_rate` | `bank_reserve_requirement_rate` | N | Statutory reserve requirement |
| `BankCredit(NB)` | `bank.credit_capacity` | A | Max credit a bank may give |
| `CreditSupply(NB)` | `bank.credit_supply` | A | Credit supply |
| `MultiplierBankCredit(NB)` | `bank.credit_supply_multiplier` | A | Credit via deposit multiplier |
| `BaselBankCredit(NB)` | `bank.credit_supply_basel` | A | Credit via Basel II rule |
| `BankEquity(2,NB)` | `bank.equity` | A | Bank equity (current & prev) |
| `BankDeposits(NB)` | `bank.deposits` | A | Total deposits at bank |
| `MonetaryBase(NB)` | `bank.monetary_base` | A | Monetary base (= initial deposits) |
| `BankReserves(NB)` | `bank.reserves` | A | Bank reserves |
| `BankProfits(NB)` | `bank.profit` | A | Bank profit |
| `BankProfits_temp(NB)` | `bank.profit_temp` | A | Auxiliary profit |
| `BankProfits_all_temp` | `bank_profits_all_temp` | N | Aggregate temp |
| `DebtRemittancestot(NB)` | `bank.debt_repayments_total` | A | Total debt repayments to bank |
| `BankCash(2,NB)` | `bank.cash` | A | Bank cash (current & prev) |
| `BankCashEmployed(NB)` | `bank.cash_employed` | A | Cash employed in lending |
| `Divb(NB)` | `bank.dividends` | A | Bank dividends |
| `Gbailout(NB)` | `bank.govt_bailout` | A | Govt bailout received |
| `Debtot(NB)` | `bank.client_debt_total` | A | Total debt of bank's clients |
| `Debtot1(NB)` | `bank.client_debt_total_s1` | A | Total client debt — sector 1 |
| `Debtot2(NB)` | `bank.client_debt_total_s2` | A | Total client debt — sector 2 |
| `Debtot2_temp(NB)` | `bank.client_debt_total_s2_temp` | A | Temporary debt aggregate |
| `FakeNetWorthtoSales2(N2,NB)` | `bank.firm_credit_worthiness` | A | Per-bank firm credit-worthiness matrix |
| `TransNetWorthtoSales2(N2)` | `bank.firm_credit_worthiness_temp` | A | Transitory vector to find max |
| `NWS2_rating(N2,NB)` | `bank.firm_rating` | A | Per-bank rating from NW/sales |
| `NWS2_max` | `firm_nws_max` | N | Max NWS ratio across firms |
| `NWS2_max_index` | `firm_nws_max_index` | N | Index of firm with max NWS |
| `rated_firm_2` | `firm_rated_index` | N | Index of firm currently being rated |
| `baddebt_matrix` (in modules: `Matrix baddebt(N2,NB)`) | `bank.bad_debt_per_firm` | A | Bad debt per firm per bank |
| `BadDebttot(NB)` | `bank.bad_debt_accumulated` | A | Accumulated bad debt |
| `BadDebttot_temp(NB)` | `bank.bad_debt_this_period` | A | Bad debt of the current period |
| `BasicCreditLines2(N2,NB)` | `bank.basic_credit_lines` | A | Basic credit lines per firm |
| `BadDebttotTemp(NB)` | `bank.bad_debt_temp` | A | Temp bad-debt aggregator |
| `Bbailout(NB)` | `bank.bailout_paid_to_buy_failed` | A | Amount paid by this bank to buy out failed |
| `Bank_active(NB)` | `bank.is_active` | A | 0=inactive / 1=active |
| `BankEquity_temp(NB)` | `bank.equity_temp` | A | Temp vector to find biggest bank |
| `NbClient(NB)` | `bank.n_clients` | A | Number of clients at bank |
| `BankMatch(N2,NB)` | `bank.client_match_matrix` | A | =1 if firm j is client of bank i |
| `RandomMatch(N2,NB)` | `bank.random_matching_init` | A | Used in bank initialization |
| `DebtInterestsClients1(NB)` | `bank.interest_income_s1` | A | Interest income from S1 clients |
| `DebtInterestsClients2(NB)` | `bank.interest_income_s2` | A | Interest income from S2 clients |
| `DebtInterestsClients2Temp` | `bank_s2_interest_income_temp` | N | Temp aggregate |
| `CreditSupplier(N2)` | `cons_firm.bank_id` | A | Firm's credit-supplier bank ID |
| `fB(2,NB)` | `bank.market_share` | A | Market shares of banks |
| `bonds(NB)` | `bank.bonds_held` | A | Bonds held by bank |
| `newbonds(NB)` | `bank.new_bonds_held` | A | Newly issued bonds held |
| `bondsremittances(NB)` | `bank.bonds_remittances` | A | Bonds principal returned |
| `WtotClient(NB)` | `bank.client_net_worth_total` | A | Total client NW |
| `WtotClient2(NB)` | `bank.client_net_worth_total_alt` | A | Total client NW (alt calc) |
| `Wtot1_share(NB)` | `bank.s1_networth_share` | A | Per-bank share of S1 NW |
| `Wtot1_equalshare` | `bank_s1_equalshare` | N | Equal-share allocation reference |
| `Sum_BankEquity` | `bank_equity_sum` | N | Sum of bank equity (bailout=3) |
| `Equity_share` | `equity_share` | N | Used by flagbailout=3 |
| `Clients_share` | `clients_share` | N | Used by flagbailout=3 |
| `NewClients` | `bank.new_clients` | A | New clients to the bank |
| `missing` | `clients_missing` | N | Missing-client tracker in init distribution |
| `Loans_CB(NB)` | `bank.cb_loans` | A | Loans from central bank (flag_giulioni=3) |
| `Loans(NB)` | `bank.loans_total` | A | Total loans (Debtot2 + bad debt) |
| `Amount_lent(NB)` | `bank.amount_lent` | A | Amount lent by each bank |
| `bank_recovery(N2)` | `cons_firm.bank_recovery` | A | Per-firm recovery in bank failure |
| `bank_recoverytot` | `bank_recovery_total` | N | Aggregate recovery |
| `Amount_refinanced(NB)` | `bank.amount_refinanced` | A | Amount refinanced |
| `BD_check` | `bank.bd_check_aux` | A | Auxiliary check vector |
| `Amount_lent_temp` | `bank.amount_lent_temp` | A | Temp amount lent |
| `Leverage(NB)` | `bank.leverage` | A | Bad-debt / (cash + bonds) |
| `bankmarkup(NB)` | `bank.markup_on_loans` | A | Endogenous markup |
| `r_deb(NB)` | `bank.loan_rate` | A | Bank-idiosyncratic loan rate |
| `r_deb_h(N2)` | `cons_firm.heterogeneous_loan_rate` | A | Per-firm heterogeneous rate (flag_interest_rate=1) |
| `k(N2)` | `cons_firm.credit_class` | A | Firm's credit-class bucket |
| `ROE(NB)` | `bank.roe` | A | Return on equity per bank |
| `buffer(NB)` | `bank.capital_buffer` | A | Endogenous capital buffer |
| `BadDebt_test` | `bad_debt_test` | N | Diagnostic |
| `count_bonds` | `count_bonds` | N | Bond-events counter |
| `mean_rdeb_all` | `loan_rate_weighted_mean` | N | Weighted-average loan rate |
| `mean_rbank_all` | `bank_prime_rate_weighted_mean` | N | Weighted-average prime rate |
| `std_rdeb_all` | `loan_rate_weighted_std` | N | Std of weighted loan rate |
| `std_rbank_all` | `bank_prime_rate_weighted_std` | N | Std of weighted prime rate |
| `count_rdeb` | `count_loan_rate` | N | Diagnostic counter |
| `count_rbank` | `count_bank_rate` | N | Diagnostic counter |
| `AvgCreditDemandSupplyRatio(NB)` | `bank.credit_demand_supply_ratio` | A | Demand/supply ratio per bank |
| `AvgCreditDemandSupplyRatio_all` | `credit_demand_supply_ratio_total` | N | Economy-wide ratio |
| `Loan_profit_share(NB)` | `bank.loan_profit_share` | A | Loan-interest share of total interest revenue |
| `countbf(NB)` | `bank.failure_count` | A | Per-bank failure count |
| `countbf_all` | `bank_failures_total_cum` | N | Cumulative total bank failures |
| `countbf_all2` | `bank_failures_per_period` | N | Bank failures this period |
| `avg_countbf` | `bank_failures_avg` | N | Statistical average |
| `countbaselconstraint(NB)` | `bank.basel_binding_count` | A | Times Basel was binding |
| `countbaselconstraint_all` | `basel_binding_count_total` | N | Sum across banks |
| `countbaselconstraintintimesteps` | `basel_binding_periods_count` | N | Periods Basel binding |
| `count_def` | `count_stability_pact_binding` | N | Times stability-pact binding |
| `count_def2` | `flag_stability_pact_binding_this_step` | N | =1 if rule binding this step |
| `count_compact` | `count_fiscal_compact_binding` | N | Times fiscal compact binding |
| `count_compact2` | `flag_fiscal_compact_binding_this_step` | N | =1 if compact binding this step |
| `count_noconstraint` | `count_no_fiscal_constraint` | N | Times no rule binding |
| `count_def_rec` | `count_pact_off_due_recession` | N | Stability pact off due to recession |
| `count_def_rec2` | `flag_pact_off_recession_this_step` | N | =1 if recession exempt |
| `def_rule` | `deficit_rule` | N | Deficit-rule threshold (experiment 08) |
| `Deposits_insurance` | `deposits_insurance_amount` | N | Insurance amount |
| `dep_ratio` | `deposit_ratio` | N | Deposit ratio |
| `insurance_ratio` | `insurance_ratio` | N | Insurance ratio |
| `Nb_act` | `n_banks_active` | N | Number of active banks |
| `Nb_act_final` | `n_banks_active_final` | N | Active banks final count |
| `count_olig` | `count_oligopoly` | N | Oligopoly count |
| `maxbank` | `largest_bank_index` | N | Largest bank index |
| `minbank` | `smallest_bank_index` | N | Smallest bank index |
| `max_equity` | `bank_equity_max` | N | Max equity |
| `min_equity` | `bank_equity_min` | N | Min equity |
| `multip_bailout` | `bailout_multiplier` | N | Bailout multiplier |
| `Bbailout_all` | `bailout_inter_bank_total` | N | Total of inter-bank bailouts |
| `Gbailout_all` | `govt_bailout_total` | N | Total govt bailout payments |
| `count_savings` | `count_savings_lt_deficit` | N | When economy savings < deficit |

### Banking-sector aggregates (per-nation sums)
These are summary totals across all banks in the nation.
| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `Debt_all` | `banking.debt_total` | N | Total private debt (S1 + S2) |
| `Debt1_all` | `banking.debt_total_s1` | N | Total S1 private debt |
| `Debt2_all` | `banking.debt_total_s2` | N | Total S2 private debt (= `DebtRemittances_all`) |
| `BadDebt_all` | `banking.bad_debt_total` | N | Total bad debt across all banks |
| `BankDeposits_all` | `banking.deposits_total` | N | Sum of bank deposits |
| `BankEquity_all` | `banking.equity_total` | N | Sum of bank equity |
| `BankProfits_all` | `banking.profit_total` | N | Sum of bank profits |
| `BankCash_all` | `banking.cash_total` | N | Sum of bank cash |
| `MultiplierBankCredit_all` | `banking.credit_via_multiplier_total` | N | Sum of credit via deposit-multiplier rule |
| `BaselBankCredit_all` | `banking.credit_via_basel_total` | N | Sum of credit via Basel II rule |
| `BankCredit_all` | `banking.credit_capacity_total` | N | Sum of bank credit capacities |
| `DebtRemittances_all` | `banking.debt_repayments_total` | N | Total debt repayments (= S2 debt) |
| `DebtInterestsClients2_all` | `banking.interest_income_s2_total` | N | Total interest income from S2 |
| `CreditDemand_all` | `banking.credit_demand_total` | N | Credit demand of all firms |
| `CreditSupply_all` | `banking.credit_supply_total` | N | Total credit supply economy-wide |
| `HB` | `banking.herf_index` | N | Banking-sector Herfindahl index |
| `DFB` | `banking.market_share_variance` | N | Banking-sector market-share variability index |
| `NBr` | `banking.market_share_init_seed` | N | Auxiliary used to initialize bank market shares |
| `avg_cpi` | `avg_cpi_test` | N | Average CPI for testing (declared in macro module) |

---

## 12. Macro / Aggregate Nation State

**N (Nation)** — these live on `Nation.accounting` / `Nation` or `Nation.labour_market`.

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `Am(2)` | `mean_productivity` | N | Average labour productivity (curr & prev) |
| `cpi(2)` | `cpi` | N | Consumer price index history |
| `cpi_old(3)` | `cpi_extended_history` | N | Previous CPI values (prev, prev-prev, ever-first) |
| `ppi(2)` | `ppi` | N | Producer price index |
| `U(2)` | `unemployment_rate` | N | Unemployment fraction |
| `w(3)` | `wage` | N | Wage (current + 2 lags) |
| `G(2)` | `govt_spending` | N | Government spending |
| `ftot(3)` | `market_share_sum` | N | Sum of market shares (sanity check) |
| `diff_w(2)` | `wage_growth` | N | First difference of wage |
| `diff_cpi(2)` | `inflation_rate` | N | First difference of CPI |
| `GDP(3)` | `gdp` | N | GDP (current + 2 lags) |
| `Divtot(2)` | `dividends_total` | N | Total dividends |
| `A1front(2)` | `s1_exog_machine_frontier` | N | Exogenous machine frontier |
| `A1pfront(2)` | `s1_exog_process_frontier` | N | Exogenous process frontier |
| `A1top(2)` | `s1_endog_machine_frontier` | N | Endogenous machine frontier |
| `A1ptop(2)` | `s1_endog_process_frontier` | N | Endogenous process frontier |
| `Cons` | `consumption_real_or_nominal` | N | Consumption total |
| `Imon` | `investment_money` | N | Monetary investment (Σ new machines × price) |
| `EItot` | `investment_expansion_real` | N | Total expansion investment, real |
| `SItot` | `investment_substitution_real` | N | Total substitution investment, real |
| `Imon_BankCredit` | `inv_money_to_credit_ratio` | N | I_money / credit supply |
| `Ir_BankCredit` | `inv_real_to_credit_ratio` | N | Real investment / credit-supply ratio |
| `Y` | `gdp_aggregate` | N | Aggregate GDP scalar |
| `LS` | `labour_supply` | N | Total labour supply |
| `LD` | `labour_demand_total` | N | Total labour demand |
| `LD2(2)` | `labour_demand_total_rd` | N | R&D labour demand history |
| `Pitot1` | `profit_total_s1` | N | Total profit, sector 1 |
| `Pitot2` | `profit_total_s2` | N | Total profit, sector 2 |
| `Pitot` | `profit_total_economy` | N | Total profit, economy |
| `Wtot1` | `net_worth_total_s1` | N | Total NW, sector 1 |
| `Wtot2` | `net_worth_total_s2` | N | Total NW, sector 2 |
| `Wtot` | `net_worth_total` | N | Total NW |
| `maxtao` | `max_vintage_index` | N | Maximum vintage index |
| `scrapmax` | `max_scrapped_count` | N | Max machines scrapped |
| `payback` | `payback_result` | N | Payback rule output |
| `cmax` | `payback_cost_max` | N | Max payback cost |
| `N1r` | `n1_alive` | N | Surviving sector-1 firm count (real) |
| `N2r` | `n2_alive` | N | Surviving sector-2 firm count (real) |
| `N2eff` | `n2_effective` | N | Effective sector-2 firm count |
| `epss` | `normal_draw` | N | Normal-distribution random draw |
| `NW` | `net_worth_for_rationing` | N | Net worth used for credit rationing |
| `LD1tot` | `labour_demand_s1` | N | Aggregate labour demand, sector 1 |
| `LD2tot` | `labour_demand_s2` | N | Aggregate labour demand, sector 2 |
| `LD1rdtot` | `labour_demand_rd_total` | N | Aggregate labour demand for R&D |
| `Ntot` | `inventory_total` | N | Total inventories |
| `l2m` | `unsatisfied_demand_mean` | N | Mean unsatisfied demand |
| `p2m` | `s2_price_mean` | N | Mean S2 price |
| `LSe` | `labour_supply_alt` | N | Auxiliary labour supply |
| `LD2e` | `labour_demand_s2_aux` | N | Auxiliary S2 labour demand |
| `d_cpi` | `cpi_change` | N | Δ CPI (scalar shortcut) |
| `d_Am` | `mean_prod_change` | N | Δ mean productivity |
| `d_U` | `unemployment_change` | N | Δ unemployment |
| `Qtot1` | `s1_production_total` | N | Total S1 production (#machines) |
| `Qtot2` | `s2_production_total` | N | Total S2 production |
| `W1m` | `s1_net_worth_mean` | N | Mean S1 net worth |
| `W2m` | `s2_net_worth_mean` | N | Mean S2 net worth |
| `Creal` | `consumption_real` | N | Real consumption |
| `Ir` | `investment_real` | N | Real investment |
| `Ir2` | `investment_real_alt` | N | Real investment (alt) |
| `dNtot` | `inventory_change_total` | N | Total Δ inventories |
| `dNtot2` | `inventory_change_alt` | N | Alternate inventory aggregator |
| `dw` | `wage_change_scalar` | N | Δ wage (scalar) |
| `avg_prod` | `mean_prod_running` | N | Running mean productivity |
| `avg_w` | `mean_wage_running` | N | Running mean wage |
| `avg_y` | `mean_y_running` | N | Running mean GDP |
| `avg_LS` | `mean_ls_running` | N | Running mean labour supply |
| `Y0` | `gdp_init` | N | Initial GDP |
| `GDP1` | `gdp_lag1` | N | GDP at t-1 (auxiliary) |
| `Am0` | `mean_prod_init` | N | Initial mean productivity |
| `TFP` | `tfp` | N | Total factor productivity |
| `nmachprod` | `n_machines_produced` | N | #machines produced |
| `nmp_temp` | `n_machines_produced_temp` | N | Temp #machines produced |
| `Amax` | `productivity_max` | N | Max productivity |
| `prestmax` | `loan_max` | N | Max loan |
| `A1m` | `s1_mean_machine_prod` | N | Mean S1 machine productivity |
| `ftot1` | `s1_market_share_sum` | N | Sum of S1 market shares |
| `Itot` | `investment_total_scalar` | N | Total investment |
| `RD1tot` | `rd_total_s1` | N | Total S1 R&D spending |
| `D1tot` | `demand_total_s1` | N | Total S1 demand |
| `Qpast` | `production_past` | N | Past production |
| `gcont` | `g_counter` | N | Generic accumulator |
| `npayback` | `n_payback` | N | Payback-related counter |
| `mintao` | `min_vintage_index` | N | Minimum vintage index |
| `Q2tot` | `s2_production_total_alt` | N | Total S2 production (alt) |
| `D2tot` | `s2_demand_total` | N | Total S2 demand |
| `Cpast` | `consumption_past` | N | Past consumption |
| `l2tot` | `unsatisfied_demand_total` | N | Total unsatisfied demand |
| `machtemp` | `machine_temp` | N | Auxiliary machine value |
| `Am1` | `s1_mean_machine_prod_alt` | N | Mean S1 productivity (alt aggregator) |
| `Am2` | `s2_mean_productivity` | N | Mean S2 productivity |
| `Cres` | `consumption_residual` | N | Residual consumption (allocation) |
| `Cresbis` | `consumption_residual_alt` | N | Residual consumption (alt) |
| `Amm` | `productivity_grand_mean` | N | Cross-sector mean productivity |
| `p1m` | `s1_price_mean` | N | Mean S1 price |
| `c1m` | `s1_unit_cost_mean` | N | Mean S1 unit cost |
| `S1m` | `s1_sales_mean` | N | Mean S1 sales |
| `Q1m` | `s1_production_mean` | N | Mean S1 production |
| `age0` | `age_baseline` | N | Reference machine age |
| `Netot` | `expected_inventories_total` | N | Total expected inventories |
| `Nt1tot` | `inventories_s1_total` | N | Total S1-related stock |
| `Nt2tot` | `inventories_s2_total` | N | Total S2-related stock |
| `D20` | `s2_demand_init` | N | Initial S2 demand |
| `agetop` | `age_top` | N | Max age in active stock |
| `m2m` | `s2_markup_mean` | N | Mean S2 markup |
| `dNmtot` | `inventory_money_change_total` | N | Total Δ inventory (money) |
| `Cmon` | `consumption_money` | N | Money spent on consumption |
| `GDPm` | `gdp_money` | N | Monetary GDP |
| `A_mi` | `productivity_log_mean` | N | Log-mean productivity |
| `A1_mi` | `s1_productivity_log_mean` | N | Log-mean S1 productivity |
| `A_sd` | `productivity_std` | N | Standard deviation productivity |
| `A2scr` | `s2_scrapped_count` | N | Sector-2 scrapped count |
| `A1scr` | `s1_scrapped_count` | N | Sector-1 scrapped count |
| `A_mi_nolog` | `productivity_mean_nolog` | N | Non-log mean productivity |
| `avg_LS_MC` | `mean_labour_supply_mc` | N | MC-mean labour supply |
| `GDP_growth(T-1)` | `gdp_growth_series` | N | GDP growth time series |
| `Useries(T-1)` | `unemployment_series` | N | Unemployment time series |
| `GDP_g` | `gdp_growth_scalar` | N | GDP growth scalar |
| `GDP_growth_mean` | `gdp_growth_mean` | N | Mean GDP growth |
| `MC_GDP_growth_mean` | `gdp_growth_mean_mc` | N | MC mean GDP growth |
| `GDP_growth_avgstd` | `gdp_growth_avgstd` | N | Average std of GDP growth |
| `U_avgstd` | `unemployment_avgstd` | N | Average std of unemployment |
| `GDP_growth_pooled` | `gdp_growth_pooled` | N | Pooled GDP growth (across MC) |
| `U_pooled` | `unemployment_pooled` | N | Pooled unemployment |
| `count_rationingper` | `count_rationing_periods` | N | Periods with credit rationing |
| `count_firm2_rationed` | `count_s2_firms_rationed` | N | S2 firms rationed |
| `AvgRationingRate` | `rationing_rate_avg` | N | Average rationing rate |
| `mysamplesize` | `sample_size` | N | Sample size diagnostic |
| `samplenum` | `sample_id` | N | Sample identifier |
| `llGDP_crises` | `gdp_crisis_log_likelihood` | N | Crisis log-likelihood (GDP) |
| `llU_crises` | `u_crisis_log_likelihood` | N | Crisis log-likelihood (unemployment) |
| `gdpcountcrisis` | `gdp_crisis_count` | N | GDP-crisis count |
| `ucountcrisis` | `u_crisis_count` | N | Unemployment-crisis count |
| `LD0` | `labour_demand_init` | N | Initial labour demand |
| `avg_LD` | `mean_labour_demand_running` | N | Running mean labour demand |
| `Pi20` | `s2_profit_init` | N | Initial S2 profit |
| `avg_Pi2` | `s2_profit_mean_running` | N | Running mean S2 profit |
| `Pi10` | `s1_profit_init` | N | Initial S1 profit |
| `avg_Pi1` | `s1_profit_mean_running` | N | Running mean S1 profit |
| `GDPonPi` | `gdp_to_profit` | N | GDP / profit ratio |
| `GDPonPi1` | `gdp_to_s1_profit` | N | GDP / S1 profit ratio |
| `GDPonPi2` | `gdp_to_s2_profit` | N | GDP / S2 profit ratio |
| `dNonGDP` | `inventory_change_to_gdp` | N | ΔN / GDP ratio |
| `IonK` | `investment_to_capital` | N | I/K ratio |
| `rw` | `real_wage` | N | Real wage |
| `nclientmax` | `n_clients_max` | N | Max #clients per cap-good firm |
| `contQI` | `count_qi_event` | N | Counter — investment events |
| `contalfasup` | `count_alfasup_binding` | N | Counter — alfasup binding |
| `contQtot1` | `count_qtot1_event` | N | Counter — Qtot1 events |
| `contINN` | `count_innovation_events` | N | Innovation event count |
| `contIMM` | `count_imitation_events` | N | Imitation event count |
| `contfront` | `count_frontier_uses` | N | Frontier-use counter |
| `contfront2` | `count_frontier2_uses` | N | Frontier-use counter 2 |
| `contA1entry` | `count_a1_entry` | N | Counter for A1 entry events |
| `contA1front` | `count_a1_frontier` | N | Counter for A1 frontier events |
| `contFE` | `count_full_employment_periods` | N | Full-employment periods |
| `contCC` | `count_credit_crunch` | N | Credit-crunch counter |
| `contcpi1` | `count_cpi_event` | N | CPI counter 1 |
| `contppi1` | `count_ppi_event` | N | PPI counter 1 |
| `contIMMnaz` | `count_imit_domestic` | N | Domestic imitation counter |
| `contIMMfor` | `count_imit_foreign` | N | Foreign imitation counter |
| `Gtot` | `govt_spending_total` | N | Total govt spending |
| `GonGDP` | `g_to_gdp` | N | G/GDP ratio |
| `Tax` | `tax_revenue_total` | N | Total tax revenue |
| `Deb` | `public_debt` | N | Public debt |
| `Def` | `public_deficit` | N | Public deficit |
| `DebonGDP` | `debt_to_gdp` | N | Debt/GDP |
| `DefonGDP` | `deficit_to_gdp` | N | Deficit/GDP |
| `GbailoutonGDP` | `bailout_to_gdp` | N | Bailout/GDP |
| `countbailout` | `bailout_count` | N | Bailout events count |
| `c2tot` | `s2_unit_cost_total` | N | Aggregate S2 unit cost |
| `Mutot` | `markup_total` | N | Aggregate markup |
| `rnd` | `rng_index` | N | RNG index |
| `parbertot` | `bernoulli_total` | N | Σ Bernoulli draw |
| `parbertot1` | `bernoulli_total_alt` | N | Σ Bernoulli draw (alt) |
| `Inntot1` | `innovation_count_s1_props` | N | Total innov events, S1 properties |
| `Inntot2` | `innovation_count_s2_props` | N | Total innov events, S2 properties |
| `Immtot1` | `imitation_count_s1` | N | Total imitation events S1 |
| `Immtot2` | `imitation_count_s2` | N | Total imitation events S2 |
| `parbermax` | `bernoulli_max` | N | Max Bernoulli draw |
| `parbermax1` | `bernoulli_max_alt` | N | Max Bernoulli (alt) |
| `tbermax` | `bernoulli_time_max` | N | Time of max Bernoulli |
| `tbermax1` | `bernoulli_time_max_alt` | N | Time of max Bernoulli (alt) |
| `ninv` | `n_investing_firms` | N | Number of investing firms |
| `A1max` | `s1_productivity_max` | N | Max S1 productivity |
| `A1pmax` | `s1_process_productivity_max` | N | Max S1 process productivity |
| `Km` | `capital_mean` | N | Mean capital |
| `f2exit` | `s2_exit_market_share` | N | Exit-time market share |
| `n2exit` | `s2_exit_count` | N | S2 exit count |
| `f2max` | `s2_market_share_max` | N | Max S2 market share |
| `Tdtot` | `tech_distance_total` | N | Tech-distance total |
| `tax1` | `tax_s1` | N | S1 taxes paid |
| `tax1_collect` | `tax_s1_collected` | N | S1 taxes collected |
| `p1prova` | `s1_price_test` | N | Test price S1 |
| `DebonGDPm1` | `debt_to_gdp_lag1` | N | Lag-1 Debt/GDP |
| `DebonGDPm2` | `debt_to_gdp_lag2` | N | Lag-2 Debt/GDP |
| `contSI` | `count_substitution_investment` | N | SI events counter |
| `Umean` | `unemployment_mean` | N | Mean unemployment |
| `MC_Umean` | `unemployment_mean_mc` | N | MC mean unemployment |
| `contMONOP` | `count_monopoly_periods` | N | Monopoly-period counter |
| `H1` | `herf_s1` | N | Herfindahl index, sector 1 |
| `H2` | `herf_s2` | N | Herfindahl index, sector 2 |
| `DF1` | `mkt_share_variance_s1` | N | Market-share variability, S1 |
| `DF2` | `mkt_share_variance_s2` | N | Market-share variability, S2 |
| `HI` | `herf_inv` | N | Herf inv-weighted |
| `HIn` | `herf_inv_nom` | N | Herf inv nominal |
| `IxHI` | `i_times_hi` | N | I × HI |
| `IxHIn` | `i_times_hin` | N | I × HIn |
| `N2lI` | `n2_low_investment` | N | #firms with low investment |
| `N2hI` | `n2_high_investment` | N | #firms with high investment |
| `N2lEI` | `n2_low_expansion_invest` | N | #firms with low expansion investment |
| `N2hEI` | `n2_high_expansion_invest` | N | #firms with high expansion investment |
| `contmach` | `count_machine_events` | N | Machine-events counter |
| `umin` | `unemployment_min` | N | Min unemployment |
| `A1fmax` | `foreign_machine_prod_max` | N | Max foreign machine productivity |
| `A1pfmax` | `foreign_process_prod_max` | N | Max foreign process productivity |
| `A1fmin` | `foreign_machine_prod_min` | N | Min foreign machine prod |
| `A1pfmin` | `foreign_process_prod_min` | N | Min foreign process prod |
| `A1favg` | `foreign_machine_prod_mean` | N | Mean foreign machine prod |
| `A1pfavg` | `foreign_process_prod_mean` | N | Mean foreign process prod |
| `A1fstd` | `foreign_machine_prod_std` | N | Std foreign machine prod |
| `A1pfstd` | `foreign_process_prod_std` | N | Std foreign process prod |
| `A1ratio` | `foreign_to_domestic_ratio_machine` | N | Foreign/domestic ratio (machine) |
| `A1pratio` | `foreign_to_domestic_ratio_process` | N | Foreign/domestic ratio (process) |
| `Am1bis` | `s1_mean_prod_alt` | N | Alt aggregator |
| `A1avg` | `s1_machine_prod_avg` | N | Mean S1 machine prod |
| `A1pavg` | `s1_process_prod_avg` | N | Mean S1 process prod |
| `Tdtot` | `tech_distance_total` | N | Total technological distance (alias of earlier row) |
| `TotalW2` | `s2_total_net_worth` | N | Used in MAXCREDIT — total S2 NW |
| `networth_firm_ratio` | `firm_networth_to_total_ratio` | N | Firm NW / total NW |
| `TotalS2` | `s2_total_sales` | N | Total S2 sales |
| `turnover_firm_ratio` | `firm_turnover_to_total_ratio` | N | Firm turnover / total turnover |
| `myNWScount` | `nws_rating_index` | N | Index for NWS rating loop |
| `totaltechscrapping` | `total_tech_scrap_desired` | N | Firms wanting total tech scrapping |
| `totaleffscrapping` | `total_eff_scrap_actual` | N | Firms that effectively totally scrap |
| `totaltechscrappingevents` | `total_tech_scrap_events` | N | Total tech-scrap events |
| `totaleffscrappingevents` | `total_eff_scrap_events` | N | Total eff-scrap events |
| `mydebttot` | `debt_total_aux` | N | Debt-total aux |
| `bankreserve_requirement_rate` | `bank_reserve_requirement_rate` | N | Reserve-requirement rate (operational; also in §11) |
| `machtool_collapse` | `machtool_collapse_flag` | N | Cap-good sector collapse indicator |
| `machtool_financial_collapse` | `machtool_financial_collapse_value` | N | Financial-collapse magnitude |
| `dieW1` | `s1_firms_died_financial` | N | S1 firms that died for financial reasons |
| `consgood_collapse` | `consgood_collapse_value` | N | Cons-good collapse indicator |
| `nwm1` | `s1_surviving_count` | N | Surviving S1 firms |
| `nwm2` | `s2_surviving_count` | N | Surviving S2 firms |
| `next1` | `s1_exit_count` | N | S1 exits |
| `next2` | `s2_exit_count` | N | S2 exits |
| `next2bc` | `s2_bankruptcy_count` | N | S2 bankruptcies |
| `errFULLEMP` | `full_employment_error_flag` | N | Full-employment error flag |
| `imc` | `mc_index` | N | Monte-Carlo iteration index |
| `Q1_next` | `s1_exit_production` | N | Total production of S1 exiting firms |
| `Q2_next` | `s2_exit_production` | N | Total production of S2 exiting firms |
| `Q_next` | `exit_production_total` | N | Total exit production both sectors |
| `bankr_Qtot` | `bankrupt_production_share` | N | Qtot of bankrupt firms / total Qtot |
| `avg_bankr_Q` | `bankrupt_production_share_avg` | N | Avg of above |
| `bankr_LDtot` | `bankrupt_labour_share` | N | LD of bankrupt firms / total LD |
| `avg_bankr_LD` | `bankrupt_labour_share_avg` | N | Avg of above |
| `Ld1_next` | `s1_exit_labour_demand` | N | Labour demand of exiting S1 |
| `Ld2_next` | `s2_exit_labour_demand` | N | Labour demand of exiting S2 |
| `Def_Gbailout` | `deficit_share_bailout` | N | Share of fiscal cost from bailout |
| `Def_G` | `deficit_share_g` | N | Share of fiscal cost from G |
| `Def_Deb` | `deficit_share_debt_service` | N | Share of fiscal cost from debt service |
| `Deb_temp` | `debt_temp` | N | Temporary debt value |
| `deltami2` | `s2_markup_step_change` | N | Δ markup |
| `count_min_dw` | `count_wage_rigidity_binding` | N | Times flagWAGE2 binding |
| `count_wage_lag` | `count_wage_lags` | N | Wage update lag counter |
| `cpi_lag` | `cpi_lag` | N | CPI lag (flagWAGE=4) |
| `Am_lag` | `mean_productivity_lag` | N | Mean prod lag (flagWAGE=4) |
| `U_lag` | `unemployment_lag` | N | Unemployment lag (flagWAGE=4) |
| `GDP_g2` | `gdp_growth_alt` | N | Alt GDP-growth scalar |
| `share_CB` | `cb_bonds_share` | N | Share of bonds on CB balance sheet |
| `count_share_def` | `count_share_def` | N | Share-deficit counter |
| `GDP_temp` | `gdp_temp` | N | Temp GDP scalar (flagEXP_switch) |
| `neg_count` | `negative_expected_demand_count` | N | Expected-demand<0 events count |
| `Q2dtot` | `s2_desired_production_total` | N | Aggregate desired production, S2 |
| `FC_Prod_tot` | `financial_constraint_production` | N | Q2tot / Q2dtot |
| `Avg_FC_Prod_tot` | `financial_constraint_production_avg` | N | Average of above |
| `Idtot` | `desired_investment_total` | N | Aggregate desired investment |
| `FC_Inv_tot` | `financial_constraint_investment` | N | Itot/Idtot |
| `Avg_FC_Inv_tot` | `financial_constraint_investment_avg` | N | Average of above |
| `Invmach` | `investment_machtool` | N | Machine-tool investment |
| `DebonInv(2)` | `debt_to_investment_ratio` | N | Debt/Investment (current & prev) |
| `Debmach` | `machtool_debt` | N | Machine-tool debt |
| `Debprod` | `production_debt` | N | Production-related debt |
| `Totprod` | `production_total` | N | Total production |
| `DebonProd(2)` | `debt_to_production_ratio` | N | Debt/Production |
| `DebonQ1(2)` | `debt_to_s1_production_ratio` | N | Debt to S1 production |
| `DebonQ2(2)` | `debt_to_s2_production_ratio` | N | Debt to S2 production |
| `DebQ2` | `debt_s2_aggregate` | N | Aggregate S2 debt aggregator |
| `r` | `policy_rate` | N | Central-bank base rate |
| `r_depo` | `deposit_rate` | N | Deposit rate |
| `r_cbreserves` | `cb_reserves_rate` | N | CB-reserves rate |
| `r_bonds` | `bonds_rate` | N | Bonds interest rate |
| `r_base` | `base_rate` | N | Base rate (Taylor reference) |
| `wu` | `unemployment_benefit_share` | N | Unemployment benefit as fraction of wage |
| `aliq` | `tax_rate_firms_wages` | N | Income/firm tax rate |
| `aliqb` | `tax_rate_banks` | N | Bank-profit tax rate |
| `mi2` | `s2_markup_init_or_current` | N | Sector-2 markup |
| `credit_multiplier` | `credit_multiplier` | N | Credit multiplier (inverse of credit/equity ratio) |
| `Newbonds_financed` | `new_bonds_financed` | N | Newly financed bonds |
| `count_bonds` | `count_bonds` | N | Bond-events counter (operational copy) |
| `psi1` | `wage_inflation_response` | N | Sensitivity wage rule to inflation |
| `psi3` | `wage_unemployment_response` | N | Sensitivity wage rule to unemployment |
| `multip_entry` | `entry_size_multiplier` | N | Entry-size multiplier for incumbent imitation |
| `count_zerobound` | `count_zero_lower_bound` | N | Zero-lower-bound hits |
| `count_deflation` | `count_deflation_periods` | N | Periods of deflation |
| `count_large_deflation` | `count_large_deflation` | N | Periods of large deflation |
| `count_inflation_target` | `count_inflation_target_hit` | N | Periods at inflation target |
| `count_unemp_target` | `count_unemployment_target_hit` | N | Periods at unemployment target |
| `avg_r` | `mean_policy_rate` | N | Average policy rate |
| `Tax_Bankprofits` | `tax_bank_profits` | N | Tax revenue from bank profits |
| `Taxbase_banks` | `taxbase_banks` | N | Tax base, banks |
| `Tax_wages` | `tax_wages` | N | Tax revenue from wages |
| `Taxbase_wages` | `taxbase_wages` | N | Tax base, wages |
| `Tax_firms` | `tax_firms` | N | Tax revenue from firms |
| `Taxbase_firms` | `taxbase_firms` | N | Tax base, firms |
| `taylor2` | `taylor_rule_unemployment_coef` | N | Unemployment-coefficient in Taylor rule |
| `taylor1` | `taylor_rule_inflation_coef` | N | Inflation-coefficient in Taylor rule |
| `dr` | `policy_rate_change` | N | Δ central-bank rate |
| `ROE_all` | `bank_sector_roe` | N | Banking-sector ROE |
| `count_no_FC_prod` | `count_no_financial_constraint_prod` | N | No-FC-on-production count |
| `count_FC_prod` | `count_financial_constraint_prod` | N | FC-on-production count |
| `share_FC_prod` | `share_financial_constraint_prod` | N | Share — FC on prod |
| `count_no_FC_inv` | `count_no_financial_constraint_inv` | N | No-FC-on-investment count |
| `count_FC_inv` | `count_financial_constraint_inv` | N | FC-on-investment count |
| `share_FC_inv` | `share_financial_constraint_inv` | N | Share — FC on investment |
| `avg_share_FC_prod` | `share_fc_prod_avg` | N | Average share |
| `avg_share_FC_inv` | `share_fc_inv_avg` | N | Average share |
| `share_na` | `expectation_rule_share_na` | N | Share of NA rule (flagEXP_switch) |
| `share_ada` | `expectation_rule_share_ada` | N | Share ADA |
| `share_wtr` | `expectation_rule_share_wtr` | N | Share WTR |
| `share_str` | `expectation_rule_share_str` | N | Share STR |
| `share_laa` | `expectation_rule_share_laa` | N | Share LAA |
| `share_all` | `expectation_rule_share_all` | N | Share — all rules summed |
| `nb_na` | `n_firms_na` | N | #firms using NA |
| `nb_ada` | `n_firms_ada` | N | #firms ADA |
| `nb_wtr` | `n_firms_wtr` | N | #firms WTR |
| `nb_str` | `n_firms_str` | N | #firms STR |
| `nb_laa` | `n_firms_laa` | N | #firms LAA |
| `nb_all` | `n_firms_all_rules` | N | Σ firms by rule |
| `r_switch` | `switching_random_draw` | N | Switching RNG draw |
| `count_exit_NA` | `count_exit_na` | N | Exits using NA rule |
| `count_exit_ADA` | `count_exit_ada` | N | Exits ADA |
| `count_exit_WTR` | `count_exit_wtr` | N | Exits WTR |
| `count_exit_STR` | `count_exit_str` | N | Exits STR |
| `count_exit_LAA` | `count_exit_laa` | N | Exits LAA |
| `share_exit_na` | `share_exit_na` | N | Share of exits NA |
| `share_exit_ada` | `share_exit_ada` | N | Share of exits ADA |
| `share_exit_wtr` | `share_exit_wtr` | N | Share of exits WTR |
| `share_exit_str` | `share_exit_str` | N | Share of exits STR |
| `share_exit_laa` | `share_exit_laa` | N | Share of exits LAA |
| `exp_gr` | `bank_markup_exp_growth` | N | Exponent in spread rule |
| `max_rl` | `bank_markup_max` | N | TOTCREDIT max on bankmarkup |
| `beta_basel` | `basel_multiplier_coef` | N | Basel multiplier coef |
| `count_Keynes_high` | `count_keynes_high` | N | flagKeynes=1 high-event count |
| `count_Keynes_low` | `count_keynes_low` | N | flagKeynes=1 low-event count |
| `FDebonGDP` | `private_debt_to_gdp` | N | Private debt / monetary GDP |
| `t0` | `t_start_main_loop` | N | Counter for initial period in some loops |

### Expectation-rule-specific working matrices (sector-2)
| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `De_na(2,N2)` | `cons_firm.expected_demand_na` | A | Expected demand — naive |
| `De_ada(2,N2)` | `cons_firm.expected_demand_ada` | A | Expected demand — adaptive |
| `De_wtr(2,N2)` | `cons_firm.expected_demand_wtr` | A | Expected demand — weak trend |
| `De_str(2,N2)` | `cons_firm.expected_demand_str` | A | Expected demand — strong trend |
| `De_laa(2,N2)` | `cons_firm.expected_demand_laa` | A | Expected demand — LAA |
| `n_na(2,N2)` | `cons_firm.rule_prob_na` | A | Probability of choosing NA |
| `n_ada(2,N2)` | `cons_firm.rule_prob_ada` | A | Probability ADA |
| `n_wtr(2,N2)` | `cons_firm.rule_prob_wtr` | A | Probability WTR |
| `n_str(2,N2)` | `cons_firm.rule_prob_str` | A | Probability STR |
| `n_laa(2,N2)` | `cons_firm.rule_prob_laa` | A | Probability LAA |
| `U_na(2,N2)` | `cons_firm.rule_performance_na` | A | Performance NA |
| `U_ada(2,N2)` | `cons_firm.rule_performance_ada` | A | Performance ADA |
| `U_wtr(2,N2)` | `cons_firm.rule_performance_wtr` | A | Performance WTR |
| `U_str(2,N2)` | `cons_firm.rule_performance_str` | A | Performance STR |
| `U_laa(2,N2)` | `cons_firm.rule_performance_laa` | A | Performance LAA |
| `Z_switch(N2)` | `cons_firm.switching_partition_function` | A | Logit denominator for switching |
| `n_all(5,N2)` | `cons_firm.rule_prob_all` | A | All 5 rules × N2 |
| `exp_rule(N2)` | `cons_firm.expectation_rule_choice` | A | Per-firm chosen rule (1=NA..5=LAA) |

---

## 13. Energy-Sector State

**A** for plant-level, **N** for energy-sector aggregates of one nation. Lives on `ElectricityProducer` + `PowerPlant` `AgentSet`s (`GreenPlantSet`, `BrownPlantSet`).

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `K_ge(2)` | `electricity.green_capacity` | N | Green plant capacity |
| `K_de(2)` | `electricity.brown_capacity` | N | Brown plant capacity |
| `Q_ge(2)` | `electricity.green_output` | N | Green supply |
| `Q_de(2)` | `electricity.brown_output` | N | Brown supply |
| `A_de(T)` | `brown_plant.thermal_efficiency_inverse` | A | 1/η thermal efficiency, per vintage |
| `EM_de(T)` | `brown_plant.emissions_per_fuel` | A | Emissions per fuel unit, per vintage |
| `CF_de(T)` | `brown_plant.build_cost_per_vintage` | A | Unit expansion cost, per vintage |
| `C_de(T)` | `brown_plant.operational_cost_per_vintage` | A | Operational unit cost (green plants: zero) |
| `G_de(T)` | `brown_plant.count_per_vintage` | A | #brown plants per vintage |
| `G_de_act(T)` | `brown_plant.count_active_per_vintage` | A | Active (not-replaced) brown count per vintage |
| `G_de_temp(T)` | `brown_plant.count_temp_per_vintage` | A | Temp brown count |
| `G_ge(T)` | `green_plant.count_per_vintage` | A | #green plants per vintage |
| `CF_ge(T)` | `green_plant.build_cost_per_vintage` | A | Nominal unit expansion cost, per vintage |
| `CF_ge_full(T)` | `green_plant.build_cost_full_per_vintage` | A | Effective unit expansion cost (incl. hurry + subsidy) |
| `CS_ge(T)` | `green_plant.subsidy_per_vintage` | A | Subsidy per built green plant, per vintage |
| `IC_en_quota(T)` | `green_plant.amortisation_quota_per_vintage` | A | Quota of expansion cost amortised across vintages |
| `derank_tt(life_plant)` | `brown_plant.dispatch_rank_vintage` | A | Dispatch-ranking helper — vintage |
| `derank_nr(life_plant)` | `brown_plant.dispatch_rank_count` | A | Dispatch ranking — count |
| `derank_nr_act(life_plant)` | `brown_plant.dispatch_rank_count_active` | A | Dispatch ranking — active count |
| `derank_cf(life_plant)` | `brown_plant.dispatch_rank_fixed_cost` | A | Fixed cost in dispatch ranking |
| `derank_cp(life_plant)` | `brown_plant.dispatch_rank_prod_cost` | A | Production cost in dispatch ranking |
| `derank_em(life_plant)` | `brown_plant.dispatch_rank_emissions` | A | Emissions in dispatch ranking |
| `derank_ff(life_plant)` | `brown_plant.dispatch_rank_fuel_use` | A | Fuel use in dispatch ranking |
| `derank_pe(life_plant)` | `brown_plant.dispatch_rank_price_bid` | A | Price bid in dispatch ranking |
| `gerank_tt(life_plant)` | `green_plant.dispatch_rank_vintage` | A | Same for green — vintage |
| `gerank_nr(life_plant)` | `green_plant.dispatch_rank_count` | A | Count |
| `gerank_cf(life_plant)` | `green_plant.dispatch_rank_fixed_cost` | A | Fixed cost |
| `gerank_cs(life_plant)` | `green_plant.dispatch_rank_subsidy` | A | Subsidy |
| `gerank_pe(life_plant)` | `green_plant.dispatch_rank_price_bid` | A | Price bid |
| `N_vintage_de` | `electricity.n_brown_vintages_active` | N | #brown vintages alive |
| `N_vintage_ge` | `electricity.n_green_vintages_active` | N | #green vintages alive |
| `mc_ge` | `electricity.green_marginal_build_cost` | N | Cost of building one extra green plant (incl. hurry, subsidy) |
| `hurrycost` | `electricity.hurry_cost_extra` | N | Hurry cost beyond exp_quota |
| `N_hurrycost` | `electricity.n_plants_before_hurry` | N | Plant count above which hurry-cost is paid |
| `N_ge_prev` | `electricity.green_built_this_step` | N | Green built so far this step |
| `N_ge_des` | `electricity.green_desired_new` | N | Desired new green plants |
| `N_ge_easy` | `electricity.green_easy_desired` | N | Easy-to-compute desired greens |
| `N_ge_subs` | `electricity.green_with_subsidy_no_hurry` | N | Greens built with subsidy, no hurry |
| `N_ge_stan` | `electricity.green_standard_built` | N | Greens with neither subsidy nor hurry |
| `N_ge_unwill` | `electricity.green_unwilling_flag` | N | =0 when willing to build more green |
| `CF_ge_limlow` | `green_plant_build_cost_floor_now` | G | Inflation-corrected minimum CF_ge |
| `CF_de_limlow` | `dirty_plant_build_cost_floor_now` | G | Inflation-corrected minimum CF_de |
| `CF_ge_gov_limlow` | `green_plant_build_cost_govt_floor_now` | G | Inflation-corrected min CF_ge via govt RnD |
| `c_en(3)` | `electricity.cost_history` | N | Cost of energy history |
| `c_en_raw(8)` | `electricity.cost_raw_history` | N | Raw cost of energy history |
| `PC_en` | `electricity.production_cost` | N | Production cost of energy |
| `pf` | `fossil_fuel_price` | N | Price of fossil fuel (v3 Appendix B item 7) |
| `mi_en` | `electricity.markup` | N | Energy-producer markup |
| `Q_de_temp` | `electricity.brown_residual_demand_loop` | N | Residual dirty demand in loop |
| `c_de_min` | `electricity.brown_cost_min_loop` | N | Min dirty cost in loop |
| `cf_de_min` | `electricity.brown_build_cost_min_loop` | N | Min dirty build cost in loop |
| `cf_ge_min` | `electricity.green_build_cost_min_loop` | N | Min green build cost in loop |
| `cf_min_ge` | `electricity.green_build_cost_min_aux` | N | Min green build cost aux |
| `c_infra` | `electricity.inframarginal_unit_cost` | N | Unit cost of inframarginal plant |
| `idmin` | `electricity.cheapest_plant_index` | N | Plant index with min cost |
| `tt_ge` | `electricity.best_green_vintage` | N | Best green plant index |
| `tt_de` | `electricity.best_brown_vintage` | N | Best brown plant index |
| `newplant_yn` | `electricity.replace_decision_flag` | N | Whether to do premature replacement |
| `EI_en` | `electricity.expansion_investment_total` | N | Total expansionary investment |
| `EI_en_de` | `electricity.expansion_investment_brown` | N | Brown expansion investment |
| `EI_en_ge` | `electricity.expansion_investment_green` | N | Green expansion investment |
| `LDexp_en` | `electricity.labour_demand_build` | N | Labour for building new plants |
| `Rev_en` | `electricity.revenue` | N | Energy-producer revenue |
| `RD_en_de` | `electricity.rd_spend_dirty` | N | R&D spend, dirty energy |
| `RD_en_ge` | `electricity.rd_spend_green` | N | R&D spend, green energy |
| `RD_en` | `electricity.rd_spend_total` | N | Total electricity R&D spend |
| `LDrd_de` | `electricity.labour_demand_rd_dirty` | N | Labour for dirty R&D |
| `LDrd_ge` | `electricity.labour_demand_rd_green` | N | Labour for green R&D |
| `LDrd_en` | `electricity.labour_demand_rd_total` | N | Total R&D labour, electricity |
| `LDff_1` | `fuel_labour_demand_s1` | N | Labour for sector-1 fuel extraction |
| `LDff_en` | `fuel_labour_demand_electricity` | N | Labour for electricity-firm fuel |
| `LDff_tot` | `fuel_labour_demand_total` | N | Total fuel-extraction labour |
| `parber_en_de` | `electricity.bernoulli_dirty_innovation` | N | Bernoulli draw — dirty innovation |
| `parber_en_ge` | `electricity.bernoulli_green_innovation` | N | Bernoulli draw — green innovation |
| `parber_univ` | `electricity.bernoulli_univ` | N | Bernoulli for govt fundamental RnD |
| `rnd_univ` | `electricity.univ_innovation_gain` | N | Gain achieved by fundamental RnD |
| `uu1_ge` | `green_buildcost_innov_lower_now` | N | Current uu1_ge (drifts via university research) |
| `uu2_ge` | `green_buildcost_innov_upper_now` | N | Current uu2_ge |
| `Inn_en_de` | `electricity.innovated_dirty` | N | Innovation success — dirty |
| `Inn_en_ge` | `electricity.innovated_green` | N | Innovation success — green |
| `Inn_gov_ge` | `electricity.innovated_govt_applied` | N | Innovation success — government applied RnD |
| `Inn_univ_ge` | `electricity.innovated_govt_univ` | N | Innovation success — government fundamental RnD |
| `A_de_inn` | `electricity.dirty_thermal_eff_innov_result` | N | Innovation output — dirty thermal eff |
| `EM_de_inn` | `electricity.dirty_emissions_innov_result` | N | Innovation output — dirty emissions intensity |
| `CF_ge_inn` | `electricity.green_buildcost_innov_result` | N | Innovation output — green build cost |
| `CF_de_inn` | `electricity.dirty_buildcost_innov_result` | N | Innovation output — dirty build cost |
| `CF_ge_gov_inn` | `electricity.green_buildcost_govt_innov_result` | N | Govt innovation output for green build cost |
| `Emiss_en` | `electricity.emissions` | N | Emissions from energy sector |
| `Emiss_init` | `emissions_init_climbox` | N | Initial emissions at climate-box start |
| `Fuel_cost` | `electricity.fuel_cost_total` | N | Total fuel cost |
| `IC_en` | `electricity.investment_cost_green` | N | Total cost of green expansion |
| `Pi_en` | `electricity.profit` | N | Energy-sector profit |
| `NW_en` | `electricity.net_worth` | N | Energy-sector net worth |
| `Gbailout_en` | `electricity.govt_bailout_received` | N | Govt energy-sector bailout cost |
| `prudinv` | `electricity.prudent_investment_limit` | N | Prudent-investment limit |
| `K_green` | `electricity.green_capacity_scalar` | N | Green capacity (scalar shortcut) |
| `K_dirty` | `electricity.brown_capacity_scalar` | N | Brown capacity (scalar shortcut) |
| `share_de` | `electricity.dirty_rd_share` | N | Current share of R&D on dirty |
| `deadline` | `electricity.brown_ban_deadline` | N | Deadline of brown ban |
| `deadline_latebrown` | `electricity.brown_late_replacement_deadline` | N | Deadline corrected for late-brown rule |
| `g_rate_em_y` | `emissions_growth_rate_yearly` | N | Yearly emissions-growth rate |
| `Share_energy_emiss` | `share_emissions_from_energy_sector` | N | Energy-sector share of total emissions |
| `Share_energy_green` | `share_green_energy` | N | Green share of energy |
| `PC_en_eff` | `electricity.production_cost_eff` | N | Effective PC_en (saved value) |
| `Emiss_en_eff` | `electricity.emissions_eff` | N | Effective energy emissions |
| `Fuel_cost_eff` | `electricity.fuel_cost_eff` | N | Effective fuel cost |
| `IC_en_eff` | `electricity.investment_cost_green_eff` | N | Effective green investment cost |
| `elrat` | `electricity_fuel_ratio_aux` | N | Aux ratio raw electricity / fuel |
| `D1_en_TOT` | `electricity_demand_s1_total` | N | Total electricity demand from cap-good |
| `D2_en_TOT` | `electricity_demand_s2_total` | N | Total electricity demand from cons-good |
| `D1_ff_TOT` | `fossil_demand_s1_total` | N | Total fossil-fuel demand from cap-good |
| `D_en_TOT` | `electricity_demand_total` | N | Aggregate electricity demand |
| `D_en_build` | `electricity_demand_for_build` | N | Demand plus safety margin for plant-building |
| `D_en_hist(12)` | `electricity_demand_history` | N | Past D_en_TOT values |
| `Emiss1_TOT` | `emissions_total_s1` | N | Total cap-good emissions |
| `Emiss2_TOT` | `emissions_total_s2` | N | Total cons-good emissions |
| `Emiss_TOT(freqclim*2)` | `emissions_total_history` | N | Total emissions (recent windows) |
| `Emiss_yearly(2)` | `emissions_yearly` | N | Yearly emissions (cur + prev) |
| `Emiss_yearly_calib(2)` | `emissions_yearly_calibrated` | N | Yearly emissions calibrated to 2010 |
| `Emiss_gauge` | `emissions_gauge_climbox_start` | N | Reference emission at climate-box start |
| `dummy_replace_de` | `electricity.dummy_replace_brown` | N | Plant replacement-quota helper (brown). Declared as "dummy" but semantically tied to ENERGY's replacement logic, so retained here. |
| `dummy_replace_ge` | `electricity.dummy_replace_green` | N | Plant replacement-quota helper (green). |

---

## 14. Climate Module State

**G (Global)** by default per v3 Appendix B item 3; toggles to **N** when `flag_shared_climate=False`. Lives on `ClimateSystem` (one global instance) or per-`Nation`.

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `Con(2,ndep)` | `climate.ocean_carbon_per_layer` | G | Carbon in ocean layers (GtC) |
| `Hon(2,ndep)` | `climate.ocean_heat_per_layer` | G | Heat content (J/m²) |
| `Ton(2,ndep)` | `climate.ocean_temperature_per_layer` | G | Layer temperatures |
| `Con0(ndep)` | `climate.ocean_carbon_pre_ind` | G | Pre-industrial carbon per layer |
| `fluxC(ndep-1)` | `climate.carbon_fluxes_between_layers` | G | Inter-layer carbon fluxes |
| `fluxH(ndep-1)` | `climate.heat_fluxes_between_layers` | G | Inter-layer heat fluxes |
| `Con1` | `climate.upper_layer_carbon_guess` | G | Iteration guess — upper-layer C |
| `Ctot1` | `climate.upper_atm_total_guess` | G | Iteration guess — upper + atm C |
| `Cat(2)` | `climate.atmospheric_carbon` | G | Atmospheric carbon (GtC) |
| `biom(2)` | `climate.biosphere_carbon` | G | Biosphere carbon (GtC) |
| `humm(2)` | `climate.humus_carbon` | G | Humus carbon (GtC) |
| `NPP` | `climate.net_primary_production` | G | NPP |
| `biorelease` | `climate.biosphere_decay_release` | G | C released from decaying biomass |
| `humrelease` | `climate.humus_decay_release` | G | C released from decaying humus |
| `Cat1` | `climate.atmospheric_carbon_guess` | G | Iteration guess for Cat |
| `dCat1` | `climate.atmospheric_carbon_increment` | G | C added by emissions/land |
| `Cax(niterclim)` | `climate.cat_iter_guess` | G | Cat for atm-ocean equilibration iteration |
| `Caxx(niterclim)` | `climate.cat_iter_guess_alt` | G | Similar to Cax |
| `Cay(niterclim)` | `climate.cat_iter_residual` | G | Iteration residual |
| `Cayy(niterclim)` | `climate.cat_iter_residual_alt` | G | Alt iteration residual |
| `Caa(niterclim)` | `climate.cat_iter_slope` | G | Estimated slope during iteration |
| `Tmixed(2)` | `climate.surface_temperature` | G | Surface (mixed-layer) temperature anomaly; surface temp = top-ocean-layer temp |
| `FCO2` | `climate.radiative_forcing_co2` | G | Radiative forcing from CO2 |
| `Fin` | `climate.radiative_forcing_in` | G | Input radiative forcing (incl. non-CO2) |
| `Fout` | `climate.outgoing_radiation_due_to_warming` | G | Outgoing radiation due to warming |
| `Tanomaly(5)` | `climate.temperature_anomaly_history` | G | Temperature anomaly history |
| `U_augmented(2)` | `unemployment_augmented_for_build` | N | U augmented for new-plant labour demand |
| `X_a(2)` | `climate.shock_beta_location` | N | Beta-distribution location for shocks |
| `X_b(2)` | `climate.shock_beta_scale` | N | Beta-distribution scale for shocks |
| `shocks_encapstock_de(T)` | `brown_plant.capital_stock_shock` | A | Climate shock — dirty energy capital stock (per vintage) |
| `shocks_encapstock_ge(T)` | `green_plant.capital_stock_shock` | A | Climate shock — clean energy capital stock (per vintage) |
| `Cum_emissions` | `climate.cumulative_emissions` | G | Cumulative emissions |
| `shock_pop` | `nation.shock_population` | N | Population shock |
| `shock_cons` | `nation.shock_consumption` | N | Aggregate consumption shock |
| `Loss` | `nation.damage_loss` | N | Nordhaus 2013 quadratic loss |
| `GDP_nord` | `nation.gdp_after_damages` | N | Damage-adjusted GDP |

---

## 15. Policy Instruments State (Carbon Tax, Electrification, Green Build)

**N (Nation)** — each `ClimatePolicy` instrument lives on a `Nation`.

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `t_CO2_use(4)` | `carbon_tax_revenue_allocation_current` | N | Current allocation of CO2-tax revenue across 4 destinations |
| `t_CO2_I1` | `carbon_tax_rate_s1` | N | Carbon tax per unit emission, sector 1 |
| `t_CO2_I2` | `carbon_tax_rate_s2` | N | Carbon tax per unit emission, sector 2 |
| `t_CO2_en` | `carbon_tax_rate_energy` | N | Carbon tax per unit emission, energy |
| `Subwage(3)` | `wage_tax_subsidy_history` | N | Subsidy for wages potentially financed by CO2 tax |
| `tp_elfrac(2)` | `electrification_mandate_fine_total` | N | Total fine paid by S1 firms for missing electrification |
| `tp_CO2_I1_TOT` | `carbon_tax_revenue_s1` | N | Total CO2 tax paid by sector 1 |
| `tp_CO2_I2_TOT` | `carbon_tax_revenue_s2` | N | Total CO2 tax paid by sector 2 |
| `tp_CO2_en_TOT` | `carbon_tax_revenue_energy` | N | Total CO2 tax paid by energy sector |
| `tp_CO2_TOT(2)` | `carbon_tax_revenue_total` | N | Total CO2 tax paid economy-wide |
| `elfrac_reg_val` | `electrification_mandate_target_value` | N | Electrification value to be achieved |
| `elfrac_reg_start` | `electrification_mandate_start_step` | N | Step at which mandate starts |
| `elfrac_reg_fine` | `electrification_mandate_fine_coef` | N | Fine scaling = (target-actual)×coef |
| `elfrac_reg_react` | `electrification_mandate_reaction_periods` | N | Reaction-time-span before mandate |
| `elfrac_reg_now` | `electrification_mandate_active_target` | N | Mandate currently enforced |
| `elfrac_reg_exp` | `electrification_mandate_expected_target` | N | Mandate firms prepare for |
| `brown_invest_ban` | `brown_invest_ban_step` | N | Step after which brown investment is forbidden |
| `brown_use_ban` | `brown_use_ban_step` | N | Step after which running brown is forbidden |
| `NSubmax_ge` | `green_subsidy_max_count` | N | Max #plants subsidised |
| `Sub_ge` | `green_subsidy_per_plant` | N | Subsidy per green plant |
| `Sub_ge_used` | `green_subsidy_used_this_step` | N | Subsidy used this step |
| `GreenBuildFund` | `green_build_fund_budget` | N | Govt fund for building extra green plants |
| `GreenBuildExpend` | `green_build_fund_spent` | N | Expenditure used from green-build fund |
| `Clim_policy_cost` | `climate_policy_total_cost` | N | Total govt cost of climate policy (excl. CO2 tax expenditure) |
| `plant_worth_lost` | `stranded_asset_worth` | N | Worth of plants removed prematurely |
| `RnD_funds_En` | `electricity_rd_funds_from_tax` | N | State funds from CO2 tax for green-electricity research |
| `RnD_funds_En_eff` | `electricity_rd_funds_effective` | N | Effective state funds (declines as CF_ge falls) |
| `RnD_gov_grant_En` | `electricity_rd_grant_extra` | N | Extra (non-tax) grant for green electricity |
| `RnD_gov_grant_cost` | `electricity_rd_grant_total_cost` | N | Total cost of grants (additive or multiplicative) |
| `RnD_en_ge_mult` | `electricity_green_rd_multiplier` | N | Multiplier for firm green RnD (govt top-up) |
| `RnD_en_all_mult` | `electricity_total_rd_multiplier` | N | Govt provides this fraction of firm's TOTAL RnD for green RnD |
| `RD_gov_topup_tot` | `green_rd_topup_total` | N | Total amount added to green RnD from top-ups |
| `RnD_funds_S1` | `s1_rd_funds_from_tax` | N | State funds from CO2 tax for sector-1 energy research |
| `RnD_gov_grant_S1` | `s1_rd_grant_extra` | N | Extra grant for sector-1 energy research |
| `RD_gov_ge` | `green_rd_government_applied` | N | Govt's own applied green RnD spending |
| `RD_univ_ge` | `green_rd_university` | N | Govt's fundamental green RnD spending |
| `CUM_RD_univ` | `green_rd_university_cumulative` | N | Cumulative fundamental-RnD expenditure |

---

## 16. Miscellaneous Sector-1 / Sector-2 Aggregates Reachable as Externs

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `A1p_en_max` | `s1_energy_eff_max` | N | Tracked but not actively used — max EE (process) |
| `A1p_ef_max` | `s1_proc_emission_max` | N | Tracked but not actively used |
| `A1_en_max` | `s2_energy_eff_max` | N | Tracked but not actively used — max EE (used) |
| `A1_ef_max` | `s2_proc_emission_max` | N | Tracked but not actively used |
| `Am1_ef` | `s1_proc_emission_mean` | N | Mean EF, sector 1 (not actively used per comment) |
| `Am1_en` | `s1_energy_eff_mean` | N | Mean EE, sector 1 (not actively used per comment) |
| `Am2_ef` | `s2_proc_emission_mean` | N | Mean EF, sector 2 |
| `Am2_en` | `s2_energy_eff_mean` | N | Mean EE, sector 2 |
| `Am0_en` | `energy_eff_init` | G | Initial mean EE used in MACRO |
| `Am0_ef` | `proc_emission_init` | G | Initial mean EF used in MACRO |
| `Am_en(2)` | `economy_mean_energy_eff` | N | Economy-wide average EE |
| `Am_ef(2)` | `economy_mean_proc_emission` | N | Economy-wide average EF |
| `nmachprod` | `s1_machines_produced_count` | N | (already in §12) #machines produced |
| `cmin` | `cost_min_temp` | N | Used in COSTPROD to find min unit cost |
| `imin` | `cost_min_firm_index` | N | Firm index at min cost |
| `jmin` | `cost_min_firm_index_alt` | N | Alternate index at min cost |
| `tmin` | `cost_min_time_index` | N | Time index at min cost |

---

## 17. Auxiliary / Output / Bookkeeping

These are **G** but mostly serve the output sink in C++. In Python we use `OutputSink` and don't carry these as state.

| C++ Symbol | Python Name | Scope | Comment |
|---|---|---|---|
| `nomefile`, `nomefile0..28`, `nomefilep` | `output_filenames` | G | Output filename roots — replaced by `OutputSink` |
| `num` | `output_file_number` | G | File-numbering suffix |
| `numofpars` | `n_experiment_parameters` | G | Number of parameters in experiment sweep |
| `numMCexp` | `n_experiment_mc` | G | Number of MC runs per experiment value |
| `pars` | `experiment_parameter_matrix` | G | Vector of experiment-parameter values |
| `check_steps` | `mc_completion_counter` | G | MC-iteration completion counter |
| `broken_iterations` | `mc_broken_iterations` | G | Count of broken MC iterations |
| `seed`, `p_seed` | `rng_seed`, `rng_seed_ptr` | G | RNG seed and pointer — replaced by numpy `SeedSequence` |
| `debug` (`ofstream`) | `debug_log` | G | Debug stream — replaced by Python `logging` |
| `nomefile`s, etc. | (skip) | — | Strictly bookkeeping |
| `pareto_rv`, `num_values`, `sum_NL` | `pareto_rv`, `pareto_n_values`, `pareto_sum_nl` | N | Pareto RNG state for bank-client distribution |

---

## 18. Functions in module headers

| C++ Function | Module | Python Method | Comment |
|---|---|---|---|
| `EN_DEM(void)` | energy | `Nation.aggregate_energy_demand(t)` | Aggregates sector-1+2 energy demands |
| `EMISS_IND(void)` | energy | `Nation.compute_industrial_emissions(t)` | Sector-1 + sector-2 emissions |
| `ELETRICITY_MARKET(void)` | energy | `ElectricityProducer.organise_prices(t)` | (sic) Electricity-market prices |
| `green_plant_cost(...)` | energy | `ElectricityProducer.green_plant_cost(...)` | Build-cost helper |
| `ENERGY(void)` | energy | `Nation.run_electricity_market(t)` | Master energy-sector update |
| `BANKING(void)` | finance | `BankingSector.update_balance_sheets(t)` | Bank profit + balance-sheet composition |
| `TOTCREDIT(void)` | finance | `BankingSector.compute_total_credit_supply(t)` | Max credit in economy |
| `BAILOUT(void)` | finance | `BankingSector.bailout_failed_banks(t)` | Bailout rule |
| `WAGE(void)` | macro | `LabourMarket.update_wage(t)` | Aggregate wage |
| `TAYLOR(void)` | macro | `CentralBank.apply_taylor_rule(t)` | Monetary policy |
| `LABOR(void)` | macro | `LabourMarket.aggregate_labour_demand(t)` | Aggregate sector labour demand |
| `GOV_BUDGET(void)` | macro | `Government.update_budget(t)` | Government policy / budget |
| `MACRO(void)` | macro | `Nation.aggregate_macro_indicators(t)` | Macro aggregations |
| `CRISES_LIKELIHOOD(void)` | macro | `NationalAccounts.compute_crisis_likelihood(t)` | Crisis likelihood |
| `CLIMATEBOX(void)` | climate | `ClimateSystem.step(emissions)` | C-ROADS climate-box step |
| `UPDATECLIMATE(void)` | climate | `ClimateSystem.update_state()` | Shift current state to previous |

Non-module functions (from `dsk_main.cpp`) the build plan also touches: `INITIALIZE`, `MACH`, `BROCHURE`, `EXPECT`, `INVEST`, `SCRAPPING`, `MAXCREDIT`, `ALLOCATECREDIT`, `PRODMACH`, `COMPET2`, `PROFIT`, `ALLOC`, `ENTRYEXIT`, `TECHANGEND`, `SAVE`, `UPDATE`, `CANCMACH`, `CLIMATE_POLICY`, `BONDS_DEMAND`. These are catalogued by the IMPLEMENTATION_PLAN, not re-listed here.

---

## 19. Disambiguation Notes

1. **Machine tensor `g[T][N1][N2]` & relatives.** The C++ ships a global tensor over (time, supplier, owner). v3 replaces this with one `MachineStock` per `ConsumptionGoodFirm`, with 2-D `count[vintage, supplier]` and parallel productivity / EE / EF / elfrac arrays. There is **no** `Machine` Python class. See PORT_PLAN_v3.md §3.3.
2. **Two definitions of `Em2`.** The matrix `Em2(2)` is the mean competitiveness of the cons-good sector — it is a sector-level aggregate, hence **N**. Earlier C++ used a different `Em2`; this NAME_MAP follows the version in `dsk_globalvar.h`.
3. **Foreign firms (`A1f`, `A1pf`, `A1w`, `A1pw`).** Per v3 Appendix B item 6:
   - **N=1:** treat as exogenous foreign frontier (A scope, attached to a `ForeignFrontier` helper inside `CapitalGoodSector`).
   - **N≥2:** replaced by inter-nation imitation pool with per-pair `imitation_distance`; the C++ tables are mostly retired.
4. **`pf` / `fossil_fuel_price`.** Global default (`GlobalParameters.fossil_fuel_price`), per-nation YAML override (`NationParameters.fossil_fuel_price`). Treated as **N** at runtime.
5. **Climate state (`Cat`, `Con`, `Ton`, `Hon`, `Tmixed`, `biom`, `humm`).** **G** by default per the v3 baseline (`flag_shared_climate=True`). Becomes **N** when set to `False` for verification against the C++ `twoDSKmodel`.
6. **Carbon-tax variables (`t_CO2_*`, `tp_CO2_*`, `t_CO2_use`).** Per-nation (**N**) because policy varies per nation in asymmetric scenarios. Constants `t_CO2_I10`, `t_CO2_I20`, `t_CO2_en0` are global scaling baselines (**G**).
7. **Bank-related aggregates with `_all` suffix.** These are nation-level sums (`Debt_all`, `BankCash_all`, `BankCredit_all`, ...). All tagged **N**.
8. **Pareto distribution parameters & state.** `pareto_a/k/p` are global constants (**G**); `pareto_rv`, `num_values`, `sum_NL` are per-nation working state (**N**) used in bank initialisation.
9. **`flag_dskQE`-conditional variables.** `bonds_dem`, `bonds_sup`, `spread_marktomarket`, `r_marktomarket` are active when `flag_dskQE=1` (baseline). In Python they always exist; behavior switches via the flag.
10. **`mi2` / markup.** Listed as **N** because it is an experiment-tunable variable in `dsk_globalvar.h:581`, even though it derives from constant `mi2=0.2` in commented-out KS15 code. Keep mutable; expose on `NationParameters`.
11. **Sentinels excluded.** Variables purely internal to inner loops (`elfrac_diff1/2`, `dummy_*`, `intdummy*`, `cost*_dummy*`, `d1_*_dummy*`, `norm_dummy`, `i`, `j`, `t`, `tt`, `ii`, `jj`, `iii`, `jjj`, `kkk`, `lll`, `ttt`, `n`, `step`, `stepbis`, `cont`, `imax`, `tmax`, `jmax`, `ind_i`, `ind_tt`, `indforn`, `nextmax1`, `nextmax2`, `rni`, `rnf`, `flag`, `t00`, `nsize`, `newbroch`, `parber` (the temp float), `epss` is a draw not a variable) are intentionally not listed.
12. **Externs that are re-declarations.** Many module headers re-declare globals from `dsk_globalvar.h` (e.g., `extern Matrix Deb2` in `module_macro.h`). These are not separate symbols — they are name-bound to the same data. The NAME_MAP table lists each unique symbol once.
13. **Function aliases.** `BANKING` (finance) and the variable named `BANKING` don't conflict in C++ (function vs no-such-var). For Python we use methods on `BankingSector`.
14. **C++ source typos in `module_finance.h`.** Two `extern` declarations there are misspelt: `extern double Debtall;` (should be `Debt_all`) and `extern double DebtRemittancesot;` (should be `DebtRemittancestot`). These typos are not used elsewhere in the C++ code — they declare orphan symbols that link to nothing useful. **The Python port should not reproduce them**: use `banking.debt_total` and `banking.debt_repayments_total` (already listed above).
15. **`flagWAGE`/`flagSPREAD`/`flagC`/`flag_bonds`/`flag_dskQE`/`flag_portfolioallocation`/`flag_balancedbudget`/`flagTAYLOR`/`flag_cheat_emiss`/`flag_clim_tech`/`flag_shocks`** are re-`extern`-ed in module headers (recap). These are the same flag constants as in `dsk_flag.h` — listed once in §8.

---

## 20. Acceptance-criteria checklist

- [x] Every `const` definition in `dsk_constant.h` is listed (skipping pure scratch dummies — none present in that file).
- [x] Every `const int flag*` / `bonds_rule` / `flag_DEF` / `flagWAGE2` in `dsk_flag.h` is listed.
- [x] Every `extern` declaration in `module_energy.h` is listed (constants and variables — dummies labelled in §17 / disambiguation).
- [x] Every `extern` declaration in `module_finance.h` is listed.
- [x] Every `extern` declaration in `module_macro.h` is listed.
- [x] Every `extern` declaration in `module_climate.h` is listed.
- [x] Three mandatory columns present (C++ Symbol, Python Name, Scope).
- [x] Fourth column carries translated Italian comments and disambiguating notes.
- [x] Scope tags G/N/A are consistent with v3 Appendix B resolutions.

The user is expected to spot-check this document against the four source files before NAME_MAP becomes "blessed". Any disagreement should be filed back into this document with a note in §19 explaining the resolution.

---

*Generated: 2026-05-14. Sources: `dsk_constant.h` (542 lines), `dsk_flag.h` (403 lines), `dsk_globalvar.h` (1310 lines), `module_energy.h` (308 lines), `module_finance.h` (165 lines), `module_macro.h` (400 lines), `module_climate.h` (232 lines).*
