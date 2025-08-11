import streamlit as st
import pandas as pd
import numpy as np

# --- Number to Words Function ---
def num_to_words(n):
    units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    
    if n < 10: return units[n]
    elif n < 20: return teens[n - 10]
    elif n < 100: return tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
    elif n < 1000: return units[n // 100] + " hundred" + (" " + num_to_words(n % 100) if n % 100 != 0 else "")
    else:
        for div, word in [(10**9, "billion"), (10**6, "million"), (10**3, "thousand")]:
            if n >= div:
                return num_to_words(n // div) + " " + word + (" " + num_to_words(n % div) if n % div != 0 else "")

# --- Risk Model Functions ---
def malaa_factor(score):
    return max(min(1.45 - (score - 300) * (0.9 / 600), 1.45), 0.55)

def ltv_factor(ltv_pct):
    return max(min(0.55 + 0.0075 * ltv_pct, 1.50), 0.80)

def wcs_factor(wc, sales):
    if sales <= 0:
        return 1.20
    ratio = wc / sales
    return max(min(0.70 + 1.00 * min(ratio, 1.2), 1.70), 0.70)

# --- Spread Calculation ---
def calculate_spread(risk_score, product, industry):
    base_spread = 125 + (risk_score - 1) * 350
    if industry_factor[industry] >= 1.25:
        base_spread += 50
    if product == "Asset Backed Loan":
        base_spread += 75
    elif product in ["Term Loan", "Export Finance"]:
        base_spread += 50
    return base_spread

# --- Main Application ---
def main():
    st.set_page_config(page_title="rt 360 Risk-Adjusted Pricing Model", layout="wide")

    # Header
    st.markdown("""
    <h1 style="color:blue; display:inline;">rt</h1>
    <h1 style="color:green; display:inline;">360</h1>
    <h3>Risk-adjusted pricing model for Corporate Lending</h3>
    """, unsafe_allow_html=True)

    # Sidebar Inputs
    with st.sidebar:
        st.header("Loan Details")
        loan_amount = st.number_input("Loan Quantum (OMR)", min_value=0.0, value=1000000.0)
        st.caption(f"In words: {num_to_words(int(loan_amount))} Omani Rials")
        
        loan_tenor = st.number_input("Loan Tenor (months)", min_value=6, max_value=360, value=12)
        loan_type = st.selectbox("Loan Type", ["Asset Backed Loan", "Term Loan", "Export Finance", 
                                                "Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"])
        
        if loan_type in ["Working Capital", "Supply Chain Finance", "Vendor Finance", "Trade Finance"]:
            working_capital = st.number_input("Working Capital (OMR)", min_value=0.0, value=50000.0)
            st.caption(f"In words: {num_to_words(int(working_capital))} Omani Rials")
            sales = st.number_input("Sales (OMR)", min_value=0.0, value=100000.0)
            st.caption(f"In words: {num_to_words(int(sales))} Omani Rials")
        else:
            ltv_pct = st.number_input("LTV (%)", min_value=0.0, max_value=100.0, value=80.0)

        st.header("Borrower Profile")
        industry = st.selectbox("Industry", ["Oil & Gas", "Construction", "Real Estate", "Manufacturing", 
                                               "Trading", "Logistics", "Healthcare", "Hospitality", 
                                               "Retail", "Mining", "Utilities", "Agriculture"])
        malaa_score = st.selectbox("Mala’a Score", list(range(300, 901, 50)))

        st.header("Market & Bank Parameters")
        oibor = st.number_input("OIBOR (%)", value=4.1)
        cost_of_funds = st.number_input("Cost of Funds (%)", value=5.0)
        target_nim = st.number_input("Target NIM (%)", value=2.5)
        fee_income = st.number_input("Fee Income (%)", value=0.4)
        operating_expense = st.number_input("Operating Expense (%)", value=0.4)
        upfront_cost = st.number_input("Upfront Cost (%)", value=0.5)
        min_spread_floor = st.number_input("Min Spread Floor (bps)", value=125)
        interest_rate_clamp_min = 5.0
        interest_rate_clamp_max = 10.0

        if st.button("Compute Pricing"):
            # Risk Model Logic
            product_factor = {
                "Asset Backed Loan": 1.35, "Term Loan": 1.20, "Export Finance": 1.10,
                "Vendor Finance": 0.95, "Supply Chain Finance": 0.90, "Trade Finance": 0.85,
                "Working Capital": 0.95
            }[loan_type]

            industry_factor = {
                "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
                "Hospitality": 1.25, "Retail": 1.15, "Manufacturing": 1.10,
                "Trading": 1.05, "Logistics": 1.00, "Oil & Gas": 0.95,
                "Healthcare": 0.90, "Utilities": 0.85, "Agriculture": 1.15
            }[industry]

            malaa = malaa_factor(malaa_score)
            ltv = ltv_factor(ltv_pct) if loan_type != "Working Capital" else 1.0
            wcs = wcs_factor(working_capital, sales) if loan_type in ["Working Capital", "Supply Chain Finance", "Vendor Finance", "Trade Finance"] else 1.0

            risk_score = product_factor * industry_factor * malaa * (ltv if loan_type != "Working Capital" else wcs)

            # Spread Calculation
            spread_bps = calculate_spread(risk_score, loan_type, industry)
            rate = oibor + (spread_bps / 100)
            rate = max(min(rate, interest_rate_clamp_max), interest_rate_clamp_min)

            # NIM Calculation
            credit_cost = max(min(0.7 * risk_score, 1.8), 0.2)
            nim = rate + fee_income - (cost_of_funds + credit_cost + operating_expense)

            # Output Table
            st.subheader("Pricing Results")
            st.write(f"**Spread (bps):** {spread_bps}")
            st.write(f"**Rate (%):** {rate:.2f}")
            st.write(f"**NIM (%):** {nim:.2f}")
            st.write(f"**Risk Score:** {risk_score:.2f}")

if __name__ == "__main__":
    main()
