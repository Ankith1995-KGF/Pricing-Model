import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

# -------------------------------
# APP CONFIGURATION
# -------------------------------
st.set_page_config(
    page_title="rt 360 risk-adjusted pricing model",
    page_icon="💠",
    layout="wide"
)

# -------------------------------
# CONSTANTS
# -------------------------------
PRODUCT_TYPES = [
    "Asset Backed Loan", "Term Loan", "Export Finance", "Working Capital",
    "Trade Finance", "Supply Chain Finance", "Vendor Finance"
]

INDUSTRIES = [
    "Oil & Gas", "Construction", "Real Estate", "Manufacturing",
    "Trading", "Logistics", "Healthcare", "Hospitality", "Retail",
    "Mining", "Utilities", "Agriculture"
]

# -------------------------------
# CSS Styling
# -------------------------------
st.markdown("""
<style>
    .header { display: flex; flex-direction: column; margin-bottom: 2rem; }
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
    .kpi-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }
    .warning { color: #ff5722; font-weight: bold; }
    .success { color: #4caf50; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# Utility Functions
# -------------------------------
def num_to_words(n: int) -> str:
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

    words = []
    for scale, name in [(10**9, "billion"), (10**6, "million"), (10**3, "thousand")]:
        if n >= scale:
            words.append(f"{convert_chunk(n // scale)} {name}")
            n %= scale
    if n > 0:
        words.append(convert_chunk(n))
    return " ".join(words) + " Omani Rials"


def malaa_risk_label(score: int) -> str:
    if score < 500:
        return "High"
    elif score < 650:
        return "Med-High"
    elif score < 750:
        return "Medium"
    return "Low"


# -------------------------------
# Core Calculation Functions
# -------------------------------
def calculate_risk_factors(product: str, industry: str, malaa_score: int,
    ltv: Optional[float] = None, working_capital: Optional[float] = None,
    sales: Optional[float] = None) -> Tuple[float, float, float]:

    product_factors = {
        "Asset Backed Loan": 1.35,"Term Loan": 1.20,"Export Finance": 1.10,
        "Working Capital": 0.95,"Trade Finance": 0.85,"Supply Chain Finance": 0.90,"Vendor Finance": 0.95
    }
    industry_factors = {
        "Construction": 1.40,"Real Estate": 1.30,"Mining": 1.30,"Hospitality": 1.25,
        "Retail": 1.15,"Manufacturing": 1.10,"Trading": 1.05,"Logistics": 1.00,
        "Oil & Gas": 0.95,"Healthcare": 0.90,"Utilities": 0.85,"Agriculture": 1.15
    }

    product_factor = product_factors.get(product, 1.0)
    industry_factor = industry_factors.get(industry, 1.0)
    malaa_factor = np.clip(1.45 - (malaa_score - 300) * (0.90 / 600), 0.55, 1.45)

    if ltv is not None and product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = np.clip(0.55 + 0.0075 * ltv, 0.80, 1.50)
        risk_base = np.clip(product_factor * industry_factor * malaa_factor * ltv_factor, 0.4, 3.5)
    else:
        wc_ratio = (working_capital / sales) if sales and sales > 0 else 0
        wcs_factor = np.clip(0.70 + 1.00 * min(wc_ratio, 1.2), 0.70, 1.70)
        risk_base = np.clip(product_factor * industry_factor * malaa_factor * wcs_factor, 0.4, 3.5)

    return risk_base, product_factor, industry_factor


def calculate_pd_lgd(risk_score: float, product: str, ltv: Optional[float], stage: int) -> Tuple[float, float]:
    xs = np.array([0.4, 1.0, 2.0, 3.5])
    ys = np.array([0.3, 1.0, 3.0, 6.0])
    pd = float(np.interp(risk_score, xs, ys))
    stage_multipliers = {1: 1.0, 2: 2.5, 3: 6.0}
    pd *= stage_multipliers.get(stage, 1.0)
    pd = np.clip(pd, 0.1, 60.0)

    base_lgd = {
        "Asset Backed Loan": 32, "Term Loan": 38, "Export Finance": 35
    }.get(product, 30)

    ltv_adj = max(0.0, (ltv - 50.0) * 0.25) if ltv is not None else 8.0
    lgd = np.clip(base_lgd + ltv_adj, 25.0, 70.0)

    return pd, lgd


def calculate_loan_pricing(risk_score: float, malaa_label: str, oibor_pct: float,
                            cof_pct: float, opex_pct: float, fees_pct: float, bucket: str, product: str) -> Dict[str, float]:
    bucket_multipliers = {"Low": 0.90, "Medium": 1.00, "High": 1.25}
    bucket_bands = {"Low": 60, "Medium": 90, "High": 140}
    bucket_floors = {"Low": 150, "Medium": 225, "High": 325}

    risk_b = np.clip(risk_score * bucket_multipliers[bucket], 0.4, 3.5)
    raw_spread_bps = 75 + 350 * (risk_b - 1)

    malaa_adders = {"High": 175, "Med-High": 125, "Medium": 75, "Low": 0}
    malaa_adder = malaa_adders[malaa_label]

    product_adder = 125 if "Asset Backed" in product else 75 if product in ["Term Loan", "Export Finance"] else 0

    center_spread = max(
        bucket_floors[bucket],
        raw_spread_bps,
        125,
        raw_spread_bps + malaa_adder + product_adder
    )

    spread_min = center_spread - bucket_bands[bucket]
    spread_max = center_spread + bucket_bands[bucket]
    rate_min = np.clip(oibor_pct + spread_min / 100, 5.0, 10.0)
    rate_max = np.clip(oibor_pct + spread_max / 100, 5.0, 10.0)
    rep_rate = (rate_min + rate_max) / 2

    return {
        "spread_min": spread_min,
        "spread_max": spread_max,
        "rate_min": rate_min,
        "rate_max": rate_max,
        "rep_rate": rep_rate,
        "oibor_pct": oibor_pct
    }


def calculate_emi(principal: float, rate: float, tenor: int) -> float:
    monthly_rate = rate / 100 / 12
    if monthly_rate == 0:
        return principal / tenor
    return principal * monthly_rate * (1 + monthly_rate) ** tenor / ((1 + monthly_rate) ** tenor - 1)


def calculate_repayment_schedule(principal: float, rate: float, tenor: int, cof_pct: float,
                                 prov_pct: float, opex_pct: float, upfront_cost_pct: float):
    monthly_rate = rate / 100 / 12
    emi = calculate_emi(principal, rate, tenor)
    balance = principal
    schedule = []
    cumulative_net = 0
    be_periods = None

    for month in range(1, tenor + 1):
        interest_payment = balance * monthly_rate
        principal_payment = emi - interest_payment
        provision_payment = balance * prov_pct / 100 / 12
        funding_cost = balance * cof_pct / 100 / 12
        operating_cost = balance * opex_pct / 100 / 12

        net_income = interest_payment - (funding_cost + provision_payment + operating_cost)
        cumulative_net += net_income

        if be_periods is None and cumulative_net >= (principal * upfront_cost_pct / 100):
            be_periods = month

        schedule.append({
            "Month": month,
            "Beginning_Balance": balance,
            "Principal": principal_payment,
            "Interest": interest_payment,
            "Provision": provision_payment,
            "Funding_Cost": funding_cost,
            "Opex": operating_cost,
            "Net_Income": net_income,
            "Cumulative_Net": cumulative_net
        })

        balance -= principal_payment
        if balance <= 0:
            break

    first_year = schedule[:12]
    avg_balance = sum(p["Beginning_Balance"] for p in first_year) / len(first_year)
    total_net = sum(p["Net_Income"] for p in first_year)
    nim = (total_net / avg_balance) * 100 if avg_balance > 0 else 0

    return emi, total_net, nim, schedule, be_periods or tenor


# -------------------------------
# UI RENDER FUNCTIONS
# -------------------------------
def render_header():
    st.markdown("""
    <div class="header">
        <h1><span class="rt">rt</span><span class="three60">360</span></h1>
        <p class="subtitle">risk-adjusted pricing model for Corporate Lending</p>
    </div>
    """, unsafe_allow_html=True)


def render_assumptions_tab():
    st.header("Model Assumptions")

    with st.expander("Risk Factors"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Product Risk Factors")
            st.table(pd.DataFrame.from_dict({
                "Asset Backed Loan": 1.35, "Term Loan": 1.20, "Export Finance": 1.10,
                "Working Capital": 0.95, "Trade Finance": 0.85,
                "Supply Chain Finance": 0.90, "Vendor Finance": 0.95
            }, orient='index', columns=['Factor']))
        with col2:
            st.subheader("Industry Risk Factors")
            st.table(pd.DataFrame.from_dict({
                "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
                "Hospitality": 1.25, "Retail": 1.15, "Manufacturing": 1.10,
                "Trading": 1.05, "Logistics": 1.00, "Oil & Gas": 0.95,
                "Healthcare": 0.90, "Utilities": 0.85, "Agriculture": 1.15
            }, orient='index', columns=['Factor']))

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
           - Clipped to 0.4–3.5 range

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
        - Target NIM compared to calculated NIM to flag performance
        """)
