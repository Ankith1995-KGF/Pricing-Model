import math
from typing import Dict, Any, List, Tuple
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
    for div,name in [(10**9,"billion"),(10**6,"million"),(10**3,"thousand")]:
        if n >= div:
            parts.append(chunk(n//div) + " " + name)
            n %= div
    if n > 0: parts.append(chunk(n))
    return " ".join(parts)
# ---------- Core data and constants ----------
PRODUCTS_FUND = ["Asset Backed Loan","Term Loan","Export Finance"]
PRODUCTS_UTIL = ["Working Capital","Trade Finance","Supply Chain Finance","Vendor Finance"]
product_factor: Dict[str,float] = {
    "Asset Backed Loan":1.35, "Term Loan":1.20, "Export Finance":1.10,
    "Vendor Finance":0.95, "Supply Chain Finance":0.90, "Trade Finance":0.85, "Working Capital":0.95
}
industry_factor: Dict[str,float] = {
    "Construction":1.40, "Real Estate":1.30, "Mining":1.30, "Hospitality":1.25,
    "Retail":1.15, "Manufacturing":1.10, "Trading":1.05, "Logistics":1.00,
    "Oil & Gas":0.95, "Healthcare":0.90, "Utilities":0.85, "Agriculture":1.15
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
    "CCC+":8, "CCC":8, "CCC-":8,
    "CC":9, "C":10
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
    if sales <= 0: return 1.20
    ratio = limit_wc / sales
    return float(np.clip(0.70 + 1.00*min(ratio, 1.2), 0.70, 1.70))
def composite_risk(product: str, industry: str, malaa: int, ltv: float,
                   limit_wc: float, sales: float, is_fund: bool) -> float:
    pf = product_factor[product]
    inf = industry_factor[industry]
    mf = malaa_factor(malaa)
    rf = ltv_factor(ltv if is_fund else 60.0) if is_fund else wcs_factor(limit_wc, sales)
    return float(np.clip(pf*inf*mf*rf, 0.4, 3.5))
def pd_from_risk(r: float, stage: int)->float:
    xs=np.array([0.4,1.0,2.0,3.5])
    ys=np.array([0.3,1.0,3.0,6.0])
    pd = float(np.interp(r, xs, ys))
    if stage==2: pd *= 2.5
    if stage==3: pd *= 6.0
    return float(np.clip(pd, 0.10, 60.0))
def lgd_from_product_ltv(prod: str, ltv: float, is_fund: bool)->float:
    base = 32 if prod == "Asset Backed Loan" else 38 if prod == "Term Loan" else 35 if prod == "Export Finance" else 30
    adj = max(0.0,(ltv if ltv and not np.isnan(ltv) else 0) - 50.0 ) * 0.25
    if not is_fund: adj += 8.0
    return float(np.clip(base+adj, 25.0, 70.0))
def malaa_label(score:int)->str:
    if score < 500: return "High (poor score)"
    if score < 650: return "Medium-High"
    if score < 750: return "Medium"
    return "Low (good score)"
def industry_floor_addon(ind_fac: float)->int:
    return 100 if ind_fac>=1.25 else (50 if ind_fac>=1.10 else 0)
def product_floor_addon(prod:str)->int:
    return 125 if prod=="Asset Backed Loan" else (75 if prod in ["Term Loan","Export Finance"] else 0)
def base_spread_from_risk(risk: float)->float:
    return 75 + 350*(risk - 1.0)
def utilization_discount_bps(u: float)->int:
    if u >= 0.85: return -40
    if u >= 0.70: return -25
    if u >= 0.50: return 0
    if u >= 0.30: return +15
    return +40
def fund_first_year_metrics(P: float, tenor_m: int, rep_rate: float, fees_pct: float,
                            cof_pct: float, prov_pct: float, opex_pct: float)->Tuple[float,float,float,float]:
    i = rep_rate/100.0/12.0
    if i<=0 or tenor_m<=0 or P<=0: return 0.0,0.0,1.0,0.0
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
def fund_breakeven_months(P: float, tenor_m:int, rate_pct: float, fees_pct: float, cof_pct: float,
                          prov_pct: float, opex_pct: float, upfront_cost_pct: float):
    i = rate_pct/100.0/12.0
    if i<=0 or tenor_m<=0 or P<=0: return "Breakeven not within the tenor"
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
        if cum >= 0: return m
    return "Breakeven not within the tenor"
def util_metrics(limit_or_wc: float, u: float, rep_rate: float, fees_pct: float,
                 cof_pct: float, prov_pct: float, opex_pct: float):
    EAD = max(limit_or_wc, 0.0) * u
    margin_pct = rep_rate + fees_pct - (cof_pct + prov_pct + opex_pct)
    NIM_pct = margin_pct
    NII_annual = (margin_pct/100.0) * EAD
    return f2(EAD), f2(NIM_pct), f2(NII_annual)
# = UI and styling =
st.set_page_config(page_title="rt 360 risk-adjusted pricing", page_icon="💠", layout="wide")
st.markdown("""
<style>
.big {font-size:28px;font-weight:800}
.blue {color:#1666d3}
.green {color:#18a05e}
.dataframe td, .dataframe th {border:1px solid #ddd; padding:4px;}
tr:nth-child(even) {background-color: #f3f9ff;}
tr:hover {background-color: #eaf3ff;}
th {background-color:#1666d3;color:white;}
</style>
<div class="big"><span class="blue">rt</span> <span class="green">360</span> — Pricing Model with S&P Ratings, Utilization, and Subsidies</div>
""", unsafe_allow_html=True)
with st.sidebar:
    st.subheader("Market & Bank Assumptions")
    oibor_pct = st.number_input("OIBOR (%)", value=4.10, step=0.01)
    cof_pct = st.number_input("Cost of Funds (%)", value=5.00, step=0.01)
    target_nim_pct = st.number_input("Default NIM (%)", value=2.50, step=0.01)
    opex_pct = st.number_input("Operating Expense (%)", value=0.40, step=0.01)
    fees_default = st.number_input("Default Fees (%)", value=0.40, step=0.01)
    upfront_cost_pct = st.number_input("Upfront Origination Cost (%)", value=0.50, step=0.01)
    st.markdown("---")
    st.subheader("Borrower & Product")
    product = st.selectbox("Product", PRODUCTS_FUND + PRODUCTS_UTIL)
    industry = st.selectbox("Industry", list(industry_factor.keys()))
    malaa_score = int(st.number_input("Mala’a Credit Score", value=750, step=1))
    stage = int(st.number_input("IFRS-9 Stage", value=1, min_value=1, max_value=3, step=1))
    snp_rating = st.selectbox("S&P Issuer Rating", SNP_LIST)
    new_customer = st.checkbox("Is New Customer?", value=False, help="Adds premium for new customers")
    st.markdown("---")
    st.subheader("Loan Details")
    tenor_months = int(st.number_input("Tenor (months)", 36, min_value=6, max_value=360, step=1))
    loan_quantum_omr = st.number_input("Loan Quantum (OMR)", 100000.0, step=1000.0)
    is_fund = product in PRODUCTS_FUND
    if is_fund:
        ltv_pct = st.number_input("Loan-to-Value (%)", value=70.0)
        limit_wc = 0.0; sales_omr = 0.0
        fees_pct = fees_default if product == "Export Finance" else 0.0
        utilization_input = None
    else:
        ltv_pct = float("nan")
        limit_wc = st.number_input("Working Capital / Limit (OMR)", 80000.0)
        sales_omr = st.number_input("Annual Sales (OMR)", 600000.0)
        utilization_input = st.number_input("Current Utilization (%)", 60.0, min_value=0.0, max_value=100.0, step=0.1)
        fees_pct = fees_default
    st.markdown("---")
    st.subheader("Upload Loan Book Data (CSV only)")
    uploaded_file = st.file_uploader("Upload Loan Book (CSV)", type=["csv"])
    loan_book_df = None
    if uploaded_file:
        try:
            loan_book_df = pd.read_csv(uploaded_file)
            st.success(f"Loaded {loan_book_df.shape[0]} records from loan book.")
        except UnicodeDecodeError:
            try:
                uploaded_file.seek(0)
                loan_book_df = pd.read_csv(uploaded_file, encoding='latin1')
                st.warning("CSV encoding detected as latin1 instead of utf-8.")
            except Exception as e:
                st.error(f"Failed to read CSV with utf-8 and latin1 encodings: {e}")
                loan_book_df = None
        except Exception as e:
            st.error(f"Error loading CSV file: {e}")
            loan_book_df = None
    st.markdown("---")
    run = st.button("Compute Pricing")
industry_utilization = industry_utilization_map.get(industry, 0.5)
utilization_subsidy_bps = -15 if industry_utilization > 0.60 else 0
new_customer_risk_premium_bps = 25 if new_customer else 0
sp_risk = SP_RISK_MAP.get(snp_rating, 5)
if sp_risk == 1:
    nim_subsidy_target = 1.85
elif industry in TOP_LOW_RISK_INDUSTRIES:
    nim_subsidy_target = 1.85
else:
    nim_subsidy_target = target_nim_pct
target_nim_to_apply = nim_subsidy_target
historic_spread_adj = 0
if loan_book_df is not None:
    required_cols = ["Product", "Industry", "Stage", "Spread_bps"]
    if all(col in loan_book_df.columns for col in required_cols):
        similar_loans = loan_book_df[
            (loan_book_df["Product"] == product) &
            (loan_book_df["Industry"] == industry) &
            (loan_book_df["Stage"] == stage)
        ]
        if not similar_loans.empty:
            avg_spread = similar_loans["Spread_bps"].mean()
            historic_spread_adj = (avg_spread - 100) * 0.1
            st.sidebar.info(f"Historic avg spread for selection: {avg_spread:.0f} bps")
if run:
    util_base = utilization_input / 100.0 if utilization_input is not None and not is_fund else industry_utilization
    risk_base = composite_risk(product, industry, malaa_score,
                               ltv_pct if is_fund else 60.0,
                               limit_wc, sales_omr, is_fund)
    pd_base = pd_from_risk(risk_base, stage)
    lgd_base = lgd_from_product_ltv(product, ltv_pct if is_fund else 60.0, is_fund)
    prov_pct_base = round(pd_base * (lgd_base / 100.0), 2)
    malaa_lbl = malaa_label(malaa_score)
    ind_add = industry_floor_addon(industry_factor[industry])
    prod_add = product_floor_addon(product)
    malaa_add = MALAA_FLOOR_BPS[malaa_lbl]
    min_core_spread_bps = 125
    rows = []
    for bucket in BUCKETS:
        risk_b = float(np.clip(risk_base * BUCKET_MULT[bucket], 0.4, 3.5))
        pd_pct = pd_from_risk(risk_b, stage)
        lgd_pct = lgd_from_product_ltv(product, ltv_pct if is_fund else 60.0, is_fund)
        prov_pct = round(pd_pct * (lgd_pct / 100.0), 2)
        raw_bps = base_spread_from_risk(risk_b)
        floors = BUCKET_FLOOR_BPS[bucket] + malaa_add + ind_add + prod_add
        center_bps = max(round(raw_bps), floors, min_core_spread_bps)
        center_bps += utilization_subsidy_bps
        center_bps += new_customer_risk_premium_bps
        center_bps += historic_spread_adj
        band_bps = BUCKET_BAND_BPS[bucket]
        spread_min_bps = max(center_bps - band_bps, floors, min_core_spread_bps)
        spread_max_bps = max(center_bps + band_bps, spread_min_bps + 10)
        rate_min = clamp(oibor_pct + spread_min_bps / 100.0, 5.00, 12.00)
        rate_max = clamp(oibor_pct + spread_max_bps / 100.0, 5.00, 12.00)
        rep_rate = (rate_min + rate_max) / 2.0
        if is_fund:
            rate_min = max(rate_min, 6.00)
            rate_max = max(rate_max, 6.00)
            rep_rate = max(rep_rate, 6.00)
        required_rate = cof_pct + prov_pct + opex_pct + target_nim_to_apply
        rep_rate = max(rep_rate, required_rate)
        if is_fund:
            EMI, NII_annual, AEA_12, NIM_pct = fund_first_year_metrics(
                loan_quantum_omr, tenor_months, rep_rate, fees_pct, cof_pct, prov_pct, opex_pct)
            be_min = fund_breakeven_months(
                loan_quantum_omr, tenor_months, rate_min, fees_pct, cof_pct,
                prov_pct, opex_pct, upfront_cost_pct)
            be_rep = fund_breakeven_months(
                loan_quantum_omr, tenor_months, rep_rate, fees_pct, cof_pct,
                prov_pct, opex_pct, upfront_cost_pct)
            be_max = fund_breakeven_months(
                loan_quantum_omr, tenor_months, rate_max, fees_pct, cof_pct,
                prov_pct, opex_pct, upfront_cost_pct)
            rows.append({
                "Pricing Bucket": bucket,
                "Float Min (bps)": int(round((rate_min - oibor_pct) * 100)),
                "Float Rep (bps)": int(round((rep_rate - oibor_pct) * 100)),
                "Float Max (bps)": int(round((rate_max - oibor_pct) * 100)),
                "Rate Min (%)": round(rate_min, 2),
                "Rate Rep (%)": round(rep_rate, 2),
                "Rate Max (%)": round(rate_max, 2),
                "EMI (OMR)": EMI,
                "Annual Int Income": round((rep_rate / 100.0) * AEA_12, 2),
                "Annual Fee Income": round((fees_pct / 100.0) * loan_quantum_omr, 2),
                "Annual Funding Cost": round((cof_pct / 100.0) * AEA_12, 2),
                "Annual Provision": round((prov_pct / 100.0) * AEA_12, 2),
                "Annual Opex": round((opex_pct / 100.0) * AEA_12, 2),
                "NII (OMR)": NII_annual,
                "NIM (%)": NIM_pct,
                "Breakeven Min": be_min,
                "Breakeven Rep": be_rep,
                "Breakeven Max": be_max,
                "Composite Risk": round(risk_base, 2),
                "Provision %": prov_pct,
            })
        else:
            EAD, NIM_pct, NII_annual = util_metrics(
                limit_wc, util_base, rep_rate, fees_pct, cof_pct, prov_pct, opex_pct)
            rows.append({
                "Pricing Bucket": bucket,
                "Float Min (bps)": int(round((rate_min - oibor_pct) * 100)),
                "Float Rep (bps)": int(round((rep_rate - oibor_pct) * 100)),
                "Float Max (bps)": int(round((rate_max - oibor_pct) * 100)),
                "Rate Min (%)": round(rate_min, 2),
                "Rate Rep (%)": round(rep_rate, 2),
                "Rate Max (%)": round(rate_max, 2),
                "EAD (OMR)": EAD,
                "NII (OMR)": NII_annual,
                "NIM (%)": NIM_pct,
                "Composite Risk": round(risk_base,2),
                "Provision %": prov_pct,
            })
    df_out = pd.DataFrame(rows)
    st.markdown("### 📊 Pricing Results")
    st.dataframe(df_out, use_container_width=True)
    st.caption(f"Applied NIM Target: {target_nim_to_apply:.2f}%, S&P Rating: {snp_rating}, "
               f"Industry Utilization: {industry_utilization*100:.0f}%, "
               f"Utilization Spread Adj: {utilization_subsidy_bps} bps, New Customer Adj: {new_customer_risk_premium_bps} bps")
