import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Union

# Configure page settings
st.set_page_config(
    page_title="RT360 Risk Pricing Model",
    layout="wide",
    page_icon="💲"
)

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
    """Format currency amount with proper commas and decimals"""
    return f"{amount:,.2f}"

def get_borrower_risk_profile(malaa_score: int) -> str:
    """Categorize borrower risk based on Mala'a score"""
    if malaa_score < 500:
        return "High"
    elif 500 <= malaa_score < 650:
        return "Medium-High"
    elif 650 <= malaa_score < 750:
        return "Medium"
    else:
        return "Low"

def get_industry_risk_profile(industry: str) -> str:
    """Categorize industry risk based on industry factor"""
    factor = INDUSTRY_RISKS.get(industry, 0.75)
    if factor >= 0.85:
        return "High"
    elif 0.70 <= factor < 0.85:
        return "Medium"
    else:
        return "Low"

def get_product_risk_profile(product: str) -> str:
    """Categorize product risk based on product factor"""
    factor = PRODUCT_RISKS.get(product, 0.75)
    if factor >= 0.90:
        return "High"
    elif 0.70 <= factor < 0.90:
        return "Medium"
    else:
        return "Low"

def calculate_risk_score(params: Dict) -> float:
    """Calculate composite risk score with all factors"""
    product_factor = PRODUCT_RISKS[params["product"]]
    industry_factor = INDUSTRY_RISKS[params["industry"]]
    malaa_factor = 1.3 - (params["malaa_score"] - 300) * (0.8 / 600)
    
    if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = max(min(0.7 + 0.0035 * params["ltv"], 1.2), 0.8)
        risk_score = product_factor * industry_factor * malaa_factor * ltv_factor
    else:
        wc_to_sales = params["working_capital"] / max(params["sales"], 1)
        wcs_factor = min(1.45, max(0.85, 0.85 + 0.6 * min(wc_to_sales, 1.0)))
        utilization = UTILIZATION_FACTORS[params["industry"]]
        util_factor = max(min(1 - 0.15 * (0.8 - utilization), 1.15), 0.85)
        risk_score = product_factor * industry_factor * malaa_factor * wcs_factor * util_factor
    
    return max(min(risk_score, 2.0), 0.4)

def calculate_pricing(risk_score: float, params: Dict) -> List[Dict]:
    """Calculate pricing for all buckets (Low/Medium/High)"""
    buckets = ["Low", "Medium", "High"]
    multipliers = {"Low": 0.90, "Medium": 1.00, "High": 1.15}
    bands = {"Low": 50, "Medium": 75, "High": 100}
    
    results = []
    for bucket in buckets:
        risk_adjusted = max(min(risk_score * multipliers[bucket], 2.0), 0.4)
        
        base_spread = min(max(100 + 250 * (risk_adjusted - 1), 75), 500)
        spread_min = base_spread - bands[bucket]
        spread_max = base_spread + bands[bucket]
        
        rate_min = min(max(params["oibor_pct"] + spread_min / 100, 5.0), 10.0)
        rate_max = min(max(params["oibor_pct"] + spread_max / 100, 5.0), 10.0)
        
        # Calculate financial metrics
        avg_rate = (rate_min + rate_max) / 2
        fee_yield = params["fees_income_pct"]
        funding_cost = params["cost_of_funds_pct"]
        credit_cost = max(min(0.4 * risk_adjusted, 1.0), 0.2)
        opex = 0.4
        
        if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            E_avg = params["exposure"] * 0.55  # Amortizing approximation
            optimal_util = "–"
            
            # EMI calculation
            i_m = avg_rate / 100 / 12
            EMI = params["exposure"] * i_m * (1 + i_m) ** params["tenor"] / ((1 + i_m) ** params["tenor"] - 1)
            EMI_str = format_currency(EMI)
        else:
            utilization = UTILIZATION_FACTORS[params["industry"]]
            E_avg = params["exposure"] * utilization
            optimal_util = round(utilization * 100)
            EMI_str = "–"
        
        nim_pct = avg_rate + fee_yield - funding_cost - credit_cost - opex
        nii = (nim_pct / 100) * E_avg
        
        # Breakeven calculation
        if nim_pct <= 0:
            breakeven = "Breakeven not within tenor"
        else:
            C0 = 0.005 * params["exposure"]
            monthly_margin = (nim_pct / 100 / 12) * E_avg
            breakeven_months = np.ceil(C0 / monthly_margin)
            breakeven = int(breakeven_months) if breakeven_months <= params["tenor"] else "Breakeven not within tenor"
        
        results.append({
            "Bucket": bucket,
            "Min Spread": int(spread_min),
            "Max Spread": int(spread_max),
            "Min Rate": f"{rate_min:.2f}%",
            "Max Rate": f"{rate_max:.2f}%",
            "EMI": EMI_str,
            "NII": f"{nii:,.2f}",
            "NIM": f"{nim_pct:.2f}%",
            "Breakeven": breakeven,
            "Optimal Util": f"{optimal_util}%" if isinstance(optimal_util, int) else optimal_util,
            "Borrower Risk": get_borrower_risk_profile(params["malaa_score"]),
            "Industry Risk": get_industry_risk_profile(params["industry"]),
            "Product Risk": get_product_risk_profile(params["product"])
        })
    
    return results

