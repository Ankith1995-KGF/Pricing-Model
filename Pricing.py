# app.py
import streamlit as st
import pandas as pd
import numpy as np
from typing import Tuple, Union

# --- Safe import for num2words ---
try:
    from num2words import num2words

    def num2words_omr(amount: float) -> str:
        """Convert amount to words with 'Omani Rials' suffix."""
        try:
            integer_amount = int(round(amount))
            words = num2words(integer_amount, to='cardinal', lang='en')
            return words.capitalize() + " Omani Rials"
        except Exception:
            return f"{amount:,.2f} OMR"
except ImportError:
    # Fallback if num2words not installed
    def num2words_omr(amount: float) -> str:
        """Fallback: just return number formatted with OMR suffix."""
        return f"{amount:,.2f} OMR"

# --- Constants ---
PRODUCT_LIST = [
    "Asset Backed Loan", "Term Loan", "Export Finance",
    "Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"
]
INDUSTRY_LIST = [
    "Oil & Gas", "Construction", "Real Estate", "Manufacturing", "Trading",
    "Logistics", "Healthcare", "Hospitality", "Retail", "Mining", "Utilities", "Agriculture"
]
MALAA_SCORE_LIST = list(range(300, 901, 50))
TENOR_MIN, TENOR_MAX = 6, 360

PRODUCT_RISK = {
    "Asset Backed Loan": 1.00, "Term Loan": 0.90, "Export Finance": 0.80,
    "Vendor Finance": 0.60, "Supply Chain Finance": 0.55,
    "Trade Finance": 0.50, "Working Capital": 0.50
}
INDUSTRY_RISK = {
    "Oil & Gas": 0.70, "Construction": 0.90, "Real Estate": 0.85, "Manufacturing": 0.80, "Trading": 0.75,
    "Logistics": 0.70, "Healthcare": 0.60, "Retail": 0.80, "Hospitality": 0.85, "Mining": 0.90,
    "Utilities": 0.55, "Agriculture": 0.85
}
U_MED = {
    "Trading": 0.65, "Manufacturing": 0.55, "Construction": 0.40, "Logistics": 0.60,
    "Retail": 0.50, "Healthcare": 0.45, "Hospitality": 0.35, "Oil & Gas": 0.50,
    "Real Estate": 0.30, "Utilities": 0.55, "Mining": 0.45, "Agriculture": 0.40
}
RISK_MULT = {"Low": 0.90, "Medium": 1.00, "High": 1.15}
BAND_BPS = {"Low": 50, "Medium": 75, "High": 100}
MIN_CORE_SPREAD_BPS = 75
RATE_MIN_CLAMP, RATE_MAX_CLAMP = 5.0, 10.0
OPEX_PCT_DEFAULT = 0.4

# --- Utility functions ---
clamp = lambda x, lo, hi: max(min(x, hi), lo)
malaa_factor = lambda score: 1.3 - (score - 300) * (0.8/600)
ltv_factor = lambda pct: clamp(0.7 + 0.0035 * pct, 0.8, 1.2)
def wcs_factor(wc, sales): return 0.85 + 0.6 * min(wc/sales if sales > 0 else 0, 1.0)
def util_factor(u): return clamp(1 - 0.15 * (0.8 - u), 0.85, 1.15)

def compute_emi(p, rate_pct, tenor):
    i_m = rate_pct/100/12
    return p * i_m * (1+i_m)**tenor / ((1+i_m)**tenor - 1) if i_m else p/tenor

def compute_spread_bps(risk): return clamp(100 + 250*(risk - 1), MIN_CORE_SPREAD_BPS, 500)

def determine_risk_category(score, ind_f, prod_f):
    if score <= 499: br = "High"
    elif score <= 649: br = "Medium-High"
    elif score <= 749: br = "Medium"
    else: br = "Low"
    ir = "High" if ind_f >= 0.85 else "Medium" if ind_f >= 0.70 else "Low"
    pr = "High" if prod_f >= 0.90 else "Medium" if prod_f >= 0.70 else "Low"
    return br, ir, pr

