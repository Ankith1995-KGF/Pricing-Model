import streamlit as st
import pandas as pd
import numpy as np

# Fallback number to words conversion if num2words is not available
def amount_to_words(amount, currency="OMR"):
    """Convert numeric amount to words representation without num2words"""
    if amount == 0:
        return "Zero " + currency

    units = ["", "One", "Two", "Three", "Four", "Five", 
             "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen",
             "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "Ten", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety"]
    scales = ["", "Thousand", "Million"]

    def convert_less_than_hundred(n):
        if n < 20:
            return teens[n-10] if n >=10 else units[n]
        return tens[n//10] + (" " + units[n%10] if n%10 !=0 else "")

    def convert_less_than_thousand(n):
        if n < 100:
            return convert_less_than_hundred(n)
        return units[n//100] + " Hundred" + (
            " and " + convert_less_than_hundred(n%100) if n%100 !=0 else "")

    parts = []
    amount_int = int(amount)
    if amount_int == 0:
        return "Zero " + currency

    for i in range(len(scales)):
        chunk = amount_int % 1000
        if chunk != 0:
            chunk_str = convert_less_than_thousand(chunk)
            if i > 0:
                chunk_str += " " + scales[i]
            parts.insert(0, chunk_str)
        amount_int = amount_int // 1000

    decimal_part = int(round((amount - int(amount)) * 100))
    amount_str = " ".join(parts)
    if decimal_part > 0:
        amount_str += f" and {decimal_part:02d}/100"

    return f"{amount_str} {currency}"

# Use num2words if available, otherwise use fallback
try:
    from num2words import num2words
    def format_currency(amount):
        return num2words(amount, to='currency', currency='OMR').title()
except ImportError:
    def format_currency(amount):
        return amount_to_words(amount)

# App Configuration
st.set_page_config(
    page_title="RT360 Risk Pricing",
    layout="wide",
    page_icon="🔄"
)

st.title(":blue[rt]:green[360] Risk-Adjusted Pricing Model")

# Custom CSS for styling
st.markdown("""
<style>
    .main {
        border: 1px solid #1E90FF;
        padding: 20px;
        border-radius: 5px;
    }
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        border: 1px solid #1E90FF;
    }
    .stSelectbox>div>div>select {
        border: 1px solid #1E90FF;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #1E90FF;
    }
    .value-label {
        font-size: 0.9em;
        color: #666;
        margin-top: -10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Constants
PRODUCT_RISKS = {
    "Asset Backed Loan": 1.00,
    "Term Loan": 0.90, 
    "Export Finance": 0.80,
    "Vendor Finance": 0.60,
    "Supply Chain Finance": 0.55,
    "Trade Finance": 0.50,
    "Working Capital": 0.50
}

INDUSTRY_RISKS = {
    "Oil & Gas": 0.70,
    "Construction": 0.90,
    "Trading": 0.75,
    "Manufacturing": 0.80,
    "Logistics": 0.70,
    "Healthcare": 0.60,
    "Hospitality": 0.85,
    "Retail": 0.80,
    "Real Estate": 0.85,
    "Mining": 0.90,
    "Utilities": 0.55,
    "Agriculture": 0.85
}

# Helper Functions
def calculate_risk_score(params):
    """Calculate composite risk score from input parameters"""
    # Product risk factor
    product_factor = PRODUCT_RISKS.get(params["product"], 0.75)
    
    # Industry risk factor
    industry_factor = INDUSTRY_RISKS.get(params["industry"], 0.75)
    
    # Mala'a score factor (300-900 -> 1.3-0.5)
    malaa_factor = 1.3 - (params["malaa_score"] - 300) * (0.8 / 600)
    
    # Calculate risk score
    risk_score = product_factor * industry_factor * malaa_factor
    
    # Apply product-specific adjustments
    if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = 0.7 + 0.0035 * params.get("ltv", 70)
        ltv_factor = max(0.8, min(1.2, ltv_factor))
        risk_score *= ltv_factor
    
    return max(0.4, min(2.0, risk_score))

def calculate_pricing(risk_score, params):
    """Calculate pricing based on risk score and parameters"""
    # Base spread
    base_spread = 100 + 250 * (risk_score - 1)
    base_spread = min(max(base_spread, 50), 500)
    
    # Effective rate
    effective_rate = params["benchmark_rate_pct"] + (base_spread / 100)
    effective_rate = min(max(effective_rate, 5.0), 10.0)
    
    # Bucket assignment
    if risk_score < 0.85:
        bucket = "Low Risk"
        rate_band = 0.5
    elif risk_score <= 1.15:
        bucket = "Medium Risk" 
        rate_band = 0.75
    else:
        bucket = "High Risk"
        rate_band = 1.0
    
    rate_range = f"{max(5.0, effective_rate - rate_band):.2f}% - {min(10.0, effective_rate + rate_band):.2f}%"
    
    # Financial metrics
    fee_yield = 0.004
    credit_cost = min(0.01, max(0.002, 0.004 * risk_score))
    nim = effective_rate + fee_yield - params["cost_of_funds_pct"] - credit_cost - 0.004
    
    breakeven_rate = params["cost_of_funds_pct"] + credit_cost + 0.004 - fee_yield
    breakeven_rate = min(max(breakeven_rate, 5.0), 10.0)
    
    return {
        "risk_score": risk_score,
        "bucket": bucket,
        "rate_range": rate_range,
        "effective_rate": f"{effective_rate:.2f}%",
        "nim": f"{nim:.2f}%",
        "breakeven_rate": f"{breakeven_rate:.2f}%"
    }

# Main App
def main():
    with st.sidebar:
        st.header("Input Parameters")
        
        product = st.selectbox(
            "Product Type",
            options=list(PRODUCT_RISKS.keys()),
            index=0
        )
        
        industry = st.selectbox(
            "Industry",
            options=list(INDUSTRY_RISKS.keys()),
            index=0
        )
        
        malaa_score = st.selectbox(
            "Mala'a Score",
            options=range(300, 901, 50),
            index=6  # Default to 600
        )
        
        exposure = st.number_input(
            "Loan Quantum (OMR)",
            min_value=0,
            value=1000000,
            step=10000
        )
        st.markdown(f'<div class="value-label">{format_currency(exposure)}</div>', 
                   unsafe_allow_html=True)
        
        tenor = st.number_input(
            "Tenor (months)",
            min_value=6,
            max_value=120,
            value=36
        )
        
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.slider(
                "Loan-to-Value (%)",
                min_value=0,
                max_value=95,
                value=70
            )
        else:
            working_capital = st.number_input(
                "Working Capital (OMR)",
                min_value=0,
                value=500000,
                step=10000
            )
            st.markdown(f'<div class="value-label">{format_currency(working_capital)}</div>', 
                       unsafe_allow_html=True)
            
            sales = st.number_input(
                "Annual Sales (OMR)",
                min_value=0,
                value=2000000,
                step=10000
            )
            st.markdown(f'<div class="value-label">{format_currency(sales)}</div>', 
                       unsafe_allow_html=True)
        
        benchmark_rate_pct = st.number_input(
            "Benchmark Rate (%)",
            min_value=0.0,
            max_value=20.0,
            value=4.1,
            step=0.1
        )
        
        cost_of_funds_pct = st.number_input(
            "Cost of Funds (%)",
            min_value=0.0,
            max_value=20.0,
            value=5.0,
            step=0.1
        )
    
    # Prepare input parameters
    params = {
        "product": product,
        "industry": industry,
        "malaa_score": malaa_score,
        "exposure": exposure,
        "tenor": tenor,
        "benchmark_rate_pct": benchmark_rate_pct,
        "cost_of_funds_pct": cost_of_funds_pct,
        "ltv": ltv if product in ["Asset Backed Loan", "Term Loan", "Export Finance"] else None,
        "working_capital": working_capital if product not in ["Asset Backed Loan", "Term Loan", "Export Finance"] else None,
        "sales": sales if product not in ["Asset Backed Loan", "Term Loan", "Export Finance"] else None
    }
    
    # Calculate and display results
    with st.container():
        risk_score = calculate_risk_score(params)
        pricing = calculate_pricing(risk_score, params)
        
        st.header("Risk Assessment")
        col1, col2 = st.columns(2)
        col1.metric("Risk Score", f"{risk_score:.2f}")
        col2.metric("Risk Bucket", pricing["bucket"])
        
        st.header("Pricing Summary")
        cols = st.columns(3)
        cols[0].metric("Rate Range", pricing["rate_range"])
        cols[1].metric("Effective Rate", pricing["effective_rate"])
        cols[2].metric("Net Interest Margin", pricing["nim"])
        
        st.header("Breakeven Analysis")
        cols = st.columns(2)
        cols[0].metric("Breakeven Rate", pricing["breakeven_rate"])
        
        # Tenor breakeven check calculation
        monthly_margin = (float(pricing["effective_rate"][:-1])/1200 + 0.004/12 - 
                         cost_of_funds_pct/1200 - 
                         max(0.002, min(0.01, 0.004*risk_score))/12 - 
                         0.004/12) * exposure
        
        if monthly_margin <= 0:
            tenor_check = "Not viable"
        else:
            breakeven_months = np.ceil((0.005 * exposure) / monthly_margin)
            tenor_check = f"{int(breakeven_months)} months" if breakeven_months <= tenor else "Beyond tenor"
        
        cols[1].metric("Breakeven Period", tenor_check)

if __name__ == "__main__":
    main()
