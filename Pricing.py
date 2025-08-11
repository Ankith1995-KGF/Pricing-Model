import streamlit as st
import pandas as pd
import numpy as np

# 8. Number to Words (No External Library)
def num_to_words(n):
    units = ["","one","two","three","four","five","six","seven","eight","nine"]
    teens = ["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"]
    tens = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
    if n < 10:
        return units[n]
    elif n < 20:
        return teens[n-10]
    elif n < 100:
        return tens[n//10] + (" " + units[n%10] if n%10 != 0 else "")
    elif n < 1000:
        return units[n//100] + " hundred" + (" " + num_to_words(n%100) if n%100 != 0 else "")
    else:
        for div, word in [(10**9,"billion"),(10**6,"million"),(10**3,"thousand")]:
            if n >= div:
                return num_to_words(n//div) + " " + word + (" " + num_to_words(n%div) if n%div != 0 else "")

# 3. Risk Model Logic
product_factor = {
    "Asset Backed Loan": 1.35, "Term Loan": 1.20, "Export Finance": 1.10,
    "Vendor Finance": 0.95, "Supply Chain Finance": 0.90, "Trade Finance": 0.85,
    "Working Capital": 0.95
}
industry_factor = {
    "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
    "Hospitality": 1.25, "Retail": 1.15, "Manufacturing": 1.10,
    "Trading": 1.05, "Logistics": 1.00, "Oil & Gas": 0.95,
    "Healthcare": 0.90, "Utilities": 0.85, "Agriculture": 1.15
}
def malaa_factor(score):
    return max(min(1.45 - (score - 300) * (0.9 / 600), 1.45), 0.55)
def ltv_factor(ltv_pct):
    return max(min(0.55 + 0.0075 * ltv_pct, 1.50), 0.80)
def wcs_factor(wc, sales):
    if sales <= 0:
        return 1.20
    ratio = wc / sales
    return max(min(0.70 + 1.00 * min(ratio, 1.2), 1.70), 0.70)

# EMI calculation
def emi(loan_amount, annual_rate, months):
    if annual_rate == 0:
        return loan_amount / months
    monthly_rate = annual_rate / 12 / 100
    return loan_amount * monthly_rate * (1 + monthly_rate)**months / ((1 + monthly_rate)**months - 1)

# 1. Layout & UI
st.set_page_config(page_title="rt 360 Risk-Adjusted Pricing Model", layout="wide")

# Custom CSS for colors, borders, KPIs
st.markdown("""
<style>
h1 span.rt {color: blue; font-weight:900;}
h1 span.three60 {color: green; font-weight:900;}
.card {
    border: 4px solid #0d47a1;  /* thick blue border */
    padding: 15px;
    border-radius: 8px;
    background-color: white;
    margin-bottom: 15px;
}
.kpi-box {
    padding: 10px; border-radius: 5px; color: white; font-weight: bold; font-size: 1.1em; text-align:center;
}
.kpi-low {background-color: #4caf50;}       /* green */
.kpi-medium {background-color: #ff9800;}    /* orange */
.kpi-high {background-color: #f44336;}      /* red */
.sidebar .sidebar-content {
  background-color: #f0f2f6;
}
</style>
""", unsafe_allow_html=True)

# Title with "rt" blue and "360" green side-by-side
title_col1, title_col2 = st.columns([1,1])
with title_col1:
    st.markdown('<h1><span class="rt">rt</span> <span class="three60">360</span></h1>', unsafe_allow_html=True)
with title_col2:
    st.write("")

st.markdown("### Risk-adjusted pricing model for Corporate Lending")

# Sidebar with grouped inputs
with st.sidebar:
    st.header("Inputs")

    # Loan Details
    with st.expander("Loan Details", expanded=True):
        loan_quantum = st.number_input("Loan Quantum (OMR)", min_value=0.0, step=0.01, format="%.2f")
        st.caption(f"In words: {num_to_words(int(round(loan_quantum)))} Omani Rials")
        loan_tenor = st.slider("Loan Tenor (months)", min_value=6, max_value=360, value=12, step=1)
        loan_type = st.selectbox("Loan Type", [
            "Asset Backed Loan", "Term Loan", "Export Finance",
            "Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"
        ])
        # Determine if Fund-Based or Utilization-Based
        fund_based = loan_type in ["Asset Backed Loan", "Term Loan"]
        utilization_based = not fund_based

        if fund_based:
            ltv_pct = st.number_input("LTV (%)", min_value=0.0, max_value=100.0, step=0.1)
        else:
            wc_amt = st.number_input("Working Capital (OMR)", min_value=0.0, step=0.01, format="%.2f")
            st.caption(f"In words: {num_to_words(int(round(wc_amt)))} Omani Rials")
            sales_amt = st.number_input("Sales (OMR)", min_value=0.01, step=0.01, format="%.2f")  # avoid zero sales
            st.caption(f"In words: {num_to_words(int(round(sales_amt)))} Omani Rials")

    # Borrower Profile
    with st.expander("Borrower Profile", expanded=True):
        industry = st.selectbox("Industry", [
            "Oil & Gas", "Construction", "Real Estate", "Manufacturing",
            "Trading", "Logistics", "Healthcare", "Hospitality",
            "Retail", "Mining", "Utilities", "Agriculture"
        ])
        malaa_score = st.select_slider("Mala’a Score", options=list(range(300, 901, 50)), value=600)

    # Market & Bank Parameters
    with st.expander("Market & Bank Parameters", expanded=True):
        oibor = st.number_input("OIBOR (%)", value=4.1, min_value=0.0, max_value=20.0, step=0.01, format="%.2f")
        cost_of_funds = st.number_input("Cost of Funds (%)", value=5.0, min_value=0.0, max_value=20.0, step=0.01, format="%.2f")
        target_nim = st.number_input("Target NIM (%)", value=2.5, min_value=0.0, max_value=10.0, step=0.01, format="%.2f")
        fee_income = st.number_input("Fee Income (%)", value=0.4, min_value=0.0, max_value=5.0, step=0.01, format="%.2f")
        operating_expense = st.number_input("Operating Expense (%)", value=0.4, min_value=0.0, max_value=5.0, step=0.01, format="%.2f")
        upfront_cost = st.number_input("Upfront Cost (%)", value=0.5, min_value=0.0, max_value=5.0, step=0.01, format="%.2f")
        min_spread_floor = st.number_input("Min Spread Floor (bps)", value=125, min_value=0, max_value=1000, step=1)
        interest_rate_min = 5.0
        interest_rate_max = 10.0

    st.markdown("---")
    do_calc = st.button("Compute Pricing")

# 5. Risk model & pricing calculations - only on button press
if do_calc:

    # Calculate model factors
    pf = product_factor[loan_type]
    indf = industry_factor[industry]
    malaa = malaa_factor(malaa_score)

    if fund_based:
        lf = ltv_factor(ltv_pct)
        risk_score = pf * indf * malaa * lf
    else:
        wcsf = wcs_factor(wc_amt, sales_amt)
        risk_score = pf * indf * malaa * wcsf

    # Create buckets and multipliers
    buckets = ["Low", "Medium", "High"]
    bucket_mult = {"Low": 0.9, "Medium": 1.0, "High": 1.25}
    results = []

    for bucket in buckets:
        base_spread = min_spread_floor + (risk_score - 1) * 350
        spread_bps = base_spread * bucket_mult[bucket]

        # Add extra spread for high risk industries and products
        if indf >= 1.25:
            spread_bps += 50
        if loan_type == "Asset Backed Loan":
            spread_bps += 75
        elif loan_type in ["Term Loan", "Export Finance"]:
            spread_bps += 50

        # Compute rate and clamp
        rate = oibor + spread_bps / 100
        if rate < interest_rate_min:
            rate = interest_rate_min
        elif rate > interest_rate_max:
            rate = interest_rate_max

        # Credit cost capped 0.2%-1.8%
        credit_cost = 0.7 * risk_score
        credit_cost = max(min(credit_cost, 1.8), 0.2)

        # Fee income applicable only to WC, SCF, VF, Export Finance
        fee_pct = fee_income if loan_type in ["Working Capital", "Supply Chain Finance", "Vendor Finance", "Export Finance"] else 0.0

        # Calculate NIM
        nim = rate + fee_pct - (cost_of_funds + credit_cost + operating_expense)

        # If NIM < target, adjust spread and rate accordingly
        spread_adjustment = 0.0
        if nim < target_nim:
            spread_needed = (target_nim - nim) * 100  # bps needed approx
            spread_bps += spread_needed
            rate = oibor + spread_bps / 100
            if rate < interest_rate_min:
                rate = interest_rate_min
            elif rate > interest_rate_max:
                rate = interest_rate_max
            nim = target_nim

        rep_rate = rate  # Representative rate as midpoint (same here since one value)

        # EMI calculation (fund-based)
        emi_val = None
        if fund_based:
            emi_val = emi(loan_quantum, rate, loan_tenor)

        # Annual amounts
        annual_interest_income = loan_quantum * (rate / 100)
        annual_fee_income = loan_quantum * (fee_pct / 100)
        annual_funding_cost = loan_quantum * (cost_of_funds / 100)
        annual_credit_cost = loan_quantum * (credit_cost / 100)
        annual_opex = loan_quantum * (operating_expense / 100)
        nii = annual_interest_income + annual_fee_income - annual_funding_cost - annual_credit_cost - annual_opex

        # Breakeven Months
        breakeven_months = None
        if fund_based:
            monthly_ni = nii / 12
            if monthly_ni <= 0:
                breakeven_months = None
            else:
                breakeven_months = upfront_cost / 100 * loan_quantum / monthly_ni
        else:
            # Utilization-Based Loans: average exposure assumed as loan quantum * median utilization (assumed 75%)
            industry_median_utilization = 0.75
            avg_exposure = loan_quantum * industry_median_utilization
            monthly_net = avg_exposure * (nim / 100) / 12
            if monthly_net <= 0:
                breakeven_months = None
            else:
                breakeven_months = upfront_cost / 100 / (monthly_net / avg_exposure)

        results.append({
            "Bucket": bucket,
            "Spread_bps": round(spread_bps,2),
            "Rate_%": round(rate, 3),
            "Rep Rate%": round(rep_rate, 3),
            "EMI": round(emi_val, 2) if emi_val else None,
            "Annual Interest Income": round(annual_interest_income, 2),
            "Annual Fee Income": round(annual_fee_income, 2),
            "Annual Funding Cost": round(annual_funding_cost, 2),
            "Annual Credit Cost": round(annual_credit_cost, 2),
            "Annual Opex": round(annual_opex, 2),
            "NII": round(nii, 2),
            "NIM%": round(nim, 3),
            "Breakeven Months": round(breakeven_months, 1) if breakeven_months else None,
            "Risk Score": round(risk_score, 3),
            "Borrower Risk Label": malaa_score,
            "Industry Risk Factor": round(indf, 3),
            "Product Risk Factor": round(pf, 3),
            "Optimal Utilization%": round(industry_median_utilization*100,1) if utilization_based else None
        })
    
    # Display results in the main area with tabs
    tab1, tab2, tab3 = st.tabs(["Single Loan Pricing", "Loan Book Upload", "Assumptions & Methodology"])

    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Pricing Buckets")
        result_df = pd.DataFrame(results)
        # Color-coded KPI boxes for NIM%
        def nim_style(nim):
            if nim >= target_nim:
                return "kpi-low"
            elif nim >= target_nim * 0.9:
                return "kpi-medium"
            else:
                return "kpi-high"
        # Display each bucket metrics with colored NIM%
        for idx, row in result_df.iterrows():
            st.markdown(f"### Bucket: {row['Bucket']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Spread (bps)", f"{row['Spread_bps']}")
            col2.metric("Rate (%)", f"{row['Rate_%']}")
            col3.metric("NIM (%)", f"{row['NIM%']}")
            col4.metric("Breakeven Months", f"{row['Breakeven Months'] if row['Breakeven Months'] else 'N/A'}")

            # EMI if applicable
            if row["EMI"]:
                st.write(f"EMI: {row['EMI']:.2f} OMR")
            st.markdown("---")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.info("Batch pricing upload functionality will be implemented here in future releases.")

    with tab3:
        st.markdown("""
### Assumptions & Methodology

- Risk factors are derived based on product, industry, and borrower credit profile (Mala’a score).
- Fund-based loans use LTV factor; utilization-based loans use Working Capital to Sales ratio factor.
- Spread is calculated with base floor and extra premiums for high-risk industries and products.
- Interest rates are clamped between 5% and 10%.
- Fee income applies only to specific products.
- NIM calculated considering cost of funds, credit cost, operating expenses, and fee income.
- Credit cost is a function of risk score, capped between 0.2% and 1.8%.
- Breakeven months calculated differently for fund-based and utilization-based loans considering upfront costs.
- All numeric inputs show their amounts spelled out in words immediately below.
""")

else:
    st.info("Enter loan and borrower details in the sidebar and click 'Compute Pricing'")
