import streamlit as st
import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple

# Initialize session state with default values
def init_session_state() -> None:
    """Initialize all session state variables with default values."""
    defaults = {
        'product': "Asset Backed Loan",
        'industry': "Oil & Gas",
        'malaa_score': 600,
        'ltv': 70.0,
        'working_capital': 500000.0,
        'sales': 2000000.0,
        'loan_amount': 1000000.0,
        'tenor': 24,
        'benchmark_rate': 4.1,
        'cost_of_funds': 5.0,
        'show_details': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

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

# Configure page settings
st.set_page_config(
    page_title="rt 360 Pricing Model",
    page_icon="💲",
    layout="wide"
)

# Custom number to words conversion
def amount_to_words(amount: float, currency: str = "OMR") -> str:
    """Convert numeric amount to words representation."""
    if amount == 0:
        return "Zero " + currency
    
    units = ["", "One", "Two", "Three", "Four", "Five",
             "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen",
             "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "Ten", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety"]
    scales = ["", "Thousand", "Million"]
    
    def convert_chunk(n: int) -> str:
        if n < 10:
            return units[n]
        if n < 20:
            return teens[n - 10]
        if n < 100:
            return tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
        return units[n // 100] + " Hundred" + (
            " " + convert_chunk(n % 100) if n % 100 != 0 else "")
    
    amount_int = int(amount)
    decimal_part = int(round((amount - amount_int) * 100))
    
    chunks = []
    scale_index = 0
    
    while amount_int > 0:
        chunk = amount_int % 1000
        if chunk != 0:
            chunk_text = convert_chunk(chunk)
            if scale_index > 0:
                chunk_text += " " + scales[scale_index]
            chunks.insert(0, chunk_text)
        amount_int = amount_int // 1000
        scale_index += 1
    
    result = " ".join(chunks) if chunks else "Zero"
    if decimal_part > 0:
        result += f" and {decimal_part:02d}/100"
    
    return f"{result} {currency}"

# CSS Styling
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
.tab-content { margin-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown(
    """
    <div class="header-title">
        <span class="rt-text">rt</span><span class="threesixty-text">360</span> Risk-Adjusted Pricing Model
    </div>
    """,
    unsafe_allow_html=True
)

# Helper functions
def safe_float(value: Optional[float]) -> float:
    """Safely convert optional float values, returning 0.0 for None."""
    return float(value) if value is not None else 0.0

def calculate_risk_score() -> Tuple[float, Dict[str, float]]:
    """Calculate composite risk score and components."""
    product = st.session_state.product
    
    # Check if the product is valid
    if product not in PRODUCT_RISKS:
        st.error(f"Invalid product selected: {product}. Please select a valid product.", icon="🚨")
        return 0.0, {}
    
    industry = st.session_state.industry
    
    product_factor = PRODUCT_RISKS[product]
    industry_factor = INDUSTRY_RISK_FACTORS[industry]
    malaa_factor = 1.3 - (st.session_state.malaa_score - 300) * (0.8 / 600)
    
    components = {
        'product': product_factor,
        'industry': industry_factor,
        'malaa': malaa_factor
    }
    
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv = safe_float(st.session_state.ltv)
        ltv_factor = min(1.2, max(0.8, 0.7 + 0.0035 * ltv))
        components['ltv'] = ltv_factor
        risk_score = product_factor * industry_factor * malaa_factor * ltv_factor
    else:
        working_capital = safe_float(st.session_state.working_capital)
        sales = safe_float(st.session_state.sales)
        wc_pct = working_capital / sales if sales > 0 else 0
        wcs_factor = min(1.45, max(0.85, 0.85 + 0.6 * min(wc_pct, 1.0)))
        utilization = UTILIZATION_MEDIANS.get(industry, 0.5)
        util_factor = min(1.15, max(0.85, 1 - 0.15 * (0.8 - utilization)))
        
        components['wc_sales'] = wcs_factor
        components['utilization'] = util_factor
        risk_score = product_factor * industry_factor * malaa_factor * wcs_factor * util_factor
    
    risk_score = min(2.0, max(0.4, risk_score))
    return risk_score, components

def calculate_pricing(risk_score: float) -> Dict[str, str]:
    """Calculate all pricing metrics based on risk score."""
    # Base spread calculation
    base_spread_bps = min(500, max(50, 100 + 250 * (risk_score - 1)))
    base_rate_pct = st.session_state.benchmark_rate + (base_spread_bps / 100)
    base_rate_pct = min(10.0, max(5.0, base_rate_pct))
    
    # Bucket assignment
    if risk_score < 0.85:
        bucket = "Low Risk"
        rate_min = max(5.0, base_rate_pct - 0.5)
        rate_max = min(10.0, base_rate_pct + 0.5)
    elif risk_score <= 1.15:
        bucket = "Medium Risk"
        rate_min = max(5.0, base_rate_pct - 0.75)
        rate_max = min(10.0, base_rate_pct + 0.75)
    else:
        bucket = "High Risk"
        rate_min = max(5.0, base_rate_pct - 1.0)
        rate_max = min(10.0, base_rate_pct + 1.0)
    
    # Financial metrics
    fee_yield_pct = 0.4
    cost_of_funds_pct = st.session_state.cost_of_funds
    credit_cost_pct = min(1.0, max(0.2, 0.4 * risk_score))
    opex_pct = 0.4
    
    # NIM calculation
    expected_yield_pct = base_rate_pct + fee_yield_pct
    nim_pct = expected_yield_pct - cost_of_funds_pct - credit_cost_pct - opex_pct
    
    # Breakeven calculations
    breakeven_rate_pct = cost_of_funds_pct + credit_cost_pct + opex_pct - fee_yield_pct
    breakeven_rate_pct = min(10.0, max(5.0, breakeven_rate_pct))
    
    # Tenor analysis
    monthly_margin = (base_rate_pct/1200 + fee_yield_pct/1200 - 
                     cost_of_funds_pct/1200 - credit_cost_pct/1200 - 
                     opex_pct/1200) * safe_float(st.session_state.loan_amount)
    
    upfront_cost = 0.005 * safe_float(st.session_state.loan_amount)
    tenor_months = st.session_state.tenor
    
    if monthly_margin <= 0:
        tenor_check = "Not viable at current rates"
    elif tenor_months < 6:
        tenor_check = "Minimum tenor not met"
    else:
        breakeven_months = np.ceil(upfront_cost / monthly_margin)
        tenor_check = (f"Breakeven in ~{int(breakeven_months)} months" 
                      if breakeven_months <= tenor_months 
                      else "Extend tenor")

    return {
        'bucket': bucket,
        'risk_score': f"{risk_score:.2f}",
        'rate_range': f"{rate_min:.2f}% - {rate_max:.2f}%",
        'effective_rate': f"{base_rate_pct:.2f}%",
        'breakeven_rate': f"{breakeven_rate_pct:.2f}%",
        'nim': f"{nim_pct:.2f}%",
        'tenor_check': tenor_check,
        'monthly_margin': f"OMR {monthly_margin:,.2f}"
    }

# Sidebar Inputs
with st.sidebar:
    st.header("Loan Parameters")
    
    st.selectbox(
        "Product", 
        PRODUCTS,
        key='product'
    )
    st.selectbox(
        "Industry", 
        INDUSTRIES,
        key='industry'
    )
    st.selectbox(
        "Mala'a Score",
        range(300, 901, 50),
        key='malaa_score'
    )
    
    st.number_input(
        "Tenor (months)",
        min_value=6,
        max_value=120,
        key='tenor'
    )
    
    st.subheader("Financial Amounts")
    st.number_input(
        "Loan Amount (OMR)",
        min_value=1000.0,
        step=1000.0,
        key='loan_amount'
    )
    st.markdown(f'<div class="amount-in-words">{amount_to_words(st.session_state.loan_amount)}</div>', 
               unsafe_allow_html=True)

    if st.session_state.product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        st.number_input(
            "LTV (%)",
            min_value=10.0,
            max_value=95.0,
            key='ltv'
        )
        st.session_state.working_capital = None
        st.session_state.sales = None
    else:
        st.number_input(
            "Working Capital (OMR)",
            min_value=0.0,
            step=1000.0,
            key='working_capital'
        )
        st.markdown(f'<div class="amount-in-words">{amount_to_words(safe_float(st.session_state.working_capital))}</div>',
                   unsafe_allow_html=True)
        
        st.number_input(
            "Annual Sales (OMR)",
            min_value=0.0,
            step=1000.0,
            key='sales'
        )
        st.markdown(f'<div class="amount-in-words">{amount_to_words(safe_float(st.session_state.sales))}</div>',
                   unsafe_allow_html=True)

    st.subheader("Bank Parameters")
    st.number_input(
        "OMIBOR Rate (%)",
        min_value=0.0,
        step=0.1,
        key='benchmark_rate'
    )
    st.number_input(
        "Cost of Funds (%)",
        min_value=0.0,
        step=0.1,
        key='cost_of_funds'
    )
    
    st.checkbox(
        "Show Detailed Calculations",
        key='show_details'
    )

# Main Content
with st.container():
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    
    # Input validation
    if (st.session_state.product in ["Asset Backed Loan", "Term Loan", "Export Finance"] and 
        st.session_state.ltv is None):
        st.error('Please provide LTV for the selected product type', icon="🚨")
    elif (st.session_state.product in ["Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"] and 
          (st.session_state.working_capital is None or st.session_state.sales is None)):
        st.error('Please provide Working Capital and Sales for the selected product type', icon="🚨")
    else:
        # Perform calculations
        risk_score, risk_components = calculate_risk_score()
        pricing = calculate_pricing(risk_score)
        
        # Create tabs
        overview_tab, details_tab = st.tabs(["Overview", "Detailed Analysis"])
        
        with overview_tab:
            st.subheader("Risk Assessment")
            cols = st.columns(3)
            cols[0].metric("Risk Score", pricing['risk_score'])
            cols[1].metric("Risk Bucket", pricing['bucket'])
            cols[2].metric("Market Rate Band", "5.0% - 10.0%")
            
            st.subheader("Pricing Summary")
            cols = st.columns(3)
            cols[0].metric("Rate Range", pricing['rate_range'])
            cols[1].metric("Effective Rate", pricing['effective_rate'])
            cols[2].metric("Net Interest Margin", pricing['nim'])
            
            st.subheader("Breakeven Analysis")
            cols = st.columns(2)
            cols[0].metric("Breakeven Rate", pricing['breakeven_rate'])
            cols[1].metric("Tenor Assessment", pricing['tenor_check'])
        
        with details_tab:
            st.subheader("Risk Components")
            st.write(f"- Product Factor: {risk_components['product']:.2f} ({st.session_state.product})")
            st.write(f"- Industry Factor: {risk_components['industry']:.2f} ({st.session_state.industry})")
            st.write(f"- Mala'a Factor: {risk_components['malaa']:.2f}")
            
            if st.session_state.product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                st.write(f"- LTV Factor: {risk_components.get('ltv', 0):.2f}")
            else:
                st.write(f"- Working Capital/Sales Factor: {risk_components.get('wc_sales', 0):.2f}")
                st.write(f"- Utilization Factor: {risk_components.get('utilization', 0):.2f}")
            
            st.subheader("Pricing Details")
            st.write(f"- Base Spread Calculation: 100 + 250 × ({risk_score:.2f} - 1) = {100 + 250 * (risk_score - 1):.0f} bps")
            st.write(f"- Fees Income: 0.4% of exposure")
            st.write(f"- Monthly Margin: {pricing['monthly_margin']}")
            
            # Ensure all values are present before creating the DataFrame
            try:
                pricing_data = {
                    'Metric': ['Risk Score', 'Bucket', 'Rate Range', 'Effective Rate', 
                               'Breakeven Rate', 'NIM', 'Tenor Check'],
                    'Value': [pricing['risk_score'], pricing['bucket'], pricing['rate_range'],
                              pricing['effective_rate'], pricing['breakeven_rate'],
                              pricing['nim'], pricing['tenor_check']]
                }
                # Check
