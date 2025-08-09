import streamlit as st
import pandas as pd

# Function to calculate interest rate and utilization
def calculate_pricing(loan_amount, industry, mala_score, tenor, product_type, fees_income, existing_interest_income):
    # Define interest rate buckets
    interest_rate_buckets = {
        '5%': 0.05,
        '6%': 0.06,
        '7%': 0.07,
        '8%': 0.08
    }
    
    # Placeholder for scoring mechanism
    industry_scores = {
        'Industry A': 1.0,
        'Industry B': 0.8,
        'Industry C': 0.6,
        # Add more industries and their scores
    }
    
    # Calculate risk weightage based on inputs
    risk_weightage = industry_scores.get(industry, 0.5) * mala_score / 100  # Example calculation
    
    # Calculate required interest income to maintain NIM
    required_interest_income = existing_interest_income * (1 + risk_weightage)
    
    # Calculate interest rate based on risk
    interest_rate = None
    for bucket, rate in interest_rate_buckets.items():
        if required_interest_income <= loan_amount * rate:
            interest_rate = rate
            break
    
    # Calculate minimum utilization for working capital or trade finance loans
    min_utilization = None
    if product_type in ['Working Capital Loan', 'Trade Finance Loan']:
        min_utilization = required_interest_income / interest_rate
    
    return interest_rate, min_utilization

# Streamlit UI
st.title("rt360 Risk-adjusted Pricing Model for Corporate Lending")

# User inputs
loan_amount = st.number_input("Enter Loan Amount:", min_value=0.0)
industry = st.selectbox("Select Industry:", ['Industry A', 'Industry B', 'Industry C'])
mala_score = st.number_input("Enter Mala'a Score (0-100):", min_value=0, max_value=100)
tenor = st.number_input("Enter Tenor (in months):", min_value=1)
product_type = st.selectbox("Select Product Type:", ['Working Capital Loan', 'Trade Finance Loan', 'Other'])
fees_income = st.number_input("Enter Fees Income:", min_value=0.0)
existing_interest_income = st.number_input("Enter Existing Interest Income:", min_value=0.0)

# Calculate pricing
if st.button("Calculate Pricing"):
    interest_rate, min_utilization = calculate_pricing(loan_amount, industry, mala_score, tenor, product_type, fees_income, existing_interest_income)
    
    # Display results
    st.subheader("Pricing Results")
    if interest_rate:
        st.write(f"Recommended Interest Rate: {interest_rate * 100:.2f}%")
    else:
        st.write("No suitable interest rate found for the given parameters.")
    
    if min_utilization is not None:
        st.write(f"Minimum Utilization Required for Breakeven: {min_utilization:.2f}")
    else:
        st.write("No minimum utilization required for this product type.")

# Run the app with: streamlit run your_script.py

