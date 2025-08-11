import streamlit as st
import pandas as pd
import numpy as np
from num2words import num2words

# Configure page settings
st.set_page_config(
    page_title="rt 360 Pricing Model",
    page_icon="💲",
    layout="wide"
)

# Custom CSS styling for the application
st.markdown("""
<style>
/* Main container styling */
.main-container {
    border: 4px solid #1E88E5;
    border-radius: 10px;
    padding: 2rem;
    margin-top: 1rem;
    background-color: white;
}

/* Header styling with color split */
.header-title {
    font-size: 2.5rem;
    font-weight: 700;
    margin-bottom: 1.5rem;
    text-align: center;
}
.rt-text {
    color: #1E88E5;
}
.threesixty-text {
    color: #43A047;
}

/* Input field styling */
.stNumberInput, .stSelectbox {
    margin-bottom: 1rem;
}
.amount-in-words {
    font-size: 0.9rem;
    color: #666;
    margin-top: -0.5rem;
    margin-bottom: 1rem;
}

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {
    margin-bottom: 1rem;
}

/* KPI metric styling */
.kpi-card {
    border-radius: 0.5rem;
    padding: 1rem;
    background-color: #f8f9fa;
    margin-bottom: 1rem;
}
.kpi-title {
    font-size: 1rem;
    color: #666;
}
.kpi-value {
    font-size: 1.5rem;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

# --- Constants and Configuration ---
INDUSTRIES = [
    "Oil & Gas", "Construction", "Trading", "Manufacturing", 
    "Logistics", "Healthcare", "Hospitality", "Retail", 
    "Real Estate", "Mining", "Utilities", "Agriculture"
]

PRODUCTS = [
    "Asset Backed Loan", "Term Loan", "Export Finance", 
    "Working Capital", "Trade Finance", "Supply Chain Finance", 
    "Vendor Finance"
]

INDUSTRY_RISK_FACTORS = {
    "Oil & Gas": 0.70, "Construction": 0.90, "Real Estate": 0.85,
    "Manufacturing": 0.80, "Trading": 0.75, "Logistics": 0.70,
    "Healthcare": 0.60, "Retail": 0.80, "Hospitality": 0.85,
    "Mining": 0.90, "Utilities": 0.55, "Agriculture": 0.85
}

PRODUCT_RISKS = {
    "Asset Backed Loan": 1.00, "Term Loan": 0.90, "Export Finance": 0.80,
    "Vendor Finance": 0.60, "Supply Chain Finance": 0.55, "Trade Finance": 0.50,
    "Working Capital": 0.65
}

UTILIZATION_MEDIANS = {
    "Trading": 0.65, "Manufacturing": 0.55, "Construction": 0.40,
    "Logistics": 0.60, "Retail": 0.50, "Healthcare": 0.45,
    "Hospitality": 0.35, "Oil & Gas": 0.50, "Real Estate": 0.30,
    "Mining": 0.45, "Utilities": 0.55, "Agriculture": 0.40
}

# --- App Header ---
st.markdown(
    """
    <div class="header-title">
        <span class="rt-text">rt</span><span class="threesixty-text">360</span> Risk-Adjusted Pricing Model
    </div>
    """,
    unsafe_allow_html=True
)

# --- Sidebar with Inputs ---
with st.sidebar:
    st.header("Loan Parameters")
    
    # Product type selection
    product = st.selectbox(
        "Loan Product Type",
        PRODUCTS,
        help="Select the type of corporate lending product"
    )
    
    # Industry selection
    industry = st.selectbox(
        "Borrower Industry",
        INDUSTRIES,
        help="Select the industry sector of the borrower"
    )
    
    # Mala'a score selection
    malaa_score = st.selectbox(
        "Mala'a Credit Score", 
        list(range(300, 951, 50)),
        index=6,  # Default to 600
        help="Borrower's credit risk score (300-900)"
    )
    
    # Tenor input
    tenor = st.number_input(
        "Loan Tenor (months)", 
        min_value=6,
        max_value=120,
        value=24,
        help="Duration of the loan in months"
    )
    
    # Financial amounts
    st.subheader("Financial Amounts")
    loan_amount = st.number_input(
        "Loan Amount (OMR)", 
        min_value=10000.0,
        value=1000000.0,
        step=10000.0
    )
    st.markdown(
        f'<div class="amount-in-words">{num2words(loan_amount, to="currency", currency="OMR")}</div>',
        unsafe_allow_html=True
    )

    # Product-specific inputs
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv = st.number_input(
            "Loan-to-Value Ratio (%)",
            min_value=10.0,
            max_value=95.0,
            value=70.0,
            help="Percentage of collateral value being financed"
        )
    else:
        ltv = None
        working_capital = st.number_input(
            "Working Capital (OMR)",
            min_value=0.0,
            value=500000.0
        )
        st.markdown(
            f'<div class="amount-in-words">{num2words(working_capital, to="currency", currency="OMR")}</div>',
            unsafe_allow_html=True
        )
        
        sales = st.number_input(
            "Annual Sales (OMR)",
            min_value=0.0,
            value=2000000.0
        )
        st.markdown(
            f'<div class="amount-in-words">{num2words(sales, to="currency", currency="OMR")}</div>',
            unsafe_allow_html=True
        )

    # Bank parameters
    st.subheader("Bank Parameters")
    benchmark_rate = st.number_input(
        "OMIBOR Benchmark Rate (%)",
        min_value=0.0,
        value=4.1,
        step=0.1
    )
    cost_of_funds = st.number_input(
        "Cost of Funds (%)",
        min_value=0.0,
        value=5.0,
        step=0.1
    )
    
    # Advanced controls
    st.subheader("Advanced Controls")
    show_details = st.checkbox("Show Detailed Calculations")

# --- Helper Functions ---
def calculate_risk_score():
    """Calculate the composite risk score based on inputs"""
    product_factor = PRODUCT_RISKS[product]
    industry_factor = INDUSTRY_RISK_FACTORS[industry]
    malaa_factor = 1.3 - (malaa_score - 300) * (0.8 / 600)
    
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = 0.7 + 0.0035 * ltv
        ltv_factor = max(0.8, min(1.2, ltv_factor))
        risk_score = product_factor * industry_factor * malaa_factor * ltv_factor
    else:
        wc_pct_sales = working_capital / sales if sales > 0 else 0
        wcs_factor = 0.85 + 0.6 * min(wc_pct_sales, 1.0)
        utilization = UTILIZATION_MEDIANS.get(industry, 0.5)
        util_factor = 1 - 0.15 * (0.8 - utilization)
        util_factor = max(0.85, min(1.15, util_factor))
        risk_score = product_factor * industry_factor * malaa_factor * wcs_factor * util_factor
    
    return max(0.4, min(2.0, risk_score))

def calculate_pricing(risk_score):
    """Calculate all pricing metrics based on risk score"""
    # Base spread calculation
    base_spread_bps = 100 + 250 * (risk_score - 1)
    base_spread_bps = max(50, min(500, base_spread_bps))
    
    # Rate calculation
    base_rate = benchmark_rate + (base_spread_bps / 100)
    effective_rate = max(5.0, min(10.0, base_rate))
    fee_yield = 0.004  # 0.4% fees
    
    # Bucket assignment with rate ranges
    if risk_score < 0.85:
        bucket = "Low Risk"
        rate_min = max(5.0, effective_rate - 0.5)
        rate_max = min(10.0, effective_rate + 0.5)
    elif 0.85 <= risk_score <= 1.15:
        bucket = "Medium Risk"
        rate_min = max(5.0, effective_rate - 0.75)
        rate_max = min(10.0, effective_rate + 0.75)
    else:
        bucket = "High Risk"
        rate_min = max(5.0, effective_rate - 1.0)
        rate_max = min(10.0, effective_rate + 1.0)
    
    # Financial metrics
    credit_cost = min(0.01, max(0.002, 0.004 * risk_score))
    opex = 0.004  # 0.4%
    
    # NIM calculation
    expected_yield = effective_rate/100 + fee_yield  # Convert to decimals
    funding_cost = cost_of_funds / 100
    nim = (expected_yield - funding_cost - credit_cost - opex) * 100  # Back to percentage
    
    # Breakeven calculations
    breakeven_rate = (funding_cost + credit_cost + opex - fee_yield) * 100
    breakeven_rate = max(5.0, min(10.0, breakeven_rate))
    
    if tenor >= 6:
        monthly_margin = (expected_yield - funding_cost - credit_cost - opex) * loan_amount / 12
        upfront_cost = 0.005 * loan_amount
        breakeven_months = np.ceil(upfront_cost / monthly_margin) if monthly_margin > 0 else float('inf')
        
        if monthly_margin <= 0:
            tenor_check = "Not viable at current rates"
        elif breakeven_months > tenor:
            tenor_check = f"Extend tenor beyond {tenor} months"
        else:
            tenor_check = f"Breakeven in {int(breakeven_months)} months"
    else:
        tenor_check = "Minimum 6 months required"
    
    return {
        "bucket": bucket,
        "risk_score": risk_score,
        "rate_range": (rate_min, rate_max),
        "effective_rate": effective_rate,
        "nim": nim,
        "breakeven_rate": breakeven_rate,
        "tenor_check": tenor_check
    }

# --- Main Application Logic ---
with st.container():
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    
    # Input validation
    validation_errors = []
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"] and ltv is None:
        validation_errors.append("LTV is required for the selected product type")
    if product in ["Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"] and sales <= 0:
        validation_errors.append("Sales must be positive for the selected product type")
    
    if validation_errors:
        for error in validation_errors:
            st.error(error)
    else:
        # Calculate risk and pricing
        risk_score = calculate_risk_score()
        pricing = calculate_pricing(risk_score)
        
        # Create tabs for different views
        overview_tab, pricing_tab = st.tabs(["Overview Dashboard", "Detailed Pricing"])
        
        with overview_tab:
            st.subheader("Risk Assessment Summary")
            
            # KPI cards
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown('<div class="kpi-card"><div class="kpi-title">Risk Category</div><div class="kpi-value">{}</div></div>'.format(pricing["bucket"]), unsafe_allow_html=True)
            with col2:
                st.markdown('<div class="kpi-card"><div class="kpi-title">Composite Risk Score</div><div class="kpi-value">{:.2f}</div></div>'.format(risk_score), unsafe_allow_html=True)
            with col3:
                st.markdown('<div class="kpi-card"><div class="kpi-title">Market Rate Band</div><div class="kpi-value">5.0% - 10.0%</div></div>', unsafe_allow_html=True)
            
            # Key metrics
            st.subheader("Pricing Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Proposed Rate Range", 
                        f"{pricing['rate_range'][0]:.2f}% - {pricing['rate_range'][1]:.2f}%")
            with col2:
                st.metric("Representative Rate", f"{pricing['effective_rate']:.2f}%")
            with col3:
                st.metric("Net Interest Margin", f"{pricing['nim']:.2f}%")
            
            # Breakeven analysis
            st.subheader("Breakeven Analysis")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Breakeven Rate", f"{pricing['breakeven_rate']:.2f}%")
            with col2:
                st.metric("Tenor Assessment", pricing["tenor_check"])
        
        with pricing_tab:
            st.subheader("Pricing Details")
            
            # Create detailed pricing table
            pricing_table = pd.DataFrame({
                "Metric": [
                    "Risk Category",
                    "Composite Risk Score",
                    "Rate Range (%)",
                    "Representative Rate (%)",
                    "Breakeven Rate (%)",
                    "Net Interest Margin (%)",
                    "Tenor Assessment"
                ],
                "Value": [
                    pricing["bucket"],
                    f"{risk_score:.2f}",
                    f"{pricing['rate_range'][0]:.2f} - {pricing['rate_range'][1]:.2f}",
                    f"{pricing['effective_rate']:.2f}",
                    f"{pricing['breakeven_rate']:.2f}",
                    f"{pricing['nim']:.2f}",
                    pricing["tenor_check"]
                ]
            })
            
            # Display the table
            st.dataframe(
                pricing_table,
                column_config={
                    "Metric": st.column_config.Column(width="medium"),
                    "Value": st.column_config.Column(width="medium")
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Add helper text
            st.caption("""
            **Notes:**
            - Rates are clamped to market band of 5.0% to 10.0%
            - Fees are assumed at 0.4% of exposure annually
            - NIM calculated net of cost of funds, credit costs, and operational expenses
            """)
            
            # Download button
            csv = pricing_table.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Pricing Details",
                data=csv,
                file_name="loan_pricing_details.csv",
                mime="text/csv"
            )
        
        # Show detailed calculations if requested
        if show_details:
            st.subheader("Detailed Calculations")
            
            with st.expander("Risk Score Components"):
                st.write(f"**Product Factor ({product}):** {PRODUCT_RISKS[product]:.2f}")
                st.write(f"**Industry Factor ({industry}):** {INDUSTRY_RISK_FACTORS[industry]:.2f}")
                st.write(f"**Mala'a Score Factor (Mala'a {malaa_score}):** {1.3 - (malaa_score - 300) * (0.8 / 600):.2f}")
                
                if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                    st.write(f"**LTV Factor (LTV {ltv}%):** {0.7 + 0.0035 * ltv:.2f}")
                else:
                    wc_pct_sales = working_capital / sales if sales > 0 else 0
                    st.write(f"**WC/Sales Factor (WC/Sales {wc_pct_sales:.2f}):** {0.85 + 0.6 * min(wc_pct_sales, 1.0):.2f}")
                    utilization = UTILIZATION_MEDIANS.get(industry, 0.5)
                    st.write(f"**Utilization Factor ({industry} utilization {utilization*100:.0f}%):** {1 - 0.15 * (0.8 - utilization):.2f}")
                
                st.write(f"**Composite Risk Score:** {risk_score:.2f}")
            
            with st.expander("Pricing Components"):
                base_spread_bps = 100 + 250 * (risk_score - 1)
                st.write(f"**Base Spread Calculation:** 100 + 250 * ({risk_score:.2f} - 1) = {base_spread_bps:.0f} bps")
                st.write(f"**Effective Rate:** OMIBOR {benchmark_rate}% + {base_spread_bps/100:.2f}% = {(benchmark_rate + base_spread_bps/100):.2f}%")
                st.write(f"**After Clamping to Market Band:** {pricing['effective_rate']:.2f}%")
                
                st.write("\n**NIM Calculation:**")
                st.write(f"- Expected Yield: {pricing['effective_rate']:.2f}% (interest) + 0.4% (fees) = {pricing['effective_rate'] + 0.4:.2f}%")
                st.write(f"- Cost of Funds: {cost_of_funds:.1f}%")
                st.write(f"- Credit Cost: {0.004 * risk_score:.3f}% (proportional to risk)")
                st.write(f"- Operational Expenses: 0.4%")
                st.write(f"**Net NIM:** {pricing['nim']:.2f}%")

    st.markdown('</div>', unsafe_allow_html=True)

# --- Test Scenarios ---
with st.expander("Test Scenarios", expanded=False):
    st.write("""
    **Pre-configured test scenarios:**
    - Low-risk: Utilities, Trade Finance, Mala'a=850, WC/Sales=0.2 → bucket=Low, rate ~5-6%
    - Mid-risk: Manufacturing, Term Loan, Mala'a=700, LTV=70% → bucket=Medium, ~6.5-8%
    - High-risk: Construction, Asset Backed Loan, Mala'a=400, LTV=85% → bucket=High, ~8.5-10%
    """)

    if st.button("Load Low-Risk Scenario"):
        st.session_state.product = "Trade Finance"
        st.session_state.industry = "Utilities"
        st.session_state.malaa_score = 850
        st.session_state.loan_amount = 500000
        st.experimental_rerun()

    if st.button("Load Mid-Risk Scenario"):
        st.session_state.product = "Term Loan"
        st.session_state.industry = "Manufacturing"
        st.session_state.malaa_score = 700
        st.session_state.ltv = 70
        st.session_state.loan_amount = 1000000
        st.experimental_rerun()

    if st.button("Load High-Risk Scenario"):
        st.session_state.product = "Asset Backed Loan"
        st.session_state.industry = "Construction"
        st.session_state.malaa_score = 400
        st.session_state.ltv = 85
        st.session_state.loan_amount = 2000000
        st.experimental_rerun()



