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
    units=["","one","two","three","four","five","six","seven","eight","nine"]
    teens=["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"]
    tens=["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
    def chunk(x):
        if x<10: return units[x]
        if x<20: return teens[x-10]
        if x<100: return tens[x//10]+("-"+units[x%10] if x%10 else "")
        if x<1000: return units[x//100]+" hundred"+(" and "+chunk(x%100) if x%100 else "")
        return ""
    words=[]
    for scale,name in [(10**9,"billion"),(10**6,"million"),(10**3,"thousand")]:
        if n>=scale:
            words.append(f"{chunk(n//scale)} {name}")
            n%=scale
    if n>0: words.append(chunk(n))
    return " ".join(words)+" Omani Rials"

def malaa_risk_label(score: int) -> str:
    if score < 500: return "High"
    if score < 650: return "Med-High"
    if score < 750: return "Medium"
    return "Low"

# -------------------------------
# Core Calcs
# -------------------------------
def calculate_risk_factors(product:str, industry:str, malaa_score:int,
                            ltv:Optional[float]=None, working_capital:Optional[float]=None,
                            sales:Optional[float]=None) -> Tuple[float,float,float]:
    pf_map={"Asset Backed Loan":1.35,"Term Loan":1.20,"Export Finance":1.10,"Working Capital":0.95,
            "Trade Finance":0.85,"Supply Chain Finance":0.90,"Vendor Finance":0.95}
    inf_map={"Construction":1.40,"Real Estate":1.30,"Mining":1.30,"Hospitality":1.25,"Retail":1.15,
             "Manufacturing":1.10,"Trading":1.05,"Logistics":1.00,"Oil & Gas":0.95,"Healthcare":0.90,
             "Utilities":0.85,"Agriculture":1.15}
    pf=pf_map.get(product,1.0); inf=inf_map.get(industry,1.0)
    mf=np.clip(1.45 - (malaa_score-300)*(0.90/600),0.55,1.45)
    if ltv is not None and product in ["Asset Backed Loan","Term Loan","Export Finance"]:
        ltvf=np.clip(0.55+0.0075*ltv,0.80,1.50)
        rb=np.clip(pf*inf*mf*ltvf,0.4,3.5)
    else:
        wcr=(working_capital/sales) if sales and sales>0 else 0
        wcf=np.clip(0.70+1.0*min(wcr,1.2),0.70,1.70)
        rb=np.clip(pf*inf*mf*wcf,0.4,3.5)
    return rb,pf,inf

def calculate_pd_lgd(risk_score:float, product:str, ltv:Optional[float], stage:int) -> Tuple[float,float]:
    pd = float(np.interp(risk_score,[0.4,1.0,2.0,3.5],[0.3,1.0,3.0,6.0])) * {1:1.0,2:2.5,3:6.0}.get(stage,1.0)
    pd = np.clip(pd,0.1,60.0)
    lgd_base={"Asset Backed Loan":32,"Term Loan":38,"Export Finance":35}.get(product,30)
    ltv_adj=max(0.0,(ltv-50.0)*0.25) if ltv is not None else 8.0
    lgd=np.clip(lgd_base+ltv_adj,25.0,70.0)
    return pd,lgd

def calculate_loan_pricing(rs:float, ml:str, oibor:float, cof:float, opex:float, fees:float, bucket:str, product:str):
    bm={"Low":0.90,"Medium":1.0,"High":1.25}
    bb={"Low":60,"Medium":90,"High":140}
    bf={"Low":150,"Medium":225,"High":325}
    r_adj=np.clip(rs*bm[bucket],0.4,3.5)
    spread=75+350*(r_adj-1)
    spread+= {"High":175,"Med-High":125,"Medium":75,"Low":0}[ml]
    if "Asset Backed" in product: spread+=125
    elif product in ["Term Loan","Export Finance"]: spread+=75
    smin=spread-bb[bucket]; smax=spread+bb[bucket]
    rmin=np.clip(oibor+smin/100,5.0,10.0)
    rmax=np.clip(oibor+smax/100,5.0,10.0)
    return {"spread_min":round(smin,2),"spread_max":round(smax,2),
            "rate_min":round(rmin,2),"rate_max":round(rmax,2),
            "rep_rate":round((rmin+rmax)/2,2),"oibor_pct":oibor}

# -------------------------------
# UI
# -------------------------------
def render_header():
    st.markdown(f"<div class='header'><h1><span class='rt'>rt</span><span class='three60'>360</span></h1>"
                f"<p class='subtitle'>risk-adjusted pricing model</p></div>",unsafe_allow_html=True)

def render_market_parameters():
    st.sidebar.header("Market & Bank Parameters")
    col1,col2 = st.sidebar.columns(2)
    with col1:
        ob = st.number_input("OIBOR Base (%)", value=4.1, step=0.1, key="oibor")
        fs = st.slider("Fed Shock (bps)", -300,300,0, key="fed")
        cof= st.number_input("Cost of Funds (%)", value=5.0, step=0.1, key="cof")
    with col2:
        tn= st.number_input("Target NIM (%)", value=2.5, step=0.1, key="tnim")
        op= st.number_input("Opex (%)", value=0.4, step=0.05, key="opx")
        uc= st.number_input("Upfront Cost (%)", value=0.5, step=0.05, key="upc")
    return {"oibor_pct":ob+(fs/100),"cof_pct":cof,"target_nim":tn,"opex_pct":op,"upfront_cost":uc}

def render_loan_parameters():
    st.sidebar.header("Loan Details")
    prod = st.sidebar.selectbox("Product Type", PRODUCT_TYPES, key="prod")
    ind  = st.sidebar.selectbox("Industry", INDUSTRIES, key="ind")
    ms   = st.sidebar.slider("Mala'a Score",300,900,650,step=50,key="malaa")
    stage= st.sidebar.selectbox("Stage",[1,2,3], key="stage")
    tenor= st.sidebar.number_input("Tenor (months)",6,360,36,key="tenor")
    amt  = st.sidebar.number_input("Loan Amount (OMR)",0.0, value=100000.0, step=1000.0, key="amt")
    st.caption(f"In words: {num_to_words(int(amt))}")
    if prod in ["Asset Backed Loan","Term Loan","Export Finance"]:
        ltv = st.number_input("LTV (%)",0,100,70,key="ltv")
        wc,sales=None,None
    else:
        ltv=None
        wc = st.number_input("Working Capital (OMR)",0.0,value=50000.0,step=1000.0,key="wc")
        sales = st.number_input("Annual Sales (OMR)",0.0,value=200000.0,step=1000.0,key="sales")
    return {"product":prod,"industry":ind,"malaa_score":ms,"stage":stage,"tenor":tenor,
            "amount":amt,"ltv":ltv,"working_capital":wc,"sales":sales}

def render_assumptions_tab():
    st.header("Model Assumptions")
    st.write("Risk factor tables and methodology... (formatted)")

# -------------------------------
# Display
# -------------------------------
def display_pricing_results(df: pd.DataFrame, target_nim: float):
    df = df.round(2)
    st.dataframe(df.style.format("{:.2f}"))
    for _,row in df.iterrows():
        st.metric("Rep Rate", f"{row['rep_rate']:.2f}%")
        st.metric("NIM", f"{row['NIM']:.2f}% (target {target_nim:.2f}%)")

# -------------------------------
# Main calc and display
# -------------------------------
def calculate_and_display_single_loan(lp: Dict, mp: Dict):
    rb,pf,inf= calculate_risk_factors(lp["product"],lp["industry"],lp["malaa_score"],lp.get("ltv"),lp.get("working_capital"),lp.get("sales"))
    pdv,lgdv= calculate_pd_lgd(rb, lp["product"], lp.get("ltv"), lp["stage"])
    fees=0.4 if lp["product"] in ["Supply Chain Finance","Vendor Finance","Working Capital","Export Finance"] else 0.0
    results=[]
    for bucket in ["Low","Medium","High"]:
        pricing= calculate_loan_pricing(rb, malaa_risk_label(lp["malaa_score"]), mp["oibor_pct"], mp["cof_pct"], mp["opex_pct"], fees, bucket, lp["product"])
        prov_rate= pdv*lgdv/10000
        nim= pricing["rep_rate"] + fees - (mp["cof_pct"] + prov_rate*100 + mp["opex_pct"])
        pricing.update({"risk_score":rb,"product_factor":pf,"industry_factor":inf,"PD":pdv,"LGD":lgdv,
                        "Provision_Rate":prov_rate,"NIM":nim})
        results.append(pricing)
    df=pd.DataFrame(results)
    display_pricing_results(df, mp["target_nim"])

# -------------------------------
# MAIN
# -------------------------------
def main():
    render_header()
    tab1,tab2,tab3 = st.tabs(["Single Loan Pricing","Loan Book","Assumptions"])
    with tab1:
        mp=render_market_parameters()
        lp=render_loan_parameters()
        if st.button("Calculate Pricing",type="primary"):
            calculate_and_display_single_loan(lp, mp)
    with tab2:
        st.info("Loan Book processing here...")
    with tab3:
        render_assumptions_tab()

if __name__=="__main__":
    main()