def render_market_parameters() -> Dict[str, float]:
    st.sidebar.header("Market & Bank Parameters")
    col1, col2 = st.sidebar.columns(2)

    with col1:
        oibor_base = st.number_input("OIBOR Base (%)", value=4.1, min_value=0.0, max_value=20.0, step=0.1)
        fed_shock = st.slider("Fed Shock (bps)", -300, 300, 0)
        cof_pct = st.number_input("Cost of Funds (%)", value=5.0, min_value=0.0, max_value=20.0, step=0.1)

    with col2:
        target_nim = st.number_input("Target NIM (%)", value=2.5, min_value=0.0, max_value=10.0, step=0.1)
        opex_pct = st.number_input("Opex (%)", value=0.40, min_value=0.0, max_value=5.0, step=0.05)
        upfront_cost = st.number_input("Upfront Cost (%)", value=0.50, min_value=0.0, max_value=5.0, step=0.05)

    return {
        "oibor_pct": oibor_base + (fed_shock / 100),
        "cof_pct": cof_pct,
        "target_nim": target_nim,
        "opex_pct": opex_pct,
        "upfront_cost": upfront_cost
    }


def render_loan_parameters() -> Dict:
    st.sidebar.header("Borrower & Product")
    product = st.sidebar.selectbox("Product Type", PRODUCT_TYPES, index=0)
    industry = st.sidebar.selectbox("Industry", INDUSTRIES, index=0)
    malaa_score = st.sidebar.slider("Mala'a Score", 300, 900, 650, 50)
    stage = st.sidebar.selectbox("Stage", [1, 2, 3], index=0)
    st.sidebar.header("Loan Details")
    tenor = st.sidebar.number_input("Tenor (months)", 6, 360, 36)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        loan_amount = st.number_input("Loan Amount (OMR)", min_value=0.0, value=100000.0, step=1000.0)
        st.caption(f"**In words:** {num_to_words(int(loan_amount))}")

    with col2:
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.number_input("LTV (%)", 0, 100, 70)
            working_capital = None
            sales = None
        else:
            ltv = None
            working_capital = st.number_input("Working Capital (OMR)", min_value=0.0, value=50000.0, step=1000.0)
            sales = st.number_input("Annual Sales (OMR)", min_value=0.0, value=200000.0, step=1000.0)
            st.caption(f"**Sales in words:** {num_to_words(int(sales))}")

    return {
        "product": product, "industry": industry, "malaa_score": malaa_score,
        "stage": stage, "tenor": tenor, "amount": loan_amount, "ltv": ltv,
        "working_capital": working_capital, "sales": sales
    }


