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

def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp a value between a minimum and maximum."""
    return max(min(value, max_value), min_value)

def calculate_risk_score(params: dict) -> float:
    """Calculate composite risk score with all factors."""
    product_factor = PRODUCT_RISKS[params["product"]]
    industry_factor = INDUSTRY_RISKS[params["industry"]]
    malaa_factor = 1.3 - (params["malaa_score"] - 300) * (0.8 / 600)
    
    if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
        ltv_factor = clamp(0.7 + 0.0035 * params["ltv"], 0.8, 1.2)
        risk_score = product_factor * industry_factor * malaa_factor * ltv_factor
    else:
        wc_to_sales = params["working_capital"] / max(params["sales"], 1)
        wcs_factor = 0.85 + 0.6 * min(wc_to_sales, 1.0)
        utilization = UTILIZATION_FACTORS[params["industry"]]
        util_factor = clamp(1 - 0.15 * (0.8 - utilization), 0.85, 1.15)
        risk_score = product_factor * industry_factor * malaa_factor * wcs_factor * util_factor
    
    return clamp(risk_score, 0.4, 2.0)

def calculate_pricing(risk_score: float, params: dict) -> list:
    """Calculate pricing for all buckets (Low/Medium/High)"""
    buckets = ["Low", "Medium", "High"]
    multipliers = {"Low": 0.90, "Medium": 1.00, "High": 1.15}
    bands = {"Low": 50, "Medium": 75, "High": 100}
    
    results = []
    
    for bucket in buckets:
        risk_b = clamp(risk_score * multipliers[bucket], 0.4, 2.0)
        
        base_spread_bps = clamp(100 + 250 * (risk_b - 1), 75, 500)
        spread_min_bps = base_spread_bps - bands[bucket]
        spread_max_bps = base_spread_bps + bands[bucket]
        
        # Ensure positive spreads
        spread_min_bps = max(spread_min_bps, 75)
        spread_max_bps = max(spread_max_bps, spread_min_bps + 1)
        
        rate_min_pct = clamp(params["oibor_pct"] + spread_min_bps / 100, 5.0, 10.0)
        rate_max_pct = clamp(params["oibor_pct"] + spread_max_bps / 100, 5.0, 10.0)
        
        # Calculate EMI for fund-based products
        if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            P = params["exposure"]
            i_m = (rate_min_pct / 100) / 12
            T = params["tenor"]
            EMI = P * i_m * (1 + i_m) ** T / ((1 + i_m) ** T - 1)
            EMI_OMR = EMI
        else:
            EMI_OMR = "–"
        
        # Calculate NII and NIM
        fee_yield_pct = params["fees_income_pct"]
        funding_cost_pct = params["cost_of_funds_pct"]
        credit_cost_pct = clamp(0.4 * risk_b / 100, 0.2, 1.0)
        opex_pct = 0.4
        
        if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            E_avg = params["exposure"] * 0.55  # Amortizing approximation
            optimal_utilization = "–"
        else:
            utilization = UTILIZATION_FACTORS[params["industry"]]
            E_avg = params["exposure"] * utilization
            optimal_utilization = round(utilization * 100)
        
        nim_pct = (rate_min_pct + fee_yield_pct - funding_cost_pct - credit_cost_pct - opex_pct)
        NII_annual = (nim_pct / 100) * E_avg
        
        # Breakeven calculation
        if params["product"] in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            C0 = 0.005 * params["exposure"]  # Upfront cost
            balance = params["exposure"]
            cum_net = -C0
            breakeven_months = "Breakeven not within the tenor"
            for m in range(1, params["tenor"] + 1):
                interest_income = balance * (rate_min_pct / 100) / 12
                fee_income = params["exposure"] * (fee_yield_pct / 100) / 12
                funding_cost = balance * (funding_cost_pct / 100) / 12
                credit_cost = balance * (credit_cost_pct / 100) / 12
                opex = balance * (opex_pct / 100) / 12
                net_margin = interest_income + fee_income - funding_cost - credit_cost - opex
                cum_net += net_margin
                principal_repaid = EMI - interest_income
                balance = max(balance - principal_repaid, 0)
                if cum_net >= 0:
                    breakeven_months = m
                    break
        else:
            C0 = 0.005 * params["exposure"]
            net_margin_monthly = (nim_pct / 100 / 12) * E_avg
            if net_margin_monthly <= 0:
                breakeven_months = "Breakeven not within the tenor"
            else:
                breakeven_months = np.ceil(C0 / net_margin_monthly)
                breakeven_months = int(breakeven_months) if breakeven_months <= params["tenor"] else "Breakeven not within the tenor"
        
        results.append({
            "Bucket": bucket,
            "Float_Min_over_OIBOR_bps": int(spread_min_bps),
            "Float_Max_over_OIBOR_bps": int(spread_max_bps),
            "Rate_Min_%": f"{rate_min_pct:.2f}",
            "Rate_Max_%": f"{rate_max_pct:.2f}",
            "EMI_OMR": format_currency(EMI_OMR) if isinstance(EMI_OMR, float) else EMI_OMR,
            "Net_Interest_Income_OMR": format_currency(NII_annual),
            "NIM_%": f"{nim_pct:.2f}",
            "Breakeven_Months": breakeven_months,
            "Optimal_Utilization_%": optimal_utilization
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
        st.caption(f"Amount: {format_currency(exposure)}")
        
        tenor = st.slider("Tenor (months)", 6, 360, 36)
        
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.slider("LTV (%)", 10, 95, 70)
        else:
            working_capital = st.number_input("Working Capital (OMR)", min_value=0, value=500000)
            st.caption(f"Amount: {format_currency(working_capital)}")
            sales = st.number_input("Sales (OMR)", min_value=0, value=2000000)
            st.caption(f"Amount: {format_currency(sales)}")

    # Main content area
    with st.container():
        st.markdown('<div class="main-container">', unsafe_allow_html=True)
        
        # Only calculate when button is clicked
        if st.sidebar.button("Fetch Pricing"):
            # Validate inputs
            if (product in ["Asset Backed Loan", "Term Loan", "Export Finance"] and "ltv" not in locals()):
                st.error("LTV is required for fund-based products.")
                st.stop()
                
            if (product in ["Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"] 
                and ("working_capital" not in locals() or working_capital <= 0 or "sales" not in locals() or sales <= 0)):
                st.error("Working Capital and Sales must be greater than zero for utilization-based products.")
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
            
            # Calculate risk and pricing
            risk_score = calculate_risk_score(params)
            pricing_results = calculate_pricing(risk_score, params)
            
            # Display results in main content area
            st.subheader("Pricing Results")
            
            # Convert results to DataFrame
            results_df = pd.DataFrame(pricing_results).set_index("Bucket")
            
            # Display table with formatting
            st.dataframe(
                results_df,
                use_container_width=True
            )
        
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
