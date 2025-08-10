import streamlit as st
import pandas as pd

# ===========================================================
# rt 360 Risk Adjusted Pricing Model for Corporate Lending
# Console / Python version – No GUI
# Author: [Your Name]
# Date: August 2025
# ===========================================================

# -------------------------
# DATA SETUP
# -------------------------

# Industries (excluding Retail banking, Merchant banking, Private banking)
industries = [
    "Energy",
    "Infrastructure",
    "Industrial",
    "Real Estate",
    "Tourism",
    "Healthcare",
    "Commercial and Trade Sectors",
    "Logistics",
    "Sustainable Cities",
    "Development Projects"
]

# Industry risk scores
industry_risk_weightage = {
    "Energy": 80,
    "Infrastructure": 65,
    "Industrial": 70,
    "Real Estate": 75,
    "Tourism": 85,
    "Healthcare": 55,
    "Commercial and Trade Sectors": 60,
    "Logistics": 68,
    "Sustainable Cities": 58,
    "Development Projects": 72
}

# Loan product and risk scores
loan_products = {
    "Working Capital Loan (Supply Chain Financing)": 55,
    "Working Capital Loan (Vendor Financing)": 60,
    "Working Capital Loan (Trade Financing)": 65,
    "Export Financing": 75,
    "Term Loan": 90,
    "Asset Backed Loan": 90
}

# Mala'a score buckets & risk weights
malaa_buckets = {
    "300-350": 100,
    "351-400": 95,
    "401-450": 90,
    "451-500": 85,
    "501-550": 80,
    "551-600": 70,
    "601-650": 60,
    "651-700": 55,
    "701-750": 50,
    "751-800": 45,
    "801-850": 40,
    "851-900": 35
}

# Utilisation % buckets (2% step increments)
utilisation_buckets = [f"{i}-{i+2}%" for i in range(0, 100, 2)]

# Interest rate & utilisation - bucket mapping
pricing_buckets = [
    {
        "Name": "Low",
        "Rate_Min": 5.00,
        "Rate_Max": 7.00,
        "Optimal_Utilisation": "0% - 30%",
        "Breakeven": "Within 12 months"
    },
    {
        "Name": "Medium",
        "Rate_Min": 7.01,
        "Rate_Max": 9.00,
        "Optimal_Utilisation": "31% - 70%",
        "Breakeven": "12 to 36 months"
    },
    {
        "Name": "High",
        "Rate_Min": 9.01,
        "Rate_Max": None,
        "Optimal_Utilisation": "> 70%",
        "Breakeven": "More than 36 months"
    }
]

# -------------------------
# USER INPUTS
# -------------------------

print("\n--- rt 360 Risk Adjusted Pricing Model for Corporate Lending ---\n")

# Select Industry
print("Available Industries:")
for i, ind in enumerate(industries, start=1):
    print(f"{i}. {ind}")
selected_industry = industries[int(input("\nSelect Industry (number): ")) - 1]

# Select Loan Product
print("\nAvailable Loan Products:")
for i, prod in enumerate(loan_products.keys(), start=1):
    print(f"{i}. {prod}")
selected_product = list(loan_products.keys())[int(input("\nSelect Loan Product (number): ")) - 1]

# Select Mala'a Score Bucket
print("\nAvailable Mala’a Score Buckets:")
for i, bucket in enumerate(malaa_buckets.keys(), start=1):
    print(f"{i}. {bucket}")
selected_malaa = list(malaa_buckets.keys())[int(input("\nSelect Mala’a Score (number): ")) - 1]

# Select Utilisation %
print("\nAvailable Utilisation % Buckets:")
for i, ub in enumerate(utilisation_buckets, start=1):
    print(f"{i}. {ub}")
selected_utilisation = utilisation_buckets[int(input("\nSelect Utilisation Bucket (number): ")) - 1]

# Working capital & sales ratio for eligible products
if selected_product not in ["Term Loan", "Asset Backed Loan"]:
    working_capital = float(input("\nEnter Working Capital (OMR): "))
    sales = float(input("Enter Sales (OMR): "))
    wc_ratio = (working_capital / sales) if sales > 0 else 0
else:
    wc_ratio = None

# -------------------------
# CALCULATIONS
# -------------------------

industry_score = industry_risk_weightage[selected_industry]
product_score = loan_products[selected_product]
malaa_score = malaa_buckets[selected_malaa]
utilisation_score = int(selected_utilisation.split("-")[1].replace("%", ""))

base_interest_rate = 5.00  # example fixed base rate

risk_adjustment = (industry_score + product_score + malaa_score + utilisation_score) / 100
wc_adjustment = (wc_ratio * 2) if wc_ratio is not None else 0  # multiplier for demo

final_interest_rate = base_interest_rate + risk_adjustment + wc_adjustment

# Determine pricing bucket
def match_bucket(rate):
    for b in pricing_buckets:
        if b["Rate_Max"] is None:  # High bucket, only min check
            if rate >= b["Rate_Min"]:
                return b
        elif b["Rate_Min"] <= rate <= b["Rate_Max"]:
            return b
    return None

bucket_info = match_bucket(final_interest_rate)

# -------------------------
# OUTPUT
# -------------------------

print("\n=================== Loan Pricing Summary ===================")
print(f"Industry: {selected_industry} (Risk Score: {industry_score})")
print(f"Loan Product: {selected_product} (Risk Score: {product_score})")
print(f"Mala’a Score Bucket: {selected_malaa} (Risk Score: {malaa_score})")
print(f"Utilisation % (Upper Bound): {utilisation_score}%")

if wc_ratio is not None:
    print(f"Working Capital: {working_capital:,.2f} OMR")
    print(f"Sales: {sales:,.2f} OMR")
    print(f"WC/Sales Ratio: {wc_ratio:.2%} (Adjustment: {wc_adjustment:.2f}%)")
else:
    print("WC/Sales Ratio: Not Applicable")

print(f"Base Interest Rate: {base_interest_rate:.2f}%")
print(f"Final Risk-Adjusted Interest Rate: {final_interest_rate:.2f}%")

if bucket_info:
    print(f"\nPricing Bucket: {bucket_info['Name']}")
    print(f"Interest Rate Range: {bucket_info['Rate_Min']}% - "
          f"{bucket_info['Rate_Max'] if bucket_info['Rate_Max'] else 'Above'}%")
    print(f"Optimal Utilisation Range


