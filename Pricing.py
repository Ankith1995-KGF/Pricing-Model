import math
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import streamlit as st

# ---------------- Global formatting (2 decimals) ----------------
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

# ---------------- Tiny number-to-words helper (integers) ----------------
def num_to_words(n: int) -> str:
    units = ["","one","two","three","four","five","six","seven","eight","nine"]
    teens = ["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen",
             "seventeen","eighteen","nineteen"]
    tens = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]

    def chunk(x:int)->str:
        if x==0: return ""
        if x<10: return units[x]
        if x<20: return teens[x-10]
        if x<100: return tens[x//10] + ("" if x%10==0 else " "+units[x%10])
        if x<1000: return units[x//100]+" hundred"+("" if x%100==0 else " "+chunk(x%100))
        return ""

    if n==0: return "zero"
    parts=[]
    for div,word in [(10**9,"billion"),(10**6,"million"),(10**3,"thousand")]:
        if n>=div:
            parts.append(chunk(n//div)+" "+word)
            n%=div
    if n>0: parts.append(chunk(n))
    return " ".join(parts)

# ---------------- Core helpers ----------------
PRODUCTS_FUND = ["Asset Backed Loan","Term Loan","Export Finance"]
PRODUCTS_UTIL = ["Working Capital","Trade Finance","Supply Chain Finance","Vendor Finance"]

product_factor: Dict[str,float] = {
    "Asset Backed Loan":1.35,"Term Loan":1.20,"Export Finance":1.10,
    "Vendor Finance":0.95,"Supply Chain Finance":0.90,"Trade Finance":0.85,"Working Capital":0.95
}
industry_factor: Dict[str,float] = {
    "Construction":1.40,"Real Estate":1.30,"Mining":1.30,"Hospitality":1.25,
    "Retail":1.15,"Manufacturing":1.10,"Trading":1.05,"Logistics":1.00,
    "Oil & Gas":0.95,"Healthcare":0.90,"Utilities":0.85,"Agriculture":1.15
}
u_med_map: Dict[str,float] = {
    "Trading":0.65,"Manufacturing":0.55,"Construction":0.40,"Logistics":0.60,"Retail":0.50,
    "Healthcare":0.45,"Hospitality":0.35,"Oil & Gas":0.50,"Real Estate":0.30,"Utilities":0.55,
    "Mining":0.45,"Agriculture":0.40
}

def clamp(x: float, lo: float, hi: float) -> float: return max(lo, min(x, hi))
def malaa_factor(score:int)->float:
    return float(np.clip(1.45 - (score-300)*(0.90/600), 0.55, 1.45))
def ltv_factor(ltv: float)->float:
    return float(np.clip(0.55 + 0.0075*ltv, 0.80, 1.50))
def wcs_factor(wc: float, sales: float)->float:
    if sales<=0: return 1.20
    ratio = wc / sales
    return float(np.clip(0.70 + 1.00*min(ratio, 1.2), 0.70, 1.70))
def composite_risk(product: str, industry: str, malaa: int, ltv: float, wc: float, sales: float, is_fund: bool)->float:
    pf = product_factor[product]
    inf = industry_factor[industry]
    mf = malaa_factor(malaa)
    rf = ltv_factor(ltv if is_fund else 60.0) if is_fund else wcs_factor(wc, sales)
    return float(np.clip(pf*inf*mf*rf, 0.4, 3.5))
def pd_from_risk(r: float, stage: int)->float:
    xs = np.array([0.4,1.0,2.0,3.5])
    ys = np.array([0.3,1.0,3.0,6.0])
    pd = float(np.interp(r, xs, ys))
    if stage==2: pd*=2.5
    if stage==3: pd*=6.0
    return float(np.clip(pd, 0.10, 60.0))
def lgd_from_product_ltv(prod: str, ltv: float, is_fund: bool)->float:
    base = 32 if prod == "Asset Backed Loan" else 38 if prod == "Term Loan" else 35 if prod == "Export Finance" else 30
    adj = max(0.0, (0.0 if (ltv is None or (isinstance(ltv, float) and np.isnan(ltv))) else ltv)-50.0)*0.25
    if not is_fund: adj += 8.0
    return float(np.clip(base+adj, 25.0, 70.0))

def malaa_label(score:int)->str:
    if score < 500: return "High (poor score)"
    if score < 650: return "Medium-High"
    if score < 750: return "Medium"
    return "Low (good score)"

# floors/add-ons in basis points
BUCKETS = ["Low","Medium","High"]
BUCKET_MULT = {"Low":0.90,"Medium":1.00,"High":1.25}
BUCKET_BAND_BPS = {"Low":60,"Medium":90,"High":140}
BUCKET_FLOOR_BPS = {"Low":150,"Medium":225,"High":325}
MALAA_FLOOR_BPS = {"High (poor score)":175,"Medium-High":125,"Medium":75,"Low (good score)":0}

def industry_floor_addon(ind_fac: float)->int:
    return 100 if ind_fac>=1.25 else (50 if ind_fac>=1.10 else 0)
def product_floor_addon(prod:str)->int:
    return 125 if prod=="Asset Backed Loan" else (75 if prod in ["Term Loan","Export Finance"] else 0)
def base_spread_from_risk(risk: float)->float:
    return 75 + 350*(risk - 1.0)

# ---------------- App UI ----------------
st.set_page_config(page_title="rt 360 risk-adjusted pricing", page_icon="💠", layout="wide")
st.markdown("<h1>rt 360 — Risk-Adjusted Pricing Model</h1>", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Market & Bank Assumptions")
    oibor_pct = st.number_input("OIBOR (%)", value=4.10, step=0.01, format="%.2f")
    cof_pct = st.number_input("Cost of Funds (%)", value=5.00, step=0.01, format="%.2f")
    target_nim_pct = st.number_input("Target NIM (%)", value=2.50, step=0.01, format="%.2f")
    opex_pct = st.number_input("Opex (%)", value=0.40, step=0.01, format="%.2f")
    fees_default = st.number_input("Default Fees (%)", value=0.40, step=0.01, format="%.2f")
    upfront_cost_pct= st.number_input("Upfront Cost (%)", value=0.50, step=0.01, format="%.2f")
    st.subheader("Borrower & Product")
    product = st.selectbox("Product", PRODUCTS_FUND + PRODUCTS_UTIL)
    industry = st.selectbox("Industry", list(industry_factor.keys()))
    malaa_score = int(st.number_input("Mala’a Credit Score", value=750, step=1, format="%d"))
    stage = int(st.number_input("IFRS-9 Stage (1-3)", value=1, min_value=1, max_value=3, step=1, format="%d"))
    st.subheader("Loan Details")
    tenor_months = int(st.number_input("Tenor (months)", value=36, min_value=6, max_value=360, step=1, format="%d"))
    loan_quantum_omr = st.number_input("Loan Amount (OMR)", value=100000.00, step=1000.0, format="%.2f")
    st.caption(f"In words: {num_to_words(int(loan_quantum_omr))} Omani Rials")
    is_fund = product in PRODUCTS_FUND
    if is_fund:
        ltv_pct = st.number_input("LTV (%)", value=70.00, step=0.01, format="%.2f")
        wc_omr, sales_omr = 0.0, 0.0
        fees_pct = fees_default if product == "Export Finance" else 0.00
    else:
        ltv_pct = float("nan")
        wc_omr = loan_quantum_omr
        sales_omr = st.number_input("Annual Sales (OMR)", value=600000.00, step=1000.0, format="%.2f")
        fees_pct = fees_default
    run = st.button("Compute Pricing")

# ---------------- Calculation ----------------
if run:
    risk_base = composite_risk(product, industry, malaa_score, ltv_pct if is_fund else 60.0, wc_omr, sales_omr, is_fund)
    pd_base = pd_from_risk(risk_base, stage)
    lgd_base = lgd_from_product_ltv(product, ltv_pct, is_fund)
    provision_base = f2(pd_base * (lgd_base/100.0))

    malaa_lbl = malaa_label(malaa_score)
    ind_add = industry_floor_addon(industry_factor[industry])
    prod_add = product_floor_addon(product)
    malaa_add = MALAA_FLOOR_BPS[malaa_lbl]
    min_core_spread_bps = 125

    rows: List[Dict[str,Any]] = []
    for bucket in BUCKETS:
        risk_b = float(np.clip(risk_base * BUCKET_MULT[bucket], 0.4, 3.5))
        pd_pct = pd_from_risk(risk_b, stage)
        lgd_pct = lgd_from_product_ltv(product, ltv_pct if is_fund else 60.0, is_fund)
        prov_pct = f2(pd_pct * (lgd_pct/100.0))
        raw_bps = base_spread_from_risk(risk_b)
        floors = BUCKET_FLOOR_BPS[bucket] + malaa_add + ind_add + prod_add
        base_bps = max(int(round(raw_bps)), floors, min_core_spread_bps)
        band_bps = BUCKET_BAND_BPS[bucket]
        spread_min_bps = max(base_bps - band_bps, floors, min_core_spread_bps)
        spread_max_bps = spread_min_bps + band_bps*2
        rate_min = clamp(oibor_pct + spread_min_bps/100.0, 5.0, 12.0)
        rate_max = clamp(oibor_pct + spread_max_bps/100.0, 5.0, 12.0)
        rep_rate = max((rate_min + rate_max)/2.0, cof_pct + prov_pct + opex_pct - fees_pct + target_nim_pct)
        rows.append({
            "Bucket": bucket,
            "Risk Score": f2(risk_b),
            "PD %": f2(pd_pct),
            "LGD %": f2(lgd_pct),
            "Prov %": f2(prov_pct),
            "Rate Min %": f2(rate_min),
            "Rep Rate %": f2(rep_rate),
            "Rate Max %": f2(rate_max),
            "Spread Min bps": spread_min_bps,
            "Spread Max bps": spread_max_bps
        })

    out_df = pd.DataFrame(rows)
    out_df = out_df.round(2)
    st.dataframe(out_df, use_container_width=True)
