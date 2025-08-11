import streamlit as st
import pandas as pd
import numpy as np
from num2words import num2words

# App Configuration
st.set_page_config(page_title="RT360 Risk Pricing", layout="wide")

# Custom CSS for styling
st.markdown("""
<style>
    .main {
        border: 4px solid #1E90FF;
        padding: 20px;
        border-radius: 10px;
    }
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        border: 1px solid #1E90FF;
    }
    .stSelectbox>div>div>select {
        border: 1px solid #1E90FF;
    }
    .stSlider>div>div>div>div {
        background-color: #1E90FF;
    }
    .stMarkdown h1 {
        color: #1E90FF;
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

UTILIZATION_FACTORS = {
    "Oil & Gas": 0.50,
    "Construction": 0.40,
    "Trading": 0.65,
    "Manufacturing": 0.55,
    "Logistics": 0.60,
    "Healthcare": 0.45,
    "Hospitality": 0.35,
    "Retail": 0.50,
    "Real Estate": 0.30,
    "Mining": 0.50,
    "Utilities": 0.40,
    "Agriculture": 0.45
}

# Helper Functions
def format_amount_in_words(amount):
    try:
        return num2words(amount, to='currency', currency='OMR').title()
    except:
        return "Zero OMR"

def calculate_risk_score(params):
    # Product risk factor
    product_factor = PRODUCT_RISKS.get(params["product"], 0.5)
    
    # Industry risk factor
    industry_factor = INDUSTRY_RISKS.get(params["industry"], 0.75)
    
    # Mala'a score factor
    malaa_factor = 1.3 - (params["malaa_score"] - 300) * (0.8 / 600)
    
    # Product-specific factors
    if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = 0.7 + 0.0035 * params.get("ltv", 70)
        ltv_factor = max(min(ltv_factor, 1.2), 0.8)
        risk_score = product_factor * industry_factor * malaa_factor * ltv_factor
    else:
        wc_to_sales = params.get("working_capital", 0) / max(params.get("sales", 1), 1)
        wc_to_sales = min(wc_to_sales, 1.0)
        wcs_factor = 0.85 + 0.6 * wc_to_sales
        
        utilization = UTILIZATION_FACTORS.get(params["industry"], 0.5)
        util_factor = 1 - 0.15 * (0.8 - utilization)
        util_factor = max(min(util_factor, 1.15), 0.85)
        
        risk_score = product_factor * industry_factor * malaa_factor * wcs_factor * util_factor
    
    return max(min(risk_score, 2.0), 0.4)

def calculate_pricing(params, risk_score):
    # Base spread calculation
    base_spread = 100 + 250 * (risk_score - 1)
    base_spread = max(min(base_spread, 500), 50)
    
    # Effective rate
    effective_rate = params["benchmark_rate_pct"] + (base_spread / 100)
    effective_rate = max(min(effective_rate, 10.0), 5.0)
    
    # Bucket assignment
    if risk_score < 0.85:
        bucket = "Low Risk"
        rate_band = 50
    elif risk_score <= 1.15:
        bucket = "Medium Risk"
        rate_band = 75
    else:
        bucket = "High Risk"
        rate_band = 100
    
    # Rate range
    min_rate = effective_rate - (rate_band / 100)
    max_rate = effective_rate + (rate_band / 100)
    min_rate = max(min_rate, 5.0)
    max_rate = min(max_rate, 10.0)
    
    # NIM calculation
    credit_cost = 0.004 * min(max(risk_score, 0.5), 2.5)
    fee_yield = 0.004
    nim = effective_rate + fee_yield - params["cost_of_funds_pct"] - credit_cost - 0.004
    
    # Breakeven calculation
    breakeven_rate = params["cost_of_funds_pct"] + credit_cost + 0.004 - fee_yield
    breakeven_rate = max(min(breakeven_rate, 10.0), 5.0)
    
    # Tenor breakeven check
    if params.get("exposure", 0) > 0 and params.get("tenor", 0) > 0:
        monthly_net_margin = (effective_rate/12 + fee_yield/12 - 
                             params["cost_of_funds_pct"]/12 - credit_cost/12 - 0.004/12) * params["exposure"]
        if monthly_net_margin <= 0:
            tenor_check = "Breakeven not within the tenor"
        else:
            breakeven_months = np.ceil((0.005 * params["exposure"]) / monthly_net_margin)
            tenor_check = f"Breakeven at ~{int(breakeven_months)} months"
    else:
        tenor_check = "N/A"
    
    return {
        "risk_score": round(risk_score, 2),
        "bucket": bucket,
        "rate_range": f"{min_rate:.2f}% - {max_rate:.2f}%",
        "effective_rate": f"{effective_rate:.2f}%",
        "nim": f"{nim:.2f}%",
        "breakeven_rate": f"{breakeven_rate:.2f}%",
        "tenor_check": tenor_check,
        "rate_band": rate_band
    }

# App Layout
def main():
    st.title(":blue[rt]:green[360] Risk-Adjusted Pricing Model")
    
    with st.sidebar:
        st.header("Input Parameters")
        
        # Product selection
        product = st.selectbox(
            "Product Type",
            list(PRODUCT_RISKS.keys()),
            key="product"
        )
        
        # Industry selection
        industry = st.selectbox(
            "Industry",
            list(INDUSTRY_RISKS.keys()),
            key="industry"
        )
        
        # Mala'a score
        malaa_score = st.selectbox(
            "Mala'a Score",
            range(300, 901, 50),
            index=6,  # Default to 600
            key="malaa_score"
        )
        
        # Loan parameters
        exposure = st.number_input(
            "Loan Quantum (OMR)",
            min_value=0,
            value=100000,
            key="exposure"
        )
        st.caption(f"*{format_amount_in_words(exposure)}*")
        
        tenor = st.number_input(
            "Tenor (months)",
            min_value=6,
            max_value=120,
            value=36,
            key="tenor"
        )
        
        # Product-specific inputs
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.slider(
                "LTV (%)",
                min_value=0,
                max_value=90,
                value=70,
                key="ltv"
            )
        else:
            working_capital = st.number_input(
                "Working Capital (OMR)",
                min_value=0,
                value=50000,
                key="working_capital"
            )
            st.caption(f"*{format_amount_in_words(working_capital)}*")
            
            sales = st.number_input(
                "Annual Sales (OMR)",
                min_value=0,
                value=250000,
                key="sales"
            )
            st.caption(f"*{format_amount_in_words(sales)}*")
        
        # System parameters
        benchmark_rate_pct = st.number_input(
            "Benchmark Rate (OMIBOR, %)",
            min_value=0.0,
            max_value=20.0,
            value=4.1,
            step=0.1,
            key="benchmark_rate_pct"
        )
        
        cost_of_funds_pct = st.number_input(
            "Cost of Funds (%)",
            min_value=0.0,
            max_value=20.0,
            value=5.0,
            step=0.1,
            key="cost_of_funds_pct"
        )
        
        show_details = st.checkbox(
            "Show Detailed Calculations",
            key="show_details"
        )
    
    # Main content
    with st.container():
        tab1, tab2 = st.tabs(["Overview", "Pricing Table"])
        
        with tab1:
            st.header("Risk Assessment")
            
            # Calculate results
            input_params = {
                "product": st.session_state.product,
                "industry": st.session_state.industry,
                "malaa_score": st.session_state.malaa_score,
                "benchmark_rate_pct": st.session_state.benchmark_rate_pct,
                "cost_of_funds_pct": st.session_state.cost_of_funds_pct,
                "tenor": st.session_state.tenor,
                "exposure": st.session_state.exposure
            }
            
            if st.session_state.product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                input_params["ltv"] = st.session_state.ltv
            else:
                input_params["working_capital"] = st.session_state.working_capital
                input_params["sales"] = st.session_state.sales
            
            risk_score = calculate_risk_score(input_params)
            pricing = calculate_pricing(input_params, risk_score)
            
            # Display results
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Risk Score", f"{pricing['risk_score']:.2f}")
                st.metric("Risk Bucket", pricing["bucket"])
            
            with col2:
                st.metric("Market Rate Band", "5.00% - 10.00%")
                st.metric("Net NIM Target", "2.40%")
            
            st.header("Pricing Summary")
            cols = st.columns(3)
            cols[0].metric("Rate Range", pricing["rate_range"])
            cols[1].metric("Effective Rate", pricing["effective_rate"])
            cols[2].metric("Net Interest Margin", pricing["nim"])
            
            st.header("Breakeven Analysis")
            cols = st.columns(2)
            cols[0].metric("Breakeven Rate", pricing["breakeven_rate"])
            cols[1].metric("Tenor Assessment", pricing["tenor_check"])
            
            if show_details:
                st.subheader("Detailed Calculations")
                st.write(f"Base Risk Score: {risk_score:.2f}")
                st.write(f"Product Factor: {PRODUCT_RISKS[st.session_state.product]:.2f}")
                st.write(f"Industry Factor: {INDUSTRY_RISKS[st.session_state.industry]:.2f}")
                st.write(f"Mala'a Factor: {1.3 - (st.session_state.malaa_score - 300) * (0.8 / 600):.2f}")
                
                if st.session_state.product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                    ltv_factor = 0.7 + 0.0035 * st.session_state.ltv
                    st.write(f"LTV Factor: {ltv_factor:.2f}")
                else:
                    wc_to_sales = st.session_state.working_capital / max(st.session_state.sales, 1)
                    wcs_factor = 0.85 + 0.6 * min(wc_to_sales, 1.0)
                    st.write(f"WC/Sales Factor: {wcs_factor:.2f}")
                    
                    utilization = UTILIZATION_FACTORS[st.session_state.industry]
                    util_factor = 1 - 0.15 * (0.8 - utilization)
                    st.write(f"Utilization Factor: {util_factor:.2f}")
        
        with tab2:
            # Pricing table with all buckets
            st.header("Pricing Buckets")
            
            # Calculate for all buckets
            buckets = []
            for bucket in ["Low Risk", "Medium Risk", "High Risk"]:
                temp_params = input_params.copy()
                
                if bucket == "Low Risk":
                    temp_score = 0.7
                elif bucket == "Medium Risk":
                    temp_score = 1.0
                else:
                    temp_score = 1.3
                
                bucket_data = calculate_pricing(temp_params, temp_score)
                bucket_data["bucket"] = bucket
                buckets.append(bucket_data)
            
            # Create dataframe
            df = pd.DataFrame({
                "Bucket": [b["bucket"] for b in buckets],
                "Interest Rate Range": [b["rate_range"] for b in buckets],
                "Breakeven Rate": [b["breakeven_rate"] for b in buckets],
                "NIM": [b["nim"] for b in buckets],
                "Tenor Check": [b["tenor_check"] for b in buckets]
            })
            
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
            
            st.caption("Rates clamped to 5-10% (market band). Fees assumed 0.4% p.a.")
            
            # Add export option
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Export Pricing Table",
                csv,
                "rt360_pricing_table.csv",
                "text/csv"
            )
            
            # Test scenarios
            st.header("Test Scenarios")
            col1, col2, col3 = st.columns(3)
            
            # Low risk scenario
            with col1:
                if st.button("Low Risk Test"):
                    st.session_state.product = "Trade Finance"
                    st.session_state.industry = "Utilities"
                    st.session_state.malaa_score = 850
                    st.session_state.working_capital = 50000
                    st.session_state.sales = 250000
                    st.experimental_rerun()
            
            # Medium risk scenario
            with col2:
                if st.button("Medium Risk Test"):
                    st.session_state.product = "Term Loan"
                    st.session_state.industry = "Manufacturing"
                    st.session_state.malaa_score = 700
                    st.session_state.ltv = 70
                    st.experimental_rerun()
            
            # High risk scenario
            with col3:
                if st.button("High Risk Test"):
                    st.session_state.product = "Asset Backed Loan"
                    st.session_state.industry = "Construction"
                    st.session_state.malaa_score = 400
                    st.session_state.ltv = 85
                    st.experimental_rerun()

if __name__ == "__main__":
    main()

