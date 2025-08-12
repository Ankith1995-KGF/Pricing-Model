import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

# --- APP CONFIGURATION ---
st.set_page_config(
    page_title="rt 360 risk-adjusted pricing model",
    page_icon="💠",
    layout="wide"
)

# Custom styling for the application
st.markdown("""
<style>
    .header {
        display: flex;
        flex-direction: column;
        margin-bottom: 2rem;
    }
    .rt {
        color: #1e88e5;
        font-weight: bold;
    }
    .three60 {
        color: #4caf50;
        font-weight: bold;
    }
    .subtitle {
        color: #666;
        font-size: 1.1rem;
        margin-top: -1rem;
    }
    .card {
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 2px solid #1e88e5;
    }
    .kpi {
        background-color: #f8f9fa;
        border-left: 4px solid #1e88e5;
        padding: 1rem;
        margin-bottom: 1rem;
        border-radius: 4px;
    }
    .warning {
        color: #ff5722;
        font-weight: bold;
    }
    .success {
        color: #4caf50;
        font-weight: bold;
    }
    .stNumberInput, .stSelectbox, .stSlider {
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# --- UTILITY FUNCTIONS ---
def num_to_words(n: int) -> str:
    """Convert integer to words representation for OMR amounts"""
    if not isinstance(n, (int, float)) or n < 0:
        return ""
    
    n = int(n)
    if n == 0:
        return "zero Omani Rials"
    
    units = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
    teens = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", 
             "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    
    def convert_chunk(x: int) -> str:
        if x < 10:
            return units[x]
        if x < 20:
            return teens[x - 10]
        if x < 100:
            return tens[x // 10] + (" " + units[x % 10] if x % 10 != 0 else "")
        if x < 1000:
            return units[x // 100] + " hundred" + (" " + convert_chunk(x % 100) if x % 100 != 0 else "")
        return ""
    
    magnitude_words = []
    for magnitude, word in [(10**9, "billion"), (10**6, "million"), (10**3, "thousand")]:
        if n >= magnitude:
            magnitude_words.append(f"{convert_chunk(n // magnitude)} {word}")
            n %= magnitude
    
    if n > 0:
        magnitude_words.append(convert_chunk(n))
    
    return " ".join(magnitude_words) + " Omani Rials"

def malaa_risk_label(score: int) -> str:
    """Classify borrower risk based on Mala'a score"""
    if score < 500:
        return "High"
    elif score < 650:
        return "Med-High"
    elif score < 750:
        return "Medium"
    return "Low"

def calculate_risk_factors(
    product: str,
    industry: str,
    malaa_score: int,
    ltv: Optional[float] = None,
    working_capital: Optional[float] = None,
    sales: Optional[float] = None
) -> Tuple[float, float, float]:
    """Calculate composite risk score and components"""
    product_factors = {
        "Asset Backed Loan": 1.35, "Term Loan": 1.20, "Export Finance": 1.10,
        "Working Capital": 0.95, "Trade Finance": 0.85, "Supply Chain Finance": 0.90,
        "Vendor Finance": 0.95
    }
    
    industry_factors = {
        "Construction": 1.40, "Real Estate": 1.30, "Mining": 1.30,
        "Hospitality": 1.25, "Retail": 1.15, "Manufacturing": 1.10,
        "Trading": 1.05, "Logistics": 1.00, "Oil & Gas": 0.95,
        "Healthcare": 0.90, "Utilities": 0.85, "Agriculture": 1.15
    }
    
    # Get base factors
    product_factor = product_factors.get(product, 1.0)
    industry_factor = industry_factors.get(industry, 1.0)
    malaa_factor = np.clip(1.45 - (malaa_score - 300) * (0.90 / 600), 0.55, 1.45)
    
    # Calculate risk modifier
    if ltv is not None and ltv > 0:
        ltv_factor = np.clip(0.55 + 0.0075 * ltv, 0.80, 1.50)
        risk_base = np.clip(product_factor * industry_factor * malaa_factor * ltv_factor, 0.4, 3.5)
    else:
        wc_ratio = (working_capital / sales) if sales and sales > 0 else 0
        wcs_factor = np.clip(0.70 + 1.00 * min(wc_ratio, 1.2), 0.70, 1.70)
        risk_base = np.clip(product_factor * industry_factor * malaa_factor * wcs_factor, 0.4, 3.5)
    
    return risk_base, product_factor, industry_factor

def calculate_pd_lgd(risk_score: float, product: str, ltv: Optional[float], stage: int) -> Tuple[float, float]:
    """Calculate PD and LGD based on risk score, product type, and stage"""
    xs = np.array([0.4, 1.0, 2.0, 3.5])
    ys = np.array([0.3, 1.0, 3.0, 6.0])
    pd = float(np.interp(risk_score, xs, ys))
    
    # Stage multiplier
    if stage == 2:
        pd *= 2.5
    elif stage == 3:
        pd *= 6.0
    pd = np.clip(pd, 0.1, 60.0)
    
    # LGD calculation
    base_lgd = {
        "Asset Backed Loan": 32,
        "Term Loan": 38,
        "Export Finance": 35
    }.get(product, 30)
    
    ltv_adj = max(0.0, (ltv - 50.0) * 0.25) if ltv is not None else 8.0
    lgd = np.clip(base_lgd + ltv_adj, 25.0, 70.0)
    
    return pd, lgd

def calculate_loan_pricing(
    risk_score: float,
    malaa_label: str,
    oibor_pct: float,
    cof_pct: float,
    opex_pct: float,
    fees_pct: float,
    bucket: str
) -> Dict[str, float]:
    """Calculate pricing metrics for a single loan bucket"""
    bucket_multipliers = {"Low": 0.90, "Medium": 1.00, "High": 1.25}
    bucket_bands = {"Low": 60, "Medium": 90, "High": 140}
    bucket_floors = {"Low": 150, "Medium": 225, "High": 325}
    
    risk_b = np.clip(risk_score * bucket_multipliers[bucket], 0.4, 3.5)
    
    # Calculate base spread
    raw_spread_bps = 75 + 350 * (risk_b - 1)
    
    # Apply adders from borrower, product, and industry factors
    malaa_adders = {"High": 175, "Med-High": 125, "Medium": 75, "Low": 0}
    malaa_adder = malaa_adders[malaa_label]
    
    product_adder = 125 if "Asset Backed" in product else 75 if product in ["Term Loan", "Export Finance"] else 0
    
    # Calculate center spread with all floors
    center_spread = max(
        bucket_floors[bucket],
        raw_spread_bps,
        125,  # Global floor
        raw_spread_bps + malaa_adder + product_adder
    )
    
    # Create band around center spread
    spread_min = center_spread - bucket_bands[bucket]
    spread_max = center_spread + bucket_bands[bucket]
    
    # Convert to rates with 5-10% clamp
    rate_min = np.clip(oibor_pct + spread_min / 100, 5.0, 10.0)
    rate_max = np.clip(oibor_pct + spread_max / 100, 5.0, 10.0)
    rep_rate = (rate_min + rate_max) / 2
    
    return {
        "spread_min": spread_min,
        "spread_max": spread_max,
        "rate_min": rate_min,
        "rate_max": rate_max,
        "rep_rate": rep_rate
    }

# --- STREAMLIT UI COMPONENTS ---
def render_header():
    """Render the application header"""
    st.markdown("""
    <div class="header">
        <h1><span class="rt">rt</span><span class="three60">360</span></h1>
        <p class="subtitle">risk-adjusted pricing model for Corporate Lending</p>
    </div>
    """, unsafe_allow_html=True)

def render_market_parameters() -> Dict[str, float]:
    """Render market parameters section and return values"""
    st.sidebar.header("Market & Bank Parameters")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        oibor_pct = st.number_input("OIBOR Base (%)", value=4.1, min_value=0.0, max_value=20.0, step=0.1)
        cof_pct = st.number_input("Cost of Funds (%)", value=5.0, min_value=0.0, max_value=20.0, step=0.1)
        opex_pct = st.number_input("Opex (%)", value=0.40, min_value=0.0, max_value=5.0, step=0.05)
        
    with col2:
        fed_shock = st.slider("Fed Shock (bps)", -300, 300, 0)
        target_nim = st.number_input("Target NIM (%)", value=2.5, min_value=0.0, max_value=10.0, step=0.1)
        upfront_cost = st.number_input("Upfront Cost (%)", value=0.50, min_value=0.0, max_value=5.0, step=0.05)
    
    return {
        "oibor_pct": oibor_pct + (fed_shock / 100),
        "cof_pct": cof_pct,
        "target_nim": target_nim,
        "opex_pct": opex_pct,
        "upfront_cost": upfront_cost
    }

def render_loan_parameters() -> Dict:
    """Render loan parameters section"""
    st.sidebar.header("Borrower & Product")
    
    product = st.sidebar.selectbox(
        "Product",
        ["Asset Backed Loan", "Term Loan", "Export Finance", 
         "Working Capital", "Trade Finance", "Supply Chain Finance", 
         "Vendor Finance"]
    )
    
    industry = st.sidebar.selectbox(
        "Industry",
        ["Oil & Gas", "Construction", "Real Estate", "Manufacturing", 
         "Trading", "Logistics", "Healthcare", "Hospitality", "Retail", 
         "Mining", "Utilities", "Agriculture"]
    )
    
    malaa_score = st.sidebar.slider("Mala'a Score", 300, 900, 650, 50)
    stage = st.sidebar.selectbox("Stage", [1, 2, 3], index=0)
    
    st.sidebar.header("Loan Details")
    tenor = st.sidebar.number_input("Tenor (months)", 6, 360, 36)
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        loan_amount = st.number_input("Loan Amount (OMR)", min_value=0.0, value=100000.0, step=1000.0)
        st.caption(f"In words: {num_to_words(int(loan_amount))}")
        
    with col2:
        if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
            ltv = st.number_input("LTV (%)", 0, 100, 70)
            wc = sales = None
        else:
            ltv = None
            wc = st.number_input("Working Capital (OMR)", min_value=0.0, value=50000.0, step=1000.0)
            sales = st.number_input("Annual Sales (OMR)", min_value=0.0, value=200000.0, step=1000.0)
            st.caption(f"In words: {num_to_words(int(sales))}")
    
    return {
        "product": product,
        "industry": industry,
        "malaa_score": malaa_score,
        "stage": stage,
        "tenor": tenor,
        "amount": loan_amount,
        "ltv": ltv,
        "working_capital": wc,
        "sales": sales
    }

def render_loan_book_section():
    """Render the loan book upload section"""
    st.sidebar.header("Loan Book Processing")
    
    uploaded_file = st.sidebar.file_uploader("Upload Loan Book (CSV)", type=["csv"])
    st.sidebar.download_button(
        label="Download Template",
        data="""loan_id,product,industry,malaa_score,tenor_months,loan_quantum_omr,limit_omr,working_capital_omr,sales_omr,median_utilization,ltv_pct,stage,pd_pct,lgd_pct,provision_rate_pct,fees_pct,opex_pct
1,Term Loan,Construction,550,36,500000,,,60,2,0.8,32,,,,0.4
2,Working Capital,Manufacturing,720,24,,200000,800000,40,,1,,,,0.4
3,Asset Backed Loan,Real Estate,450,60,1000000,,,75,3,0.9,38,,,,0.4""",
        file_name="loan_book_template.csv",
        mime="text/csv"
    )
    
    return uploaded_file

def calculate_single_loan(
    loan_params: Dict,
    market_params: Dict
) -> pd.DataFrame:
    """Calculate pricing for a single loan across all buckets"""
    # Calculate base risk
    risk_base, product_factor, industry_factor = calculate_risk_factors(
        loan_params["product"],
        loan_params["industry"],
        loan_params["malaa_score"],
        loan_params["ltv"],
        loan_params["working_capital"],
        loan_params["sales"]
    )
    
    # Calculate PD and LGD
    pd, lgd = calculate_pd_lgd(
        risk_base,
        loan_params["product"],
        loan_params["ltv"],
        loan_params["stage"]
    )
    
    # Determine applicable fees
    fee_products = ["Supply Chain Finance", "Vendor Finance", "Working Capital", "Export Finance"]
    fees_pct = 0.4 if loan_params["product"] in fee_products else 0.0
    
    results = []
    buckets = ["Low", "Medium", "High"]
    
    for bucket in buckets:
        # Calculate pricing for this bucket
        pricing = calculate_loan_pricing(
            risk_base,
            malaa_risk_label(loan_params["malaa_score"]),
            market_params["oibor_pct"],
            market_params["cof_pct"],
            market_params["opex_pct"],
            fees_pct,
            bucket
        )
        
        # Prepare results
        result = {
            "Bucket": bucket,
            "Risk_Score": risk_base,
            "Product_Factor": product_factor,
            "Industry_Factor": industry_factor,
            **pricing,
            "PD": pd,
            "LGD": lgd,
            "Provision_Rate": pd * lgd / 10000,
            "Fees_Pct": fees_pct,
            "Opex_Pct": market_params["opex_pct"],
            "Upfront_Cost_Pct": market_params["upfront_cost"],
            "Target_NIM": market_params["target_nim"]
        }
        
        results.append(result)
    
    return pd.DataFrame(results)

def display_results(results_df: pd.DataFrame):
    """Display the pricing results in the main area"""
    st.subheader("Pricing Results")
    
    for _, row in results_df.iterrows():
        with st.expander(f"{row['Bucket']} Bucket Details"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Rep Rate", f"{row['rep_rate']:.2f}%")
                st.metric("Min Rate", f"{row['rate_min']:.2f}%")
                st.metric("Max Rate", f"{row['rate_max']:.2f}%")
            
            with col2:
                st.metric("Spread Min", f"{row['spread_min']} bps")
                st.metric("Spread Rep", f"{(row['rep_rate'] - row['oibor_pct'])*100:.0f} bps")
                st.metric("Spread Max", f"{row['spread_max']} bps")
            
            with col3:
                st.metric("PD", f"{row['PD']:.2f}%")
                st.metric("LGD", f"{row['LGD']:.2f}%")
                st.metric("Provision", f"{row['Provision_Rate']*100:.2f}%")
            
            # NIM calculation
            nim = row['rep_rate'] + row['Fees_Pct'] - (row['cof_pct'] + row['Provision_Rate']*100 + row['Opex_Pct'])
            nim_status = "warning" if nim < row['Target_NIM'] else "success"
            
            st.write(f"**NIM:** <span class='{nim_status}'>{nim:.2f}%</span> (Target: {row['Target_NIM']}%)", unsafe_allow_html=True)
            
            # Risk factors
            st.write("---")
            st.write("**Risk Factors:**")
            st.write(f"- Product: {row['Product_Factor']:.2f}x")
            st.write(f"- Industry: {row['Industry_Factor']:.2f}x")
            st.write(f"- Composite: {row['Risk_Score']:.2f}")

# --- MAIN APPLICATION ---
def main():
    # Render the application header
    render_header()
    
    # Get all user inputs from the sidebar
    market_params = render_market_parameters()
    loan_params = render_loan_parameters()
    uploaded_file = render_loan_book_section()
    
    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(["Single Loan Pricing", "Loan Book Pricing", "Concentration & Provisions", "Assumptions"])
    
    with tab1:
        if st.button("Calculate Pricing"):
            with st.spinner("Calculating pricing across all buckets..."):
                results = calculate_single_loan(loan_params, market_params)
                display_results(results)
    
    with tab2:
        if uploaded_file is not None:
            st.write("Loan book processing would go here")
        else:
            st.info("Upload a loan book CSV file to enable batch processing")
    
    with tab3:
        st.write("Concentration and provisions analysis would appear here")
    
    with tab4:
        st.write("Model assumptions and factor mappings would appear here")

if __name__ == "__main__":
    main()
