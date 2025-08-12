import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Tuple, List

# Set page configuration
st.set_page_config(page_title="rt 360 risk-adjusted pricing model", page_icon="💠", layout="wide")

# Custom CSS for styling
st.markdown("""
<style>
    .st-emotion-cache-1v0mbdj {
        border: 2px solid #1e88e5;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .header {
        display: flex;
        align-items: center;
        margin-bottom: 20px;
    }
    .header-title {
        font-size: 24px;
    }
    .rt {
        color: #1e88e5;
        font-weight: bold;
    }
    .three60 {
        color: #4caf50;
        font-weight: bold;
    }
    .kpi-card {
        background: white;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

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
    }.get()
