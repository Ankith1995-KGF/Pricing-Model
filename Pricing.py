import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

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
.header-title {
    font-size: 2.5rem;
    text-align: center;
    margin-bottom: 1.5rem;
}
.rt-text { color: #1E90FF; }
.threesixty-text { color: #4CAF50; }
.risk-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 15px;
    background-color: #f8f9fa;
}
</style>
""", unsafe_allow_html=True)

def format_currency(amount: float) -> str:
    """Format currency amount (basic implementation)"""
    return f"{amount:,.2f}"

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
    "Mining": 0.45
}

def get_risk_levels(malaa_score: int, industry: str, product: str) -> tuple:
    """Categorize risk levels for borrower, industry and product"""
    borrower_level = (
        "High" if malaa_score < 500 else
        "Medium-High" if malaa_score < 650 else
        "Medium" if malaa_score < 750 else "Low"
    )
    
    industry_risk = INDUSTRY_RISKS.get(industry, 0.75)
    industry_level = (
        "High" if industry_risk >= 0.85 else
        "Medium" if industry_risk >= 0.70 else "Low"
    )
    
    product_risk = PRODUCT_RISKS.get(product, 0.75)
    product_level = (
        "High" if product_risk >= 0.90 else
        "Medium" if product_risk >= 0.70 else "Low"
    )
    
    return borrower_level, industry_level, product_level

def calculate_risk_score(
    product: str,
    industry: str,
    malaa_score: int,
    ltv: Optional[float] = None,
    working_capital: Optional[float] = None,
    sales: Optional[float] = None
) -> float:
    """Calculate composite risk score (0.4-2.0 range)"""
    product_factor = PRODUCT_RISKS.get(product, 1.0)
    industry_factor = INDUSTRY_RISKS.get(industry, 1.0)
    malaa_factor = 1.3 - (malaa_score - 300) * (0.8 / 600)
    
    if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = max(min(0.7 + 0.0035 * (ltv or 70), 1.2), 0.8)
        risk = product_factor * industry_factor * malaa_factor * ltv_factor
    else:
        wc_ratio = (working_capital or 0) / max(sales or 1, 1)
        wcs_factor = max(min(0.85 + 0.6 * min(wc_ratio, 1.0), 1.45), 0.85)
        util = UTILIZATION_FACTORS.get(industry, 0.5)
        util_factor = max(min(1 - 0.15 * (0.8 - util), 1.15), 0.85)
        risk = product_factor * industry_factor * malaa_factor * wcs_factor * util_factor
    
    return max(min(risk, 2.0), 0.4)

def calculate_pricing(
    risk_score: float,
    tenor: int,
    exposure: float,
    oibor_pct: float,
    cost_of_funds_pct: float,
    target_nim_pct: float,
    product: str,
    working_capital: Optional[float] = None,
    sales: Optional[float] = None
) -> List[Dict[str, Union[str, int, float]]]:
    """Calculate pricing for all risk buckets (Low/Medium/High)"""
    min_spread = 75  # Minimum core spread in bps
    bucket_params = {
        "Low": {"multiplier": 0.9, "band": 50},
        "Medium": {"multiplier": 1.0, "band": 75}, 
        "High": {"multiplier": 1.15, "band": 100}
    }
    
    results = []
    
    for bucket, config in bucket_params.items():
        adj_risk = max(min(risk_score * config["multiplier"], 2.0), 0.4)
        
        base_spread = max(min(100 + 250 * (adj_risk - 1), 500), min_spread)
        spread_min = max(base_spread - config["band"], min_spread)
        spread_max = max(base_spread + config["band"], spread_min + 1)
        
        rate_min = max(min(oibor_pct + spread_min / 100, 10.0), 5.0)
        rate_max = max(min(oibor_pct + spread_max / 100, 10.0), rate_min + 0.01)
        rate_avg = (rate_min + rate_max) / 2
        
        funding_cost = cost_of_funds_pct
        credit_cost = max(min(0.4 * adj_risk, 1.0), 0.2)
        fee_yield = 0.4
        opex = 0.4
        
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            # Fund-based product calculations
            monthly_rate = rate_avg / 1200
            emi = exposure * monthly_rate * (1 + monthly_rate)**tenor / ((1 + monthly_rate)**tenor - 1)
            emi_str = f"{emi:,.2f}"
            
            # Simplified NII calculation (annualized)
            avg_balance = exposure * 0.55  # Approximation
            nim_pct = rate_avg + fee_yield - funding_cost - credit_cost - opex
            nii = (nim_pct / 100) * avg_balance
            optimal_util = "–"
        else:
            # Utilization-based product calculations
            emi_str = "–"
            util = UTILIZATION_FACTORS.get(industry, 0.5)
            avg_balance = exposure * util
            nim_pct = rate_avg + fee_yield - funding_cost - credit_cost - opex
            nii = (nim_pct / 100) * avg_balance
            
            # Simplified optimal utilization calculation
            optimal_util = f"{int(util * 100)}%" if util else "–"
        
        # Breakeven calculation
        setup_cost = 0.005 * exposure
        if nim_pct > 0:
            monthly_margin = nii / min(tenor, 12)
            breakeven_months = np.ceil(setup_cost / monthly_margin)
            breakeven = str(int(breakeven_months)) if breakeven_months <= tenor else "Not within tenor"
        else:
            breakeven = "Not within tenor"
        
        results.append({
            "Bucket": bucket,
            "Float_Min_over_OIBOR_bps": int(spread_min),
            "Float_Max_over_OIBOR_bps": int(spread_max),
            "Rate_Min_%": f"{rate_min:.2f}",
            "Rate_Max_%": f"{rate_max:.2f}",
            "EMI_OMR": emi_str,
            "Net_Interest_Income_OMR": f"{nii:,.2f}",
            "NIM_%": f"{nim_pct:.2f}",
            "Breakeven_Months": breakeven,
            "Optimal_Utilization_%": optimal_util
        })
    
    return results

def main():
    """Main application function"""
    st.markdown('<div class="header-title"><span class="rt-text">rt</span><span class="threesixty-text">360</span> Risk-Adjusted Pricing Model</div>', 
                unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("Market & Portfolio")
        oibor = st.number_input("OIBOR (%)", min_value=0.0, value=4.1, step=0.1)
        funding_cost = st.number_input("Cost of Funds (%)", min_value=0.0, value=5.0, step=0.1)
        target_nim = st.number_input("Target NIM (%)", min_value=0.0, value=2.5, step=0.1)
        
        st.header("Loan Parameters")
        product = st.selectbox("Product", list(PRODUCT_RISKS.keys()))
        industry = st.selectbox("Industry", list(INDUSTRY_RISKS.keys()))
        malaa_score = st.selectbox("Mala'a Score", range(300, 901, 50), index=6)
        
        exposure = st.number_input("Loan Quantum (OMR)", min_value=1000, value=1000000, step=10000)
        st.caption(f"Amount: {format_currency(exposure)}")
        
        tenor = st.slider("Tenor (months)", 6, 360, 36)
        
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.slider("LTV (%)", 10, 95, 70)
            working_capital, sales = None, None
        else:
            ltv = None
            working_capital = st.number_input("Working Capital (OMR)", min_value=0, value=500000)
            st.caption(f"Amount: {format_currency(working_capital)}")
            sales = st.number_input("Sales (OMR)", min_value=0, value=2000000)
            st.caption(f"Amount: {format_currency(sales)}")
    
    if st.sidebar.button("Calculate Pricing"):
        with st.container():
            st.markdown('<div class="main-container">', unsafe_allow_html=True)
            
            # Input validation
            if product in ["Asset Backed Loan", "Term Loan", "Export Finance"] and ltv is None:
                st.error("LTV is required for fund-based products")
                st.stop()
                
            if product not in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                if working_capital is None or sales is None or working_capital <= 0 or sales <= 0:
                    st.error("Working Capital and Sales must be positive for utilization products")
                    st.stop()
            
            # Calculate risk score and pricing
            risk_score = calculate_risk_score(
                product=product,
                industry=industry,
                malaa_score=malaa_score,
                ltv=ltv,
                working_capital=working_capital,
                sales=sales
            )
            
            pricing = calculate_pricing(
                risk_score=risk_score,
                tenor=tenor,
                exposure=exposure,
                oibor_pct=oibor,
                cost_of_funds_pct=funding_cost,
                target_nim_pct=target_nim,
                product=product,
                working_capital=working_capital,
                sales=sales
            )
            
            # Display risk profile cards
            borrower_level, industry_level, product_level = get_risk_levels(malaa_score, industry, product)
            
            st.subheader("Risk Profile")
            cols = st.columns(3)
            cols[0].metric("Borrower Risk", borrower_level)
            cols[1].metric("Industry Risk", industry_level)
            cols[2].metric("Product Risk", product_level)
            
            # Display pricing results
            st.subheader("Pricing Results")
            df = pd.DataFrame(pricing).set_index("Bucket")
            
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "Float_Min_over_OIBOR_bps": st.column_config.NumberColumn("Min Spread (bps)", format="%d"),
                    "Float_Max_over_OIBOR_bps": st.column_config.NumberColumn("Max Spread (bps)", format="%d"),
                    "Rate_Min_%": "Min Rate",
                    "Rate_Max_%": "Max Rate",
                    "EMI_OMR": "EMI",
                    "Net_Interest_Income_OMR": "Net Interest Income",
                    "NIM_%": "NIM",
                    "Breakeven_Months": "Breakeven Period",
                    "Optimal_Utilization_%": "Optimal Utilization"
                }
            )
            
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
