import streamlit as st
import pandas as pd
import numpy as np

# Custom number to words converter (fallback)
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
    
    amount_int = int(amount)
    decimal_part = int(round((amount - amount_int) * 100))
    
    chunks = []
    scale_index = 0
    
    while amount_int > 0:
        chunk = amount_int % 1000
        if chunk != 0:
            chunk_text = ""
            if chunk >= 100:
                chunk_text += units[chunk // 100] + " Hundred"
                chunk = chunk % 100
                if chunk > 0:
                    chunk_text += " and "
            if chunk >= 20:
                chunk_text += tens[chunk // 10]
                if chunk % 10 > 0:
                    chunk_text += "-" + units[chunk % 10]
            elif chunk >= 10:
                chunk_text += teens[chunk - 10]
            else:
                chunk_text += units[chunk]
                
            if scale_index > 0:
                chunk_text += " " + scales[scale_index]
            chunks.insert(0, chunk_text)
        amount_int = amount_int // 1000
        scale_index += 1
    
    amount_str = " ".join(chunks) if chunks else "Zero"
    if decimal_part > 0:
        amount_str += f" and {decimal_part:02d}/100"
    
    return f"{amount_str} {currency}".title()

# Use num2words if available, otherwise fallback to custom converter
try:
    from num2words import num2words
    def format_currency(amount):
        return num2words(amount, to='currency', currency='OMR').title()
except ImportError:
    format_currency = amount_to_words

# Constants
PRODUCT_RISKS = {
    "Asset Backed Loan": 1.00,
    "Term Loan": 0.90,
    "Export Finance": 0.80,
    "Vendor Finance": 0.60,
    "Supply Chain Finance": 0.55,
    "Trade Finance": 0.50,
    "Working Capital": 0.65
}

INDUSTRY_RISKS = {
    "Oil & Gas": 0.70,
    "Construction": 0.90,
    "Real Estate": 0.85,
    "Manufacturing": 0.80,
    "Trading": 0.75,
    "Logistics": 0.70,
    "Healthcare": 0.60,
    "Retail": 0.80,
    "Hospitality": 0.85,
    "Mining": 0.90,
    "Utilities": 0.55,
    "Agriculture": 0.85
}

UTILIZATION_FACTORS = {
    "Trading": 0.65,
    "Manufacturing": 0.55,
    "Construction": 0.40,
    "Logistics": 0.60,
    "Retail": 0.50,
    "Healthcare": 0.45,
    "Hospitality": 0.35,
    "Oil & Gas": 0.50,
    "Real Estate": 0.30,
    "Mining": 0.45,
    "Utilities": 0.55,
    "Agriculture": 0.40
}

# Configure page settings
st.set_page_config(
    page_title="RT360 Risk Pricing Model",
    layout="wide",
    page_icon="💲"
)

# Custom CSS
st.markdown("""
<style>
.main-container {
    border: 4px solid #1E90FF;
    padding: 2rem;
    border-radius: 10px;
}
.rt-text { color: #1E90FF; }
.threesixty-text { color: #43A047; }
.stTabs [role="tablist"] {
    margin-bottom: 1rem;
}
.stMarkdown h3 {
    margin-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

# Risk Calculation
def calculate_risk_score(params):
    """Calculate composite risk score with all factors"""
    product_factor = PRODUCT_RISKS[params["product"]]
    industry_factor = INDUSTRY_RISKS[params["industry"]]
    malaa_factor = 1.3 - (params["malaa_score"] - 300) * (0.8 / 600)
    
    if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = 0.7 + 0.0035 * params["ltv"]
        ltv_factor = max(min(ltv_factor, 1.2), 0.8)
        risk_score = product_factor * industry_factor * malaa_factor * ltv_factor
    else:
        wc_to_sales = params["working_capital"] / max(params["sales"], 1)
        wcs_factor = min(1.45, max(0.85, 0.85 + 0.6 * min(wc_to_sales, 1.0)))
        utilization = UTILIZATION_FACTORS[params["industry"]]
        util_factor = 1 - 0.15 * (0.8 - utilization)
        util_factor = max(min(util_factor, 1.15), 0.85)
        risk_score = product_factor * industry_factor * malaa_factor * wcs_factor * util_factor
    
    return max(min(risk_score, 2.0), 0.4)

# Pricing Calculation
def calculate_pricing(risk_score, params):
    """Calculate all pricing metrics"""
    base_spread = 100 + 250 * (risk_score - 1)
    base_spread = min(max(base_spread, 50), 500)
    
    effective_rate = params["benchmark_rate"] + (base_spread / 100)
    effective_rate = min(max(effective_rate, 5.0), 10.0)
    
    if risk_score < 0.85:
        bucket = "Low Risk"
        rate_band = 0.5
    elif risk_score <= 1.15:
        bucket = "Medium Risk"
        rate_band = 0.75
    else:
        bucket = "High Risk"
        rate_band = 1.0
    
    min_rate = max(5.0, effective_rate - rate_band)
    max_rate = min(10.0, effective_rate + rate_band)
    
    fee_yield = 0.004
    credit_cost = min(0.01, max(0.002, 0.004 * risk_score))
    opex = 0.004
    
    nim = effective_rate + fee_yield - params["cost_of_funds"] - credit_cost - opex
    
    breakeven_rate = params["cost_of_funds"] + credit_cost + opex - fee_yield
    breakeven_rate = min(max(breakeven_rate, 5.0), 10.0)
    
    monthly_margin = (effective_rate/1200 + fee_yield/1200 - params["cost_of_funds"]/1200 - 
                     credit_cost/1200 - opex/1200) * params["exposure"]
    
    upfront_cost = 0.005 * params["exposure"]
    
    if monthly_margin <= 0:
        tenor_check = "Not viable"
    else:
        breakeven_months = np.ceil(upfront_cost / monthly_margin)
        tenor_check = f"{int(breakeven_months)} months" if breakeven_months <= params["tenor"] else "Beyond tenor"
    
    return {
        "risk_score": risk_score,
        "bucket": bucket,
        "rate_range": f"{min_rate:.2f}% - {max_rate:.2f}%",
        "effective_rate": effective_rate,
        "nim": nim,
        "breakeven_rate": breakeven_rate,
        "tenor_check": tenor_check
    }

# Main App
def main():
    st.title(":blue[rt]:green[360] Risk-Adjusted Pricing Model")
    
    with st.sidebar:
        st.header("Input Parameters")
        
        product = st.selectbox("Product", list(PRODUCT_RISKS.keys()))
        industry = st.selectbox("Industry", list(INDUSTRY_RISKS.keys()))
        malaa_score = st.selectbox("Mala'a Score", range(300, 901, 50), index=6)
        
        st.subheader("Loan Details")
        exposure = st.number_input("Loan Amount (OMR)", min_value=1000, value=1000000)
        st.caption(format_currency(exposure))
        
        tenor = st.number_input("Tenor (months)", min_value=6, max_value=120, value=36)
        
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.slider("LTV (%)", min_value=10, max_value=95, value=70)
        else:
            working_capital = st.number_input("Working Capital (OMR)", min_value=0, value=500000)
            st.caption(format_currency(working_capital))
            
            sales = st.number_input("Annual Sales (OMR)", min_value=0, value=2000000)
            st.caption(format_currency(sales))
        
        st.subheader("Bank Parameters")
        benchmark_rate = st.number_input("Benchmark Rate (%)", min_value=0.0, value=4.1, step=0.1)
        cost_of_funds = st.number_input("Cost of Funds (%)", min_value=0.0, value=5.0, step=0.1)
    
    # Prepare parameters
    params = {
        "product": product,
        "industry": industry,
        "malaa_score": malaa_score,
        "exposure": exposure,
        "tenor": tenor,
        "benchmark_rate": benchmark_rate,
        "cost_of_funds": cost_of_funds
    }
    
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        params["ltv"] = ltv
    else:
        params["working_capital"] = working_capital
        params["sales"] = sales
    
    # Calculate risk and pricing
    risk_score = calculate_risk_score(params)
    pricing = calculate_pricing(risk_score, params)
    
    # Create tabs
    tab1, tab2 = st.tabs(["Overview", "Pricing Table"])
    
    with tab1:
        st.subheader("Risk Assessment")
        cols = st.columns(3)
        cols[0].metric("Risk Score", f"{risk_score:.2f}")
        cols[1].metric("Risk Bucket", pricing["bucket"])
        cols[2].metric("Market Rate Band", "5.0% - 10.0%")
        
        st.subheader("Pricing Summary")
        cols = st.columns(3)
        cols[0].metric("Rate Range", pricing["rate_range"])
        cols[1].metric("Effective Rate", f"{pricing['effective_rate']:.2f}%")
        cols[2].metric("Net Margin", f"{pricing['nim']:.2f}%")
        
        st.subheader("Breakeven Analysis")
        cols = st.columns(2)
        cols[0].metric("Breakeven Rate", f"{pricing['breakeven_rate']:.2f}%")
        cols[1].metric("Breakeven Period", pricing["tenor_check"])
    
    with tab2:
        st.subheader("Pricing Buckets")
        
        # Calculate for all three risk buckets
        buckets = []
        for bucket_params in [
            {"product": "Trade Finance", "industry": "Utilities", "malaa_score": 850, "working_capital": 50000, "sales": 2000000},
            {"product": "Term Loan", "industry": "Manufacturing", "malaa_score": 700, "ltv": 70}, 
            {"product": "Asset Backed Loan", "industry": "Construction", "malaa_score": 400, "ltv": 85}
        ]:
            test_params = params.copy()
            test_params.update(bucket_params)
            test_score = calculate_risk_score(test_params)
            bucket_data = calculate_pricing(test_score, test_params)
            bucket_data["bucket"] = bucket_params["product"]
            buckets.append(bucket_data)
        
        # Display pricing table
        pricing_data = {
            "Bucket": ["Low Risk", "Medium Risk", "High Risk"],
            "Rate Range": [b["rate_range"] for b in buckets],
            "Effective Rate": [f"{b['effective_rate']:.2f}%" for b in buckets],
            "NIM": [f"{b['nim']:.2f}%" for b in buckets],
            "Breakeven Rate": [f"{b['breakeven_rate']:.2f}%" for b in buckets],
            "Tenor Check": [b["tenor_check"] for b in buckets]
        }
        
        st.dataframe(
            pd.DataFrame(pricing_data),
            hide_index=True,
            use_container_width=True
        )
        
        # Download button
        csv = pd.DataFrame(pricing_data).to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Pricing Table",
            csv,
            "pricing_table.csv",
            "text/csv"
        )
        
        # Test scenarios
        st.subheader("Test Scenarios")
        cols = st.columns(3)
        with cols[0]:
            if st.button("Load Low Risk Scenario"):
                for key, value in {"product": "Trade Finance", "industry": "Utilities", "malaa_score": 850, "working_capital": 50000, "sales": 2000000}.items():
                    st.session_state[key] = value
                st.rerun()
        with cols[1]:
            if st.button("Load Medium Risk Scenario"):
                for key, value in {"product": "Term Loan", "industry": "Manufacturing", "malaa_score": 700, "ltv": 70}.items():
                    st.session_state[key] = value
                st.rerun()
        with cols[2]:
            if st.button("Load High Risk Scenario"):
                for key, value in {"product": "Asset Backed Loan", "industry": "Construction", "malaa_score": 400, "ltv": 85}.items():
                    st.session_state[key] = value
                st.rerun()

if __name__ == "__main__":
    main()
