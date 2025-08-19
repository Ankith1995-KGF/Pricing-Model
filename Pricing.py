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
        if x == 0:
            return ""
        if x < 10:
            return units[x]
        if x < 20:
            return teens[x-10]
        if x < 100:
            return tens[x//10] + ("" if x%10==0 else " " + units[x%10])
        if x < 1000:
            return units[x//100] + " hundred" + ("" if x%100==0 else " " + chunk(x%100))
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
        return "Breakeven not within the tenor"
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
    return "Breakeven not within the tenor"

def util_metrics(limit_or_wc: float, u: float, rep_rate: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float):
    EAD = max(limit_or_wc, 0.0) * u
    margin_pct = rep_rate + fees_pct - (cof_pct + prov_pct + opex_pct)
    NIM_pct = margin_pct
    NII_annual = (margin_pct/100.0) * EAD
    return f2(EAD), f2(NIM_pct), f2(NII_annual)

# === UI and styling ===
st.set_page_config(page_title="rt 360 risk-adjusted pricing", page_icon="💠", layout="wide")

st.title("RT 360 Risk-Adjusted Pricing")

st.markdown("""
This app calculates risk-adjusted pricing and loan metrics based on product, industry, risk scores, and utilization.
""")

# Inputs

st.sidebar.header("Loan Details")

product = st.sidebar.selectbox("Product", PRODUCTS_FUND + PRODUCTS_UTIL)
industry = st.sidebar.selectbox("Industry", list(industry_factor.keys()))
malaa_score = st.sidebar.slider("MALAA Score", min_value=300, max_value=900, value=700, step=1)
ltv = st.sidebar.number_input("Loan to Value (LTV) %", min_value=0.0, max_value=200.0, value=50.0, step=0.1, format="%.1f")
limit_wc = st.sidebar.number_input("Limit / Working Capital", min_value=0.0, value=100.0, step=1.0)
sales = st.sidebar.number_input("Sales", min_value=0.0, value=1000.0, step=1.0)
is_fund = product in PRODUCTS_FUND
rep_rate = st.sidebar.number_input("Repayment Rate % (annual)", min_value=0.0, max_value=100.0, value=13.0, step=0.1)
fees_pct = st.sidebar.number_input("Fees % (annual)", min_value=0.0, max_value=20.0, value=3.0, step=0.1)
cof_pct = st.sidebar.number_input("Cost of Funds % (annual)", min_value=0.0, max_value=20.0, value=6.0, step=0.1)
prov_pct = st.sidebar.number_input("Provisioning % (annual)", min_value=0.0, max_value=20.0, value=1.0, step=0.1)
opex_pct = st.sidebar.number_input("Opex % (annual)", min_value=0.0, max_value=20.0, value=2.5, step=0.1)
upfront_cost_pct = st.sidebar.number_input("Upfront Cost %", min_value=0.0, max_value=10.0, value=0.5, step=0.1)
principal = st.sidebar.number_input("Principal", min_value=0.0, value=1000.0, step=1.0)

tenor_months = st.number_input("Tenor (months)", value=36, min_value=6, max_value=360, step=1, format="%d")

st.sidebar.markdown("---")

# Calculations

risk = composite_risk(product, industry, malaa_score, ltv, limit_wc, sales, is_fund)
pd = pd_from_risk(risk, stage=1)
lgd = lgd_from_product_ltv(product, ltv, is_fund)
malaa_txt = malaa_label(malaa_score)

industry_floor = industry_floor_addon(industry_factor[industry])
product_floor = product_floor_addon(product)
base_spread = base_spread_from_risk(risk)
util = limit_wc/sales if sales!=0 else 0
util_disc = utilization_discount_bps(util)

final_spread_bps = base_spread + industry_floor + product_floor - util_disc

emi, nii_annual, aea_12, nim_pct = fund_first_year_metrics(principal, tenor_months, rep_rate, fees_pct, cof_pct, prov_pct, opex_pct)

breakeven_months = fund_breakeven_months(principal, tenor_months, rep_rate, fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct)

ead, nim_util_pct, nii_util = util_metrics(limit_wc, util, rep_rate, fees_pct, cof_pct, prov_pct, opex_pct)

# Output results

st.header("Risk and Pricing Summary")

st.markdown(f"""
- Product: **{product}**
- Industry: **{industry}**
- MALAA Score: **{malaa_score}** ({malaa_txt})
- Composite Risk Factor: **{risk:.2f}**
- Probability of Default (PD, %): **{pd:.2f}**
- Loss Given Default (LGD, %): **{lgd:.2f}**
- Base Spread (bps): **{base_spread:.2f}**
- Industry Floor Addon (bps): **{industry_floor}**
- Product Floor Addon (bps): **{product_floor}**
- Utilization Discount (bps): **{util_disc}**
- Final Spread (bps): **{final_spread_bps:.2f}**
""")

st.header("Funding Metrics")

st.markdown(f"""
- EMI (monthly): **{emi:.2f}**
- Net Interest Income Annual (NII): **{nii_annual:.2f}**
- Average EAD over 12 months (AEA): **{aea_12:.2f}**
- Net Interest Margin % (NIM): **{nim_pct:.2f}%**
- Breakeven Months: **{breakeven_months}**
""")

st.header("Utilization Metrics")

st.markdown(f"""
- Utilization Ratio: **{util:.2f}**
- Exposure at Default (EAD): **{ead:.2f}**
- Net Interest Margin % based on Utilization (NIM): **{nim_util_pct:.2f}%**
- Net Interest Income Annual based on Utilization (NII): **{nii_util:.2f}**
""")
