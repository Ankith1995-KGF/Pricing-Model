import streamlit as st
import pandas as pd
import numpy as np
from math import ceil, pow
from typing import Dict, Any, List, Optional
from datetime import datetime

# Handle num2words import gracefully
try:
    from num2words import num2words
except ImportError:
    def num2words(x, to="cardinal", lang="en"):
        return str(x)  # Fallback to simple number display

# --- Core Calculation Functions ---
def calculate_emi(principal: float, annual_rate: float, months: int) -> float:
    """Calculate Equated Monthly Installment (EMI)"""
    if annual_rate == 0:
        return principal / months
    monthly_rate = annual_rate / 100 / 12
    return principal * monthly_rate * pow(1 + monthly_rate, months) / (pow(1 + monthly_rate, months) - 1)

def calculate_nii(
    loan_amount: float,
    rate_pct: float,
    cost_of_funds_pct: float,
    tenor_months: int,
    fees_pct: float = 0.0
) -> Dict[str, float]:
    """Calculate Net Interest Income and Margin"""
    monthly_rate = rate_pct / 100 / 12
    cof_monthly = cost_of_funds_pct / 100 / 12
    balance = loan_amount
    total_nii = 0.0
    
    for _ in range(min(12, tenor_months)):
        interest = balance * monthly_rate
        funding_cost = balance * cof_monthly
        fee_income = loan_amount * fees_pct / 100 / 12
        total_nii += (interest + fee_income - funding_cost)
        principal = calculate_emi(loan_amount, rate_pct, tenor_months) - interest
        balance = max(balance - principal, 0)
    
    avg_balance = loan_amount * min(12, tenor_months) / 12
    nim_pct = (total_nii / avg_balance) * 100 if avg_balance > 0 else 0
    
    return {
        "nii": total_nii,
        "nim": nim_pct,
        "avg_balance": avg_balance
    }

# --- Risk Model Functions ---
def get_risk_factors() -> Dict[str, Dict]:
    return {
        "product": {
            "Asset Backed Loan": 1.35,
            "Term Loan": 1.20,
            "Export Finance": 1.10,
            "Vendor Finance": 0.95,
            "Supply Chain Finance": 0.90,
            "Trade Finance": 0.85
        },
        "industry": {
            "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
            "Hospitality": 1.25, "Retail": 1.15, "Manufacturing": 1.10,
            "Trading": 1.05, "Logistics": 1.00, "Oil & Gas": 0.95,
            "Healthcare": 0.90, "Utilities": 0.85, "Agriculture": 1.15
        }
    }

# --- UI Components ---
def display_header():
    st.markdown("""
    <style>
        .header-container {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
        }
        .rt-text {
            color: #1e88e5;
            font-weight: bold;
            font-size: 2.5rem;
        }
        .360-text {
            color: #4caf50;
            font-weight: bold;
            font-size: 2.5rem;
        }
    </style>
    <div class="header-container">
        <span class="rt-text">rt</span>
        <span class="360-text">360</span>
    </div>
    <h3 style="text-align: center;">Risk-Adjusted Pricing Model for Corporate Lending</h3>
    """, unsafe_allow_html=True)

def main():
    # Page configuration
    st.set_page_config(
        page_title="rt 360 Risk-Adjusted Pricing Model",
        page_icon="💠",
        layout="wide"
    )
    
    # Display header
    display_header()
    
    # Initialize session state
    if 'calculated' not in st.session_state:
        st.session_state.calculated = False
    
    # Sidebar inputs
    with st.sidebar:
        st.header("Market Parameters")
        oibor_base = 4.1
        fed_shock = st.slider("Fed Shock (bps)", -300, 300, 0, 
                             help="Impact on base OIBOR rate")
        oibor = oibor_base + (fed_shock / 100)
        st.metric("Effective OIBOR", f"{oibor:.2f}%")
        
        cost_of_funds = st.number_input("Cost of Funds (%)", value=5.0, min_value=0.0)
        target_nim = st.number_input("Target NIM (%)", value=2.5, min_value=0.0)
        
        st.header("Loan Parameters")
        product = st.selectbox("Product", list(get_risk_factors()["product"].keys()))
        industry = st.selectbox("Industry", list(get_risk_factors()["industry"].keys()))
        tenor = st.number_input("Tenor (months)", min_value=6, max_value=360, value=36)
        amount = st.number_input("Loan Amount (OMR)", min_value=0.0, value=1000000.0)
        st.caption(f"In words: {num2words(amount)} Omani Rials")
        
        if st.button("Calculate Pricing", type="primary"):
            st.session_state.calculated = True
            st.session_state.calculation_time = datetime.now()
    
    # Main content area
    if st.session_state.get('calculated', False):
        with st.spinner("Calculating pricing..."):
            try:
                # Example calculation (simplified)
                example_rate = oibor + 1.25  # Simplified for demo
                emi = calculate_emi(amount, example_rate, tenor)
                nii_data = calculate_nii(amount, example_rate, cost_of_funds, tenor)
                
                # Display results in a card
                with st.container():
                    st.markdown("### Pricing Results")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Repayment Rate", f"{example_rate:.2f}%")
                        st.metric("EMI", f"OMR {emi:,.2f}")
                    
                    with col2:
                        st.metric("Annual NII", f"OMR {nii_data['nii']:,.0f}")
                        st.metric("NIM", f"{nii_data['nim']:.2f}%")
                
                st.success("Calculation completed successfully!")
                st.toast(f"Calculated at {st.session_state.calculation_time:%H:%M:%S}", icon="🕒")
                
            except Exception as e:
                st.error(f"Error in calculation: {str(e)}")
    else:
        st.info("Please configure parameters and click 'Calculate Pricing'")

if __name__ == "__main__":
    main()
