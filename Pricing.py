import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from math import ceil

# Handle num2words import gracefully
try:
    from num2words import num2words
except ImportError:
    def num2words(x, to="cardinal", lang="en"):
        # Very simple fallback for integers & 2-decimal floats
        s = f"{x:,.2f}" if isinstance(x, float) else f"{x:,}"
        return s.replace(",", " ").strip()

# Set page configuration
st.set_page_config(page_title="rt 360 Risk-Adjusted Pricing Model", page_icon="💠", layout="wide")

# CSS for styling
st.markdown("""
<style>
    .header {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 20px;
    }
    .blue-text {
        color: #1e88e5;
        font-weight: bold;
        font-size: 2em;
    }
    .green-text {
        color: #4caf50;
        font-weight: bold;
        font-size: 2em;
    }
    .card {
        border: 2px solid #1e88e5;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min(value, max_val), min_val)

def calculate_malaa_factor(score: int) -> float:
    return float(clamp(1.45 - (score - 300) * (0.90 / 600), 0.55, 1.45))

def calculate_ltv_factor(ltv_pct: float) -> float:
    return float(clamp(0.55 + 0.0075 * ltv_pct, 0.80, 1.50))

def calculate_wcs_factor(wc: float, sales: float) -> float:
    if sales <= 0:
        return 1.20
    ratio = wc / sales
    return float(clamp(0.70 + 1.00 * min(ratio, 1.2), 0.70, 1.70))

def calculate_util_factor(u_med: float) -> float:
    return float(clamp(1 - 0.30 * (0.8 - u_med), 0.70, 1.30))

def calculate_risk_base(product_factor: float, industry_factor: float, malaa_factor: float, ltv_factor: float) -> float:
    return clamp(product_factor * industry_factor * malaa_factor * ltv_factor, 0.4, 3.5)

# --- Main Application ---
def main():
    st.title("rt 360 Risk-Adjusted Pricing Model")
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("Market & Portfolio")
        oibor_pct_base = 4.1
        fed_shock_bps = st.slider("Fed Shock (bps)", -300, 300, 0)
        oibor_pct = oibor_pct_base + fed_shock_bps / 100
        st.write(f"OIBOR: {oibor_pct:.2f}%")
        
        cost_of_funds_pct = st.number_input("Cost of Funds (%)", value=5.0)
        target_nim_pct = st.number_input("Target NIM (%)", value=2.5)
        fees_income_pct = st.number_input("Fees Income (%)", value=0.4)
        opex_pct = st.number_input("Opex (%)", value=0.40)
        upfront_cost_pct = st.number_input("Upfront Cost (%)", value=0.50)

        st.header("Borrower & Product")
        product = st.selectbox("Product", ["Asset Backed Loan", "Term Loan", "Export Finance", 
                                             "Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"])
        industry = st.selectbox("Industry", ["Oil & Gas", "Construction", "Real Estate", "Manufacturing", 
                                               "Trading", "Logistics", "Healthcare", "Hospitality", 
                                               "Retail", "Mining", "Utilities", "Agriculture"])
        malaa_score = st.selectbox("Mala’a Score", [300, 350, 400, 450, 500, 600, 700, 800, 900])
        tenor_months = st.number_input("Tenor (months)", min_value=6, max_value=360, value=12)
        loan_quantum = st.number_input("Loan Quantum (OMR)", value=100000)
        ltv_pct = st.number_input("LTV (%)", min_value=0.0, max_value=100.0, value=80.0)

        st.header("Loan Book Upload")
        uploaded_file = st.file_uploader("Upload Loan Book CSV", type=["csv"])
        if uploaded_file is not None:
            loan_book_df = pd.read_csv(uploaded_file)
            st.write(loan_book_df)

        if st.button("Fetch Pricing"):
            # Pricing logic here
            product_factor = {
                "Asset Backed Loan": 1.35,
                "Term Loan": 1.20,
                "Export Finance": 1.10,
                "Vendor Finance": 0.95,
                "Supply Chain Finance": 0.90,
                "Trade Finance": 0.85
            }[product]

            industry_factor = {
                "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
                "Hospitality": 1.25, "Retail": 1.15, "Manufacturing": 1.10,
                "Trading": 1.05, "Logistics": 1.00, "Oil & Gas": 0.95,
                "Healthcare": 0.90, "Utilities": 0.85, "Agriculture": 1.15
            }[industry]

            malaa_factor_value = calculate_malaa_factor(malaa_score)
            ltv_factor_value = calculate_ltv_factor(ltv_pct)

            risk_base = calculate_risk_base(product_factor, industry_factor, malaa_factor_value, ltv_factor_value)

            # Calculate pricing buckets
            results = []
            for bucket in ["Low", "Medium", "High"]:
                risk_multiplier = {"Low": 0.90, "Medium": 1.00, "High": 1.25}[bucket]
                risk_b = clamp(risk_base * risk_multiplier, 0.4, 3.5)
                raw_spread = 75 + 350 * (risk_b - 1)
                base_spread_bps = max(int(round(raw_spread)), 125)  # Example floor
                spread_min_bps = max(base_spread_bps - 60, 125)
                spread_max_bps = base_spread_bps + 60

                rate_min_pct = clamp(oibor_pct + spread_min_bps / 100, 5.0, 10.0)
                rate_max_pct = clamp(oibor_pct + spread_max_bps / 100, 5.0, 10.0)

                EMI = calculate_emi(loan_quantum, (rate_min_pct + rate_max_pct) / 2, tenor_months)

                results.append({
                    "Bucket": bucket,
                    "Float_Min_over_OIBOR_bps": spread_min_bps,
                    "Float_Max_over_OIBOR_bps": spread_max_bps,
                    "Rate_Min_%": round(rate_min_pct, 2),
                    "Rate_Max_%": round(rate_max_pct, 2),
                    "EMI_OMR": round(EMI, 2)
                })

            # Display results
            results_df = pd.DataFrame(results)
            st.write(results_df)

if __name__ == "__main__":
    main()
