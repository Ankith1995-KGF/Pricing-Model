import math
from typing import Dict, Tuple, List
import numpy as np
import pandas as pd
import streamlit as st

# ---------- Global formatting (2 decimals everywhere) ----------
pd.options.display.float_format = lambda x: f"{x:.2f}"

def f2(x: float) -> float:
    try:
        return float(np.round(float(x), 2))
    except Exception:
        return float('nan')

def fmt2(x) -> str:
    try:
        return f"{f2(float(x)):.2f}"
    except Exception:
        return ""

# ---------- Tiny number-to-words (integers; no external lib) ----------
def num_to_words(n: int) -> str:
    units = ["","one","two","three","four","five","six","seven","eight","nine"]
    teens = ["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"]
    tens  = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]

    def chunk(x: int) -> str:
        if x == 0: return ""
        if x < 10: return units[x]
        if x < 20: return teens[x-10]
        if x < 100: return tens[x//10] + ("" if x%10==0 else " " + units[x%10])
        if x < 1000: return units[x//100] + " hundred" + ("" if x%100==0 else " " + chunk(x%100))
        return ""

    if n == 0: return "zero"
    parts = []
    for div, word in [(10**9,"billion"), (10**6,"million"), (10**3,"thousand")]:
        if n >= div:
            parts.append(chunk(n//div) + " " + word)
            n %= div
    if n > 0:
        parts.append(chunk(n))
    return " ".join(parts)

# ---------- Utility helpers ----------
def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(x, hi))

def malaa_label(score: int) -> str:
    if score < 500: return "High"
    if score < 650: return "Medium-High"
    if score < 750: return "Medium"
    return "Low"

# ---------- Factors / maps ----------
PRODUCTS_FUND = ["Asset Backed Loan", "Term Loan", "Export Finance"]
PRODUCTS_UTIL = ["Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"]

product_factor: Dict[str, float] = {
    "Asset Backed Loan": 1.35, "Term Loan": 1.20, "Export Finance": 1.10,
    "Vendor Finance": 0.95, "Supply Chain Finance": 0.90, "Trade Finance": 0.85,
    "Working Capital": 0.95
}
industry_factor: Dict[str, float] = {
    "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
    "Hospitality": 1.25, "Retail": 1.15, "Manufacturing": 1.10,
    "Trading": 1.05, "Logistics": 1.00, "Oil & Gas": 0.95,
    "Healthcare": 0.90, "Utilities": 0.85, "Agriculture": 1.15
}
u_med_map: Dict[str, float] = {
    "Trading":0.65,"Manufacturing":0.55,"Construction":0.40,"Logistics":0.60,"Retail":0.50,
    "Healthcare":0.45,"Hospitality":0.35,"Oil & Gas":0.50,"Real Estate":0.30,"Utilities":0.55,
    "Mining":0.45,"Agriculture":0.40
}

def malaa_factor(score: int) -> float:
    # 300->1.45 risk factor, 900->0.55 (inverse relation)
    return float(np.clip(1.45 - (score - 300)*(0.90/600), 0.55, 1.45))

def ltv_factor(ltv_pct: float) -> float:
    return float(np.clip(0.55 + 0.0075*ltv_pct, 0.80, 1.50))

def wcs_factor(wc: float, sales: float) -> float:
    if sales <= 0: 
        return 1.20
    ratio = wc / sales
    return float(np.clip(0.70 + 1.00*min(ratio, 1.2), 0.70, 1.70))

def pd_from_risk(r: float, stage: int) -> float:
    # 0.4→0.3%, 1.0→1.0%, 2.0→3.0%, 3.5→6.0% with stage multipliers
    xs = np.array([0.4, 1.0, 2.0, 3.5])
    ys = np.array([0.3, 1.0, 3.0, 6.0])
    pd = float(np.interp(r, xs, ys))
    if stage == 2: pd *= 2.5
    if stage == 3: pd *= 6.0
    return float(np.clip(pd, 0.10, 60.0))

def lgd_from_product_ltv(prod: str, ltv: float) -> float:
    base = 32 if prod=="Asset Backed Loan" else 38 if prod=="Term Loan" else 35 if prod=="Export Finance" else 30
    adj = max(0.0, (0.0 if (ltv is None or np.isnan(ltv)) else ltv)-50.0)*0.25
    if prod in PRODUCTS_UTIL:
        adj += 8.0  # receivable/short-term recovery haircuts
    return float(np.clip(base + adj, 25.0, 70.0))

# ---------- Pricing engine ----------
BUCKETS = ["Low","Medium","High"]
BUCKET_MULT = {"Low":0.90,"Medium":1.00,"High":1.25}
BUCKET_BAND_BPS = {"Low":60,"Medium":90,"High":140}
BUCKET_FLOOR_BPS = {"Low":150,"Medium":225,"High":325}
MALAA_FLOOR_BPS = {"High":175,"Medium-High":125,"Medium":75,"Low":0}

def industry_floor_addon(ind_fac: float) -> int:
    return 100 if ind_fac >= 1.25 else (50 if ind_fac >= 1.10 else 0)

def product_floor_addon(product: str) -> int:
    return 125 if product == "Asset Backed Loan" else (75 if product in ["Term Loan","Export Finance"] else 0)

def spread_from_risk(risk: float) -> float:
    # base curve in bps
    return 75 + 350*(risk - 1.0)

def composite_risk(product: str, industry: str, malaa: int, ltv: float, wc: float, sales: float, loan_type: str) -> float:
    pf = product_factor[product]
    inf = industry_factor[industry]
    mf = malaa_factor(malaa)
    if loan_type == "Fund":
        rf = ltv_factor(ltv if ltv is not None else 60.0)
    else:
        rf = wcs_factor(wc if wc is not None else 0.0, sales if sales is not None else 0.0)
    return float(np.clip(pf * inf * mf * rf, 0.4, 3.5))

def compute_bucket_rates(
    bucket: str,
    risk_base: float,
    product: str,
    industry: str,
    malaa_score: int,
    oibor_pct: float,
    cof_pct: float,
    target_nim_pct: float,
    fees_pct: float,
    opex_pct: float,
    stage: int,
    loan_type: str,
    rate_min_floor: float = 5.00,
    fund_rate_floor: float = 6.00,
    rate_cap: float = 12.00,
    min_core_spread_bps: int = 125
) -> Dict:
    # 1) risk for bucket
    risk_b = float(np.clip(risk_base * BUCKET_MULT[bucket], 0.4, 3.5))

    # 2) PD/LGD and Provision (annual % of avg EAD)
    pd_pct = pd_from_risk(risk_b, stage)
    lgd_pct = lgd_from_product_ltv(product, np.nan)  # for fund we’ll recalc later if needed
    prov_pct = float(np.clip(pd_pct * (lgd_pct/100.0), 0.10, 60.0))

    # 3) Base spread (bps) = curve + floors
    raw_bps = spread_from_risk(risk_b)
    malaa_lbl = malaa_label(malaa_score)
    ind_add = industry_floor_addon(industry_factor[industry])
    prod_add = product_floor_addon(product)
    floors = BUCKET_FLOOR_BPS[bucket] + MALAA_FLOOR_BPS[malaa_lbl] + ind_add + prod_add
    base_spread_bps = max(int(round(raw_bps)), floors, min_core_spread_bps)

    # 4) Build band around center
    band = BUCKET_BAND_BPS[bucket]
    spread_min_bps = max(base_spread_bps - band, floors, min_core_spread_bps)
    spread_max_bps = max(base_spread_bps + band, spread_min_bps + 10)

    # 5) Convert to rates, apply floors & cap
    rate_min = clamp(oibor_pct + spread_min_bps/100.0, rate_min_floor, rate_cap)
    rate_max = clamp(oibor_pct + spread_max_bps/100.0, rate_min_floor, rate_cap)
    rep_rate = (rate_min + rate_max) / 2.0

    # Fund-based floor rate 6.00% before NIM floor
    if loan_type == "Fund":
        rate_min = max(rate_min, fund_rate_floor)
        rate_max = max(rate_max, fund_rate_floor)
        rep_rate = max(rep_rate, fund_rate_floor)

    # 6) Target NIM floor (lift center if needed)
    required_rate = target_nim_pct + cof_pct + prov_pct + opex_pct - fees_pct
    rep_rate = max(rep_rate, required_rate)

    # 7) Rebuild min/max symmetrically around new center, clamp again
    half_band = band / 200.0  # because band is bps, /100 to %, then /2 for half-band
    rate_min = clamp(rep_rate - half_band, rate_min_floor, rate_cap)
    rate_max = clamp(rep_rate + half_band, rate_min_floor, rate_cap)
    # keep ordering guarantees
    if rate_max - rate_min < 0.10:
        rate_max = clamp(rate_min + 0.10, rate_min_floor, rate_cap)

    # recompute floats over OIBOR in bps from clamped rates
    fl_min_bps = max(int(round((rate_min - oibor_pct)*100)), min_core_spread_bps)
    fl_max_bps = max(int(round((rate_max - oibor_pct)*100)), fl_min_bps + 10)

    return {
        "risk_b": f2(risk_b),
        "pd_pct": f2(pd_pct),
        "lgd_pct": f2(lgd_pct),
        "provision_pct": f2(prov_pct),
        "spread_min_bps": int(fl_min_bps),
        "spread_max_bps": int(fl_max_bps),
        "rate_min": f2(rate_min),
        "rate_max": f2(rate_max),
        "rep_rate": f2(rep_rate),
        "malaa_label": malaa_lbl,
        "floors_total_bps": floors
    }

def fund_based_metrics(
    P: float, tenor_m: int, rep_rate: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float, upfront_cost_pct: float
) -> Tuple[float, float, float, float, float, float, float]:
    """Returns EMI, NII_annual, AEA_12, NIM_pct, BE_min, BE_rep, BE_max are computed outside;
       here we compute for representative rate, and we expose a function for BE given an arbitrary rate."""
    i = rep_rate/100.0/12.0
    if i <= 0: 
        return 0.0, 0.0, 0.0, 0.0

    EMI = P * i * (1+i)**tenor_m / ((1+i)**tenor_m - 1)

    # 12-month NII & avg earning assets
    sum_net_12, sum_bal_12, bal = 0.0, 0.0, P
    months = min(12, max(1, tenor_m))
    for m in range(1, months+1):
        interest = bal * i
        fee      = P * (fees_pct/100.0/12.0)
        funding  = bal * (cof_pct/100.0/12.0)
        prov     = bal * (prov_pct/100.0/12.0)
        opex     = bal * (opex_pct/100.0/12.0)
        net      = interest + fee - (funding + prov + opex)
        sum_net_12 += net
        sum_bal_12 += bal
        principal = EMI - interest
        bal = max(bal - principal, 0.0)

    AEA_12 = max(sum_bal_12 / months, 1e-9)
    NII_annual = sum_net_12
    NIM_pct = (NII_annual / AEA_12) * 100.0
    return f2(EMI), f2(NII_annual), f2(AEA_12), f2(NIM_pct)

def fund_breakeven_months(P: float, tenor_m: int, rate_pct: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float, upfront_cost_pct: float):
    i = rate_pct/100.0/12.0
    if i <= 0 or tenor_m <= 0: return "Breakeven not within the tenor"
    EMI = P * i * (1+i)**tenor_m / ((1+i)**tenor_m - 1)
    bal = P
    C0  = upfront_cost_pct/100.0 * P
    cum = -C0
    for m in range(1, tenor_m+1):
        interest = bal * i
        fee      = P * (fees_pct/100.0/12.0)
        funding  = bal * (cof_pct/100.0/12.0)
        prov     = bal * (prov_pct/100.0/12.0)
        opex     = bal * (opex_pct/100.0/12.0)
        net      = interest + fee - (funding + prov + opex)
        cum += net
        principal = EMI - interest
        bal = max(bal - principal, 0.0)
        if cum >= 0:
            return m
    return "Breakeven not within the tenor"

def util_metrics(
    limit_or_wc: float, industry: str, rep_rate: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float, upfront_cost_pct: float
):
    u = u_med_map[industry]
    EAD = max(limit_or_wc, 0.0) * u
    margin_pct = rep_rate + fees_pct - (cof_pct + prov_pct + opex_pct)
    NIM_pct = margin_pct
    NII_annual = (margin_pct/100.0) * EAD
    C0 = upfront_cost_pct/100.0 * max(limit_or_wc, 0.0)
    if margin_pct > 0 and EAD > 0:
        m_be = math.ceil(C0 / (NII_annual/12.0))
        return f2(EAD), f2(NIM_pct), f2(NII_annual), (m_be if m_be > 0 else 1), f2(u*100.0)
    return f2(EAD), f2(NIM_pct), f2(NII_annual), "Breakeven not within the tenor", f2(u*100.0)

# ---------- Streamlit UI ----------
st.set_page_config(page_title="rt 360 risk-adjusted pricing model", page_icon="💠", layout="wide")

# Header with branding
st.markdown("""
<style>
.big-title {font-size: 28px; font-weight: 800;}
.blue {color: #1666d3;}
.green {color: #18a05e;}
.card {background: white; border: 4px solid #1666d3; padding: 14px 18px; border-radius: 14px; box-shadow: 0 6px 18px rgba(0,0,0,0.08);}
.caption {color: #6b7280; font-size: 12px;}
</style>
<div class="big-title"><span class="blue">rt</span> <span class="green">360</span> — risk-adjusted pricing model for Corporate Lending</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Market & Bank")
    oibor_pct = st.number_input("OIBOR (%)", value=4.10, step=0.00, format="%.2f")
    cof_pct = st.number_input("Cost of Funds (%)", value=5.00, step=0.00, format="%.2f")
    target_nim_pct = st.number_input("Target NIM (%)", value=2.50, step=0.00, format="%.2f")
    fees_default = st.number_input("Default Fees (%) (WC/SCF/VF/Export)", value=0.40, step=0.00, format="%.2f")
    opex_pct = st.number_input("Opex (%)", value=0.40, step=0.00, format="%.2f")
    upfront_cost_pct = st.number_input("Upfront Cost (%)", value=0.50, step=0.00, format="%.2f")
    st.markdown("---")

    st.subheader("Borrower & Product")
    product = st.selectbox("Product", PRODUCTS_FUND + PRODUCTS_UTIL)
    industry = st.selectbox("Industry", list(industry_factor.keys()))
    malaa_score = int(st.number_input("Mala’a Score (300–900)", value=750, step=0, format="%d"))
    stage = int(st.number_input("Stage (1/2/3)", value=1, min_value=1, max_value=3, step=0, format="%d"))
    st.markdown("---")

    st.subheader("Loan Details")
    tenor_months = int(st.number_input("Tenor (months, 6–360)", value=36, min_value=6, max_value=360, step=0, format="%d"))

    loan_type = "Fund" if product in PRODUCTS_FUND else "Utilization"
    if loan_type == "Fund":
        loan_quantum_omr = st.number_input("Loan Quantum (OMR)", value=100000.00, step=0.00, format="%.2f")
        st.caption(f"In words: {num_to_words(int(loan_quantum_omr))} Omani Rials")
        ltv_pct = st.number_input("LTV (%)", value=70.00, step=0.00, format="%.2f")
        wc_omr, sales_omr = 0.0, 0.0
    else:
        # For utilization loans, allow WC and Sales inputs; limit ≈ WC as exposure base
        wc_omr = st.number_input("Working Capital / Limit (OMR)", value=80000.00, step=0.00, format="%.2f")
        st.caption(f"In words: {num_to_words(int(wc_omr))} Omani Rials")
        sales_omr = st.number_input("Annual Sales (OMR)", value=600000.00, step=0.00, format="%.2f")
        st.caption(f"In words: {num_to_words(int(sales_omr))} Omani Rials")
        loan_quantum_omr, ltv_pct = 0.0, float('nan')

    st.markdown("---")
    st.subheader("Loan Book Upload")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    # Downloadable template
    template_cols = [
        "loan_id","product","industry","malaa_score","tenor_months",
        "loan_quantum_omr","limit_omr","working_capital_omr","sales_omr","median_utilization",
        "ltv_pct","stage","pd_pct","lgd_pct","provision_rate_pct",
        "fees_pct","opex_pct","oibor_pct","current_rate_pct"
    ]
    template_df = pd.DataFrame(columns=template_cols)
    st.download_button("Download CSV Template", template_df.to_csv(index=False).encode("utf-8"), file_name="loan_book_template.csv", mime="text/csv")

    st.markdown("---")
    run = st.button("Compute Pricing")

tabs = st.tabs(["Single Loan Pricing", "Loan Book Pricing", "Assumptions"])

# ---------- Single Loan Pricing ----------
with tabs[0]:
    if run:
        # Determine fees for this product
        fees_pct = fees_default if product in ["Working Capital","Trade Finance","Supply Chain Finance","Vendor Finance","Export Finance"] else 0.00

        # Composite risk
        risk_base = composite_risk(product, industry, malaa_score, ltv_pct, wc_omr, sales_omr, loan_type)

        # Prepare bucket results
        bucket_rows: List[Dict] = []

        for b in BUCKETS:
            row = compute_bucket_rates(
                bucket=b,
                risk_base=risk_base,
                product=product,
                industry=industry,
                malaa_score=malaa_score,
                oibor_pct=oibor_pct,
                cof_pct=cof_pct,
                target_nim_pct=target_nim_pct,
                fees_pct=fees_pct,
                opex_pct=opex_pct,
                stage=stage,
                loan_type=loan_type,
                rate_min_floor=5.00,
                fund_rate_floor=6.00,
                rate_cap=12.00,
                min_core_spread_bps=125
            )

            # Compute cashflow metrics for rep rate, and breakeven for min/rep/max
            if loan_type == "Fund":
                # LGD can be refined with LTV for funds:
                lgd_pct_fund = lgd_from_product_ltv(product, ltv_pct)
                prov_pct = f2(pd_from_risk(row["risk_b"], stage) * (lgd_pct_fund/100.0))

                EMI, NII_annual, AEA_12, NIM_pct = fund_based_metrics(
                    loan_quantum_omr, tenor_months, row["rep_rate"], fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct
                )
                be_min = fund_breakeven_months(loan_quantum_omr, tenor_months, row["rate_min"], fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct)
                be_rep = fund_breakeven_months(loan_quantum_omr, tenor_months, row["rep_rate"], fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct)
                be_max = fund_breakeven_months(loan_quantum_omr, tenor_months, row["rate_max"], fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct)

                # Decompose annual components (approximate using rep rate & average balance)
                i_month = row["rep_rate"]/100.0/12.0
                # Approximations over first year using AEA_12:
                annual_interest = (row["rep_rate"]/100.0) * AEA_12
                annual_fee = (fees_pct/100.0) * loan_quantum_omr  # fees on origination base, annualized flat
                annual_funding = (cof_pct/100.0) * AEA_12
                annual_prov = (prov_pct/100.0) * AEA_12
                annual_opex = (opex_pct/100.0) * AEA_12
                nii = annual_interest + annual_fee - (annual_funding + annual_prov + annual_opex)

                bucket_rows.append({
                    "Bucket": b,
                    "Float_Min_over_OIBOR_bps": row["spread_min_bps"],
                    "Float_Max_over_OIBOR_bps": row["spread_max_bps"],
                    "Rate_Min_%": f2(row["rate_min"]),
                    "Rate_Max_%": f2(row["rate_max"]),
                    "Rep_Rate_%": f2(row["rep_rate"]),
                    "EMI_OMR": f2(EMI),
                    "Annual_Interest_Income_OMR": f2(annual_interest),
                    "Annual_Fee_Income_OMR": f2(annual_fee),
                    "Annual_Funding_Cost_OMR": f2(annual_funding),
                    "Annual_Provision_OMR": f2(annual_prov),
                    "Annual_Opex_OMR": f2(annual_opex),
                    "Net_Interest_Income_OMR": f2(nii),
                    "NIM_%": f2(NIM_pct),
                    "Breakeven_Min_Months": be_min,
                    "Breakeven_Rep_Months": be_rep,
                    "Breakeven_Max_Months": be_max,
                    "Borrower_Risk_Label": row["malaa_label"],
                    "Industry_Risk_Factor": f2(industry_factor[industry]),
                    "Product_Risk_Factor": f2(product_factor[product]),
                    "Composite_Risk_Score": f2(risk_base)
                })

            else:
                # Utilization loans: EAD = limit/working_capital × u (industry median)
                EAD, NIM_pct, NII_annual, be_rep, u_pct = util_metrics(
                    wc_omr if wc_omr > 0 else 0.0, industry, row["rep_rate"], fees_pct, cof_pct, row["provision_pct"], opex_pct, upfront_cost_pct
                )
                # Compute min/max BE by substituting rate
                EAD_tmp = max(wc_omr, 0.0) * (u_med_map[industry])
                def util_be(rate):
                    margin = rate + fees_pct - (cof_pct + row["provision_pct"] + opex_pct)
                    if margin <= 0 or EAD_tmp <= 0: return "Breakeven not within the tenor"
                    m = math.ceil((upfront_cost_pct/100.0 * max(wc_omr,0.0)) / ((margin/100.0)*EAD_tmp/12.0))
                    return m if m <= tenor_months else "Breakeven not within the tenor"
                be_min = util_be(row["rate_min"])
                be_max = util_be(row["rate_max"])

                # Decompose annual components with rep rate
                annual_interest = (row["rep_rate"]/100.0) * EAD
                annual_fee = (fees_pct/100.0) * max(wc_omr, 0.0)   # assume fee base on limit for revolving
                annual_funding = (cof_pct/100.0) * EAD
                annual_prov = (row["provision_pct"]/100.0) * EAD
                annual_opex = (opex_pct/100.0) * EAD
                nii = annual_interest + annual_fee - (annual_funding + annual_prov + annual_opex)

                bucket_rows.append({
                    "Bucket": b,
                    "Float_Min_over_OIBOR_bps": row["spread_min_bps"],
                    "Float_Max_over_OIBOR_bps": row["spread_max_bps"],
                    "Rate_Min_%": f2(row["rate_min"]),
                    "Rate_Max_%": f2(row["rate_max"]),
                    "Rep_Rate_%": f2(row["rep_rate"]),
                    "EMI_OMR": "-" ,
                    "Annual_Interest_Income_OMR": f2(annual_interest),
                    "Annual_Fee_Income_OMR": f2(annual_fee),
                    "Annual_Funding_Cost_OMR": f2(annual_funding),
                    "Annual_Provision_OMR": f2(annual_prov),
                    "Annual_Opex_OMR": f2(annual_opex),
                    "Net_Interest_Income_OMR": f2(nii),
                    "NIM_%": f2(NIM_pct),
                    "Breakeven_Min_Months": be_min,
                    "Breakeven_Rep_Months": be_rep,
                    "Breakeven_Max_Months": be_max,
                    "Borrower_Risk_Label": row["malaa_label"],
                    "Industry_Risk_Factor": f2(industry_factor[industry]),
                    "Product_Risk_Factor": f2(product_factor[product]),
                    "Composite_Risk_Score": f2(risk_base),
                    "Optimal_Utilization_%": f2(u_pct)
                })

        out_df = pd.DataFrame(bucket_rows)
        # Ensure two-decimal rendering
        for col in out_df.columns:
            if out_df[col].dtype.kind in "f":
                out_df[col] = out_df[col].apply(f2)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Pricing Buckets (Single Loan)")
        st.dataframe(out_df, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.info("Enter inputs in the sidebar and click **Compute Pricing**.")

# ---------- Loan Book Pricing ----------
with tabs[1]:
    if uploaded is not None and run:
        try:
            df = pd.read_csv(uploaded)
            cols = {c.lower(): c for c in df.columns}
            def get(col):
                for k,v in cols.items():
                    if k == col.lower(): return v
                return None

            # Normalize required columns
            required = ["loan_id","product","industry","malaa_score","tenor_months","stage"]
            missing = [c for c in required if get(c) is None]
            if missing:
                st.error(f"Missing required columns in CSV: {missing}")
            else:
                rows = []
                for _, r in df.iterrows():
                    prod = r[get("product")]
                    if prod not in (PRODUCTS_FUND + PRODUCTS_UTIL):
                        continue
                    ind = r[get("industry")]
                    malaa = int(r[get("malaa_score")])
                    tenor = int(r[get("tenor_months")])
                    stg = int(r[get("stage")])

                    loan_type = "Fund" if prod in PRODUCTS_FUND else "Utilization"
                    ltv = float(r[get("ltv_pct")]) if get("ltv_pct") in df.columns else (np.nan if loan_type=="Utilization" else 60.0)
                    LQ = float(r[get("loan_quantum_omr")]) if get("loan_quantum_omr") in df.columns else (0.0 if loan_type=="Utilization" else 0.0)
                    LIM = float(r[get("limit_omr")]) if get("limit_omr") in df.columns else (0.0 if loan_type=="Fund" else 0.0)
                    wc = float(r[get("working_capital_omr")]) if get("working_capital_omr") in df.columns else (0.0)
                    sales = float(r[get("sales_omr")]) if get("sales_omr") in df.columns else (0.0)
                    oibor_row = float(r[get("oibor_pct")]) if get("oibor_pct") in df.columns else oibor_pct

                    # fees/opex overrides
                    fees_pct_row = float(r[get("fees_pct")]) if get("fees_pct") in df.columns and not pd.isna(r[get("fees_pct")]) else (fees_default if prod in ["Working Capital","Trade Finance","Supply Chain Finance","Vendor Finance","Export Finance"] else 0.0)
                    opex_pct_row = float(r[get("opex_pct")]) if get("opex_pct") in df.columns and not pd.isna(r[get("opex_pct")]) else opex_pct

                    risk_base = composite_risk(prod, ind, malaa, ltv, wc, sales, loan_type)

                    # Provisioning: if provision_rate_pct provided, use it; else PD×LGD
                    if get("provision_rate_pct") in df.columns and not pd.isna(r[get("provision_rate_pct")]):
                        prov_pct = float(r[get("provision_rate_pct")])
                    else:
                        pd_pct = pd_from_risk(risk_base, stg)
                        lgd_pct = lgd_from_product_ltv(prod, ltv)
                        prov_pct = float(np.clip(pd_pct*(lgd_pct/100.0), 0.10, 60.0))

                    # Use Medium bucket logic as representative for batch
                    bres = compute_bucket_rates(
                        bucket="Medium",
                        risk_base=risk_base,
                        product=prod,
                        industry=ind,
                        malaa_score=malaa,
                        oibor_pct=oibor_row,
                        cof_pct=cof_pct,
                        target_nim_pct=target_nim_pct,
                        fees_pct=fees_pct_row,
                        opex_pct=opex_pct_row,
                        stage=stg,
                        loan_type=loan_type,
                        rate_min_floor=5.00,
                        fund_rate_floor=6.00,
                        rate_cap=12.00,
                        min_core_spread_bps=125
                    )

                    if loan_type == "Fund":
                        EMI, NII_annual, AEA_12, NIM_pct = fund_based_metrics(LQ, tenor, bres["rep_rate"], fees_pct_row, cof_pct, bres["provision_pct"], opex_pct_row, upfront_cost_pct)
                        # Components (approx; using AEA_12)
                        annual_interest = (bres["rep_rate"]/100.0) * AEA_12
                        annual_fee = (fees_pct_row/100.0) * LQ
                        annual_funding = (cof_pct/100.0) * AEA_12
                        annual_prov = (bres["provision_pct"]/100.0) * AEA_12
                        annual_opex = (opex_pct_row/100.0) * AEA_12
                        nii = annual_interest + annual_fee - (annual_funding + annual_prov + annual_opex)

                        rows.append({
                            "loan_id": r[get("loan_id")],
                            "product": prod, "industry": ind, "malaa_score": malaa, "stage": stg,
                            "Medium_Rate_%": f2(bres["rep_rate"]),
                            "Float_over_OIBOR_bps": bres["spread_min_bps"],  # representative
                            "EMI_OMR": f2(EMI),
                            "Annual_NII_OMR": f2(nii),
                            "NIM_%": f2(NIM_pct)
                        })
                    else:
                        u = u_med_map[ind]; EAD = max(LIM if LIM>0 else wc, 0.0) * u
                        margin_pct = bres["rep_rate"] + fees_pct_row - (cof_pct + bres["provision_pct"] + opex_pct_row)
                        NIM_pct = margin_pct
                        annual_interest = (bres["rep_rate"]/100.0) * EAD
                        annual_fee = (fees_pct_row/100.0) * (LIM if LIM>0 else wc)
                        annual_funding = (cof_pct/100.0) * EAD
                        annual_prov = (bres["provision_pct"]/100.0) * EAD
                        annual_opex = (opex_pct_row/100.0) * EAD
                        nii = annual_interest + annual_fee - (annual_funding + annual_prov + annual_opex)

                        rows.append({
                            "loan_id": r[get("loan_id")],
                            "product": prod, "industry": ind, "malaa_score": malaa, "stage": stg,
                            "Medium_Rate_%": f2(bres["rep_rate"]),
                            "Float_over_OIBOR_bps": bres["spread_min_bps"],
                            "EMI_OMR": "-",
                            "Annual_NII_OMR": f2(nii),
                            "NIM_%": f2(NIM_pct)
                        })

                out = pd.DataFrame(rows)
                st.subheader("Loan Book — Medium Bucket Pricing")
                st.dataframe(out, use_container_width=True)
                st.download_button("Download Priced Loan Book (CSV)", out.to_csv(index=False).encode("utf-8"), file_name="loan_book_priced.csv", mime="text/csv")

        except Exception as e:
            st.error(f"Failed to parse or price the uploaded file: {e}")
    else:
        st.info("Upload a CSV (or click Compute with no file to test Single Loan).")

# ---------- Assumptions ----------
with tabs[2]:
    st.markdown("""
**Assumptions & Methodology**

- **Rate band:** min **5.00%**, max **12.00%**; **fund-based floor = 6.00%**.
- **Target NIM** is a **floor**, not an equality. Center rate is lifted to satisfy:  
  `required_rate = TargetNIM + CoF + Provision% + Opex% − Fees%`.
- **Provision% = PD × LGD** (annual, % of average EAD).  
  PD from composite risk & stage; LGD by product & LTV (util products get an 8 bps-equivalent add-on).
- **Composite risk** multiplies product, industry, Mala’a and LTV/WC:Sales factors and is clipped to [0.4, 3.5].
- **Bucketization:** Low/Medium/High with multipliers (0.90/1.00/1.25) and bands (±60/±90/±140 bps).
- Floors added for **industry** (up to +100 bps), **product** (up to +125 bps), and **Mala’a** band.
- **Fund-based EMI** cash flows used for NII/NIM over first 12m and breakeven over full tenor.
- **Utilization loans** use EAD = limit (or WC input) × industry median utilization.
- **Outputs** are formatted to **2 decimals**. Amounts entered show an **in-words** helper.
    """)
