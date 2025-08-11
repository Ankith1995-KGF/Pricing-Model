import streamlit as st
import pandas as pd
import numpy as np

# Initialize session state for form fields
if 'product' not in st.session_state:
    st.session_state.product = "Asset Backed Loan"
if 'industry' not in st.session_state:
    st.session_state.industry = "Oil & Gas"
if 'malaa_score' not in st.session_state:
    st.session_state.malaa_score = 600
if 'ltv' not in st.session_state:
    st.session_state.ltv = 70.0
if 'working_capital' not in st.session_state:
    st.session_state.working_capital = 500000.0
if 'sales' not in st.session_state:
    st.session_state.sales = 2000000.0
if 'loan_amount' not in st.session_state:
    st.session_state.loan_amount = 1000000.0
if 'tenor' not in st.session_state:
    st.session_state.tenor = 24
if 'benchmark_rate' not in st.session_state:
    st.session_state.benchmark_rate = 4.1
if 'cost_of_funds' not in st.session_state:
    st.session_state.cost_of_funds = 5.0

# Custom fallback for num2words functionality
def amount_to_words(amount, currency="OMR"):
    """Convert numbers to words with proper OMR formatting"""
    if amount == 0:
        return "Zero " + currency
    
    units = ["", "One", "Two", "Three", "Four", "Five", 
             "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", 
             "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "Ten", "Twenty", "Thirty", "Forty", "Fifty", 
            "Sixty", "Seventy", "Eighty", "Ninety"]
    thousands = ["", "Thousand", "Million"]
    
    def convert_less_than_thousand(n):
        if n < 10:
            return units[int(n)]
        if n < 20:
            return teens[int(n) - 10]
        if n < 100:
            return tens[int(n) // 10] + (" " + units[int(n) % 10] if int(n) % 10 != 0 else "")
        return units[int(n) // 100] + " Hundred" + (" " + convert_less_than_thousand(n % 100) if n % 100 != 0 else "")
    
    amount_str = ""
    chunks = []
    for i in range(len(thousands)):
        chunk = amount % 1000
        if chunk != 0:
            chunks.append(chunk)
        amount = amount // 1000
    
    for i, chunk in enumerate(reversed(chunks)):
        if i > 0 and chunk != 0:
            amount_str += " " + thousands[i] + " "
        amount_str += convert_less_than_thousand(chunk)
    
    return f"{amount_str} {currency}".strip()

try:
    from num2words import num2words
    def format_currency(amount):
        return num2words(amount, to='currency', currency='OMR')
except ImportError:
    st.warning("Package 'num2words' not found. Using built-in number conversion.")
    def format_currency(amount):
        return amount_to_words(amount)

# Configure page settings
st.set_page_config(
    page_title="rt 360 Pricing Model",
    page_icon="💲",
    layout="wide"
)

# Custom CSS styling
st.markdown("""
<style>
.main-container {
    border: 4px solid #1E88E5;
    border-radius: 10px;
    padding: 2rem;
    margin-top: 1rem;
    background-color: white;
}
.header-title {
    font-size: 2.5rem;
    font-weight: 700;
    margin-bottom: 1.5rem;
    text-align: center;
}
.rt-text { color: #1E88E5; }
.threesixty-text { color: #43A047; }
.amount-in-words {
    font-size: 0.9rem;
    color: #666;
    margin-top: -0.5rem;
    margin-bottom: 1rem;
}
.kpi-card {
    border-radius: 0.5rem;
    padding: 1rem;
    background-color: #f8f9fa;
    margin-bottom: 1rem;
}
.kpi-title { font-size: 1rem; color: #666; }
.kpi-value { font-size: 1.5rem; font-weight: 700; }
.error-message { color: #ff4b4b; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Constants
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
    "Vendor Finance": 0.60, "Supply Chain Finance": 0.55, "Trade Finance": 0.50
}

UTILIZATION_MEDIANS = {
    "Trading": 0.65, "Manufacturing": 0.55, "Construction": 0.40,
    "Logistics": 0.60, "Retail": 0.50, "Healthcare": 0.45,
    "Hospitality": 0.35, "Oil & Gas": 0.50, "Real Estate": 0.30,
    "Mining": 0.45, "Utilities": 0.55, "Agriculture": 0.40
}

# App Header
st.markdown("""
<div class="header-title">
    <span class="rt-text">rt</span><span class="threesixty-text">360</span> Risk-Adjusted Pricing Model
</div>
""", unsafe_allow_html=True)

# Sidebar Inputs
with st.sidebar:
    st.header("Loan Parameters")
    
    product = st.selectbox(
        "Product", 
        PRODUCTS,
        index=PRODUCTS.index(st.session_state.product),
        key='product'
    )
    industry = st.selectbox(
        "Industry", 
        INDUSTRIES,
        index=INDUSTRIES.index(st.session_state.industry),
        key='industry'
    )
    malaa_score = st.selectbox(
        "Mala'a Score", 
        list(range(300, 901, 50)),
        index=list(range(300, 901, 50)).index(st.session_state.malaa_score),
        key='malaa_score'
    )
    tenor = st.number_input(
        "Tenor (months)", 
        min_value=6,
        max_value=120,
        value=st.session_state.tenor,
        key='tenor'
    )
    
    st.subheader("Financial Amounts")
    loan_amount = st.number_input(
        "Loan Amount (OMR)", 
        min_value=1000.0,
        value=float(st.session_state.loan_amount),
        step=1000.0,
        key='loan_amount'
    )
    st.markdown(f'<div class="amount-in-words">{format_currency(loan_amount)}</div>', unsafe_allow_html=True)

    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv = st.number_input(
            "LTV (%)",
            min_value=10.0,
            max_value=95.0,
            value=float(st.session_state.ltv),
            key='ltv'
        )
        st.session_state.working_capital = None
        st.session_state.sales = None
    else:
        working_capital = st.number_input(
            "Working Capital (OMR)",
            min_value=0.0,
            value=float(st.session_state.working_capital),
            step=1000.0,
            key='working_capital'
        )
        st.markdown(f'<div class="amount-in-words">{format_currency(working_capital)}</div>', unsafe_allow_html=True)
        
        sales = st.number_input(
            "Annual Sales (OMR)",
            min_value=0.0,
            value=float(st.session_state.sales),
            step=1000.0,
            key='sales'
        )
        st.markdown(f'<div class="amount-in-words">{format_currency(sales)}</div>', unsafe_allow_html=True)

    st.subheader("Bank Parameters")
    benchmark_rate = st.number_input(
        "OMIBOR Rate (%)",
        min_value=0.0,
        value=float(st.session_state.benchmark_rate),
        step=0.1,
        key='benchmark_rate'
    )
    cost_of_funds = st.number_input(
        "Cost of Funds (%)",
        min_value=0.0,
        value=float(st.session_state.cost_of_funds),
        step=0.1,
        key='cost_of_funds'
    )
    show_details = st.checkbox("Show Detailed Calculations")

# Risk Calculation Logic
def calculate_risk_score():
    product_factor = PRODUCT_RISKS[st.session_state.product]
    industry_factor = INDUSTRY_RISK_FACTORS[st.session_state.industry]
    malaa_factor = 1.3 - (st.session_state.malaa_score - 300) * (0.8 / 600)
    
    if st.session_state.product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = 0.7 + 0.0035 * st.session_state.ltv
        ltv_factor = max(0.8, min(1.2, ltv_factor))
        risk_score = product_factor * industry_factor * malaa_factor * ltv_factor
    else:
        wc_pct = st.session_state.working_capital / st.session_state.sales if st.session_state.sales > 0 else 0
        wcs_factor = 0.85 + 0.6 * min(wc_pct, 1.0)
        utilization = UTILIZATION_MEDIANS.get(st.session_state.industry, 0.5)
        util_factor = 1 - 0.15 * (0.8 - utilization)
        util_factor = max(0.85, min(1.15, util_factor))
        risk_score = product_factor * industry_factor * malaa_factor * wcs_factor * util_factor
    
    return max(0.4, min(2.0, risk_score)), product_factor, industry_factor, malaa_factor

def calculate_pricing(risk_score):
    # Base spread calculation
    base_spread_bps = 100 + 250 * (risk_score - 1)
    base_spread_bps = max(50, min(500, base_spread_bps))
    
    # Rate calculation
    benchmark = st.session_state.benchmark_rate / 100
    base_rate = benchmark + (base_spread_bps / 100)
    effective_rate = max(5.0, min(10.0, base_rate))
    fee_yield = 0.004  # 0.4% fees
    
    # Bucket assignment with rate ranges
    if risk_score < 0.85:
        bucket = "Low Risk"
        rate_min = max(5.0, base_rate - 0.5)
        rate_max = min(10.0, base_rate + 0.5)
    elif 0.85 <= risk_score <= 1.15:
        bucket = "Medium Risk"
        rate_min = max(5.0, base_rate - 0.75)
        rate_max = min(10.0, base_rate + 0.75)
    else:
        bucket = "High Risk"
        rate_min = max(5.0, base_rate - 1.0)
        rate_max = min(10.0, base_rate + 1.0)
    
    # Financial metrics
    cost_of_funds = st.session_state.cost_of_funds / 100
    credit_cost = min(0.01, max(0.002, 0.004 * risk_score))
    opex = 0.004
    
    # NIM calculation
    expected_yield = effective_rate/100 + fee_yield
    nim = (expected_yield - cost_of_funds - credit_cost - opex) * 100
    
    # Breakeven calculations
    breakeven_rate = (cost_of_funds + credit_cost + opex - fee_yield) * 100
    breakeven_rate = max(5.0, min(10.0, breakeven_rate))
    
    # Tenor analysis
    monthly_margin = (expected_yield - cost_of_funds - credit_cost - opex) * st.session_state.loan_amount / 12
    upfront_cost = 0.005 * st.session_state.loan_amount
    
    if monthly_margin <= 0:
        tenor_check = "Not viable at current rates"
    elif st.session_state.tenor < 6:
        tenor_check = "Minimum tenor not met"
    else:
        breakeven_months = np.ceil(upfront_cost / monthly_margin)
        if breakeven_months > st.session_state.tenor:
            tenor_check = "Extend tenor to breakeven"
        else:
            tenor_check = f"Breakeven in ~{int(breakeven_months)} months"
    
    return {
        "bucket": bucket,
        "risk_score": risk_score,
        "rate_range": f"{rate_min:.2f}% - {rate_max:.2f}%",
        "effective_rate": f"{effective_rate:.2f}%",
        "nim": f"{nim:.2f}%",
        "breakeven_rate": f"{breakeven_rate:.2f}%",
        "tenor_check": tenor_check,
        "base_spread": base_spread_bps,
        "monthly_margin": monthly_margin
    }

# Main Content
with st.container():
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    
    # Input validation
    validation_passed = True
    if st.session_state.product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        if st.session_state.ltv <= 0:
            st.error('<div class="error-message">⚠️ LTV must be provided for selected product type!</div>', unsafe_allow_html=True)
            validation_passed = False
    else:
        if st.session_state.working_capital <= 0 or st.session_state.sales <= 0:
            st.error('<div class="error-message">⚠️ Working Capital and Sales must be positive for selected product type!</div>', unsafe_allow_html=True)
            validation_passed = False
    
    if validation_passed:
        # Calculate risk and pricing
        risk_score, product_factor, industry_factor, malaa_factor = calculate_risk_score()
        pricing = calculate_pricing(risk_score)
        
        # Create tabs
        overview_tab, pricing_tab = st.tabs(["Overview Dashboard", "Pricing Details"])
        
        with overview_tab:
            st.subheader("Risk Assessment")
            cols = st.columns(3)
            cols[0].metric("Risk Score", f"{risk_score:.2f}")
            cols[1].metric("Risk Bucket", pricing["bucket"])
            cols[2].metric("Market Rate Band", "5.0% - 10.0%")
            
            st.subheader("Pricing Summary")
            cols = st.columns(3)
            cols[0].metric("Proposed Rate", pricing["effective_rate"])
            cols[1].metric("Rate Range", pricing["rate_range"])
            cols[2].metric("Net Interest Margin", pricing["nim"])
            
            st.subheader("Breakeven Analysis")
            cols = st.columns(2)
            cols[0].metric("Breakeven Rate", pricing["breakeven_rate"])
            cols[1].metric("Tenor Assessment", pricing["tenor_check"])
        
        with pricing_tab:
            st.subheader("Detailed Pricing Table")
            pricing_data = {
                "Bucket": [pricing["bucket"]],
                "Risk Score": [f"{risk_score:.2f}"],
                "Rate Range (%)": [pricing["rate_range"]],
                "Effective Rate (%)": [pricing["effective_rate"]],
                "Breakeven Rate (%)": [pricing["breakeven_rate"]],
                "NIM (%)": [pricing["nim"]],
                "Tenor Check": [pricing["tenor_check"]]
            }
            st.dataframe(
                pd.DataFrame(pricing_data),
                hide_index=True,
                use_container_width=True
            )
            
            # Download button
            csv = pd.DataFrame(pricing_data).to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Pricing Details",
                csv,
                "loan_pricing.csv",
                "text/csv"
            )
            
            st.caption("Note: All rates are constrained to the market band of 5.0% to 10.0%")
        
        if show_details:
            with st.expander("Detailed Calculations"):
                st.write("**Risk Score Components:**")
                st.write(f"- Product Factor: {product_factor:.2f} ({st.session_state.product})")
                st.write(f"- Industry Factor: {industry_factor:.2f} ({st.session_state.industry})")
                st.write(f"- Mala'a Score Factor: {malaa_factor:.2f} (Score: {st.session_state.malaa_score})")
                
                if st.session_state.product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                    st.write(f"- LTV Factor: {0.7 + 0.0035 * st.session_state.ltv:.2f} (LTV: {st.session_state.ltv}%)")
                else:
                    wc_pct = st.session_state.working_capital / st.session_state.sales
                    st.write(f"- WC/Sales Factor: {0.85 + 0.6 * min(wc_pct, 1.0):.2f} (WC/Sales: {wc_pct:.2f})")
                    util = UTILIZATION_MEDIANS.get(st.session_state.industry, 0.5)
                    st.write(f"- Utilization Factor: {1 - 0.15 * (0.8 - util):.2f} ({st.session_state.industry} median: {util*100:.0f}%)")
                
                st.write("\n**Pricing Components:**")
                st.write(f"- Base Spread: 100 + 250 × ({risk_score:.2f} - 1) = {pricing['base_spread']:.0f} bps")
                st.write(f"- Effective Rate: {st.session_state.benchmark_rate}% + {pricing['base_spread']/100:.2f}% = {pricing['effective_rate']}")
                st.write(f"- Fees Income: 0.4% of exposure")
                st.write(f"- Cost of Funds: {st.session_state.cost_of_funds}%")
                st.write(f"- Credit Cost: {0.004 * risk_score:.3f}% (based on risk)")
                st.write(f"- Operational Expenses: 0.4%")
                st.write(f"- Monthly Margin: OMR {pricing['monthly_margin']:,.2f}")

# Test Scenarios
with st.expander("Test Scenarios"):
    st.write("""
    **Pre-configured test cases:**
    - **Low Risk:** Utilities / Trade Finance / Mala'a 850 → Rate ~5-6%
    - **Medium Risk:** Manufacturing / Term Loan / Mala'a 700 / LTV 70% → Rate ~6.5-8%
    - **High Risk:** Construction / ABL / Mala'a 400 / LTV 85% → Rate ~8.5-10%
    """)
    
    def set_scenario(scenario):
        if scenario == "low":
            st.session_state.product = "Trade Finance"
            st.session_state.industry = "Utilities"
            st.session_state.malaa_score = 850
            st.session_state.ltv = None
            st.session_state.working_capital = 500000.0
            st.session_state.sales = 2000000.0
        elif scenario == "medium":
            st.session_state.product = "Term Loan"
            st.session_state.industry = "Manufacturing"
            st.session_state.malaa_score = 700
            st.session_state.ltv = 70.0
            st.session_state.working_capital = None
            st.session_state.sales = None
        elif scenario == "high":
            st.session_state.product = "Asset Backed Loan"
            st.session_state.industry = "Construction"
            st.session_state.malaa_score = 400
            st.session_state.ltv = 85.0
            st.session_state.working_capital = None
            st.session_state.sales = None
    
    cols = st.columns(3)
    with cols[0]:
        if st.button("Load Low Risk"):
            set_scenario("low")
    with cols[1]:
        if st.button("Load Medium Risk"):
            set_scenario("medium")
    with cols[2]:
        if st.button("Load High Risk"):
            set_scenario("high")

st.markdown('</div>', unsafe_allow_html=True)
