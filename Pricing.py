import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

# -------------------------------
# APP CONFIGURATION
# -------------------------------
st.set_page_config(
    page_title="rt 360 risk-adjusted pricing model",
    page_icon="💠",
    layout="wide"
)

# -------------------------------
# CONSTANTS
# -------------------------------
PRODUCT_TYPES = [
    "Asset Backed Loan", "Term Loan", "Export Finance", "Working Capital",
    "Trade Finance", "Supply Chain Finance", "Vendor Finance"
]

INDUSTRIES = [
    "Oil & Gas", "Construction", "Real Estate", "Manufacturing",
    "Trading", "Logistics", "Healthcare", "Hospitality", "Retail",
    "Mining", "Utilities", "Agriculture"
]

# -------------------------------
# CSS Styling
# -------------------------------
st.markdown("""
<style>
.header { display: flex; flex-direction: column; margin-bottom: 2rem; }
.rt { color: #1e88e5; font-weight: bold; }
.three60 { color: #4caf50; font-weight: bold; }
.subtitle { color: #666; font-size: 1.1rem; margin-top: -1rem; }
.card { border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 2px solid #1e88e5; }
.kpi-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }
.warning { color: #ff5722; font-weight: bold; }
.success { color: #4caf50; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# Utility Functions
# -------------------------------
def num_to_words(n: int) -> str:
    if not isinstance(n, (int, float)) or n < 0: return ""
    n = int(n)
    if n == 0: return "zero Omani Rials"
    units = ["","one","two","three","four","five","six","seven","eight","nine"]
    teens = ["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen",
             "seventeen","eighteen","nineteen"]
    tens = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]

    def chunk(x: int) -> str:
        if x<10: return units[x]
        if x<20: return teens[x-10]
        if x<100: return tens[x//10] + ("-"+units[x%10] if x%10!=0 else "")
        if x<1000: return units[x//100] + " hundred" + (" and "+chunk(x%100) if x%100!=0 else "")
        return ""

    words = []
    for scale, name in [(10**9,"billion"),(10**6,"million"),(10**3,"thousand")]:
        if n>=scale:
            words.append(f"{chunk(n//scale)} {name}")
            n %= scale
    if n>0: words.append(chunk(n))
    return " ".join(words) + " Omani Rials"

def malaa_risk_label(score: int) -> str:
    if score < 500: return "High"
    if score < 650: return "Med-High"
    if score < 750: return "Medium"
    return "Low"

# -------------------------------
# Core Calculation Functions
# -------------------------------
def calculate_risk_factors(product: str, industry: str, malaa_score: int,
    ltv: Optional[float]=None, working_capital: Optional[float]=None,
    sales: Optional[float]=None) -> Tuple[float,float,float]:

    product_factors = {"Asset Backed Loan":1.35, "Term Loan":1.20, "Export Finance":1.10,
                       "Working Capital":0.95, "Trade Finance":0.85,
                       "Supply Chain Finance":0.90, "Vendor Finance":0.95}
    industry_factors = {"Construction":1.40,"Real Estate":1.30,"Mining":1.30,"Hospitality":1.25,
                        "Retail":1.15,"Manufacturing":1.10,"Trading":1.05,"Logistics":1.00,
                        "Oil & Gas":0.95,"Healthcare":0.90,"Utilities":0.85,"Agriculture":1.15}

    pf = product_factors.get(product,1.0)
    inf = industry_factors.get(industry,1.0)
    mf = np.clip(1.45 - (malaa_score-300)*(0.90/600),0.55,1.45)

    if ltv is not None and product in ["Asset Backed Loan","Term Loan","Export Finance"]:
        ltv_factor = np.clip(0.55+0.0075*ltv,0.80,1.50)
        rb = np.clip(pf*inf*mf*ltv_factor,0.4,3.5)
    else:
        wc_ratio = (working_capital/sales) if sales and sales>0 else 0
        wcf = np.clip(0.70+1.0*min(wc_ratio,1.2),0.70,1.70)
        rb = np.clip(pf*inf*mf*wcf,0.4,3.5)
    return rb,pf,inf

def calculate_pd_lgd(risk_score: float, product: str, ltv: Optional[float], stage: int) -> Tuple[float,float]:
    xs, ys = np.array([0.4,1.0,2.0,3.5]), np.array([0.3,1.0,3.0,6.0])
    pd = float(np.interp(risk_score,xs,ys))*{1:1.0,2:2.5,3:6.0}.get(stage,1.0)
    pd = np.clip(pd,0.1,60.0)
    base_lgd = {"Asset Backed Loan":32,"Term Loan":38,"Export Finance":35}.get(product,30)
    ltv_adj = max(0.0,(ltv-50.0)*0.25) if ltv is not None else 8.0
    lgd = np.clip(base_lgd+ltv_adj,25.0,70.0)
    return pd, lgd

def calculate_loan_pricing(rs: float, ml: str, oibor: float, cof: float, opex: float, fees: float, bucket: str, product: str):
    bm={"Low":0.90,"Medium":1.0,"High":1.25}
    bb={"Low":60,"Medium":90,"High":140}
    bf={"Low":150,"Medium":225,"High":325}
    rb = np.clip(rs*bm[bucket],0.4,3.5)
    raw_spread = 75+350*(rb-1)
    malaa_adder = {"High":175,"Med-High":125,"Medium":75,"Low":0}[ml]
    prod_add = 125 if "Asset Backed" in product else 75 if product in ["Term Loan","Export Finance"] else 0
    center = max(bf[bucket],raw_spread,125,raw_spread+malaa_adder+prod_add)
    smin, smax = center-bb[bucket], center+bb[bucket]
    rmin = np.clip(oibor+smin/100,5.0,10.0)
    rmax = np.clip(oibor+smax/100,5.0,10.0)
    rep  = (rmin+rmax)/2
    return {"spread_min":round(smin,2),"spread_max":round(smax,2),
            "rate_min":round(rmin,2),"rate_max":round(rmax,2),
            "rep_rate":round(rep,2),"oibor_pct":oibor}

def calculate_emi(principal: float, rate: float, tenor: int) -> float:
    mr = rate/100/12
    return principal/tenor if mr==0 else principal*mr*(1+mr)**tenor / ((1+mr)**tenor - 1)

def calculate_repayment_schedule(principal: float, rate: float, tenor:int, cof:float, prov:float, opex:float, upc:float):
    mr = rate/100/12
    emi = calculate_emi(principal, rate, tenor)
    bal=principal; sched=[]; cum_net=0; be=None
    for m in range(1,tenor+1):
        intpay = bal*mr
        prinpay= emi-intpay
        provpay= bal*prov/100/12
        fund = bal*cof/100/12
        op = bal*opex/100/12
        net= intpay - (fund+provpay+op)
        cum_net += net
        if be is None and cum_net >= (principal*upc/100): be=m
        sched.append({"Month":m,"Net_Income":net,"Cumulative_Net":cum_net})
        bal-=prinpay
        if bal<=0: break
    avg_bal = principal  # simplified
    nim = (cum_net/avg_bal)*100 if avg_bal>0 else 0
    return emi, cum_net, nim, sched, be or tenor

# -------------------------------
# UI RENDER FUNCTIONS
# -------------------------------
def render_header():
    st.markdown("""
    <div class="header">
        <h1><span class="rt">rt</span><span class="three60">360</span></h1>
        <p class="subtitle">risk-adjusted pricing model for Corporate Lending</p>
    </div>
    """, unsafe_allow_html=True)

def render_market_parameters():
    st.sidebar.header("Market & Bank Parameters")
    col1,col2 = st.sidebar.columns(2)
    with col1:
        oibor_base = st.number_input("OIBOR Base (%)", value=4.1, step=0.1, key="oibor_base")
        fed_shock  = st.slider("Fed Shock (bps)", -300, 300, 0, key="fed_shock")
        cof_pct    = st.number_input("Cost of Funds (%)", value=5.0, step=0.1, key="cof")
    with col2:
        target_nim = st.number_input("Target NIM (%)", value=2.5, step=0.1, key="tnim")
        opex_pct   = st.number_input("Opex (%)", value=0.40, step=0.05, key="opex")
        upfront_cost = st.number_input("Upfront Cost (%)", value=0.50, step=0.05, key="upc")
    return {"oibor_pct": oibor_base+(fed_shock/100),"cof_pct":cof_pct,
            "target_nim":target_nim,"opex_pct":opex_pct,"upfront_cost":upfront_cost}

def render_loan_parameters():
    st.sidebar.header("Borrower & Product")
    product  = st.sidebar.selectbox("Product Type", PRODUCT_TYPES, key="prod")
    industry = st.sidebar.selectbox("Industry", INDUSTRIES, key="ind")
    malaa_score = st.sidebar.slider("Mala'a Score", 300, 900, 650, step=50, key="malaa")
    stage = st.sidebar.selectbox("Stage", [1,2,3], key="stage")
    tenor = st.sidebar.number_input("Tenor (months)", 6, 360, 36, key="tenor")
    col1,col2=st.sidebar.columns(2)
    with col1:
        amount = st.number_input("Loan Amount (OMR)", min_value=0.0, value=100000.0, step=1000.0, key="amt")
        st.caption(f"**In words:** {num_to_words(int(amount))}")
    with col2:
        if product in ["Asset Backed Loan","Term Loan","Export Finance"]:
            ltv = st.number_input("LTV (%)", 0, 100, 70, key="ltv")
            wc,sales = None,None
        else:
            ltv=None
            wc = st.number_input("Working Capital (OMR)",0.0, value=50000.0, step=1000.0, key="wc")
            sales = st.number_input("Annual Sales (OMR)",0.0, value=200000.0, step=1000.0, key="sales")
            st.caption(f"**Sales in words:** {num_to_words(int(sales))}")
    return {"product":product,"industry":industry,"malaa_score":malaa_score,"stage":stage,"tenor":tenor,
            "amount":amount,"ltv":ltv,"working_capital":wc,"sales":sales}

def render_assumptions_tab():
    st.header("Model Assumptions")
    with st.expander("Risk Factors"):
        col1,col2=st.columns(2)
        with col1:
            st.subheader("Product Risk Factors")
            st.table(pd.DataFrame.from_dict({
                "Asset Backed Loan":1.35,"Term Loan":1.20,"Export Finance":1.10,"Working Capital":0.95,
                "Trade Finance":0.85,"Supply Chain Finance":0.90,"Vendor Finance":0.95
            }, orient='index', columns=['Factor']).round(2))
        with col2:
            st.subheader("Industry Risk Factors")
            st.table(pd.DataFrame.from_dict({
                "Construction":1.40,"Real Estate":1.30,"Mining":1.30,"Hospitality":1.25,"Retail":1.15,
                "Manufacturing":1.10,"Trading":1.05,"Logistics":1.00,"Oil & Gas":0.95,"Healthcare":0.90,
                "Utilities":0.85,"Agriculture":1.15
            }, orient='index', columns=['Factor']).round(2))
    st.expander("Pricing Parameters").markdown("""
    - **Base Spread Curve:** 75 bps + 350 × (Risk - 1)  
    - **Bucket Multipliers:** Low (0.9x), Medium (1.0x), High (1.25x)  
    - **Adders**: Product: ABL +125bps, Term/Export +75bps  
    """)
    st.expander("Methodology").markdown("... PDF and LGD calculation details ...")
    st.expander("NIM Calculation").markdown("... formula details ...")

# -------------------------------
# Results Display
# -------------------------------
def display_pricing_results(results_df: pd.DataFrame, target_nim: float):
    results_df = results_df.round(2)
    st.dataframe(results_df.style.format("{:.2f}"))
    for _, row in results_df.iterrows():
        st.metric("Rep Rate", f"{row['rep_rate']:.2f}%")
        st.metric("NIM", f"{row['NIM']:.2f}% (target {target_nim:.2f}%)")

# -------------------------------
# Main Calc
# -------------------------------
def calculate_and_display_single_loan(lp: Dict, mp: Dict):
    rb,pf,inf=calculate_risk_factors(lp["product"],lp["industry"],lp["malaa_score"],lp.get("ltv"),lp.get("working_capital"),lp.get("sales"))
    pdv,lgdv=calculate_pd_lgd(rb, lp["product"], lp.get("ltv"), lp["stage"])
    fees=0.4 if lp["product"] in ["Supply Chain Finance","Vendor Finance","Working Capital","Export Finance"] else 0.0
    results=[]
    for bucket in ["Low","Medium","High"]:
        pr=calculate_loan_pricing(rb, malaa_risk_label(lp["malaa_score"]), mp["oibor_pct"], mp["cof_pct"], mp["opex_pct"], fees, bucket, lp["product"])
        pr.update({"risk_score":rb,"product_factor":pf,"industry_factor":inf,
                   "PD":pdv,"LGD":lgdv,"Provision_Rate":pdv*lgdv/10000})
        results.append(pr)
    df=pd.DataFrame(results).round(2)
    display_pricing_results(df, mp["target_nim"])

# -------------------------------
# MAIN APP
# -------------------------------
def main():
    render_header()
    tab1,tab2,tab3 = st.tabs(["Single Loan Pricing","Loan Book","Assumptions"])

    with tab1:
        mp = render_market_parameters()
        lp = render_loan_parameters()
        if st.button("Calculate Pricing", type="primary"):
            calculate_and_display_single_loan(lp,mp)

    with tab2:
        st.write("Batch processing of Loan Book — to be extended with CSV upload and processing...")

    with tab3:
        render_assumptions_tab()

if __name__ == "__main__":
    main()
