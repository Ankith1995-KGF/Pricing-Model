import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from io import StringIO

# --- APP CONFIGURATION ---
st.set_page_config(
    page_title="rt 360 risk-adjusted pricing model",
    page_icon="💠",
    layout="wide"
)

# --- GLOBAL CONSTANTS ---
PRODUCT_TYPES = [
    "Asset Backed Loan", "Term Loan", "Export Finance", "Working Capital",
    "Trade Finance", "Supply Chain Finance", "Vendor Finance"
]

INDUSTRIES = [
    "Oil & Gas", "Construction", "Real Estate", "Manufacturing",
    "Trading", "Logistics", "Healthcare", "Hospitality", "Retail",
    "Mining", "Utilities", "Agriculture"
]

# --- STYLING ---
st.markdown("""
<style>
    .header {
        display: flex;
        flex-direction: column;
        margin-bottom: 2rem;
    }
    .rt { color: #1e88e5; font-weight: bold; }
    .three60 { color: #4caf50; font-weight: bold; }
    .subtitle { color: #666; font-size: 1.1rem; margin-top: -1rem; }
    .card {
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 2px solid #1e88e5;
    }
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .kpi {
        background-color: #f8f9fa;
        border-left: 4px solid #1e88e5;
        padding: 1rem;
        border-radius: 4px;
    }
    .warning { color: #ff5722; font-weight: bold; }
    .success { color: #4caf50; font-weight: bold; }
    .stNumberInput, .stSelectbox, .stSlider { margin-bottom: 1rem; }
    .tab-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# Utility functions (your original calc logic intact)
# --------------------------------------------------
def num_to_words(n: int) -> str:
    """Convert integer to Omani Rials in words"""
    if not isinstance(n, (int, float)) or n < 0:
        return ""
    n = int(n)
    if n == 0:
        return "zero Omani Rials"

    units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = [
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
        "seventeen", "eighteen", "nineteen"
    ]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    def convert_chunk(x: int) -> str:
        if x < 10:
            return units[x]
        if x < 20:
            return teens[x - 10]
        if x < 100:
            return tens[x // 10] + ("-" + units[x % 10] if x % 10 != 0 else "")
        if x < 1000:
            return units[x // 100] + " hundred" + (" and " + convert_chunk(x % 100) if x % 100 != 0 else "")
        return ""

    magnitude_words = []
    scales = [(10**9, "billion"), (10**6, "million"), (10**3, "thousand")]

    for scale, name in scales:
        if n >= scale:
            magnitude_words.append(f"{convert_chunk(n // scale)} {name}")
            n %= scale

    if n > 0:
        magnitude_words.append(convert_chunk(n))

    return " ".join(magnitude_words) + " Omani Rials"

def malaa_risk_label(score: int) -> str:
    if score < 500:
        return "High"
    elif score < 650:
        return "Med-High"
    elif score < 750:
        return "Medium"
    return "Low"

# --------------------------------------------------
# (Keep your complete calculation functions here 
# unchanged — calculate_risk_factors, calculate_pd_lgd, 
# calculate_loan_pricing, calculate_repayment_schedule,
# calculate_emi, generate_results_dataframe, etc.)
# --------------------------------------------------

def render_header():
    st.markdown("""
    <div class="header">
        <h1><span class="rt">rt</span><span class="three60">360</span></h1>
        <p class="subtitle">risk-adjusted pricing model for Corporate Lending</p>
    </div>
    """, unsafe_allow_html=True)

# --------------------------------------------------
# Corrected render_assumptions_tab
# --------------------------------------------------
def render_assumptions_tab():
    st.header("Model Assumptions")

    with st.expander("Risk Factors"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Product Risk Factors")
            st.table(pd.DataFrame.from_dict({
                "Asset Backed Loan": 1.35,
                "Term Loan": 1.20, 
                "Export Finance": 1.10,
                "Working Capital": 0.95,
                "Trade Finance": 0.85,
                "Supply Chain Finance": 0.90,
                "Vendor Finance": 0.95
            }, orient="index", columns=["Factor"]))
        with col2:
            st.subheader("Industry Risk Factors")
            st.table(pd.DataFrame.from_dict({
                "Construction": 1.40, 
                "Real Estate": 1.30,
                "Mining": 1.30, 
                "Hospitality": 1.25,
                "Retail": 1.15, 
                "Manufacturing": 1.10,
                "Trading": 1.05,
                "Logistics": 1.00,
                "Oil & Gas": 0.95,
                "Healthcare": 0.90,
                "Utilities": 0.85, 
                "Agriculture": 1.15
            }, orient="index", columns=["Factor"]))

    with st.expander("Pricing Parameters"):
        st.markdown("""
        - **Base Spread Curve:** 75 bps + 350 × (Risk - 1)
        - **Bucket Multipliers:** Low (0.9x), Medium (1.0x), High (1.25x)
        - **Spread Floors:** Low (150 bps), Medium (225 bps), High (325 bps)
        - **Adders:**
          - Product: ABL (+125 bps), Term/Export (+75 bps)
          - Mala'a Score: High (+175), Med-High (+125), Medium (+75)
        """)

    with st.expander("Methodology"):
        st.markdown("""
        1. **Composite Risk Score:**
           - Product × Industry × Mala'a × (LTV or WC/Sales factor)
           - Clipped to 0.4-3.5 range

        2. **PD Calculation:** Piecewise interpolation
           - 0.4 → 0.3%, 1.0 → 1.0%, 2.0 → 3.0%, 3.5 → 6.0%
           - Stage multiplier: Stage 2 (×2.5), Stage 3 (×6.0)

        3. **LGD Calculation:**
           - Base: ABL=32%, Term=38%, Export=35%, Others=30%
           - LTV adjustment: +0.25% per LTV% >50%
        """)

    with st.expander("NIM Calculation"):
        st.markdown("""
        - **NIM** = Representative Rate + Fees − (Cost of Funds + Provision + Opex)
        - Target NIM is compared against calculated NIM to flag performance
        """)

# --------------------------------------------------
# MAIN ENTRY
# --------------------------------------------------
def main():
    render_header()
    # Render all sections here
    render_assumptions_tab()
    # You would also call render_market_parameters(), render_loan_parameters()
    # and other processing functions you have, then show results.

if __name__ == "__main__":
    main()