def compute_fund_based(principal, r_rep_b, cf_pct, credit_cost_pct_b, fee_yield_pct, tenor, emi):
    i_b, c_b = r_rep_b/100/12, cf_pct/100/12
    cc_b, op_b = credit_cost_pct_b/100/12, OPEX_PCT_DEFAULT/100/12
    fy_b = fee_yield_pct/100/12
    bal, sum_net, sum_bal, months = principal, 0, 0, min(tenor, 12)
    for _ in range(months):
        interest = bal*i_b
        net_margin = interest + principal*fy_b - bal*c_b - bal*cc_b - bal*op_b
        sum_net += net_margin; sum_bal += bal
        bal = max(bal - (emi - interest), 0)
    NII = sum_net
    NIM = 100 * NII / (sum_bal/months)
    return NII, NIM

def compute_utilization(principal, util, r_pct, cf_pct, credit_cost, fee_yield_pct):
    E_avg = principal*util
    margin_pct = r_pct + fee_yield_pct - cf_pct - credit_cost - OPEX_PCT_DEFAULT
    return (margin_pct/100)*E_avg, margin_pct

def breakeven_fund(principal, r_pct, cf_pct, credit_cost, fee_yield_pct, tenor, emi):
    i_b, c_b = r_pct/100/12, cf_pct/100/12
    cc_b, op_b = credit_cost/100/12, OPEX_PCT_DEFAULT/100/12
    fy_b, bal = fee_yield_pct/100/12, principal
    C0, cum_net = 0.5/100*principal, -0.5/100*principal
    for m in range(1, tenor+1):
        interest = bal*i_b
        net_margin = interest + principal*fy_b - bal*c_b - bal*cc_b - bal*op_b
        cum_net += net_margin
        bal = max(bal - (emi - interest), 0)
        if cum_net >= 0: return m
    return "Breakeven not within the tenor"

def breakeven_util(principal, util, nim_pct, tenor):
    C0, net_monthly = 0.5/100*principal, (nim_pct/100/12)*principal*util
    if net_monthly <= 0: return "Breakeven not within the tenor"
    mths = int(np.ceil(C0 / net_monthly))
    return mths if mths <= tenor else "Breakeven not within the tenor"

def optimal_util(prod_f, ind_f, malaa_f, wcs_f, oibor_pct, fee_yield_pct, cf_pct, target_nim_pct):
    for u in np.arange(0.30, 0.96, 0.01):
        util_f = util_factor(u)
        risk_u = clamp(prod_f*ind_f*malaa_f*wcs_f*util_f, 0.4, 2.0)
        spread_u = clamp(100 + 250*(risk_u - 1), MIN_CORE_SPREAD_BPS, 500)
        r_u = clamp(oibor_pct + spread_u/100, RATE_MIN_CLAMP, RATE_MAX_CLAMP)
        credit_cost_u = clamp(0.4 * risk_u / 100, 0.2, 1.0)
        margin_pct = r_u + fee_yield_pct - cf_pct - credit_cost_u - OPEX_PCT_DEFAULT
        if margin_pct >= target_nim_pct: return round(u*100)
    return "– (not achievable)"

# --- Streamlit UI ---
st.set_page_config("rt 360 risk-adjusted pricing model", layout="wide")
st.markdown("<h1><span style='color:blue;'>rt</span> <span style='color:green;'>360</span></h1>", unsafe_allow_html=True)
st.markdown("<style>.main-container{border:4px solid blue;padding:20px;border-radius:8px;background:white;}</style>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Inputs")
    oibor_pct = st.number_input("OIBOR %", value=4.1)
    cost_of_funds_pct = st.number_input("Cost of Funds %", value=5.0)
    target_nim_pct = st.number_input("Target NIM %", value=2.5)
    fees_income_pct = st.number_input("Fees Income %", value=0.4)
    product = st.selectbox("Product", PRODUCT_LIST)
    industry = st.selectbox("Industry", INDUSTRY_LIST)
    malaa_score = st.selectbox("Mala’a Score", MALAA_SCORE_LIST, index=7)
    tenor_months = st.slider("Tenor (months)", TENOR_MIN, TENOR_MAX, 36)
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        loan_quantum = st.number_input("Loan Quantum (OMR)", value=100000.0)
        LTV_pct = st.number_input("Loan to Value %", value=80.0)
        st.caption(f"In words: {num2words_omr(loan_quantum)}")
    else:
        working_capital = st.number_input("Working Capital (OMR)", value=50000.0)
        sales = st.number_input("Sales (OMR)", value=200000.0)
        st.caption(f"WC in words: {num2words_omr(working_capital)}")
        st.caption(f"Sales in words: {num2words_omr(sales)}")
    fetch = st.button("Fetch Pricing")

