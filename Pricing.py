import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Union, Optional

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

# Custom number to words conversion (fallback)
def amount_to_words(amount: float, currency: str = "OMR") -> str:
    """
    Converts numeric amount to words representation
    Args:
        amount: Numeric value to convert
        currency: Currency symbol (default "OMR")
    Returns:
        String representation of amount in words
    """
    if amount == 0:
        return f"Zero {currency}"
    
    units = ["", "One", "Two", "Three", "Four", "Five",
             "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen",
             "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "Ten", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety"]
    scales = ["", "Thousand", "Million"]
    
    def convert_less_than_thousand(n):
        if n < 10:
            return units[n]
        if n < 20:
            return teens[n - 10]
        if n < 100:
            return tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
        return units[n // 100] + " Hundred" + (" " + convert_less_than_thousand(n % 100) if n % 100 != 0 else "")
    
    amount_int = int(amount)
    parts = []
    
    for i in range(len(scales)):
        chunk = amount_int % 1000
        amount_int = amount_int // 1000
        if chunk != 0:
            part = convert_less_than_thousand(chunk)
            if scales[i]:
                part += " " + scales[i]
            parts.insert(0, part)
    
    amount_str = " ".join(parts) or "Zero"
    if amount != int(amount):
        decimal_part = int(round((amount - int(amount)) * 100))
        if decimal_part > 0:
            amount_str += f" and {decimal_part:02d}/100"
    
    return f"{amount_str} {currency}"

# Use num2words if available, otherwise fallback
try:
    from num2words import num2words
    def format_currency(amount: float) -> str:
        """Format amount using num2words if available"""
        return num2words(amount, to='currency', currency='OMR').title()
except ImportError:
    def format_currency(amount: float) -> str:
        """Fallback currency formatter"""
        return amount_to_words(amount)

# Constants and configuration
PRODUCT_RISKS = {
    "Asset Backed Loan": 1.00, "Term Loan": 0.90, "Export Finance": 0.80,
    "Vendor Finance": 0.60, "Supply Chain Finance": 0.55, "Trade Finance": 0.50
}

INDUSTRY_RISKS = {
    "Oil & Gas": 0.70, "Construction": 0.90, "Real Estate": 0.85,
    "Manufacturing": 0.80, "Trading": 0.75, "Logistics": 0.70,
    "Healthcare": 0.60, "Retail": 0.80, "Hospitality": 0.85,
    "Mining": 0.90, "Utilities": 0.55, "Agriculture": 0.85
}

UTILIZATION_FACTORS = {
    "Trading": 0.65, "Manufacturing": 0.55, "Construction": 0.40,
    "Logistics": 0.60, "Retail": 0.50, "Healthcare": 0.45,
    "Hospitality": 0.35, "Oil & Gas": 0.50, "Real Estate": 0.30
}

def get_borrower_risk(malaa_score: int) -> str:
    """Categorize borrower risk based on Mala'a score"""
    if malaa_score < 500: return "High"
    if malaa_score < 650: return "Medium-High"
    if malaa_score < 750: return "Medium"
    return "Low"

def get_product_risk(product: str) -> str:
    """Categorize product risk"""
    risk = PRODUCT_RISKS.get(product, 0.75)
    if risk >= 0.90: return "High"
    if risk >= 0.70: return "Medium"
    return "Low"

def get_industry_risk(industry: str) -> str:
    """Categorize industry risk"""
    risk = INDUSTRY_RISKS.get(industry, 0.75)
    if risk >= 0.85: return "High"
    if risk >= 0.70: return "Medium"
    return "Low"

def calculate_risk_score(product: str, industry: str, malaa_score: int, ltv: Optional[float] = None,
                       working_capital: Optional[float] = None, sales: Optional[float] = None) -> float:
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

def calculate_pricing(risk_score: float, params: Dict) -> List[Dict]:
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
        
        # Spread calculations
        base_spread = max(min(100 + 250 * (adj_risk - 1), 500), min_spread)
        spread_min = max(base_spread - config["band"], min_spread)
        spread_max = max(base_spread + config["band"], spread_min + 1)
        
        # Rate calculations (clamped to 5-10%)
        rate_min = max(min(params["oibor_pct"] + spread_min / 100, 10.0), 5.0)
        rate_max = max(min(params["oibor_pct"] + spread_max / 100, 10.0), rate_min + 0.01)
        rate_avg = (rate_min + rate_max) / 2
        
        # Financial metrics
        funding_cost = params["cost_of_funds_pct"]
        credit_cost = max(min(0.4 * adj_risk, 1.0), 0.2)
        fee_yield = params["fees_income_pct"]
        opex = 0.4
        
        if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            # Fund-based product calculations
            emi = params["exposure"] * (rate_avg/1200) * (1 + rate_avg/1200)**params["tenor"] / ((1 + rate_avg/1200)**params["tenor"] - 1)
            emi_str = f"{emi:,.2f}"
            
            # Amortization schedule for NII calculation
            balance = params["exposure"]
            sum_nii = 0
            for m in range(1, min(params["tenor"], 12) + 1):
                int_income = balance * (rate_avg/1200)
                fee_income = params["exposure"] * (fee_yield/1200)
                int_expense = balance * (funding_cost/1200)
                credit_expense = balance * (credit_cost/1200)
                opex_expense = balance * (opex/1200)
                net_margin = int_income + fee_income - int_expense - credit_expense - opex_expense
                sum_nii += net_margin
                balance -= emi - int_income  # Principal repayment
            
            aea = (params["exposure"] + balance) / 2 if params["tenor"] > 1 else params["exposure"]
            nim_pct = rate_avg + fee_yield - funding_cost - credit_cost - opex
            optimal_util = "–"
        else:
            # Utilization-based product calculations
            emi_str = "–"
            util = UTILIZATION_FACTORS.get(params["industry"], 0.5)
            e_avg = params["exposure"] * util
            nim_pct = rate_avg + fee_yield - funding_cost - credit_cost - opex
            sum_nii = (nim_pct/100) * e_avg
            
            # Calculate optimal utilization
            optimal_util = "–"
            for u in np.arange(0.3, 0.95, 0.01):
                util_factor = max(min(1 - 0.15 * (0.8 - u), 1.15), 0.85)
                wc_ratio = (params["working_capital"] or 0) / max(params["sales"] or 1, 1)
                wcs_factor = max(min(0.85 + 0.6 * min(wc_ratio, 1.0), 1.45), 0.85)
                temp_risk = max(min(adj_risk * util_factor / UTILIZATION_FACTORS.get(params["industry"], 0.5), 2.0), 0.4)
                temp_margin = (max(min(100 + 250 * (temp_risk - 1), 500), min_spread)/100 + 
                              params["oibor_pct"] + fee_yield - funding_cost - 
                              max(min(0.4 * temp_risk, 1.0), 0.2) - opex)
                if temp_margin >= params["target_nim_pct"]:
                    optimal_util = f"{int(u * 100)}%"
                    break
        
        # Breakeven calculation
        setup_cost = 0.005 * params["exposure"]
        if nim_pct > 0:
            breakeven_mths = np.ceil(setup_cost / (sum_nii/min(params["tenor"], 12)))
            breakeven = int(breakeven_mths) if breakeven_mths <= params["tenor"] else "Breakeven not within tenor"
        else:
            breakeven = "Breakeven not within tenor"
        
        results.append({
            "Bucket": bucket,
            "Float_Min_over_OIBOR_bps": int(max((rate_min - params["oibor_pct"]) * 100, min_spread)),
            "Float_Max_over_OIBOR_bps": int(max((rate_max - params["oibor_pct"]) * 100, min_spread + 1)),
            "Rate_Min_%": f"{rate_min:.2f}",
            "Rate_Max_%": f"{rate_max:.2f}",
            "EMI_OMR": emi_str,
            "Net_Interest_Income_OMR": f"{sum_nii:,.2f}",
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
        malaa_score = st.selectbox("Mala'a Score", range(300, 901, 50))
        
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
                return
            
            if product in ["Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"]:
                if working_capital is None or sales is None or working_capital <= 0 or sales <= 0:
                    st.error("Working Capital and Sales must be positive for utilization products")
                    return
            
            # Prepare parameters
            params = {
                "product": product,
                "industry": industry,
                "malaa_score": malaa_score,
                "oibor_pct": oibor,
                "cost_of_funds_pct": funding_cost,
                "target_nim_pct": target_nim,
                "fees_income_pct": 0.4,
                "exposure": exposure,
                "tenor": tenor,
                "ltv": ltv,
                "working_capital": working_capital,
                "sales": sales
            }
            
            # Display risk profiles
            st.subheader("Risk Profile")
            cols = st.columns(3)
            cols[0].metric("Borrower", get_borrower_risk(malaa_score))
            cols[1].metric("Industry", get_industry_risk(industry))
            cols[2].metric("Product", get_product_risk(product))
            
            # Calculate and display pricing
            risk_score = calculate_risk_score(**params)
            pricing = calculate_pricing(risk_score, params)
            
            st.subheader("Pricing Structure")
            pricing_df = pd.DataFrame(pricing).set_index("Bucket")
            
            # Configure column display
            column_config = {
                "Float_Min_over_OIBOR_bps": st.column_config.NumberColumn("Min Spread (bps)", format="%d"),
                "Float_Max_over_OIBOR_bps": st.column_config.NumberColumn("Max Spread (bps)", format="%d"),
                "Rate_Min_%": "Min Rate",
                "Rate_Max_%": "Max Rate",
                "EMI_OMR": "EMI",
                "Net_Interest_Income_OMR": "Net Interest Income",
                "NIM_%": "NIM",
                "Breakeven_Months": "Breakeven",
                "Optimal_Utilization_%": "Optimal Utilization"
            }
            
            st.dataframe(
                pricing_df,
                use_container_width=True,
                column_config=column_config
            )
            
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
