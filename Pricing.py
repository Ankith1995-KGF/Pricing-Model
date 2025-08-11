import streamlit as st
import pandas as pd
import numpy as np
from math import ceil
from typing import Dict, List, Tuple, Union

# Custom number to words conversion (basic implementation)
def number_to_words(n: Union[float, int], is_percent: bool = False) -> str:
    """Convert numbers to words without external dependencies"""
    units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", 
             "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "ten", "twenty", "thirty", "forty", 
            "fifty", "sixty", "seventy", "eighty", "ninety"]
    scales = ["", "thousand", "million", "billion", "trillion"]
    
    def convert_less_than_one_thousand(n):
        if n == 0:
            return ""
        elif n < 10:
            return units[n]
        elif n < 20:
            return teens[n - 10]
        elif n < 100:
            return tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
        else:
            return units[n // 100] + " hundred" + (" " + convert_less_than_one_thousand(n % 100) if n % 100 != 0 else "")
    
    try:
        n = float(n)
        if n == 0:
            return "zero" + (" percent" if is_percent else "")
        
        # Handle decimal parts
        int_part = int(n)
        decimal_part = round((n - int_part) * 100)
        words = []
        
        if int_part > 0:
            words.append(convert_less_than_one_thousand(int_part))
        if decimal_part > 0:
            words.append("point")
            words.append(convert_less_than_one_thousand(decimal_part))
        
        result = " ".join(words).strip()
        return f"{result} percent" if is_percent else result
    except:
        return str(n)

# Core pricing functions
def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min(value, max_val), min_val)

def calculate_emi(principal: float, annual_rate: float, months: int) -> float:
    """Calculate equated monthly installment"""
    if annual_rate <= 0:
        return principal / months
    monthly_rate = annual_rate / 100 / 12
    return principal * monthly_rate * (1 + monthly_rate)**months / ((1 + monthly_rate)**months - 1)

# Risk Model Components
PRODUCT_FACTORS = {
    "Asset Backed Loan": 1.35,
    "Term Loan": 1.20,
    "Export Finance": 1.10,  
    "Vendor Finance": 0.95,
    "Supply Chain Finance": 0.90,
    "Trade Finance": 0.85,
    "Working Capital": 0.95
}

INDUSTRY_FACTORS = {
    "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
    "Hospitality": 1.25, "Retail": 1.15, "Manufacturing": 1.10,
    "Trading": 1.05, "Logistics": 1.00, "Oil & Gas": 0.95,
    "Healthcare": 0.90, "Utilities": 0.85, "Agriculture": 1.15
}

# UI Implementation
def main():
    st.set_page_config(
        page_title="rt 360 Pricing Model",
        page_icon="💠",
        layout="wide"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
        }
        .blue-text {
            color: #1e88e5;
            font-weight: bold;
        }
        .green-text {
            color: #4caf50;
            font-weight: bold;
        }
        .card {
            border: 2px solid #1e88e5;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="header">
        <span class="blue-text">rt</span>
        <span class="green-text">360</span>
        <span style="margin-left: 10px;">Risk-Adjusted Pricing Model</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Main layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Market parameters
        with st.expander("Market Parameters", expanded=True):
            st.number_input("Base OIBOR (%)", value=4.1, key="oibor_base")
            st.slider("Fed Shock (bps)", -300, 300, 0, key="fed_shock")
            st.number_input("Cost of Funds (%)", value=5.0, key="cof")
            st.number_input("Target NIM (%)", value=2.5, key="target_nim")
    
    with col2:
        # Loan parameters
        with st.expander("Loan Parameters", expanded=True):
            st.selectbox("Product", list(PRODUCT_FACTORS.keys()), key="product")
            st.selectbox("Industry", list(INDUSTRY_FACTORS.keys()), key="industry")
            st.number_input("Loan Amount (OMR)", value=100000, key="amount")
            st.number_input("Tenor (months)", 6, 360, 36, key="tenor")
    
    if st.button("Calculate Pricing"):
        # Calculate results
        oibor = st.session_state.oibor_base + (st.session_state.fed_shock / 100)
        
        results = [{
            "Bucket": "Low",
            "Min Spread (bps)": 150,
            "Max Spread (bps)": 225,
            "Rate Range": f"{oibor + 1.50}% - {oibor + 2.25}%",
            "EMI (OMR)": f"{calculate_emi(st.session_state.amount, oibor + 1.75, st.session_state.tenor):,.2f}",
            "NII (OMR)": f"{st.session_state.amount * (oibor + 1.75 - st.session_state.cof) / 100:,.0f}",
            "NIM (%)": f"{oibor + 1.75 - st.session_state.cof:.2f}%"
        }]
        
        # Show results
        st.dataframe(pd.DataFrame(results))
        
        # Value in words demonstration
        st.markdown(f"**Loan amount in words:** {number_to_words(st.session_state.amount)} Omani Rials")
        st.markdown(f"**Interest rate in words:** {number_to_words(oibor + 1.75, True)}")

if __name__ == "__main__":
    main()
