import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Tuple, List

# Set page configuration
st.set_page_config(page_title="rt 360 risk-adjusted pricing model", page_icon="💠", layout="wide")

# --- Helper Functions ---
def num_to_words(n: int) -> str:
    """Convert integer to words representation (for OMR amounts)"""
    if not isinstance(n, (int, float)):
        return ""
    n = int(n)
    
    if n == 0:
        return "zero"
    
    units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", 
             "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    
    def convert_less_than_one_thousand(x: int) -> str:
        if x == 0:
            return ""
        if x < 10:
            return units[x]
        if x < 20:
            return teens[x - 10]
        if x < 100:
            return tens[x // 10] + (" " + units[x % 10] if x % 10 != 0 else "")
        if x < 1000:
            return units[x // 100] + " hundred" + (" and " + convert_less_than_one_thousand(x % 100) if x % 100 != 0 else "")
        return ""
    
    parts = []
    for divisor, word in [(10**9, "billion"), (10**6, "million"), (10**3, "thousand")]:
        if n >= divisor:
            parts.append(convert_less_than_one_thousand(n // divisor) + " " + word)
            n %= divisor
    
    if n > 0:
        parts.append(convert_less_than_one_thousand(n))
    
    return " ".join(parts) + " Omani Rials"

def malaa_risk_label(score: int) -> str:
    """Get risk label based on Mala'a score"""
    if 300 <= score < 500:
        return "High"
    elif 500 <= score < 650:
        return "Med-High"
    elif 650 <= score < 750:
        return "Medium"
    elif score >= 750:
        return "Low"
    return "Unknown"

def pd_from_risk(risk_score: float, stage: int) -> float:
    """Calculate probability of default based on risk score and stage"""
    xs = np.array([0.4, 1.0, 2.0, 3.5])
    ys = np.array([0.3, 1.0, 3.0, 6.0])
    pd = float(np.interp(risk_score, xs, ys))
    
    if stage == 2:
        pd *= 2.5
    elif stage == 3:
        pd *= 6.0
    
    return float(np.clip(pd, 0.1, 60.0))

def lgd_from_product_ltv(product: str, ltv: float) -> float:
    """Calculate loss given default based on product and LTV"""
    base_lgd = {
        "Asset Backed Loan": 32,
        "Term Loan": 38,
        "Export Finance": 35,
        "Working Capital": 30,
        "Trade Finance": 30,
        "Supply Chain Finance": 30,
        "Vendor Finance": 30
    }.get(product, 35)
    
    ltv_adj = max(0.0, ltv - 50.0) * 0.25 if not np.isnan(ltv) else 8.0
    return float(np.clip(base_lgd + ltv_adj, 25.0, 70.0))

def calculate_emi(principal: float, rate: float, tenor: int) -> float:
    """Calculate EMI for amortizing loans"""
    monthly_rate = rate / 100 / 12
    denominator = 1 - (1 + monthly_rate) ** (-tenor)
    if denominator == 0:
        return 0.0
    return principal * monthly_rate / denominator

def calculate_cashflow(principal: float, rate: float, tenor: int, 
                      cof: float, prov: float, opex: float, fee: float = 0.0) -> dict:
    """Calculate cash flow metrics for fund-based loans (NII, NIM, breakeven)"""
    results = {
        'emi': 0.0,
        'annual_interest': 0.0,
        'annual_provision': 0.0,
        'annual_opex': 0.0,
        'annual_funding': 0.0,
        'annual_fees': fee * principal / 100 if fee > 0 else 0.0,
        'nim': 0.0,
        'be_min': 0,
        'be_rep': 0,
        'be_max': 0
    }
    
    if principal <= 0 or tenor <= 0:
        return results
    
    # Calculate EMI
    results['emi'] = calculate_emi(principal, rate, tenor)
    
    # Calculate annual metrics (first 12 months)
    balance = principal
    total_interest = 0.0
    total_provision = 0.0
    total_opex = 0.0
    total_funding = 0.0
    
    for month in range(1, tenor + 1):
        interest = balance * rate / 100 / 12
        provision = balance * prov / 100 / 12
        operating_cost = balance * opex / 100 / 12
        funding_cost = balance * cof / 100 / 12
        
        principal_payment = results['emi'] - interest
        
        if month <= 12:
            total_interest += interest
            total_provision += provision
            total_opex += operating_cost
            total_funding += funding_cost
        
        balance = max(0, balance - principal_payment)
        if balance <= 0:
            break
    
    results['annual_interest'] = total_interest * 12 / min(12, tenor)
    results['annual_provision'] = total_provision * 12 / min(12, tenor)
    results['annual_opex'] = total_opex * 12 / min(12, tenor)
    results['annual_funding'] = total_funding * 12 / min(12, tenor)
    
    results['nim'] = (results['annual_interest'] + results['annual_fees'] - 
                     (results['annual_funding'] + results['annual_provision'] + 
                      results['annual_opex'])) / principal * 100
    
    return results

def calculate_utilization_metrics(limit: float, utilization: float, rate: float,
                                 cof: float, prov: float, opex: float, fee: float = 0.0) -> dict:
    """Calculate metrics for utilization-based loans"""
    ead = limit * (utilization / 100) if utilization > 0 else 0.0
    margin = rate + fee - (cof + prov + opex)
    
    return {
        'annual_interest': ead * rate / 100,
        'annual_fees': ead * fee / 100 if fee > 0 else 0.0,
        'annual_funding': ead * cof / 100,
        'annual_provision': ead * prov / 100,
        'annual_opex': ead * opex / 100,
        'nim': margin,
        'emi': None,  # Not applicable for utilization loans
        'be_min': 0,
        'be_rep': 0,
        'be_max': 0
    }

@st.cache_data
def calculate_pricing(
    product: str, industry: str, malaa_score: int, loan_quantum: float, tenor: int,
    ltv: float, working_capital: float, sales: float, utilization: float, stage: int,
    oibor_pct: float, cof_pct: float, target_nim_pct: float, 
    fees_pct: float, opex_pct: float, upfront_cost_pct: float
) -> pd.DataFrame:
    """Main pricing calculation function for all three buckets"""
    # Product and industry risk factors
    product_factor = {
        "Asset Backed Loan": 1.35, "Term Loan": 1.20, "Export Finance": 1.10,
        "Working Capital": 0.95, "Trade Finance": 0.85, "Supply Chain Finance": 0.90,
        "Vendor Finance": 0.95
    }.get(product, 1.0)
    
    industry_factor = {
        "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
        "Hospitality": 1.25, "Retail": 1.15, "Manufacturing": 1.10,
        "Trading": 1.05, "Logistics": 1.00, "Oil & Gas": 0.95,
        "Healthcare": 0.90, "Utilities": 0.85, "Agriculture": 1.15
    }.get(industry, 1.0)

    malaa_factor = float(np.clip(1.45 - (malaa_score - 300) * (0.90 / 600), 0.55, 1.45))
    
    # Calculate risk base
    if ltv is not None and ltv > 0:
        ltv_factor = float(np.clip(0.55 + 0.0075 * ltv, 0.80, 1.50))
        risk_base = np.clip(product_factor * industry_factor * malaa_factor * ltv_factor, 0.4, 3.5)
    else:
        wcs_factor = 1.20 if sales <= 0 else float(np.clip(0.70 + 1.00 * (working_capital / sales), 0.70, 1.70))
        risk_base = np.clip(product_factor * industry_factor * malaa_factor * wcs_factor, 0.4, 3.5)

    # Calculate PD and LGD
    pd = pd_from_risk(risk_base, stage)
    lgd = lgd_from_product_ltv(product, ltv)
    provision_rate = pd * lgd / 100

    # Pricing calculations
    buckets = ["Low", "Medium", "High"]
    results = []

    for bucket in buckets:
        multiplier = {"Low": 0.90, "Medium": 1.00, "High": 1.25}[bucket]
        risk_b = np.clip(risk_base * multiplier, 0.4, 3.5)

        # Calculate spreads
        raw_spread_bps = 75 + 350 * (risk_b - 1)
        industry_floor_addon = 100 if industry_factor >= 1.25 else 50 if industry_factor >= 1.10 else 0
        product_floor_addon = 125 if product == "Asset Backed Loan" else 75 if product in ["Term Loan", "Export Finance"] else 0
        borrower_floor_addon = {"High": 175, "Med-High": 125, "Medium": 75, "Low": 0}[malaa_risk_label(malaa_score)]
        
        sum_floors = max(125, 150 + industry_floor_addon + product_floor_addon + borrower_floor_addon)
        center_spread_bps = max(raw_spread_bps, sum_floors)

        # Calculate rates
        spread_min = center_spread_bps - (60 if bucket == "Low" else 90 if bucket == "Medium" else 140)
        spread_max = center_spread_bps + (60 if bucket == "Low" else 90 if bucket == "Medium" else 140)
        
        rate_min = max(5.0, oibor_pct + spread_min / 100)
        rate_max = max(5.0, oibor_pct + spread_max / 100)
        rep_rate = (rate_min + rate_max) / 2

        # NIM calculations
        fees_pct = 0.4 if product in ["Supply Chain Finance", "Vendor Finance", "Working Capital", "Export Finance"] else 0.0
        nim_rep = rep_rate + fees_pct - (cof_pct + provision_rate + opex_pct)
        required_rate = target_nim_pct + cof_pct + provision_rate + opex_pct - fees_pct

        # Enforce NIM floor
        if rep_rate < required_rate:
            center_spread_bps = required_rate - fees_pct + (cof_pct + provision_rate + opex_pct)
            spread_min = center_spread_bps - (60 if bucket == "Low" else 90 if bucket == "Medium" else 140)
            spread_max = center_spread_bps + (60 if bucket == "Low" else 90 if bucket == "Medium" else 140)
            rate_min = max(5.0, oibor_pct + spread_min / 100)
            rate_max = max(5.0, oibor_pct + spread_max / 100)
            rep_rate = (rate_min + rate_max) / 2

        # Cash flow calculations
        if ltv is not None and ltv > 0:
            cashflow = calculate_cashflow(loan_quantum, rep_rate, tenor, cof_pct, provision_rate, opex_pct, fees_pct)
        else:
            cashflow = calculate_utilization_metrics(working_capital, utilization, rep_rate, cof_pct, provision_rate, opex_pct, fees_pct)

        results.append({
            "Bucket": bucket,
            "Float_Min_over_OIBOR_bps": int(spread_min),
            "Float_Max_over_OIBOR_bps": int(spread_max),
            "Rate_Min_%": round(rate_min, 2),
            "Rate_Max_%": round(rate_max, 2),
            "Rep_Rate_%": round(rep_rate, 2),
            "EMI_OMR": cashflow['emi'],
            "Annual_Interest_Income_OMR": round(cashflow['annual_interest'], 2),
            "Annual_Fee_Income_OMR": round(cashflow['annual_fees'], 2),
            "Annual_Funding_Cost_OMR": round(cashflow['annual_funding'], 2),
            "Annual_Provision_OMR": round(cashflow['annual_provision'], 2),
            "Annual_Opex_OMR": round(cashflow['annual_opex'], 2),
            "Net_Interest_Income_OMR": round(cashflow['annual_interest'] + cashflow['annual_fees'] - 
                                              (cashflow['annual_funding'] + cashflow['annual_provision'] + 
                                               cashflow['annual_opex']), 2),
            "NIM_%": round(cashflow['nim'], 2),
            "Breakeven_Min_Months": cashflow['be_min'],
            "Breakeven_Rep_Months": cashflow['be_rep'],
            "Breakeven_Max_Months": cashflow['be_max'],
            "Optimal_Utilization_%": utilization if utilization > 0 else "-",
            "Borrower_Risk_Label": malaa_risk_label(malaa_score),
            "Industry_Risk_Factor": round(industry_factor, 2),
            "Product_Risk_Factor": round(product_factor, 2),
            "Composite_Risk_Score": round(risk_base, 2)
        })

    return pd.DataFrame(results)

# --- UI Layout ---
st.title("rt 360 risk-adjusted pricing model for Corporate Lending")

# Sidebar
st.sidebar.header("Market & Bank Parameters")
oibor_pct_base = st.sidebar.number_input("OIBOR Base (%)", value=4.1)
fed_shock_bps = st.sidebar.slider("Fed Shock (bps)", -300, 300, 0)
oibor_pct = oibor_pct_base + fed_shock_bps / 100
cost_of_funds_pct = st.sidebar.number_input("Cost of Funds (%)", value=5.0)
target_nim_pct = st.sidebar.number_input("Target NIM (%)", value=2.5)
fees_income_pct_default = st.sidebar.number_input("Fees Income (%)", value=0.4)
opex_pct = st.sidebar.number_input("Opex (%)", value=0.40)
upfront_cost_pct = st.sidebar.number_input("Upfront Cost (%)", value=0.50)

# Borrower & Product
st.sidebar.header("Borrower & Product")
product = st.sidebar.selectbox("Product", ["Asset Backed Loan", "Term Loan", "Export Finance", 
                                             "Working Capital", "Trade Finance", "Supply Chain Finance", 
                                             "Vendor Finance"])
industry = st.sidebar.selectbox("Industry", ["Oil & Gas", "Construction", "Real Estate", 
                                               "Manufacturing", "Trading", "Logistics", 
                                               "Healthcare", "Hospitality", "Retail", 
                                               "Mining", "Utilities", "Agriculture"])
malaa_score = st.sidebar.slider("Mala’a Score", 300, 900, 300, 50)

# Loan Details
st.sidebar.header("Loan Details")
tenor_months = st.sidebar.number_input("Tenor (months)", 6, 360, 12)
loan_quantum_omr = st.sidebar.number_input("Loan Quantum (OMR)", 0)
st.caption(f"In words: {num_to_words(int(loan_quantum_omr))}")

# Upload Loan Book
st.sidebar.header("Upload Loan Book (CSV)")
uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
if uploaded_file is not None:
    loan_book_df = pd.read_csv(uploaded_file)
    st.write(loan_book_df)

# Compute Pricing Button
if st.sidebar.button("Compute Pricing"):
    # Call the pricing calculation function
    pricing_results = calculate_pricing(
        product, industry, malaa_score, loan_quantum_omr, tenor_months,
        ltv=None, working_capital=0, sales=0, utilization=0, stage=1,
        oibor_pct=oibor_pct, cof_pct=cost_of_funds_pct, target_nim_pct=target_nim_pct, 
        fees_pct=fees_income_pct_default, opex_pct=opex_pct, upfront_cost_pct=
