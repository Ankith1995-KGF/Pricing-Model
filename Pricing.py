import streamlit as st
import pandas as pd

st.title("Rt 360 Risk-Adjusted Pricing model for Corporate Lending ")

# ==== Input Section ====

# Existing portfolio metrics
existing_nim = st.number_input(
    "Existing Net Interest Margin (NIM %) from Loan Book",
    min_value=0.0,
    value=2.38,
    format="%.2f",
    help="Net Interest Margin (%) currently earned by the bank on its loan book.",
)

existing_avg_interest_rate = st.number_input(
    "Existing Average Interest Rate (%) on Loan Book",
    min_value=0.0,
    value=6.5,
    format="%.2f",
    help="Average interest rate (%) currently charged on existing loans.",
)

existing_fees_income_pct = st.number_input(
    "Existing Fees Income (% of Loan Amount)",
    min_value=0.0,
    value=0.4,
    format="%.2f",
    help="Fees income (%) earned as a percentage of loan amount on average.",
)

# New loan details
loan_amount = st.number_input(
    "New Loan Amount (OMR)", min_value=1000, value=50000, step=1000, format="%d"
)

tenor_years = st.number_input(
    "Loan Tenor (Years)", min_value=1, max_value=10, value=3, step=1
)

product_type = st.selectbox(
    "Product Type",
    [
        "Term Loan",
        "Trade Finance",
        "Syndicated Loan",
        "Invoice Discounting",
        "Working Capital Loan",
    ],
)

industry = st.selectbox(
    "Industry Sector",
    [
        "Energy",
        "Construction",
        "Manufacturing",
        "Trade",
        "Hospitality",
        "Utilities",
        "Transportation",
    ],
)

mala_score = st.slider(
    "Mala'a Credit Score", min_value=300, max_value=900, value=750, step=1
)

# Adjustable proposed fees income for this loan (transaction-based)
proposed_fees_income = st.number_input(
    "Proposed Fees Income (% of Loan Amount)",
    min_value=0.0,
    value=0.4,
    format="%.2f",
    help=(
        "Fees charged as a percentage of the loan amount (typically transaction-based, e.g., per LoC or bill discount). "
        "Used to offset risk and support profitability."
    ),
)

# ==== Constants / Parameters ====

# Interest rate ranges per product type (approximate Oman Arab Bank ranges)
interest_rate_ranges = {
    "Term Loan": (5.0, 8.0),
    "Trade Finance": (5.0, 7.0),
    "Syndicated Loan": (4.5, 7.5),
    "Invoice Discounting": (5.5, 8.0),
    "Working Capital Loan": (5.0, 8.0),
}

# Industry risk premiums (% added to base rate)
industry_risk_premiums = {
    "Energy": 0.5,
    "Construction": 2.0,
    "Manufacturing": 1.5,
    "Trade": 1.0,
    "Hospitality": 2.5,
    "Utilities": 0.7,
    "Transportation": 1.0,
}

# Mala'a score risk premium function
def mala_score_risk_premium(score):
    if score >= 751:
        return 0.5
    elif score >= 701:
        return 1.0
    elif score >= 651:
        return 1.5
    elif score >= 601:
        return 2.5
    else:
        return 4.0


# Tenor premium: 0.1% per year of tenure
def tenor_premium(years):
    return 0.1 * years


# ==== Calculation ====

base_min_rate, base_max_rate = interest_rate_ranges[product_type]
industry_premium = industry_risk_premiums[industry]
mala_premium = mala_score_risk_premium(mala_score)
tenor_prem = tenor_premium(tenor_years)

risk_adjusted_base_rate = base_min_rate + industry_premium + mala_premium + tenor_prem

# Cap the risk-adjusted base rate within the product bounds
adjusted_rate = min(max(risk_adjusted_base_rate, base_min_rate), base_max_rate)

# Approximate cost of funds from existing portfolio
cost_of_funds = existing_avg_interest_rate - existing_nim

# Breakeven interest rate (excluding fees income)
breakeven_interest_rate = cost_of_funds + existing_nim - proposed_fees_income

# Final pricing rate must be at least breakeven and within allowed range
final_pricing_rate = max(adjusted_rate, breakeven_interest_rate)

# Interest rate buckets for display (ranges within product min/max)
bucket_labels = ["Low Risk", "Medium Risk", "High Risk", "Very High Risk"]
bucket_ranges = [
    (base_min_rate, base_min_rate + 1.5),
    (base_min_rate + 1.5, base_max_rate - 1),
    (base_max_rate - 1, base_max_rate),
    (base_max_rate, base_max_rate + 1),
]


