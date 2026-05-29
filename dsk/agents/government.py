"""Fiscal authority — Government singleton per Nation.

Mirrors C++ nation-level fiscal variables from dsk_globalvar.h:
Deb, G, bonds, newbonds, Gbailout, Gbailout_all, Deposits_insurance,
t_CO2_I1/I2/en, tp_CO2_* (carbon tax totals), Subwage(1,2,3).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dsk.nation import Nation
    from dsk.parameters.global_parameters import GlobalParameters
    from dsk.parameters.nation_parameters import NationParameters


class Government:
    """Fiscal authority. Collects taxes, pays unemployment benefits, issues bonds."""

    def __init__(self, nation: "Nation") -> None:
        self.nation = nation

        # --- Debt and spending ---
        # Deb: outstanding government debt (bonds stock)
        self.debt: float = 0.0
        # G: autonomous government spending per period
        # flagC==2 baseline: G=0 (only flagC==1 sets G=0.005*LS0)
        self.spending: float = 0.0

        # --- Bond market ---
        # bonds: total bonds outstanding (includes Deb)
        self.bonds_outstanding: float = 0.0
        # newbonds: newly issued bonds this period
        self.new_bonds: float = 0.0
        # bonds_sup / bonds_sup_tot: bonds supply this period (= Def under dskQE)
        self.bonds_supply: float = 0.0
        self.bonds_supply_total: float = 0.0
        # Newbonds_financed: residual deficit left after banks buy (financed by the CB)
        self.new_bonds_financed: float = 0.0

        # --- Bailout ---
        # Gbailout: government cost for bank bailout this period
        self.bailout_cost: float = 0.0
        # Gbailout_all: cumulative bailout spending
        self.total_bailout: float = 0.0

        # --- Deposit insurance fund ---
        # Deposits_insurance: insurance fund balance
        self.deposits_insurance: float = 0.0

        # --- Carbon tax rates (initially 0; set by ClimatePolicy instruments) ---
        # t_CO2_I1: carbon tax rate applied to sector-1 industrial emissions
        self.carbon_tax_rate_industry1: float = 0.0
        # t_CO2_I2: carbon tax rate applied to sector-2 industrial emissions
        self.carbon_tax_rate_industry2: float = 0.0
        # t_CO2_en: carbon tax rate applied to energy sector
        self.carbon_tax_rate_energy: float = 0.0

        # --- Carbon tax revenue accumulators ---
        # tp_CO2_en_TOT: total carbon tax paid by energy firms (cumulative or per-period)
        self.total_carbon_tax_energy: float = 0.0
        # tp_CO2_I1_TOT: total carbon tax by sector 1
        self.total_carbon_tax_industry1: float = 0.0
        # tp_CO2_I2_TOT: total carbon tax by sector 2
        self.total_carbon_tax_industry2: float = 0.0

        # --- Electrification fine revenue ---
        # tp_elfrac: total fines collected from capital-good firms for insufficient electrification
        self.total_electrification_fine: float = 0.0

        # --- Wage subsidies / taxes ---
        # Subwage(1): subsidy to sector-1 wages (negative = tax)
        # Subwage(2): subsidy to sector-2 wages
        # Subwage(3): unused / reserved
        self.wage_subsidy: list = [0.0, 0.0, 0.0]

        # --- Per-period tax revenue aggregates (populated by realise_profits_and_taxes) ---
        self.tax_revenue_firms: float = 0.0     # taxes on firm profits
        self.tax_revenue_wages: float = 0.0     # payroll / wage taxes
        self.tax_revenue_banks: float = 0.0     # bank profit taxes
        self.unemployment_benefit_paid: float = 0.0  # total transfer payments
        self.deficit: float = 0.0               # = spending + benefits - tax revenue

        # --- Government R&D support (energy, Milestone 3+) ---
        self.rd_gov_grant_energy: float = 0.0   # RnD_gov_grant_En
        self.rd_funds_energy: float = 0.0       # RnD_funds_En

    # ------------------------------------------------------------------

    def initialise_from_parameters(
        self,
        gparams: "GlobalParameters",
        nparams: "NationParameters",
    ) -> None:
        """Set government initial state to C++ INITIALIZE baseline.

        C++ lines ~1463–1547 (fiscal aggregates), 1124–1130 (carbon tax = 0).
        flagC==2 baseline: G = 0 (only flagC==1 sets G = 0.005*LS0).
        """
        self.debt = 0.0                  # Deb = 0
        self.spending = 0.0              # G = 0 (flagC==2)
        self.bonds_outstanding = 0.0     # bonds = 0
        self.new_bonds = 0.0             # newbonds = 0
        self.bonds_supply = 0.0          # bonds_sup = 0
        self.bonds_supply_total = 0.0    # bonds_sup_tot = 0
        self.new_bonds_financed = 0.0    # Newbonds_financed = 0
        self.bailout_cost = 0.0          # Gbailout = 0
        self.total_bailout = 0.0         # Gbailout_all = 0
        self.deposits_insurance = 0.0    # Deposits_insurance = 0

        # Carbon tax rates: initially 0 (Claudia comment)
        self.carbon_tax_rate_industry1 = 0.0   # t_CO2_I1 = 0
        self.carbon_tax_rate_industry2 = 0.0   # t_CO2_I2 = 0
        self.carbon_tax_rate_energy = 0.0      # t_CO2_en = 0
        self.total_carbon_tax_energy = 0.0     # tp_CO2_en_TOT = 0
        self.total_carbon_tax_industry1 = 0.0  # tp_CO2_I1_TOT = 0
        self.total_carbon_tax_industry2 = 0.0  # tp_CO2_I2_TOT = 0
        self.total_electrification_fine = 0.0  # tp_elfrac = 0

        # Wage subsidies all zero at start
        self.wage_subsidy = [0.0, 0.0, 0.0]   # Subwage(1,2,3) = 0

        # Per-period flow aggregates
        self.tax_revenue_firms = 0.0
        self.tax_revenue_wages = 0.0
        self.tax_revenue_banks = 0.0
        self.unemployment_benefit_paid = 0.0
        self.deficit = 0.0

        # Energy R&D support
        self.rd_gov_grant_energy = 0.0   # RnD_gov_grant_En = 0
        self.rd_funds_energy = 0.0       # RnD_funds_En = 0

    # ------------------------------------------------------------------
    # GOV_BUDGET — full implementation (Task 2.2)
    # ------------------------------------------------------------------

    def compute_budget(
        self,
        t: int,
        labour_supply: float,
        labour_demand: float,
        wage: float,
        tax_previous_period: float,
        banks: list,
    ) -> None:
        """Compute government budget: G, deficit, debt, bond repayment, bond issuance.

        Ports C++ module_macro.cpp GOV_BUDGET() (lines 581-1120) for the M2 baseline:
          flagC = 2        : G = (LS-LD)*w*wu  (unemployment benefit only)
          flagTAX = 2      : Tax = previous period's total (firm+bank profit taxes)
          flag_balancedbudget = 0 : Deb += Def  (no fiscal rule)
          flag_DEF = 1     : if Def>0 and Deb<0, use surplus to reduce deficit first
          bonds_payment_rule = 1 : bonds enabled
          bonds_allocation_rule = 1 : new bonds allocated by bank after-tax profit share
          use_dskqe = 1    : banks use cash when profits insufficient
          bonds_repayment_share = 0.025 : fraction of existing bonds repaid each period

        Parameters
        ----------
        t : int
            Current period (1-indexed; t==1 triggers init block).
        labour_supply, labour_demand : float
            LS and LD from the labour market.
        wage : float
            w(2) — previous period's wage (current at GOV_BUDGET call time in C++).
        tax_previous_period : float
            Tax accumulated at END of the previous period (C++ uses Tax from prior
            period; dsk_main.cpp:5093 comment: "Taxes from previous period needed").
        banks : list[Bank]
            Active bank agents; used for bond operations and bailout sum.
        """
        gparams = self.nation.gparams
        nparams = self.nation.params
        wu = nparams.unemployment_benefit_share
        r = nparams.policy_rate
        r_bonds = r * (1.0 - gparams.bonds_markdown)          # = r (bondsmarkdown=0 baseline)
        r_cbreserves = r * (1.0 - gparams.cb_reserves_markdown)  # = r*(1-0.33) ~ 0.0134

        # C++ t==1 init block: GDPm=20000; Tax=60000; Deb=0
        if t == 1:
            Tax = 60_000.0
            self.debt = 0.0
        else:
            Tax = tax_previous_period

        # G(1) — flagC=2: unemployment benefit only (no carbon spending in baseline)
        excess_workers = labour_supply - labour_demand
        self.spending = excess_workers * (wage * wu) if excess_workers > 0.0 else 0.0
        G = self.spending

        # Gbailout_all: sum of per-bank government bailout costs this period
        Gbailout_all = sum(b.bailout_cost for b in banks)
        self.bailout_cost = Gbailout_all
        self.total_bailout += Gbailout_all

        # Deficit (flag_balancedbudget=0; no climate policy cost in baseline)
        if self.debt > 0.0:
            Def = G + Gbailout_all + (r_bonds * self.debt) - Tax
        else:
            Def = G + Gbailout_all + (r_cbreserves * self.debt) - Tax

        # flag_DEF=1: use government surplus (negative debt) to reduce deficit first
        if Def > 0.0 and self.debt < 0.0 and gparams.flag_def == 1:
            if -self.debt > Def:
                self.debt += Def
                Def = 0.0
            else:
                Deb_temp = self.debt + Def
                Def += self.debt
                self.debt = Deb_temp
        else:
            self.debt += Def

        self.deficit = Def

        # ── Bond repayment (flag_mtm=0, bonds_share=0.025) ────────────────
        # Each bank receives bonds_share of its existing bond holdings back as cash.
        bonds_repayment_share = gparams.bonds_repayment_share
        for bank in banks:
            remittances = bonds_repayment_share * bank.bonds_held
            bank.bonds_held -= remittances
            bank.cash += remittances

        # ── New bond issuance (bonds_payment_rule>0, bonds_allocation_rule=1) ──
        self.new_bonds = 0.0
        self.bonds_supply = 0.0
        self.bonds_supply_total = 0.0
        self.new_bonds_financed = 0.0
        if gparams.bonds_payment_rule > 0 and Def > 0.0:
            aliqb = nparams.tax_rate_banks
            # After-tax profit share determines each bank's bond quota (bonds_rule=1)
            net_profits = [(1.0 - aliqb) * b.profits for b in banks]
            total_net_profit = sum(p for p in net_profits if p > 0.0)

            # bonds_sup tracks the residual deficit as banks buy (C++ bonds_sup,
            # only meaningful under dskQE); it starts at the full new issuance Def.
            bonds_sup = Def
            if gparams.use_dskqe:
                self.bonds_supply_total = Def

            if gparams.bonds_portfolio_allocation == 0:
                # KS15 baseline: demand = profit share of Def; bought with cash.
                for bank, net_p in zip(banks, net_profits):
                    if total_net_profit > 0.0:
                        bonds_dem = (max(0.0, net_p) / total_net_profit) * Def
                    else:
                        # Fallback: market-share proportional allocation
                        bonds_dem = bank.market_share * Def

                    # flag_dskQE=1, flag_portfolioallocation=0:
                    # buy bonds_dem if cash covers it; otherwise spend all available cash
                    if bank.cash >= bonds_dem:
                        newbonds = bonds_dem
                    else:
                        newbonds = max(0.0, bank.cash)

                    bank.bonds_held += newbonds
                    bank.cash -= newbonds
                    self.new_bonds += newbonds
                    bonds_sup -= newbonds
            else:
                # flag_portfolioallocation=1: demand pre-set in BONDS_DEMAND
                # (bonds_demand = varphi*BaselBankCredit); bought with credit, not cash.
                bonds_dem_tot = self.nation.banking_sector.bonds_demand_total
                for bank, net_p in zip(banks, net_profits):
                    if total_net_profit > 0.0:
                        profit_quota = (max(0.0, net_p) / total_net_profit) * Def
                    else:
                        profit_quota = bank.market_share * Def

                    if bonds_dem_tot >= bonds_sup and bank.bonds_demand >= profit_quota:
                        newbonds = profit_quota
                    else:
                        # demand below the profit quota, or total demand < supply:
                        # the bank simply takes its (varphi-based) demand
                        newbonds = bank.bonds_demand

                    # C++ overwrites the holding (bonds(i)=newbonds) and uses credit,
                    # so cash is unchanged in this branch.
                    bank.bonds_held = newbonds
                    self.new_bonds += newbonds
                    bonds_sup -= newbonds

            # Residual (Newbonds_financed) financed by the central bank under dskQE.
            self.new_bonds_financed = max(0.0, bonds_sup)
            self.bonds_supply = self.new_bonds_financed
            if gparams.use_dskqe:
                self.nation.central_bank.buy_residual_bonds(
                    residual=self.new_bonds_financed,
                    deficit=Def,
                )

        elif gparams.bonds_payment_rule > 0 and Def <= 0.0:
            # Surplus: redeem outstanding bonds proportionally by market share
            for bank in banks:
                redemption = bank.market_share * (-Def)  # Def<=0, redemption>=0
                if bank.bonds_held >= redemption:
                    bank.bonds_held -= redemption
                    bank.cash += redemption
                else:
                    bank.cash += bank.bonds_held
                    bank.bonds_held = 0.0

        # ── Update aggregate trackers ──────────────────────────────────────
        self.bonds_outstanding = sum(b.bonds_held for b in banks)
        self.tax_revenue_firms = Tax
        self.unemployment_benefit_paid = G