if fetch:
    is_fund = product in ["Asset Backed Loan", "Term Loan", "Export Finance"]
    if is_fund:
        if LTV_pct <= 0: st.error("LTV must be > 0"); st.stop()
        principal = loan_quantum
        risk_base = clamp(PRODUCT_RISK[product]*INDUSTRY_RISK[industry]*malaa_factor(malaa_score)*ltv_factor(LTV_pct), 0.4, 2.0)
    else:
        if working_capital <= 0 or sales <= 0: st.error("WC & Sales must be > 0"); st.stop()
        principal = working_capital
        wcs_f = wcs_factor(working_capital, sales)
        util_f = util_factor(U_MED[industry])
        risk_base = clamp(PRODUCT_RISK[product]*INDUSTRY_RISK[industry]*malaa_factor(malaa_score)*wcs_f*util_f, 0.4, 2.0)

    rows = []
    for bucket in ["Low", "Medium", "High"]:
        risk_b = clamp(risk_base*RISK_MULT[bucket], 0.4, 2.0)
        spread_bps = compute_spread_bps(risk_b)
        spread_min = max(int(round(spread_bps - BAND_BPS[bucket])), MIN_CORE_SPREAD_BPS)
        spread_max = max(int(round(spread_bps + BAND_BPS[bucket])), spread_min+1)
        rate_min = clamp(oibor_pct + spread_min/100, RATE_MIN_CLAMP, RATE_MAX_CLAMP)
        rate_max = clamp(oibor_pct + spread_max/100, RATE_MIN_CLAMP, RATE_MAX_CLAMP)
        spread_min = max(int(round((rate_min - oibor_pct)*100)), MIN_CORE_SPREAD_BPS)
        spread_max = max(int(round((rate_max - oibor_pct)*100)), spread_min+1)
        r_rep = (rate_min + rate_max) / 2
        credit_cost = clamp(0.4 * risk_b / 100, 0.2, 1.0)

        if is_fund:
            emi = compute_emi(principal, r_rep, tenor_months)
            NII, NIM = compute_fund_based(principal, r_rep, cost_of_funds_pct, credit_cost, fees_income_pct, tenor_months, emi)
            breakeven = breakeven_fund(principal, r_rep, cost_of_funds_pct, credit_cost, fees_income_pct, tenor_months, emi)
            opt_util = "–"
            EMI_display = f"{emi:,.2f}"
        else:
            NII, NIM = compute_utilization(principal, U_MED[industry], r_rep, cost_of_funds_pct, credit_cost, fees_income_pct)
            breakeven = breakeven_util(principal, U_MED[industry], NIM, tenor_months)
            opt_util = optimal_util(PRODUCT_RISK[product], INDUSTRY_RISK[industry], malaa_factor(malaa_score), wcs_f, oibor_pct, fees_income_pct, cost_of_funds_pct, target_nim_pct)
            EMI_display = "–"

        rows.append({
            "Bucket": bucket,
            "Float_Min_over_OIBOR_bps": spread_min,
            "Float_Max_over_OIBOR_bps": spread_max,
            "Rate_Min_% (OIBOR+)": f"{rate_min:.2f}",
            "Rate_Max_%": f"{rate_max:.2f}",
            "EMI_OMR": EMI_display,
            "Net_Interest_Income_OMR": f"{NII:,.2f}",
            "NIM_%": f"{NIM:.2f}",
            "Breakeven_Months": breakeven,
            "Optimal_Utilization_%": opt_util
        })
    df = pd.DataFrame(rows)
    br, ir, pr = determine_risk_category(malaa_score, INDUSTRY_RISK[industry], PRODUCT_RISK[product])
    st.subheader("Risk Categorization")
    st.write(f"**Borrower Risk:** {br}  |  **Industry Risk:** {ir}  |  **Product Risk:** {pr}")
    st.subheader("Pricing Table")
    st.dataframe(df, use_container_width=True)
