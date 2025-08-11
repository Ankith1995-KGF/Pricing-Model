import streamlit as st
import pandas as pd
import numpy as np

# Configure page settings
st.set_page_config(
    page_title="RT360 Risk Pricing Model",
    layout="wide",
    page_icon="💲"
)

# Custom CSS for styling
st.markdown("""
<style>
.main-container {
    border: 4px solid #1E90FF;
    padding: 2rem;
    border-radius: 10px;
    background-color: white;
    margin-top: 1rem;
}
.result-container {
    margin-top: 2rem;
}
.rt-text { color: #1E90FF; }
.threesixty-text { color: #43A047; }
.market-info {
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# Constants for risk multipliers
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

def format_currency(amount: float) -> str:
    """Format currency amount with thousands separators"""
    return f"{amount:,.2f}"

def calculate_risk_score(params: dict) -> float:
    """Calculate composite risk score with all factors."""
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

def calculate_pricing(risk_score: float, params: dict) -> list:
    """Calculate pricing for all buckets (Low/Medium/High)"""
    buckets = ["Low", "Medium", "High"]
    multipliers = {"Low": 0.9, "Medium": 1.0, "High": 1.15}
    bands = {"Low": 50, "Medium": 75, "High": 100}
    
    results = []
    
    for bucket in buckets:
        risk_adjusted = max(min(risk_score * multipliers[bucket], 2.0), 0.4)
        
        base_spread = min(max(100 + 250 * (risk_adjusted - 1), 50), 500)
        spread_min = base_spread - bands[bucket]
        spread_max = base_spread + bands[bucket]
        
        rate_min = min(max(params["oibor_pct"] + spread_min / 100, 5.0), 10.0)
        rate_max = min(max(params["oibor_pct"] + spread_max / 100, 5.0), 10.0)
        
        # Net Interest Income calculation
        avg_rate = (rate_min + rate_max) / 2
        fee_yield = params["fees_income_pct"]
        funding_cost = params["cost_of_funds_pct"]
        credit_cost = min(max(0.4 * risk_adjusted, 0.2), 1.0)
        opex = 0.4
        
        if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            E_avg = params["exposure"] * 0.55  # Amortizing approximation
            optimal_util = "–"
        else:
            utilization = UTILIZATION_FACTORS[params["industry"]]
            E_avg = params["exposure"] * utilization
            optimal_util = round(utilization * 100)
        
        nim_net_pct = avg_rate + fee_yield - funding_cost - credit_cost - opex
        nii_omr = (nim_net_pct / 100) * E_avg
        
        # Breakeven calculation
        if nim_net_pct <= 0:
            breakeven_months = "Breakeven not within tenor"
        else:
            C0 = 0.005 * params["exposure"]  # Upfront cost
            monthly_margin = (nim_net_pct / 100 / 12) * E_avg
            breakeven_months = np.ceil(C0 / monthly_margin)
            breakeven_months = int(breakeven_months) if breakeven_months <= params["tenor"] else "Breakeven not within tenor"
        
        results.append({
            "Bucket": bucket,
            "Float_Min_over_OIBOR_bps": int(spread_min),
            "Float_Max_over_OIBOR_bps": int(spread_max),
            "Rate_Min_%": f"{rate_min:.2f}",
            "Rate_Max_%": f"{rate_max:.2f}",
            "Net_Interest_Income_OMR": format_currency(nii_omr),
            "Breakeven_Months": breakeven_months,
            "Optimal_Utilization_%": optimal_util
        })
    
    return results

def main():
    st.title(":blue[rt]:green[360] Risk-Adjusted Pricing Model")
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("Market & Portfolio")
        oibor_pct = st.number_input("OIBOR (%)", value=4.1, step=0.1)
        cost_of_funds_pct = st.number_input("Cost of Funds (%)", value=5.0, step=0.1)
        target_nim_pct = st.number_input("Target NIM (%)", value=2.5, step=0.1)
        fees_income_pct = 0.4  # Fixed
        
        st.header("Loan Parameters")
        product = st.selectbox("Product", list(PRODUCT_RISKS.keys()))
        industry = st.selectbox("Industry", list(INDUSTRY_RISKS.keys()))
        malaa_score = st.selectbox("Mala'a Score", range(300, 901, 50), index=6)
        
        exposure = st.number_input("Loan Quantum (OMR)", min_value=1000, value=1000000)
        st.caption(f"Amount: {exposure:,.2f} OMR")
        
        tenor = st.slider("Tenor (months)", 6, 360, 36)
        
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.slider("LTV (%)", 10, 95, 70)
        else:
            working_capital = st.number_input("Working Capital (OMR)", min_value=0, value=500000)
            st.caption(f"Amount: {working_capital:,.2f} OMR")
            sales = st.number_input("Sales (OMR)", min_value=0, value=2000000)
            st.caption(f"Amount: {sales:,.2f} OMR")

    # Main content area
    with st.container():
        st.markdown('<div class="main-container">', unsafe_allow_html=True)
        
        # Only calculate when button is clicked
        if st.sidebar.button("Calculate Pricing"):
            # Validate inputs
            if (product in ["Asset Backed Loan", "Term Loan", "Export Finance"] and "ltv" not in locals()):
                st.error("LTV is required for fund-based products")
                st.stop()
                
            if (product in ["Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"] 
                and ("working_capital" not in locals() or working_capital <= 0 or "sales" not in locals() or sales <= 0)):
                st.error("Working Capital and Sales must be positive for utilization products")
                st.stop()
            
            # Prepare parameters
            params = {
                "product": product,
                "industry": industry,
                "malaa_score": malaa_score,
                "exposure": exposure,
                "tenor": tenor,
                "oibor_pct": oibor_pct,
                "cost_of_funds_pct": cost_of_funds_pct,
                "target_nim_pct": target_nim_pct,
                "fees_income_pct": fees_income_pct
            }
            
            if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                params["ltv"] = ltv
            else:
                params["working_capital"] = working_capital
                params["sales"] = sales
            
            # Calculate pricing
            risk_score = calculate_risk_score(params)
            pricing_results = calculate_pricing(risk_score, params)
            
            # Display results in main content area
            st.markdown('<div class="result-container">', unsafe_allow_html=True)
            st.subheader("Pricing Results")
            
            # Convert results to DataFrame
            results_df = pd.DataFrame(pricing_results).set_index("Bucket")
            
            # Display table with formatting
            st.dataframe(
                results_df,
                column_config={
                    "Float_Min_over_OIBOR_bps": st.column_config.NumberColumn("Min Spread (bps)", format="%d"),
                    "Float_Max_over_OIBOR_bps": st.column_config.NumberColumn("Max Spread (bps)", format="%d"),
                    "Rate_Min_%": "Min Rate (%)",
                    "Rate_Max_%": "Max Rate (%)",
                    "Net_Interest_Income_OMR": st.column_config.NumberColumn("NII (OMR)", format="%.2f"),
                    "Breakeven_Months": "Breakeven (months)",
                    "Optimal_Utilization_%": "Optimal Util (%)"
                },
                use_container_width=True
            )
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
