import streamlit as st
import pandas as pd
import numpy as np

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

# Custom fallback for num2words functionality
def amount_to_words(amount, currency="OMR"):
    """Fallback function to convert numbers to words"""
    if amount == 0:
        return "Zero " + currency
    
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", 
             "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "Ten", "Twenty", "Thirty", "Forty", "Fifty", 
            "Sixty", "Seventy", "Eighty", "Ninety"]
    thousands = ["", "Thousand", "Million"]
    
    def convert_less_than_thousand(n):
        if n == 0:
            return ""
        if n < 10:
            return units[int(n)]
        if n < 20:
            return teens[int(n) - 10]
        if n < 100:
            return tens[int(n) // 10] + (" " + convert_less_than_thousand(n % 10) if n % 10 != 0 else "")
        return units[int(n) // 100] + " Hundred" + (" " + convert_less_than_thousand(n % 100) if n % 100 != 0 else "")
    
    amount = float(amount)
    if amount < 0:
        return "Negative " + amount_to_words(abs(amount), currency)
    
    parts = []
    for i in range(len(thousands)):
        chunk = amount % 1000
        if chunk != 0:
            part = convert_less_than_thousand(chunk)
            if thousands[i]:
                part += " " + thousands[i]
            parts.insert(0, part)
        amount = amount // 1000
    
    amount_str = " ".join(parts)
    return f"{amount_str} {currency}".strip()

try:
    from num2words import num2words
    def format_currency(amount):
        return num2words(amount, to='currency', currency='OMR')
except ImportError:
    st.warning("Package 'num2words' not found. Using built-in number conversion.")
    def format_currency(amount):
        return amount_to_words(amount)

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
    "Vendor Finance": 0.60, "Supply Chain Finance": 0.55, "Trade Finance": 0.50
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
    product = st.selectbox("Product", PRODUCTS, index=0)
    industry = st.selectbox("Industry", INDUSTRIES, index=0)
    malaa_score = st.selectbox("Mala'a Score", range(300, 901, 50), index=6)
    tenor = st.number_input("Tenor (months)", min_value=6, value=24)
    
    st.subheader("Financial Amounts")
    loan_amount = st.number_input("Loan Amount (OMR)", min_value=1000.0, value=1000000.0, step=1000.0)
    st.markdown(f'<div class="amount-in-words">{format_currency(loan_amount)}</div>', unsafe_allow_html=True)

    # Product-specific inputs
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv = st.number_input("LTV (%)", min_value=10.0, max_value=95.0, value=70.0)
        working_capital = sales = None
    else:
        ltv = None
        working_capital = st.number_input("Working Capital (OMR)", min_value=0.0, value=500000.0, step=1000.0)
        st.markdown(f'<div class="amount-in-words">{format_currency(working_capital)}</div>', unsafe_allow_html=True)
        sales = st.number_input("Annual Sales (OMR)", min_value=0.0, value=2000000.0, step=1000.0)
        st.markdown(f'<div class="amount-in-words">{format_currency(sales)}</div>', unsafe_allow_html=True)

    st.subheader("Bank Parameters")
    benchmark_rate = st.number_input("OMIBOR Rate (%)", min_value=0.0, value=4.1, step=0.1) / 100
    cost_of_funds = st.number_input("Cost of Funds (%)", min_value=0.0, value=5.0, step=0.1) / 100
    show_details = st.checkbox("Show Detailed Calculations")

# --- Helper Functions ---
def calculate_risk_score():
    """Calculate composite risk score"""
    product_factor = PRODUCT_RISKS[product]
    industry_factor = INDUSTRY_RISK_FACTORS[industry]
    malaa_factor = 1.3 - (malaa_score - 300) * (0.8 / 600)
    
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = min(1.2, max(0.8, 0.7 + 0.0035 * ltv))
        risk_score = product_factor * industry_factor * malaa_factor * ltv_factor
    else:
        wc_pct = working_capital / sales if sales else 0
        wcs_factor = min(1.45, max(0.85, 0.85 + 0.6 * min(wc_pct, 1.0)))
        utilization = UTILIZATION_MEDIANS.get(industry, 0.5)
        util_factor = min(1.15, max(0.85, 1 - 0.15 * (0.8 - utilization)))
        risk_score = product_factor * industry_factor * malaa_factor * wcs_factor * util_factor
    
    return min(2.0, max(0.4, risk_score))

def calculate_pricing(risk_score):
    """Calculate all pricing metrics"""
    # Base spread calculation
    base_spread_bps = min(500, max(50, 100 + 250 * (risk_score - 1)))
    base_rate = min(10.0, max(5.0, benchmark_rate + base_spread_bps / 100))
    
    # Bucket assignment
    if risk_score < 0.85:
        bucket = "Low Risk"
        rate_min = min(10.0, max(5.0, base_rate - 0.5))
        rate_max = min(10.0, max(5.0, base_rate + 0.5))
    elif risk_score <= 1.15:
        bucket = "Medium Risk"
        rate_min = min(10.0, max(5.0, base_rate - 0.75))
        rate_max = min(10.0, max(5.0, base_rate + 0.75))
    else:
        bucket = "High Risk"
        rate_min = min(10.0, max(5.0, base_rate - 1.0))
        rate_max = min(10.0, max(5.0, base_rate + 1.0))
    
    # Financial metrics
    fee_yield = 0.004
    credit_cost = min(0.01, max(0.002, 0.004 * risk_score))
    opex = 0.004
    
    # NIM calculation
    expected_yield = base_rate/100 + fee_yield
    nim = (expected_yield - cost_of_funds - credit_cost - opex) * 100
    
    # Breakeven calculations
    breakeven_rate = (cost_of_funds + credit_cost + opex - fee_yield) * 100
    breakeven_rate = min(10.0, max(5.0, breakeven_rate))
    
    monthly_margin = (expected_yield - cost_of_funds - credit_cost - opex) * loan_amount / 12
    upfront_cost = 0.005 * loan_amount
    
    if monthly_margin <= 0:
        tenor_check = "Not viable at current rates"
    elif tenor < 6:
        tenor_check = "Minimum tenor not met"
    else:
        breakeven_months = np.ceil(upfront_cost / monthly_margin)
        tenor_check = f"Breakeven in ~{int(breakeven_months)} months" if breakeven_months <= tenor else "Extend tenor"
    
    return {
        "bucket": bucket,
        "risk_score": risk_score,
        "rate_range": f"{rate_min:.2f}% - {rate_max:.2f}%",
        "effective_rate": f"{base_rate:.2f}%",
        "nim": f"{nim:.2f}%",
        "breakeven_rate": f"{breakeven_rate:.2f}%",
        "tenor_check": tenor_check
    }

# --- Main Content ---
with st.container():
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    
    # Input validation
    validation_passed = True
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"] and (ltv is None or ltv <= 0):
        st.error("⚠️ LTV must be provided for selected product type!")
        validation_passed = False
    if product not in ["Asset Backed Loan", "Term Loan", "Export Finance"] and (working_capital is None or working_capital <= 0 or sales is None or sales <= 0):
        st.error("⚠️ Working Capital and Sales must be positive for selected product type!")
        validation_passed = False
    
    if validation_passed:
        risk_score = calculate_risk_score()
        pricing = calculate_pricing(risk_score)
        
        # Create tabs
        overview_tab, pricing_tab = st.tabs(["Overview Dashboard", "Pricing Table"])
        
        with overview_tab:
            st.subheader("Risk Assessment Summary")
            cols = st.columns(3)
            cols[0].metric("Risk Score", f"{risk_score:.2f}")
            cols[1].metric("Risk Bucket", pricing["bucket"])
            cols[2].metric("Market Rate Band", "5.0% - 10.0%")
            
            st.subheader("Key Pricing Metrics")
            cols = st.columns(3)
            cols[0].metric("Proposed Rate Range", pricing["rate_range"])
            cols[1].metric("Representative Rate", pricing["effective_rate"])
            cols[2].metric("Net Interest Margin", pricing["nim"])
            
            st.subheader("Breakeven Analysis")
            cols = st.columns(2)
            cols[0].metric("Breakeven Rate", pricing["breakeven_rate"])
            cols[1].metric("Tenor Assessment", pricing["tenor_check"])
        
        with pricing_tab:
            st.subheader("Detailed Pricing")
            pricing_data = {
                "Metric": ["Risk Bucket", "Risk Score", "Rate Range", 
                          "Representative Rate", "NIM", "Breakeven Rate", 
                          "Tenor Check"],
                "Value": [pricing["bucket"], f"{risk_score:.2f}", pricing["rate_range"],
                         pricing["effective_rate"], pricing["nim"], 
                         pricing["breakeven_rate"], pricing["tenor_check"]]
            }
            st.dataframe(pd.DataFrame(pricing_data), hide_index=True)
            
            # Download button
            csv = pd.DataFrame(pricing_data).to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Pricing Details",
                csv,
                "loan_pricing.csv",
                "text/csv"
            )
        
        if show_details:
            with st.expander("Detailed Calculations"):
                st.write("**Risk Score Components:**")
                st.write(f"- Product Factor ({product}): {PRODUCT_RISKS[product]:.2f}")
                st.write(f"- Industry Factor ({industry}): {INDUSTRY_RISK_FACTORS[industry]:.2f}")
                
                if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                    st.write(f"- LTV Factor ({ltv}%): {min(1.2, max(0.8, 0.7 + 0.0035 * ltv)):.2f}")
                else:
                    st.write(f"- WC/Sales Factor: {0.85 + 0.6 * min(working_capital/sales, 1.0):.2f}")
                    st.write(f"- Utilization Factor: {1 - 0.15 * (0.8 - UTILIZATION_MEDIANS.get(industry, 0.5)):.2f}")
                
                st.write("\n**Pricing Components:**")
                base_spread = 100 + 250 * (risk_score - 1)
                st.write(f"- Base Spread Calculation: 100 + 250 × ({risk_score:.2f} - 1) = {base_spread:.0f} bps")
                st.write(f"- Effective Rate: {benchmark_rate*100:.1f}% + {base_spread/100:.2f}% = {min(10.0, max(5.0, benchmark_rate + base_spread/100)):.2f}%")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Test scenarios
with st.expander("Test Scenarios"):
    st.write("""
    **Pre-configured test cases:**
    - Low Risk: Utilities, Trade Finance, Mala'a 850, WC/Sales=0.2 → Rate ~5-6%
    - Medium Risk: Manufacturing, Term Loan, Mala'a 700, LTV 70% → Rate ~6.5-8%
    - High Risk: Construction, ABL, Mala'a 400, LTV 85% → Rate ~8.5-10%
    """)
    
    if st.button("Load Low Risk Scenario"):
        st.session_state.product = "Trade Finance"
        st.session_state.industry = "Utilities"
        st.session_state.malaa_score = 850
        st.experimental_rerun()
    
    if st.button("Load Medium Risk Scenario"):
        st.session_state.product = "Term Loan"
        st.session_state.industry = "Manufacturing"
        st.session_state.malaa_score = 700
        st.session_state.ltv = 70
        st.experimental_rerun()
    
    if st.button("Load High Risk Scenario"):
        st.session_state.product = "Asset Backed Loan"
        st.session_state.industry = "Construction"
        st.session_state.malaa_score = 400
        st.session_state.ltv = 85
        st.experimental_rerun()