def render_loan_book_upload() -> Optional[pd.DataFrame]:
    st.sidebar.header("Loan Book Processing")
    uploaded_file = st.sidebar.file_uploader("Upload Loan Book (CSV)", type=["csv"])
    template = pd.DataFrame(columns=[
        "loan_id", "product", "industry", "malaa_score", "tenor_months",
        "loan_quantum_omr", "limit_omr", "working_capital_omr", "sales_omr",
        "median_utilization", "ltv_pct", "stage", "pd_pct", "lgd_pct",
        "provision_rate_pct", "fees_pct", "opex_pct"
    ])
    st.sidebar.download_button(
        "Download Template",
        data=template.to_csv(index=False),
        file_name="loan_book_template.csv",
        mime="text/csv"
    )

    if uploaded_file is not None:
        try:
            return pd.read_csv(uploaded_file)
        except Exception as e:
            st.sidebar.error(f"Error reading file: {e}")
    return None


def display_pricing_results(results_df: pd.DataFrame):
    st.subheader("Pricing Results")
    for _, row in results_df.iterrows():
        with st.expander(f"{row['Bucket']} Bucket Details", expanded=row['Bucket'] == "Medium"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Representative Rate", f"{row['rep_rate']:.2f}%")
                st.metric("Minimum Rate", f"{row['rate_min']:.2f}%")
                st.metric("Maximum Rate", f"{row['rate_max']:.2f}%")

            with col2:
                st.metric("Spread over OIBOR (Min)", f"{row['spread_min']} bps")
                st.metric("Spread over OIBOR (Rep)", f"{(row['rep_rate'] - row['oibor_pct']) * 100:.0f} bps")
                st.metric("Spread over OIBOR (Max)", f"{row['spread_max']} bps")

            with col3:
                st.metric("Probability of Default", f"{row['PD']:.2f}%")
                st.metric("Loss Given Default", f"{row['LGD']:.2f}%")
                st.metric("Annual Provision", f"{row['Provision_Rate']*100:.2f}%")


def generate_results_dataframe(loan_params: Dict, market_params: Dict, pricing_results: List) -> pd.DataFrame:
    results = []
    buckets = ["Low", "Medium", "High"]

    for i, bucket in enumerate(buckets):
        pricing = pricing_results[i]
        wc_ratio = (loan_params['working_capital'] / loan_params['sales']) if loan_params['working_capital'] and loan_params['sales'] else None
        fees_pct = 0.4 if loan_params['product'] in ["Supply Chain Finance", "Vendor Finance", "Working Capital", "Export Finance"] else 0.0
        nim = pricing['rep_rate'] + fees_pct - (
            market_params['cof_pct'] + pricing['Provision_Rate']*100 + market_params['opex_pct']
        )

        results.append({
            "Bucket": bucket,
            "Risk_Score": pricing['risk_score'],
            "Product_Factor": pricing['product_factor'],
            "Industry_Factor": pricing['industry_factor'],
            "Borrower_Risk": malaa_risk_label(loan_params['malaa_score']),
            "tenor": loan_params['tenor'],
            "amount": loan_params['amount'],
            "ltv": loan_params.get('ltv'),
            "wc_ratio": wc_ratio,
            "rate_min": pricing['rate_min'],
            "rate_max": pricing['rate_max'],
            "rep_rate": pricing['rep_rate'],
            "spread_min": pricing['spread_min'],
            "spread_max": pricing['spread_max'],
            "oibor_pct": pricing['oibor_pct'],
            "PD": pricing['PD'],
            "LGD": pricing['LGD'],
            "Provision_Rate": pricing['Provision_Rate'],
            "EMI": pricing.get('emi'),
            "NIM": nim,
            "Target_NIM": market_params['target_nim'],
            "be_months": pricing.get('be_periods')
        })

    return pd.DataFrame(results)


def calculate_and_display_single_loan(loan_params: Dict, market_params: Dict):
    risk_base, product_factor, industry_factor = calculate_risk_factors(
        loan_params["product"], loan_params["industry"], loan_params["malaa_score"],
        loan_params.get("ltv"), loan_params.get("working_capital"), loan_params.get("sales")
    )

    pd_val, lgd_val = calculate_pd_lgd(
        risk_base, loan_params["product"], loan_params.get("ltv"), loan_params["stage"]
    )

    fee_products = ["Supply Chain Finance", "Vendor Finance", "Working Capital", "Export Finance"]
    fees_pct = 0.4 if loan_params["product"] in fee_products else 0.0

    buckets = ["Low", "Medium", "High"]
    pricing_results = []

    for bucket in buckets:
        pricing = calculate_loan_pricing(
            risk_base, malaa_risk_label(loan_params["malaa_score"]),
            market_params["oibor_pct"], market_params["cof_pct"],
            market_params["opex_pct"], fees_pct, bucket, loan_params["product"]
        )

        if bucket == "Medium" and loan_params.get("ltv"):
            emi, annual_net, nim, schedule, be_periods = calculate_repayment_schedule(
                loan_params["amount"], pricing["rep_rate"], loan_params["tenor"],
                market_params["cof_pct"], pd_val * lgd_val / 10000,
                market_params["opex_pct"], market_params["upfront_cost"]
            )
            pricing["emi"] = emi
            pricing["be_periods"] = be_periods

        pricing.update({
            "risk_score": risk_base,
            "product_factor": product_factor,
            "industry_factor": industry_factor,
            "PD": pd_val,
            "LGD": lgd_val,
            "Provision_Rate": pd_val * lgd_val / 10000,
            "oibor_pct": market_params["oibor_pct"]
        })
        pricing_results.append(pricing)

    results_df = generate_results_dataframe(loan_params, market_params, pricing_results)
    display_pricing_results(results_df)


# -------------------------------
# MAIN APP ENTRYPOINT
# -------------------------------
def main():
    render_header()
    tab1, tab2, tab3 = st.tabs(["Single Loan Pricing", "Loan Book", "Assumptions"])

    with tab1:
        market_params = render_market_parameters()
        loan_params = render_loan_parameters()
        if st.button("Calculate Pricing", type="primary"):
            calculate_and_display_single_loan(loan_params, market_params)

    with tab2:
        loan_book_df = render_loan_book_upload()
        if loan_book_df is not None:
            st.write("Loan book uploaded. Batch processing logic here...")

    with tab3:
        render_assumptions_tab()


if __name__ == "__main__":
    main()
