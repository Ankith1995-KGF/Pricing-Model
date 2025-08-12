import streamlit as st
import pandas as pd
import numpy as np

# Set page configuration
st.set_page_config(page_title="rt 360 risk-adjusted pricing model", page_icon="💠", layout="wide")

# Internal function to convert numbers to words
def num_to_words(n: int) -> str:
    units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    def chunk(x):
        if x == 0: return ""
        if x < 10: return units[x]
        if x < 20: return teens[x - 10]
        if x < 100: return tens[x // 10] + ("" if x % 10 == 0 else " " + units[x % 10])
        if x < 1000: return units[x // 100] + " hundred" + ("" if x % 100 == 0 else " " + chunk(x % 100))
        return ""

    if n == 0: return "zero"
    parts = []
    for div, word in [(10**9, "billion"), (10**6, "million"), (10**3, "thousand")]:
        if n >= div:
            parts.append(chunk(n // div) + " " + word)
            n %= div
    if n > 0: parts.append(chunk(n))
    s = " ".join(parts)
    return s

# Caching heavy calculations
@st.cache_data
def calculate_pricing(...):  # Add parameters as needed
    # Implement the pricing calculations here
    pass

# Sidebar
st.sidebar.header("Market & Bank Parameters")
oibor_pct_base = st.sidebar.number_input("OIBOR Base (%)", value=4.1)
fed_shock_bps = st.sidebar.slider("Fed Shock (bps)", -300, 300, 0)
cost_of_funds_pct = st.sidebar.number_input("Cost of Funds (%)", value=5.0)
target_nim_pct = st.sidebar.number_input("Target NIM (%)", value=2.5)
fees_income_pct_default = st.sidebar.number_input("Fees Income (%)", value=0.4)
opex_pct = st.sidebar.number_input("Opex (%)", value=0.40)
upfront_cost_pct = st.sidebar.number_input("Upfront Cost (%)", value=0.50)

# Borrower & Product
st.sidebar.header("Borrower & Product")
product = st.sidebar.selectbox("Product", ["Asset Backed Loan", "Term Loan", "Export Finance", "Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"])
industry = st.sidebar.selectbox("Industry", ["Oil & Gas", "Construction", "Real Estate", "Manufacturing", "Trading", "Logistics", "Healthcare", "Hospitality", "Retail", "Mining", "Utilities", "Agriculture"])
malaa_score = st.sidebar.slider("Mala’a Score", 300, 900, 300, 50)

# Loan Details
st.sidebar.header("Loan Details")
tenor_months = st.sidebar.number_input("Tenor (months)", 6, 360, 12)
loan_quantum_omr = st.sidebar.number_input("Loan Quantum (OMR)", 0)
st.caption(f"In words: {num_to_words(int(loan_quantum_omr))} Omani Rials")

# Upload Loan Book
st.sidebar.header("Upload Loan Book (CSV)")
uploaded_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
if uploaded_file is not None:
    loan_book_df = pd.read_csv(uploaded_file)
    st.write(loan_book_df)

# Compute Pricing Button
if st.sidebar.button("Compute Pricing"):
    # Call the pricing calculation function
    pricing_results = calculate_pricing(...)
    st.write(pricing_results)

# Main area with tabs
tab1, tab2, tab3, tab4 = st.tabs(["Single Loan Pricing", "Loan Book Pricing", "Concentration & Provisions", "Assumptions"])

with tab1:
    st.header("Single Loan Pricing")
    # Display single loan pricing results here

with tab2:
    st.header("Loan Book Pricing")
    # Display loan book pricing results here

with tab3:
    st.header("Concentration & Provisions")
    # Display concentration and provisions results here

with tab4:
    st.header("Assumptions")
    # Display assumptions here

# Add additional calculations and outputs as needed
