import streamlit as st
import pandas as pd
import numpy as np

# Custom number to words converter (fallback)
def amount_to_words(amount: float, currency: str = "OMR") -> str:
    """Convert numeric amount to words representation without num2words."""
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
    def format_currency(amount: float) -> str:
        return num2words(amount, to='currency', currency='OMR').title()
except ImportError:
    format_currency = amount_to_words

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

# Industry median utilization
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

# Custom CSS for styling
st.markdown("""
<style>
.main-container {
    border: 4px solid #1E90FF;
    padding: 2rem;
    border-radius: 10px;
    background-color: white;
}
.rt-text { color: #1E90FF; }
.threesixty-text { color: #43A047; }
</style>
""", unsafe_allow_html=True)

# Risk Calculation
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

# Pricing Calculation
def calculate_pricing(risk_score: float, params: dict) -> dict:
    """Calculate all pricing metrics."""
    base_spread_bps = 100 + 250 * (risk_score - 1)
    base_spread_bps = min(max(base_spread_bps, 50), 500)
    
    effective_rate = params["oibor_pct"] + (base_spread_bps / 100)
    effective_rate = min(max(effective_rate, 5.0), 10.0)
    
    # Define buckets
    risk_multipliers = {"Low": 0.90, "Medium": 1.00, "High": 1.15}
    pricing_results = []
    
    for bucket, multiplier in risk_multipliers.items():
        risk_b = max(min(risk_score * multiplier, 2.0), 0.4)
        base_spread_bps_b = min(max(100 + 250 * (risk_b - 1), 50), 500)
        
        band_bps = {"Low": 50, "Medium": 75, "High": 100}[bucket]
        spread_min_bps_b = base_spread_bps_b - band_bps
        spread_max_bps_b = base_spread_bps_b + band_bps
        
        rate_min_pct_b = min(max(params["oibor_pct"] + spread_min_bps_b / 100, 5.0), 10.0)
        rate_max_pct_b = min(max(params["oibor_pct"] + spread_max_bps_b / 100, 5.0), 10.0)
        
        # Calculate NII
        fee_yield_pct = params["fees_income_pct"]
        funding_cost_pct = params["cost_of_funds_pct"]
        credit_cost_pct_b = min(max(0.4 * risk_b / 100, 0.2), 1.0)
        opex_pct = 0.4
        
        E_avg = params["exposure"] * 0.55 if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"] else params["exposure"] * (UTILIZATION_FACTORS[params["industry"]] if params["industry"] in UTILIZATION_FACTORS else 0.5)
        
        nim_net_pct_b = (rate_min_pct_b + rate_max_pct_b) / 2 + fee_yield_pct - funding_cost_pct / 100 - credit_cost_pct_b - opex_pct
        
        # Breakeven calculation
        if nim_net_pct_b <= 0:
            breakeven_months_b = "Breakeven not within the tenor"
        else:
            C0 = 0.005 * params["exposure"]  # Upfront cost
            net_margin_monthly = (nim_net_pct_b / 100 / 12) * E_avg
            breakeven_months_b = np.ceil(C0 / net_margin_monthly)
            breakeven_months_b = int(breakeven_months_b) if breakeven_months_b <= params["tenor"] else "Breakeven not within the tenor"
        
        pricing_results.append({
            "bucket": bucket,
            "spread_min_bps": spread_min_bps_b,
            "spread_max_bps": spread_max_bps_b,
            "rate_min_pct": rate_min_pct_b,
            "rate_max_pct": rate_max_pct_b,
            "nii_omr": (nim_net_pct_b / 100) * E_avg,
            "breakeven_months": breakeven_months_b,
            "optimal_utilization": "–" if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"] else "–"
        })
    
    return pricing_results

# Main App
def main():
    st.title(":blue[rt]:green[360] Risk-Adjusted Pricing Model")
    
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
        st.caption(format_currency(exposure))
        
        tenor = st.slider("Tenor (months)", min_value=6, max_value=360, value=36)
        
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.slider("LTV (%)", min_value=10, max_value=95, value=70)
        else:
            working_capital = st.number_input("Working Capital (OMR)", min_value=0, value=500000)
            st.caption(format_currency(working_capital))
            sales = st.number_input("Sales (OMR)", min_value=0, value=2000000)
            st.caption(format_currency(sales))
        
        if st.button("Fetch Pricing"):
            # Prepare parameters
            params = {
                "product": product,
                "industry": industry,
                "malaa_score": malaa_score,
                "exposure": exposure,
                "tenor": tenor,
                "oibor_pct": oibor_pct,
                "cost_of_funds_pct": cost_of_funds_pct,
                "fees_income_pct": fees_income_pct
            }
            
            if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                params["ltv"] = ltv
            else:
                params["working_capital"] = working_capital
                params["sales"] = sales
            
            # Validate inputs
            if product in ["Asset Backed Loan", "Term Loan", "Export Finance"] and "ltv" not in params:
                st.error("LTV is required for fund-based products.")
                return
            if product in ["Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"] and (params["working_capital"] <= 0 or params["sales"] <= 0):
                st.error("Working Capital and Sales must be greater than zero for utilization-based products.")
                return
            
            # Calculate risk and pricing
            risk_score = calculate_risk_score(params)
            pricing_results = calculate_pricing(risk_score, params)
            
            # Create output table
            output_data = {
                "Bucket": [result["bucket"] for result in pricing_results],
                "Float_Min_over_OIBOR_bps": [result["spread_min_bps"] for result in pricing_results],
                "Float_Max_over_OIBOR_bps": [result["spread_max_bps"] for result in pricing_results],
                "Rate_Min_%": [f"{result['rate_min_pct']:.2f}" for result in pricing_results],
                "Rate_Max_%": [f"{result['rate_max_pct']:.2f}" for result in pricing_results],
                "Net_Interest_Income_OMR": [f"{result['nii_omr']:,.2f}" for result in pricing_results],
                "Breakeven_Months": [result["breakeven_months"] for result in pricing_results],
                "Optimal_Utilization_%": [result["optimal_utilization"] for result in pricing_results]
            }
            
            # Display output table
            st.subheader("Pricing Output")
            st.table(pd.DataFrame(output_data))

if __name__ == "__main__":
    main()
