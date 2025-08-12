import math
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import streamlit as st

# ---------------- Global formatting (2 decimals) ----------------
pd.options.display.float_format = lambda x: f"{x:.2f}"

def f2(x: float) -> float:
    try:
        return float(np.round(float(x), 2))
    except Exception:
        return float("nan")

def fmt2(x) -> str:
    try:
        return f"{f2(float(x)):.2f}"
    except Exception:
        return ""

# ---------------- Tiny number-to-words helper (integers) ----------------
def num_to_words(n: int) -> str:
    units = ["","one","two","three","four","five","six","seven","eight","nine"]
    teens = ["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"]
    tens = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
    def chunk(x:int)->str:
        if x==0: return ""
        if x<10: return units[x]
        if x<20: return teens[x-10]
        if x<100: return tens[x//10] + ("" if x%10==0 else " "+units[x%10])
        if x<1000: return units[x//100]+" hundred"+("" if x%100==0 else " "+chunk(x%100))
        return ""
    if n==0: return "zero"
    parts=[]
    for div,word in [(10**9,"billion"),(10**6,"million"),(10**3,"thousand")]:
        if n>=div: parts.append(chunk(n//div)+" "+word); n%=div
    if n>0: parts.append(chunk(n))
    return " ".join(parts)

# ---------------- Core helpers ----------------
PRODUCTS_FUND = ["Asset Backed Loan","Term Loan","Export Finance"]
PRODUCTS_UTIL = ["Working Capital","Trade Finance","Supply Chain Finance","Vendor Finance"]

product_factor: Dict[str,float] = {
    "Asset Backed Loan":1.35,"Term Loan":1.20,"Export Finance":1.10,
    "Vendor Finance":0.95,"Supply Chain Finance":0.90,"Trade Finance":0.85,"Working Capital":0.95
}
industry_factor: Dict[str,float] = {
    "Construction":1.40,"Real Estate":1.30,"Mining":1.30,"Hospitality":1.25,
    "Retail":1.15,"Manufacturing":1.10,"Trading":1.05,"Logistics":1.00,
    "Oil & Gas":0.95,"Healthcare":0.90,"Utilities":0.85,"Agriculture":1.15
}
u_med_map: Dict[str,float] = {
    "Trading":0.65,"Manufacturing":0.55,"Construction":0.40,"Logistics":0.60,"Retail":0.50,
    "Healthcare":0.45,"Hospitality":0.35,"Oil & Gas":0.50,"Real Estate":0.30,"Utilities":0.55,
    "Mining":0.45,"Agriculture":0.40
}

def clamp(x: float, lo: float, hi: float) -> float: return max(lo, min(x, hi))

def malaa_factor(score:int)->float:
    # inverse: 300→1.45 risk, 900→0.55 risk
    return float(np.clip(1.45 - (score-300)*(0.90/600), 0.55, 1.45))

def ltv_factor(ltv: float)->float:
    return float(np.clip(0.55 + 0.0075*ltv, 0.80, 1.50))

def wcs_factor(wc: float, sales: float)->float:
    if sales<=0: return 1.20
    ratio = wc / sales
    return float(np.clip(0.70 + 1.00*min(ratio, 1.2), 0.70, 1.70))

def composite_risk(product: str, industry: str, malaa: int, ltv: float, wc: float, sales: float, is_fund: bool)->float:
    pf = product_factor[product]; inf = industry_factor[industry]; mf = malaa_factor(malaa)
    rf = ltv_factor(ltv if is_fund else 60.0) if is_fund else wcs_factor(wc, sales)
    return float(np.clip(pf*inf*mf*rf, 0.4, 3.5))

def pd_from_risk(r: float, stage: int)->float:
    # curve: 0.4→0.3%, 1.0→1.0%, 2.0→3.0%, 3.5→6.0%; stage: ×2.5 (S2), ×6 (S3)
    xs = np.array([0.4,1.0,2.0,3.5]); ys = np.array([0.3,1.0,3.0,6.0])
    pd = float(np.interp(r, xs, ys))
    if stage==2: pd*=2.5
    if stage==3: pd*=6.0
    return float(np.clip(pd, 0.10, 60.0))

def lgd_from_product_ltv(prod:str, ltv: float, is_fund: bool)->float:
    base = 32 if prod=="Asset Backed Loan" else 38 if prod=="Term Loan" else 35 if prod=="Export Finance" else 30
    adj = max(0.0, (0.0 if (ltv is None or (isinstance(ltv,float) and np.isnan(ltv))) else ltv)-50.0)*0.25
    if not is_fund: adj += 8.0
    return float(np.clip(base+adj, 25.0, 70.0))

def malaa_label(score:int)->str:
    if score < 500: return "High (poor score)"
    if score < 650: return "Medium-High"
    if score < 750: return "Medium"
    return "Low (good score)"

# floors/add-ons in basis points
BUCKETS = ["Low","Medium","High"]
BUCKET_MULT = {"Low":0.90,"Medium":1.00,"High":1.25}
BUCKET_BAND_BPS = {"Low":60,"Medium":90,"High":140}
BUCKET_FLOOR_BPS = {"Low":150,"Medium":225,"High":325}
MALAA_FLOOR_BPS = {"High (poor score)":175,"Medium-High":125,"Medium":75,"Low (good score)":0}

def industry_floor_addon(ind_fac: float)->int:
    return 100 if ind_fac>=1.25 else (50 if ind_fac>=1.10 else 0)

def product_floor_addon(prod:str)->int:
    return 125 if prod=="Asset Backed Loan" else (75 if prod in ["Term Loan","Export Finance"] else 0)

def base_spread_from_risk(risk: float)->float:
    # bps curve around risk
    return 75 + 350*(risk - 1.0)

# ---------------- Cashflow blocks ----------------
def fund_first_year_metrics(P: float, tenor_m: int, rep_rate: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float)\
        -> Tuple[float,float,float,float]:
    i = rep_rate/100.0/12.0
    if i<=0 or tenor_m<=0 or P<=0: return 0.0,0.0,1.0,0.0
    EMI = P * i * (1+i)**tenor_m / ((1+i)**tenor_m - 1)
    months = min(12, tenor_m)
    bal = P; sum_net_12=0.0; sum_bal_12=0.0
    for _ in range(months):
        interest = bal * i
        fee = P * (fees_pct/100.0/12.0)
        funding = bal * (cof_pct/100.0/12.0)
        prov = bal * (prov_pct/100.0/12.0)
        opex = bal * (opex_pct/100.0/12.0)
        net = interest + fee - (funding + prov + opex)
        sum_net_12 += net
        sum_bal_12 += bal
        principal = EMI - interest
        bal = max(bal - principal, 0.0)
    AEA_12 = max(sum_bal_12/months, 1e-9)
    NII_annual = sum_net_12
    NIM_pct = (NII_annual/AEA_12)*100.0
    return f2(EMI), f2(NII_annual), f2(AEA_12), f2(NIM_pct)

def fund_breakeven_months(P: float, tenor_m:int, rate_pct: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float, upfront_cost_pct: float):
    i = rate_pct/100.0/12.0
    if i<=0 or tenor_m<=0 or P<=0: return "Breakeven not within the tenor"
    EMI = P * i * (1+i)**tenor_m / ((1+i)**tenor_m - 1)
    bal=P; C0 = upfront_cost_pct/100.0 * P; cum=-C0
    for m in range(1, tenor_m+1):
        interest = bal*i
        fee = P * (fees_pct/100.0/12.0)
        funding = bal * (cof_pct/100.0/12.0)
        prov = bal * (prov_pct/100.0/12.0)
        opex = bal * (opex_pct/100.0/12.0)
        net = interest + fee - (funding + prov + opex)
        cum += net
        principal = EMI - interest
        bal = max(bal - principal, 0.0)
        if cum>=0: return m
    return "Breakeven not within the tenor"

def util_metrics(limit_or_wc: float, industry:str, rep_rate: float, fees_pct: float, cof_pct: float, prov_pct: float, opex_pct: float, upfront_cost_pct: float):
    u = u_med_map[industry]
    EAD = max(limit_or_wc, 0.0) * u
    margin_pct = rep_rate + fees_pct - (cof_pct + prov_pct + opex_pct)
    NIM_pct = margin_pct
    NII_annual = (margin_pct/100.0) * EAD
    C0 = upfront_cost_pct/100.0 * max(limit_or_wc, 0.0)
    if margin_pct>0 and EAD>0:
        m_be = math.ceil(C0 / (NII_annual/12.0))
        return f2(EAD), f2(NIM_pct), f2(NII_annual), (m_be if m_be>0 else 1), f2(u*100.0)
    return f2(EAD), f2(NIM_pct), f2(NII_annual), "Breakeven not within the tenor", f2(u*100.0)

# ---------------- UI ----------------
st.set_page_config(page_title="rt 360 risk-adjusted pricing", page_icon="💠", layout="wide")
st.markdown("""
<style>
.big {font-size:28px;font-weight:800}
.blue {color:#1666d3}
.green {color:#18a05e}
.card {background:white;border:4px solid #1666d3;border-radius:14px;padding:14px 18px;box-shadow:0 6px 18px rgba(0,0,0,0.08);}
.small {color:#6b7280;font-size:12px}
</style>
<div class="big"><span class="blue">rt</span> <span class="green">360</span> — Risk-Adjusted Pricing Model for Corporate Lending</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("Market & Bank Assumptions")
    oibor_pct = st.number_input("OIBOR (Reference Rate, %)", value=4.10, step=0.00, format="%.2f")
    cof_pct = st.number_input("Cost of Funds (%, annual)", value=5.00, step=0.00, format="%.2f")
    target_nim_pct = st.number_input("Target Net Interest Margin (%, floor)", value=2.50, step=0.00, format="%.2f")
    opex_pct = st.number_input("Operating Expense (%, annual)", value=0.40, step=0.00, format="%.2f")
    fees_default = st.number_input("Default Fees (%, WC/SCF/VF/Export)", value=0.40, step=0.00, format="%.2f")
    upfront_cost_pct= st.number_input("Upfront Origination Cost (%, one-time)", value=0.50, step=0.00, format="%.2f")
    st.markdown("---")

    st.subheader("Borrower & Product")
    product = st.selectbox("Product", PRODUCTS_FUND + PRODUCTS_UTIL)
    industry = st.selectbox("Borrower Industry", list(industry_factor.keys()))
    malaa_score = int(st.number_input("Mala’a Credit Score (300–900)", value=750, step=0, format="%d"))
    stage = int(st.number_input("IFRS-9 Stage (1=Performing, 2=Underperforming, 3=Impaired)", value=1, min_value=1, max_value=3, step=0, format="%d"))
    st.markdown("---")

    st.subheader("Loan Details (Typed Inputs)")
    tenor_months = int(st.number_input("Tenor (months, 6–360)", value=36, min_value=6, max_value=360, step=0, format="%d"))
    loan_quantum_omr = st.number_input("Loan Quantum (OMR) — principal or limit", value=100000.00, step=0.00, format="%.2f")
    st.caption(f"In words: {num_to_words(int(loan_quantum_omr))} Omani Rials")

    is_fund = product in PRODUCTS_FUND
    if is_fund:
        ltv_pct = st.number_input("Loan-to-Value (LTV, %)", value=70.00, step=0.00, format="%.2f")
        wc_omr, sales_omr = 0.0, 0.0
        fees_pct = 0.00 # fund-based: no default fees unless Export Finance
        if product == "Export Finance":
            fees_pct = fees_default
    else:
        ltv_pct = float("nan")
        wc_omr = loan_quantum_omr # treat entered quantum as limit for utilization products
        sales_omr = st.number_input("Annual Sales (OMR)", value=600000.00, step=0.00, format="%.2f")
        st.caption(f"In words: {num_to_words(int(sales_omr))} Omani Rials")
        fees_pct = fees_default

    st.markdown("---")
    run = st.button("Compute Pricing")

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Pricing Buckets (Low / Medium / High)")
if not run:
    st.info("Enter inputs in the left pane and click **Compute Pricing**.")
st.markdown('</div>', unsafe_allow_html=True)

if run:
    # ------- Composite risk & Provision -------
    risk_base = composite_risk(product, industry, malaa_score, ltv_pct if is_fund else 60.0, wc_omr, sales_omr, is_fund)
    pd_pct_base = pd_from_risk(risk_base, stage)
    lgd_pct_base = lgd_from_product_ltv(product, ltv_pct, is_fund)
    provision_pct_base = f2(pd_pct_base * (lgd_pct_base/100.0)) # annual % of avg EAD

    # ------- Buckets: spread construction -------
    rows: List[Dict[str,Any]] = []
    malaa_lbl = malaa_label(malaa_score)
    ind_add = industry_floor_addon(industry_factor[industry])
    prod_add = product_floor_addon(product)
    malaa_add = MALAA_FLOOR_BPS[malaa_lbl]
    min_core_spread_bps = 125

    for bucket in BUCKETS:
        # scale risk for bucket
        risk_b = float(np.clip(risk_base * BUCKET_MULT[bucket], 0.4, 3.5))
        # PD/LGD per bucket (stage-aware)
        pd_pct = pd_from_risk(risk_b, stage)
        lgd_pct = lgd_from_product_ltv(product, ltv_pct if is_fund else 60.0, is_fund)
        prov_pct = f2(pd_pct * (lgd_pct/100.0)) # shown in brackets later

        raw_bps = base_spread_from_risk(risk_b)
        floors = BUCKET_FLOOR_BPS[bucket] + malaa_add + ind_add + prod_add
        base_bps = max(int(round(raw_bps)), floors, min_core_spread_bps)
        band_bps = BUCKET_BAND_BPS[bucket]

        # Initial band → convert to rate band
        spread_min_bps = max(base_bps - band_bps, floors, min_core_spread_bps)
        spread_max_bps = max(base_bps + band_bps, spread_min_bps + 10)

        rate_min = clamp(oibor_pct + spread_min_bps/100.0, 5.00, 12.00)
        rate_max = clamp(oibor_pct + spread_max_bps/100.0, 5.00, 12.00)
        rep_rate = (rate_min + rate_max)/2.0

        # Fund floor first (6.00)
        if is_fund:
            rate_min = max(rate_min, 6.00)
            rate_max = max(rate_max, 6.00)
            rep_rate = max(rep_rate, 6.00)

        # Strict Target NIM floor:
        # required rate = CoF + Provision + Opex - Fees + Target NIM
        required_rate = f2(cof_pct + prov_pct + opex_pct - fees_pct + target_nim_pct)
        rep_rate = max(rep_rate, required_rate)

        # Rebuild symmetric mini-band around center; clamp
        half_band = band_bps/200.0
        rate_min = clamp(rep_rate - half_band, 5.00, 12.00)
        rate_max = clamp(rep_rate + half_band, 5.00, 12.00)
        if rate_max - rate_min < 0.10:
            rate_max = clamp(rate_min + 0.10, 5.00, 12.00)

        # Floats over OIBOR (bps)
        fl_min_bps = max(int(round((rate_min - oibor_pct)*100)), min_core_spread_bps)
        fl_max_bps = max(int(round((rate_max - oibor_pct)*100)), fl_min_bps + 10)

        # ------- Cash metrics -------
        if is_fund:
            EMI, NII_annual, AEA_12, NIM_pct = fund_first_year_metrics(
                loan_quantum_omr, tenor_months, rep_rate, fees_pct, cof_pct, prov_pct, opex_pct
            )
            be_min = fund_breakeven_months(loan_quantum_omr, tenor_months, rate_min, fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct)
            be_rep = fund_breakeven_months(loan_quantum_omr, tenor_months, rep_rate, fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct)
            be_max = fund_breakeven_months(loan_quantum_omr, tenor_months, rate_max, fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct)

            # Decomposed annual components (approx using AEA_12)
            annual_interest = f2((rep_rate/100.0)*AEA_12)
            annual_fee = f2((fees_pct/100.0)*loan_quantum_omr)
            annual_funding = f2((cof_pct/100.0)*AEA_12)
            annual_prov = f2((prov_pct/100.0)*AEA_12)
            annual_opex = f2((opex_pct/100.0)*AEA_12)
            nii = f2(annual_interest + annual_fee - (annual_funding + annual_prov + annual_opex))

            rows.append({
                "Pricing Bucket": bucket,
                "Float (Min) over OIBOR (basis points)": fl_min_bps,
                "Float (Max) over OIBOR (basis points)": fl_max_bps,
                "Interest Rate — Min (%)": f2(rate_min),
                "Interest Rate — Representative (%)": f2(rep_rate),
                "Interest Rate — Max (%)": f2(rate_max),
                "Equivalent Monthly Installment (OMR)": f2(EMI),
                "Annual Interest Income (OMR)": annual_interest,
                "Annual Fee Income (OMR)": annual_fee,
                "Annual Funding Cost (OMR)": annual_funding,
                "Annual Provision (OMR)": annual_prov,
                "Annual Operating Expense (OMR)": annual_opex,
                "Net Interest Income (OMR)": nii,
                "Net Interest Margin (%)": f2(NIM_pct),
                "Breakeven — Min Rate (months)": be_min,
                "Breakeven — Rep Rate (months)": be_rep,
                "Breakeven — Max Rate (months)": be_max,
                # Expanded labels & Provision% in brackets on risk lines:
                "Borrower Risk (by Mala’a)": f"{malaa_lbl}",
                "Industry Risk Factor (×)": f2(industry_factor[industry]),
                "Product Risk Factor (×)": f2(product_factor[product]),
                "Composite Risk Score (×)": f2(risk_base),
                "Provision % (PD × LGD, annual)": f2(prov_pct)
            })
        else:
            # Utilization loans
            EAD, NIM_pct, NII_annual, be_rep, u_pct = util_metrics(
                loan_quantum_omr, industry, rep_rate, fees_pct, cof_pct, prov_pct, opex_pct, upfront_cost_pct
            )
            # recompute BE for min/max via margin
            def util_be(rate: float):
                margin = rate + fees_pct - (cof_pct + prov_pct + opex_pct)
                if margin<=0 or loan_quantum_omr<=0: return "Breakeven not within the tenor"
                m = math.ceil((upfront_cost_pct/100.0 * loan_quantum_omr) / ((margin/100.0)*(loan_quantum_omr*u_med_map[industry])/12.0))
                return m if m<=tenor_months else "Breakeven not within the tenor"
            be_min = util_be(rate_min); be_max = util_be(rate_max)

            annual_interest = f2((rep_rate/100.0) * EAD)
            annual_fee = f2((fees_pct/100.0) * loan_quantum_omr)
            annual_funding = f2((cof_pct/100.0) * EAD)
            annual_prov = f2((prov_pct/100.0) * EAD)
            annual_opex = f2((opex_pct/100.0) * EAD)
            nii = f2(annual_interest + annual_fee - (annual_funding + annual_prov + annual_opex))

            rows.append({
                "Pricing Bucket": bucket,
                "Float (Min) over OIBOR (basis points)": fl_min_bps,
                "Float (Max) over OIBOR (basis points)": fl_max_bps,
                "Interest Rate — Min (%)": f2(rate_min),
                "Interest Rate — Representative (%)": f2(rep_rate),
                "Interest Rate — Max (%)": f2(rate_max),
                "Equivalent Monthly Installment (OMR)": "-",
                "Annual Interest Income (OMR)": annual_interest,
                "Annual Fee Income (OMR)": annual_fee,
                "Annual Funding Cost (OMR)": annual_funding,
                "Annual Provision (OMR)": annual_prov,
                "Annual Operating Expense (OMR)": annual_opex,
                "Net Interest Income (OMR)": nii,
                "Net Interest Margin (%)": f2(NIM_pct),
                "Breakeven — Min Rate (months)": be_min,
                "Breakeven — Rep Rate (months)": be_rep,
                "Breakeven — Max Rate (months)": be_max,
                "Borrower Risk (by Mala’a)": f"{malaa_lbl}",
                "Industry Risk Factor (×)": f2(industry_factor[industry]),
                "Product Risk Factor (×)": f2(product_factor[product]),
                "Composite Risk Score (×)": f2(risk_base),
                "Provision % (PD × LGD, annual)": f2(prov_pct),
                "Optimal Utilization (%)": f2(u_pct)
            })

    out = pd.DataFrame(rows)
    # ensure 2-decimals for floats
    for col in out.columns:
        if out[col].dtype.kind in "f":
            out[col] = out[col].apply(f2)

    st.dataframe(out, use_container_width=True)

# ---------------- Notes / legend ----------------
with st.expander("Legend & Formulas"):
    st.markdown("""
- **Float over OIBOR (bps)**: basis points of spread over the reference rate (OIBOR).
- **Equivalent Monthly Installment (EMI)**: monthly payment for fund-based loans at the representative rate.
- **Net Interest Income (NII)**: Interest + Fees − (Funding Cost + Provision + Operating Expense), annualized.
- **Net Interest Margin (NIM)**: NII ÷ Average Earning Assets (first 12 months).
- **Provision % (PD × LGD, annual)**: Probability of Default × Loss Given Default, as a % of average exposure.
- **Buckets**: Low / Medium / High apply risk multipliers and wider / narrower bands to spreads.
- **Floors & Caps**: Rate ≥ 5.00%; **fund-based floor = 6.00%**; **cap = 12.00%**.
- **Target NIM** is enforced as a floor:  
  `Required Rate = Cost of Funds + Provision + Operating Expense − Fees + Target NIM`.
- **Utilization loans** (WC/Trade/SCF/VF): income volume uses industry median utilization for 
