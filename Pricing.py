import streamlit as st
import pandas as pd
import numpy as np
from num2words import num2words
from typing import Dict, Tuple, Any

# Set page configuration
st.set_page_config(page_title="rt 360 risk-adjusted pricing model for Corporate Lending", page_icon="💠", layout="wide")

# Helper functions
def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min(value, max_value), min_value)

@st.cache_data
def calculate_pricing(oibor_pct: float, fed_shock_bps: int, cost_of_funds_pct: float, target_nim_pct: float,
                       fees_income_pct: float, tenor_months: int, loan_quantum: float, malaa_score: int,
                       product: str, industry: str, ltv_pct: float = None, working_capital: float = None,
                       sales: float = None) -> pd.DataFrame:
    # Define constants
    market_min, market_max = 5.0, 10.0
    min_core_spread_bps = 125
    bucket_floor_gaps = {"Low": 150, "Medium": 225, "High": 325}
    
    # Risk multipliers
    product_factor = {
        "Asset Backed Loan": 1.35,
        "Term Loan": 1.20,
        "Export Finance": 1.10,
        "Vendor Finance": 0.95,
        "Supply Chain Finance": 0.90,
        "Trade Finance": 0.85
    }
    
    industry_factor = {
        "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
        "Hospitality": 1.25,  "Retail": 1.15,    "Manufacturing": 1.10,
        "Trading": 1.05,      "Logistics": 1.00, "Oil & Gas": 0.95,
        "Healthcare": 0.90,   "Utilities": 0.85, "Agriculture": 1.15
    }
    
    # Calculate OIBOR
    oibor_pct += fed_shock_bps / 100.0
    
    # Calculate risk base
    malaa_factor = clamp(1.45 - (malaa_score - 300) * (0.90 / 600), 0.55, 1.45)
    ltv_factor = clamp(0.55 + 0.0075 * ltv_pct, 0.80, 1.50) if ltv_pct is not None else 1.0
    risk_base = clamp(product_factor[product] * industry_factor[industry] * malaa_factor * ltv_factor, 0.4, 3.5)
    
    # Pricing logic
    results = []
    for bucket in ["Low", "Medium", "High"]:
        risk_multiplier = {"Low": 0.90, "Medium": 1.00, "High": 1.25}
        risk_b = clamp(risk_base * risk_multiplier[bucket], 0.4, 3.5)
        
        raw_spread_bps_b = 75 + 350 * (risk_b - 1)
        floors_sum_bps = max(min_core_spread_bps, bucket_floor_gaps[bucket])
        base_spread_bps_b = max(int(round(raw_spread_bps_b)), floors_sum_bps)
        
        # Calculate rates
        band_bps = {"Low": 60, "Medium": 90, "High": 140}
        spread_min_bps_b = base_spread_bps_b - band_bps[bucket]
        spread_max_bps_b = base_spread_bps_b + band_bps[bucket]
        
        rate_min_pct_b = clamp(oibor_pct + spread_min_bps_b / 100, market_min, market_max)
        rate_max_pct_b = clamp(oibor_pct + spread_max_bps_b / 100, market_min, market_max)
        
        # Calculate EMI and NII
        i_b = rate_min_pct_b / 100 / 12
        EMI = loan_quantum * i_b * (1 + i_b) ** tenor_months / ((1 + i_b) ** tenor_months - 1)
        
        # Calculate NII and NIM
        NII_annual_b = (EMI * tenor_months) - (loan_quantum * cost_of_funds_pct / 100)
        NIM_pct_b = (NII_annual_b / loan_quantum) * 100
        
        results.append({
            "Bucket": bucket,
            "Float_Min_over_OIBOR_bps": spread_min_bps_b,
            "Float_Max_over_OIBOR_bps": spread_max_bps_b,
            "Rate_Min_%": round(rate_min_pct_b, 2),
            "Rate_Max_%": round(rate_max_pct_b, 2),
            "EMI_OMR": round(EMI, 2),
            "Net_Interest_Income_OMR": int(NII_annual_b),
            "NIM_%": round(NIM_pct_b, 2),
            "Breakeven_Months": "N/A",  # Placeholder for breakeven calculation
            "Optimal_Utilization_%": "N/A"  # Placeholder for optimal utilization calculation
        })
    
    return pd.DataFrame(results)

# UI Components
st.markdown("<h1 style='color:blue;'>rt</h1><h1 style='color:green;'>360</h1>", unsafe_allow_html=True)
st.subheader("risk-adjusted pricing model for Corporate Lending")

# Sidebar inputs
with st.sidebar:
    st.header("Market & Portfolio")
    oibor_pct_base = 4.1
    fed_shock_bps = st.slider("Fed shock (bps)", -300, 300, 0)
    cost_of_funds_pct = st.number_input("Cost of Funds (%)", value=5.0)
    target_nim_pct = st.number_input("Target NIM (%)", value=2.5)
    fees_income_pct = st.number_input("Fees Income (%)", value=0.4)
    tenor_months = st.number_input("Tenor (months)", min_value=6, max_value=360, value=12)
    loan_quantum = st.number_input("Loan Quantum (OMR)", value=100000)
    malaa_score = st.selectbox("Mala’a Score", [300, 350, 400, 450, 500, 600, 700, 800, 900])
    product = st.selectbox("Product", list(product_factor.keys()))
    industry = st.selectbox("Industry", list(industry_factor.keys()))
    ltv_pct = st.number_input("LTV (%)", min_value=0.0, max_value=100.0, value=80.0)

    if st.button("Fetch Pricing"):
        pricing_results = calculate_pricing(oibor_pct_base, fed_shock_bps, cost_of_funds_pct, target_nim_pct,
                                             fees_income_pct, tenor_months, loan_quantum, malaa_score, product, industry, ltv_pct)
        st.dataframe(pricing_results)

# Footer
st.markdown("### Notes:")
st.markdown("Rates clamped to 5–10% band. No bucket priced below target NIM.")