def main():
    st.title(":blue[rt]:green[360] Risk-Adjusted Pricing Model")
    
    # Sidebar inputs
    with st.sidebar:
        st.header("Market & Portfolio")
        oibor_pct = st.number_input("OIBOR (%)", value=4.1, step=0.1)
        cost_of_funds_pct = st.number_input("Cost of Funds (%)", value=5.0, step=0.1)
        target_nim_pct = st.number_input("Target NIM (%)", value=2.5, step=0.1)
        fees_income_pct = 0.4
        
        st.header("Loan Parameters")
        product = st.selectbox("Product", list(PRODUCT_RISKS.keys()))
        industry = st.selectbox("Industry", list(INDUSTRY_RISKS.keys()))
        malaa_score = st.selectbox("Mala'a Score", range(300, 901, 50), index=6)
        
        exposure = st.number_input("Loan Quantum (OMR)", min_value=1000, value=1000000)
        st.caption(f"{exposure:,.2f} OMR")
        
        tenor = st.slider("Tenor (months)", 6, 360, 36)
        
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.slider("LTV (%)", 10, 95, 70)
        else:
            working_capital = st.number_input("Working Capital (OMR)", min_value=0, value=500000)
            st.caption(f"{working_capital:,.2f} OMR")
            sales = st.number_input("Sales (OMR)", min_value=0, value=2000000)
            st.caption(f"{sales:,.2f} OMR")

    # Main content
    with st.container():
        col1, col2 = st.columns(2)
        
        # Risk profile cards
        with col1:
            if st.sidebar.button("Fetch Pricing"):
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
                
                # Validate inputs
                if (product in ["Asset Backed Loan", "Term Loan", "Export Finance"] and "ltv" not in params):
                    st.error("LTV is required for fund-based products")
                    st.stop()
                
                if (product in ["Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"] 
                    and (params["working_capital"] <= 0 or params["sales"] <= 0)):
                    st.error("Working Capital and Sales must be positive for utilization products")
                    st.stop()
                
                # Calculate pricing
                risk_score = calculate_risk_score(params)
                prices = calculate_pricing(risk_score, params)
                
                # Display risk profile cards
                st.subheader("Risk Profile Summary")
                
                borrower_risk = get_borrower_risk_profile(params["malaa_score"])
                industry_risk = get_industry_risk_profile(params["industry"])
                product_risk = get_product_risk_profile(params["product"])
                
                st.metric("Borrower Risk", borrower_risk)
                st.metric("Industry Risk", industry_risk)
                st.metric("Product Risk", product_risk)
        
        # Pricing results
        with col2:
            if st.sidebar.button("Fetch Pricing"):
                st.subheader("Pricing Results")
                
                # Convert to DataFrame
                df = pd.DataFrame(prices)
                
                # Format columns
                columns = {
                    "Bucket": "Bucket",
                    "Min Spread": "Min Spread (bps)",
                    "Max Spread": "Max Spread (bps)",
                    "Min Rate": "Min Rate",
                    "Max Rate": "Max Rate",
                    "EMI": "EMI (OMR)",
                    "NII": "NII (OMR)",
                    "NIM": "NIM",
                    "Breakeven": "Breakeven (months)",
                    "Optimal Util": "Optimal Util",
                }
                
                # Display only the desired columns
                st.dataframe()
                    df[]