def fees_required_to_maintain_nim(interest_rate):
    return max(0, cost_of_funds + existing_nim - interest_rate)


# Populate bucket data including minimum utilization required
bucket_data = []
for label, (low, high) in zip(bucket_labels, bucket_ranges):
    avg_rate = (low + high) / 2
    fees_req = fees_required_to_maintain_nim(avg_rate)
    # Compute minimum utilization required to maintain NIM considering fee income comes from transactions:
    # (Interest Rate * Utilization) + Fees Income >= Cost of Funds + NIM
    numerator = cost_of_funds + existing_nim - fees_req
    denominator = avg_rate
    if denominator > 0:
        min_utilization = max(0.0, min(1.0, numerator / denominator)) * 100  # percentage
    else:
        min_utilization = None  # Undefined or infinite

    bucket_data.append(
        {
            "Risk Bucket": label,
            "Interest Rate Range (%)": f"{low:.2f} - {high:.2f}",
            "Average Interest Rate (%)": round(avg_rate, 2),
            "Fees Income Required (%)": round(fees_req, 2),
            "Minimum Utilization Required (%)": (
                f"{min_utilization:.2f}%" if min_utilization is not None else "N/A"
            ),
        }
    )

df_buckets = pd.DataFrame(bucket_data)

# ==== Display Results ====

st.header("Loan Pricing Summary")
st.write(f"**Industry Risk Premium:** {industry_premium:.2f}%")
st.write(f"**Mala'a Score Risk Premium:** {mala_premium:.2f}%")
st.write(f"**Tenor Premium ({tenor_years} years):** {tenor_prem:.2f}%")
st.write(
    f"**Base Interest Rate Range for {product_type}:** {base_min_rate:.2f}% - {base_max_rate:.2f}%"
)
st.write(f"**Initial Risk-Adjusted Interest Rate:** {risk_adjusted_base_rate:.2f}%")
st.write(f"**Adjusted (Capped) Interest Rate:** {adjusted_rate:.2f}%")
st.write(f"**Cost of Funds Approximation:** {cost_of_funds:.2f}%")
st.write(f"**Proposed Fees Income (%):** {proposed_fees_income:.2f}%")
st.write(f"**Breakeven Interest Rate (excl. fees):** {breakeven_interest_rate:.2f}%")
st.write(f"**Final Pricing Interest Rate:** {final_pricing_rate:.2f}%")

st.header("Interest Rate Buckets & Fees / Utilization Metrics")
st.dataframe(df_buckets)

# Calculate estimated total interest, fees, and monthly payments (simple interest)
total_interest = loan_amount * final_pricing_rate / 100 * tenor_years
total_fees = loan_amount * proposed_fees_income / 100
total_cost = loan_amount + total_interest + total_fees
monthly_payment = total_cost / (tenor_years * 12)

st.header("Estimated Payment Details (Simple Interest)")
st.write(f"**Total Interest Payable over {tenor_years} years:** OMR {total_interest:,.2f}")
st.write(f"**Total Fees Income:** OMR {total_fees:,.2f}")
st.write(f"**Total Cost of Loan:** OMR {total_cost:,.2f}")
st.write(f"**Estimated Monthly Payment (Principal + Interest + Fees):** OMR {monthly_payment:,.2f}")

st.caption(
    "Note: This model assumes simple interest with fees charged upfront or spread evenly over loan term. "
    "For detailed amortization, incorporate compounding effects."
)

# Additional: Minimum utilization required separately displayed when relevant product types chosen
if product_type in ["Trade Finance", "Working Capital Loan"]:
    st.subheader("Minimum Utilization Required for Breakeven (Specific to Loan Type)")

    numerator = cost_of_funds + existing_nim - proposed_fees_income
    denominator = final_pricing_rate

    if denominator > 0:
        min_utilization_pct = (numerator / denominator) * 100
        min_utilization_pct = min(max(min_utilization_pct, 0), 100)  # Clamp 0-100%
        st.write(
            f"For the selected loan parameters, the minimum utilization required to keep the loan "
            f"breakeven and maintain NIM is: **{min_utilization_pct:.2f}%**"
        )
        st.write(
            "This means the borrower should utilize at least this percentage of the sanctioned loan "
            "amount for the bank to avoid losses, considering fees income from transactions."
        )
    else:
        st.write(
            "The interest rate is too low relative to fees to calculate minimum utilization. "
            "Please adjust inputs."
        )

