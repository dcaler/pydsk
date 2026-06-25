# Output reference

pydsk records results through an **output sink** that writes one parquet file per
*table*. Out of the box the core records a single table, **`macro`**, written once per
simulated year by `Nation.save_outputs`. After a run you get `macro.parquet`.

Every row carries three **context columns**, then the economic aggregates.

```python
import pandas as pd
df = pd.read_parquet("out/macro.parquet")
```

## Context columns

| Column | Meaning |
|--------|---------|
| `mc_run` | Monte-Carlo run id (whatever you set on `nation._mc_run`; `0` for a single run). |
| `t` | Simulated year (1-indexed). |
| `nation_id` | The nation that produced the row (the `id` from the simulation YAML). |

To select one run / one nation, filter on these (e.g. `df[df.mc_run == 0]`).

## National accounts

| Column | Meaning |
|--------|---------|
| `gdp_real` | Real GDP (expenditure-based, deflated). |
| `gdp_nominal` | Nominal GDP (current prices). |
| `consumption_real` | Real household consumption. |
| `consumption_nominal` | Nominal household consumption. |
| `investment_real` | Real investment (machines, in machine units). |
| `investment_nominal` | Nominal investment. |
| `inventory_change` | Real change in sector-2 inventories. |

## Prices

| Column | Meaning |
|--------|---------|
| `cpi` | Consumer price index (sales-weighted sector-2 prices). |
| `ppi` | Producer price index (production-weighted sector-1 prices). |

## Labour market

| Column | Meaning |
|--------|---------|
| `unemployment_rate` | Share of the labour force unemployed. |
| `wage` | The economy-wide wage. |
| `labour_demand` | Total labour demanded by firms (+ R&D). |
| `labour_supply` | Total labour available. |

## Productivity

| Column | Meaning |
|--------|---------|
| `mean_machine_prod` | Mean labour productivity embodied in machines sold (sector 1). |
| `mean_process_prod` | Mean productivity of sector-1 firms' own production process. |

## Firm sectors

| Column | Meaning |
|--------|---------|
| `total_profit_s1` | Total sector-1 (capital-good) profit. |
| `total_profit_s2` | Total sector-2 (consumption-good) profit. |
| `total_net_worth_s1` | Aggregate sector-1 net worth. |
| `total_net_worth_s2` | Aggregate sector-2 net worth. |
| `total_debt_s1` | Aggregate sector-1 debt. |
| `n_s2_bankruptcies` | Sector-2 firms exiting this year with positive bad debt. |

## Banking

| Column | Meaning |
|--------|---------|
| `total_bank_equity` | Sum of bank equity. |
| `total_bad_debt` | Bad debt recognised by banks this year. |
| `n_bank_failures` | Number of banks that failed this year. |

## Government & fiscal

| Column | Meaning |
|--------|---------|
| `government_spending` | Government spending (unemployment benefits in the baseline). |
| `government_debt` | Outstanding government debt stock (`Deb`). |
| `government_deficit` | This year's deficit (`Def`). |
| `government_bailout` | Bank-bailout cost this year. |
| `tax_revenue` | Total tax revenue. |
| `debt_on_gdp` | Debt-to-GDP (debt / nominal GDP when GDP > 1). |

## Monetary policy

| Column | Meaning |
|--------|---------|
| `policy_rate` | Central-bank base rate (`r`). |
| `bonds_rate` | Interest rate paid on government bonds. |

## Energy

| Column | Meaning |
|--------|---------|
| `share_energy_green` | Share of electricity supplied by green plants. |
| `electricity_price` | Price of electricity. |
| `total_energy_demand` | Total electricity demanded by firms. |
| `total_green_capacity` | Installed green generating capacity. |
| `total_brown_capacity` | Installed fossil generating capacity. |

## Emissions

| Column | Meaning |
|--------|---------|
| `emissions_total_s1` | Process emissions from sector 1. |
| `emissions_total_s2` | Process emissions from sector 2. |
| `emissions_energy` | Emissions from electricity generation. |
| `emissions_total` | Total emissions (s1 + s2 + energy). |
| `d1_fossil_fuel_demand` | Sector-1 direct fossil-fuel demand. |

## Energy intensity & electrification

| Column | Meaning |
|--------|---------|
| `mean_electrification_s1` | Production-weighted mean electrification fraction of sector-1 firms. |
| `mean_elfrac_s1` | Simple mean electrification fraction (sector 1). |
| `mean_energy_use_s1` | Mean total energy use per unit of output (sector 1). |
| `mean_elec_use_s2` | Mean electricity use per unit of output (sector 2). |

## Climate

| Column | Meaning |
|--------|---------|
| `atmospheric_carbon` | Atmospheric carbon stock from the climate module. |
| `surface_temperature` | Surface temperature anomaly (K above pre-industrial). |
| `emissions_yearly_calib` | Calibrated yearly emissions fed into the climate box. |

---

!!! tip "Adding your own columns"
    The output sink accepts arbitrary keyword fields — to record a new number, add a
    keyword to the `self.sink.record("macro", …)` call in `save_outputs`, or write a
    new table with a different `table_name`. Full recipe in
    [Extending → new outputs](extending.md#recipe-add-a-new-output-variable).

---

**Next:** [Fidelity & randomness](fidelity-and-rng.md) — reproducibility and how to
change the model without silently breaking it.
