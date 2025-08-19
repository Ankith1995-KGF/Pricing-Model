import math
from typing import Dict, Tuple
import numpy as np
import pandas as pd
import streamlit as st

# ---------- Global formatting ----------
pd.options.display.float_format = lambda x: f"{x:.2f}"

def f2(x: float) -> float:
    try:
        return float(np.round(float(x), 2))
    except Exception:
        return float("nan")

def fmt2(x) -> str:
    try:
        return f"{f2(float(x)):.2f}"
    except Exception:
        return ""

def num_to_words(n: int) -> str:
    units = ["","one","two","three","four","five","six","seven","eight","nine"]
    teens = ["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"]
    tens = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
    def chunk(x: int) -> str:
        if x == 0: return ""
        if x < 10: return units[x]
        if x < 20: return teens[x-10]
        if x < 100: return tens[x//10] + ("" if x%10==0 else " " + units[x%10])
        if x < 1000: return units[x//100] + " hundred" + ("" if x%100==0 else " " + chunk(x%100))
        return ""
    if n == 0:
        return "zero"
    parts = []
    for div,name in [(10**9,"billion"),(10**6,"million"),(10**3,"thousand")]:
        if n >= div:
            parts.append(chunk(n//div) + " " + name)
            n %= div
    if n > 0:
        parts.append(chunk(n))
    return " ".join(parts)

# ---------- Core data and constants ----------

PRODUCTS_FUND = ["Asset Backed Loan","Term Loan","Export Finance"]
PRODUCTS_UTIL = ["Working Capital","Trade Finance","Supply Chain Finance","Vendor Finance"]

product_factor: Dict[str,float] = {
    "Asset Backed Loan":1.35,
    "Term Loan":1.20,
    "Export Finance":1.10,
    "Vendor Finance":0.95,
    "Supply Chain Finance":0.90,
    "Trade Finance":0.85,
    "Working Capital":0.95
}

industry_factor: Dict[str,float] = {
    "Construction":1.40,
    "Real Estate":1.30,
    "Mining":1.30,
    "Hospitality":1.25,
    "Retail":1.15,
    "Manufacturing":1.10,
    "Trading":1.05,
    "Logistics":1.00,
    "Oil & Gas":0.95,
    "Healthcare":0.90,
    "Utilities":0.85,
    "Agriculture":1.15
}

u_med_map: Dict[str,float] = {
    "Trading":0.65,"Manufacturing":0.55,"Construction":0.40,"Logistics":0.60,"Retail":0.50,
    "Healthcare":0.45,"Hospitality":0.35,"Oil & Gas":0.50,"Real Estate":0.30,"Utilities":0.55,
    "Mining":0.45,"Agriculture":0.40
}

BUCKETS = ["Low","Medium","High"]

BUCKET_MULT = {"Low":0.90,"Medium":1.00,"High":1.25}

BUCKET_BAND_BPS = {"Low":60,"Medium":90,"High":140}

BUCKET_FLOOR_BPS = {"Low":150,"Medium":225,"High":325}

MALAA_FLOOR_BPS = {"High (poor score)":175,"Medium-High":125,"Medium":75,"Low (good score)":0}

SNP_LIST = [
    "AAA","AA+","AA","AA-","A+","A","A-",
    "BBB+","BBB","BBB-","BB+","BB","BB-",
    "B+","B","B-","CCC+","CCC","CCC-","CC","C"
]

SP_RISK_MAP = {
    "AAA":1, "AA+":1, "AA":1, "AA-":1,
    "A+":2, "A":2, "A-":2,
    "BBB+":3, "BBB":3, "BBB-":3,
    "BB+":4, "BB":4, "BB-":5,
    "B+":6, "B":6, "B-":7,
    "CCC+":8, "CCC":8, "CCC-":8, "CC":9, "C":10
}

TOP_LOW_RISK_INDUSTRIES = ["Healthcare", "Utilities", "Oil & Gas", "Retail"]

industry_utilization_map = dict(u_med_map)

# ---------- Utility Functions ----------

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(x, hi))

def malaa_factor(score:int)->float:
    return float(np.clip(1.45 - (score-300)*(0.90/600), 0.55, 1.45))

def ltv_factor(ltv: float)->float:
    return float(np.clip(0.55 + 0.0075*ltv, 0.80, 1.50))

def wcs_factor(limit_wc: float, sales: float)->float:
    if sales <= 0:
        return 1.20
    ratio = limit_wc / sales
    return float(np.clip(0.70 + 1.00*min(ratio, 1.2), 0.70, 1.70))

def composite_risk(product: str, industry: str, malaa: int, ltv: float, limit_wc: float, sales: float, is_fund: bool) -> float:
    pf = product_factor[product]
    inf = industry_factor[industry]
    mf = malaa_factor(malaa)
    rf = ltv_factor(ltv if is_fund else 60.0) if is_fund else wcs_factor(limit_wc, sales)
    return float(np.clip(pf*inf*mf*rf, 0.4, 3.5))

def pd_from_risk(r: float, stage: int)->float:
    xs=np.array([0.4,1.0,2.0,3.5])
    ys=np.array([0.3,1.0,3.0,6.0])
    pd = float(np.interp(r, xs, ys))
    if stage==2:
        pd *= 2.5
    if stage==3:
        pd *= 6.0
    return float(np.clip(pd, 0.10, 60.0))

def lgd_from_product_ltv(prod: str, ltv: float, is_fund: bool)->float:
    base = 32 if prod=="Asset Backed Loan" else 38 if prod=="Term Loan" else 35 if prod=="Export Finance" else 30
    adj = max(0.0,(ltv if ltv and not np.isnan(ltv) else 0) - 50.0 ) * 0.25
    if not is_fund:
        adj += 8.0
    return float(np.clip(base+adj, 25.0, 70.0))

def malaa_label(score:int)->str:
    if score < 500:
        return "High (poor score)"
    if score < 650:
        return "Medium-High"
    if score < 750:
        return "Medium"
    return "Low (good score)"

def industry_floor_addon(ind_fac: float)->int:
    return 100 if ind_fac>=1.25 else (50 if ind_fac>=1.10 else 0)

def product_floor_addon(prod:str)->int:
    return 125 if prod=="Asset Backed Loan" else (75 if prod in ["Term Loan","Export Finance"] else 0)

def base_spread_from_risk(risk: float)->float:
    return 75 + 350*(risk - 1.0)

def utilization_discount_bps(u: float)->int:
    if u >= 0.85:
        return -40
    if u >= 0.70:
        return -25
    if u >= 0.50:
        return 0
    if u >= 0.30:
        return +15
    return +40

def fund_first_year_metrics(P: float, tenor_m: int, rep_rate: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float) -> Tuple[float,float,float,float]:
    i = rep_rate/100.0/12.0
    if i<=0 or tenor_m<=0 or P<=0:
        return 0.0,0.0,1.0,0.0
    EMI = P * i * (1+i)**tenor_m / ((1+i)**tenor_m - 1)
    months = min(12, tenor_m)
    bal = P; sum_net_12=0.0; sum_bal_12=0.0
    for _ in range(months):
        interest = bal * i
        fee = P * (fees_pct/100.0/12.0)
        funding = bal * (cof_pct/100.0/12.0)
        prov = bal * (prov_pct/100.0/12.0)
        opex = bal * (opex_pct/100.0/12.0)
        net = interest + fee - (funding + prov + opex)
        sum_net_12 += net
        sum_bal_12 += bal
        principal = EMI - interest
        bal = max(bal - principal, 0.0)
    AEA_12 = max(sum_bal_12/months, 1e-9)
    NII_annual = sum_net_12
    NIM_pct = (NII_annual/AEA_12)*100.0
    return f2(EMI), f2(NII_annual), f2(AEA_12), f2(NIM_pct)

def fund_breakeven_months(P: float, tenor_m:int, rate_pct: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float, upfront_cost_pct: float):
    i = rate_pct/100.0/12.0
    if i<=0 or tenor_m<=0 or P<=0:
        return "NA"
    EMI = P * i * (1+i)**tenor_m / ((1+i)**tenor_m - 1)
    bal=P; C0 = upfront_cost_pct/100.0 * P; cum=-C0
    for m in range(1, tenor_m+1):
        interest = bal*i
        fee = P * (fees_pct/100.0/12.0)
        funding = bal * (cof_pct/100.0/12.0)
        prov = bal * (prov_pct/100.0/12.0)
        opex = bal * (opex_pct/100.0/12.0)
        net = interest + fee - (funding + prov + opex)
        cum += net
        principal = EMI - interest
        bal = max(bal - principal, 0.0)
        if cum >= 0:
            return m
    return "NA"

def util_metrics(limit_or_wc: float, u: float, rep_rate: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float):
    EAD = max(limit_or_wc, 0.0) * u
    margin_pct = rep_rate + fees_pct - (cof_pct + prov_pct + opex_pct)
    NIM_pct = margin_pct
    NII_annual = (margin_pct/100.0) * EAD
    return f2(EAD), f2(NIM_pct), f2(NII_annual)

# === UI and styling ===
st.set_page_config(page_title="rt 360 risk-adjusted pricing", page_icon="💠", layout="wide")

st.title("RT 360 Risk-Adjusted Pricing - Pricing Buckets")

# --- Inputs (dropdowns only) ---
st.sidebar.header("Loan Details (Select from dropdowns)")

product = st.sidebar.selectbox("Product", PRODUCTS_FUND + PRODUCTS_UTIL)

industry = st.sidebar.selectbox("Industry", list(industry_factor.keys()))

malaa_score = st.sidebar.selectbox("MALAA Score", options=list(range(300, 901)), index=400)  # default 700

ltv_options = list(np.round(np.arange(0, 201, 0.5), 2))
ltv = st.sidebar.selectbox("Loan to Value (LTV) %", ltv_options, index=100)  # default 50%

limit_wc_options = list(range(0, 2001, 10))
limit_wc = st.sidebar.selectbox("Limit / Working Capital", limit_wc_options, index=10)  # default 100

sales_options = list(range(0, 10001, 100))
sales = st.sidebar.selectbox("Sales", sales_options, index=10)  # default 1000

is_fund = product in PRODUCTS_FUND

rep_rate_options = list(np.round(np.arange(0, 101, 0.1), 1))
rep_rate = st.sidebar.selectbox("Repayment Rate % (annual)", rep_rate_options, index=130)  # default 13.0

fees_pct_options = list(np.round(np.arange(0, 20.1, 0.1), 1))
fees_pct = st.sidebar.selectbox("Fees % (annual)", fees_pct_options, index=30)  # default 3.0

cof_pct_options = list(np.round(np.arange(0, 20.1, 0.1), 1))
cof_pct = st.sidebar.selectbox("Cost of Funds % (annual)", cof_pct_options, index=60)  # default 6.0

prov_pct_options = list(np.round(np.arange(0, 20.1, 0.1), 1))
prov_pct = st.sidebar.selectbox("Provisioning % (annual)", prov_pct_options, index=10)  # default 1.0

opex_pct_options = list(np.round(np.arange(0, 20.1, 0.1), 1))
opex_pct = st.sidebar.selectbox("Opex % (annual)", opex_pct_options, index=25)  # default 2.5

upfront_cost_options = list(np.round(np.arange(0, 10.1, 0.1), 1))
upfront_cost_pct = st.sidebar.selectbox("Upfront Cost %", upfront_cost_options, index=5)  # default 0.5

principal_options = list(range(0, 10001, 100))
principal = st.sidebar.selectbox("Principal", principal_options, index=10)  # default 1000

tenor_options = list(range(6, 361))
tenor_months = st.sidebar.selectbox("Tenor (months)", tenor_options, index=30)  # default 36

st.sidebar.markdown("---")

fetch = st.sidebar.button("Fetch")

if fetch:
    # Calculate composite risk and base final spread
    risk = composite_risk(product, industry, malaa_score, ltv, limit_wc, sales, is_fund)
    base_spread_bps = base_spread_from_risk(risk) + industry_floor_addon(industry_factor[industry]) + product_floor_addon(product)

    # Prepare bucket-wise results
    bucket_results = []
    for bucket in BUCKETS:
        bucket_spread = base_spread_bps * BUCKET_MULT[bucket]
        annual_rate_pct = bucket_spread / 100.0  # bps to percentage
        
        emi, nii_annual, _, _ = fund_first_year_metrics(principal, tenor_months, annual_rate_pct * 12, fees_pct, cof_pct, prov_pct, opex_pct)
        breakeven_m = fund_breakeven_months(principal, tenor_months, annual_rate_pct * 12, fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct)

        bucket_results.append({
            "Bucket": bucket,
            "Spread (bps)": round(bucket_spread, 2),
            "NII Annual": round(nii_annual, 2),
            "Breakeven Months": breakeven_m if breakeven_m != "NA" else "NA"
        })

    st.header("Pricing Buckets and Metrics")
    st.dataframe(pd.DataFrame(bucket_results))
else:
    st.info("Please provide inputs on the sidebar and press 'Fetch' to calculate.")
