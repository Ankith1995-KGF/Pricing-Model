# app.py
import streamlit as st
import pandas as pd
import numpy as np
from num2words import num2words
from typing import Dict, Tuple, Union, List

# --- Constants and Lookup Tables ---
PRODUCT_LIST = [
    "Asset Backed Loan", "Term Loan", "Export Finance",
    "Working Capital", "Trade Finance", "Supply Chain Finance", "Vendor Finance"
]

INDUSTRY_LIST = [
    "Oil & Gas", "Construction", "Real Estate", "Manufacturing", "Trading", "Logistics",
    "Healthcare", "Hospitality", "Retail", "Mining", "Utilities", "Agriculture"
]

MALAA_SCORE_LIST = list(range(300, 901, 50))

TENOR_MIN = 6
TENOR_MAX = 360

PRODUCT_RISK_MULTIPLIER = {
    "Asset Backed Loan": 1.00, "Term Loan": 0.90, "Export Finance": 0.80,
    "Vendor Finance": 0.60, "Supply Chain Finance": 0.55, "Trade Finance": 0.50,
    "Working Capital": 0.50  # Included for utilization check
}

INDUSTRY_RISK_MULTIPLIER = {
    "Oil & Gas": 0.70, "Construction": 0.90, "Real Estate": 0.85, "Manufacturing": 0.80, "Trading": 0.75,
    "Logistics": 0.70, "Healthcare": 0.60, "Retail": 0.80, "Hospitality": 0.85, "Mining": 0.90,
    "Utilities": 0.55, "Agriculture": 0.85
}

INDUSTRY_MEDIAN_UTILIZATION = {
    "Trading": 0.65, "Manufacturing": 0.55, "Construction": 0.40, "Logistics": 0.60,
    "Retail": 0.50, "Healthcare": 0.45, "Hospitality": 0.35, "Oil & Gas": 0.50,
    "Real Estate": 0.30, "Utilities": 0.55, "Mining": 0.45, "Agriculture": 0.40
}

RISK_MULTIPLIERS = {"Low": 0.90, "Medium": 1.00, "High": 1.15}
BAND_BPS = {"Low": 50, "Medium": 75, "High": 100}
MIN_CORE_SPREAD_BPS = 75
RATE_MIN_CLAMP = 5.0
RATE_MAX_CLAMP = 10.0
FEE_YIELD_PCT_DEFAULT = 0.4
FUNDING_COST_PCT_DEFAULT = 5.0
TARGET_NIM_PCT_DEFAULT = 2.5
OPEX_PCT_DEFAULT = 0.4

# --- Utility Functions ---


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp the value between min_val and max_val."""
    return max(min(value, max_val), min_val)


def malaa_factor(malaa_score: int) -> float:
    """Calculate borrower (Mala’a) factor linearly from score."""
    return 1.3 - (malaa_score - 300) * (0.8 / 600)


def ltv_factor(ltv_pct: float) -> float:
    """Calculate LTV factor, clamped for fund-based products."""
    val = 0.7 + 0.0035 * ltv_pct
    return clamp(val, 0.8, 1.2)


def wcs_factor(working_capital: float, sales: float) -> float:
    """Calculate WC/Sales factor for utilization-based products."""
    wc_to_sales = working_capital / sales if sales > 0 else 0
    return 0.85 + 0.6 * min(wc_to_sales, 1.0)


def util_factor(u_med: float) -> float:
    """Calculate utilization factor for utilization-based products, clamped."""
    return clamp(1 - 0.15 * (0.8 - u_med), 0.85, 1.15)


def calc_risk_base(product_factor: float, industry_factor: float, malaa_f: float,
                   ltv_f: float = None, wcs_f: float = None, util_f: float = None,
                   is_fund_based: bool = True) -> float:
    """Calculate composite base risk factor with clamping."""
    if is_fund_based:
        risk = product_factor * industry_factor * malaa_f * ltv_f
    else:
        risk = product_factor * industry_factor * malaa_f * wcs_f * util_f
    return clamp(risk, 0.4, 2.0)


def compute_spread_bps(risk: float) -> float:
    """Compute base spread in bps from risk, clamped to bounds."""
    raw = 100 + 250 * (risk - 1)
    return clamp(raw, MIN_CORE_SPREAD_BPS, 500)


def compute_emi(principal: float, rate_annual_pct: float, tenor_months: int) -> float:
    """Calculate EMI monthly payment for amortizing loan."""
    i_m = rate_annual_pct / 100 / 12
    if i_m == 0:
        return principal / tenor_months
    emi = principal * i_m * (1 + i_m) ** tenor_months / ((1 + i_m) ** tenor_months - 1)
    return emi


def num2words_omr(amount: float) -> str:
    """Convert OMR amount to words (integer only) with Omani Rial currency."""
    # num2words outputs in English by default
    try:
        integer_amount = int(round(amount))
        words = num2words(integer_amount, to='cardinal', lang='en')
        return words.capitalize() + " Omani Rials"
    except Exception:
        return "-"


def determine_risk_category(score: int, industry_factor: float, product_factor: float) -> Tuple[str, str, str]:
    """Categorize borrower, industry and product risk levels."""
    if 300 <= score <= 499:
        borrower_risk = "High"
    elif 500 <= score <= 649:
        borrower_risk = "Medium-High"
    elif 650 <= score <= 749:
        borrower_risk = "Medium"
    else:
        borrower_risk = "Low"

    if industry_factor >= 0.85:
        industry_risk = "High"
    elif 0.70 <= industry_factor < 0.85:
        industry_risk = "Medium"
    else:
        industry_risk = "Low"

    if product_factor >= 0.90:
        product_risk = "High"
    elif 0.70 <= product_factor < 0.90:
        product_risk = "Medium"
    else:
        product_risk = "Low"

    return borrower_risk, industry_risk, product_risk


def compute_nim_and_nii_fund_based(principal: float, rate_pct: float, funding_cost_pct: float,
                                   credit_cost_pct: float, fee_yield_pct: float, opex_pct: float,
                                   tenor_months: int, emi: float) -> Tuple[float, float]:
    """Compute Annual Net Interest Income (NII) and NIM% for fund-based amortizing loan."""
    # Monthly parameters
    i_b = rate_pct / 100 / 12
    c_b = funding_cost_pct / 100 / 12
    cc_b = credit_cost_pct / 100 / 12
    op_b = opex_pct / 100 / 12
    fy_b = fee_yield_pct / 100 / 12

    balance = principal
    sum_net_12 = 0.0
    sum_bal_12 = 0.0
    months = min(tenor_months, 12)

    for m in range(1, months + 1):
        interest_income_m = balance * i_b
        fee_income_m = principal * fy_b
        funding_cost_m = balance * c_b
        credit_cost_m = balance * cc_b
        opex_m = balance * op_b

        net_margin_m = interest_income_m + fee_income_m - funding_cost_m - credit_cost_m - opex_m
        sum_net_12 += net_margin_m
        sum_bal_12 += balance

        principal_repaid = emi - interest_income_m
        balance = max(balance - principal_repaid, 0)

    NII_annual = sum_net_12
    AEA_12 = sum_bal_12 / (months if months > 0 else 1)
    NIM_pct = 100 * (NII_annual / max(AEA_12, 1e-9))
    return NII_annual, NIM_pct


def compute_nim_and_nii_utilization(principal: float, utilization: float, rate_pct: float,
                                    funding_cost_pct: float, credit_cost_pct: float,
                                    fee_yield_pct: float, opex_pct: float) -> Tuple[float, float]:
    """Compute Annual Net Interest Income (NII) and NIM% for utilization (revolving) product."""
    E_avg = principal * utilization
    margin_pct = rate_pct + fee_yield_pct - funding_cost_pct - credit_cost_pct - opex_pct
    NII_annual = (margin_pct / 100) * E_avg
    NIM_pct = margin_pct
    return NII_annual, NIM_pct


def compute_breakeven_fund_based(principal: float, rate_pct: float, funding_cost_pct: float,
                                 credit_cost_pct: float, fee_yield_pct: float, opex_pct: float,
                                 tenor_months: int, emi: float) -> Union[int, str]:
    """Compute breakeven months for fund-based product based on cumulative net margin."""
    i_b = rate_pct / 100 / 12
    c_b = funding_cost_pct / 100 / 12
    cc_b = credit_cost_pct / 100 / 12
    op_b = opex_pct / 100 / 12
    fy_b = fee_yield_pct / 100 / 12

    C0 = 0.5 / 100 * principal  # upfront setup cost
    balance = principal
    cum_net = -C0

    for m in range(1, tenor_months + 1):
        interest_income_m = balance * i_b
        fee_income_m = principal * fy_b
        funding_cost_m = balance * c_b
        credit_cost_m = balance * cc_b
        opex_m = balance * op_b

        net_margin_m = interest_income_m + fee_income_m - funding_cost_m - credit_cost_m - opex_m
        cum_net += net_margin_m
        principal_repaid = emi - interest_income_m
        balance = max(balance - principal_repaid, 0)

        if cum_net >= 0:
            return m
    return "Breakeven not within the tenor"


def compute_breakeven_utilization(principal: float, utilization: float, nim_pct: float,
                                  tenor_months: int) -> Union[int, str]:
    """Compute breakeven months for utilization products."""
    C0 = 0.5 / 100 * principal
    net_margin_monthly = (nim_pct / 100 / 12) * principal * utilization
    if net_margin_monthly <= 0:
        return "Breakeven not within the tenor"
    breakeven = int(np.ceil(C0 / net_margin_monthly))
    if breakeven > tenor_months:
        return "Breakeven not within the tenor"
    return breakeven


def find_optimal_utilization(product_factor: float, industry_factor: float, malaa_f: float,
                             wcs_f: float, oibor_pct: float,
                             fees_income_pct: float, funding_cost_pct: float,
                             opex_pct: float, target_nim_pct: float,
                             working_capital: float, sales: float) -> Union[int, str]:
    """Find minimum utilization u ∈ [0.30, 0.95] such that annualized NIM% ≥ target_nim_pct."""
    # Check in steps of 0.01
    for u in np.arange(0.30, 0.9501, 0.01):
        util_f = clamp(1 - 0.15 * (0.8 - u), 0.85, 1.15)
        risk_u = clamp(product_factor * industry_factor * malaa_f * wcs_f * util_f, 0.4, 2.0)
        base_spread_bps_u = clamp(100 + 250 * (risk_u - 1), MIN_CORE_SPREAD_BPS, 500)
        r_u = clamp(oibor_pct + base_spread_bps_u / 100, RATE_MIN_CLAMP, RATE_MAX_CLAMP)
        credit_cost_pct_u = clamp(0.4 * risk_u / 100, 0.2, 1.0)
        margin_pct_u = r_u + fees_income_pct - funding_cost_pct - credit_cost_pct_u - opex_pct
        if margin_pct_u >= target_nim_pct:
            return round(u * 100)
    return "– (not achievable)"


# --- Main App ---

def main():
    st.set_page_config(page_title="rt 360 risk-adjusted pricing model for Corporate Lending", layout="wide")

    # Title with "rt" blue and "360" green combined
    st.markdown(
        """
        <h1 style='font-weight:bold; font-size:2.5rem'>
            <span style='color:blue;'>rt</span>
            <span style='color:green;'>360</span>
        </h1>
        """, unsafe_allow_html=True
    )

    # CSS style for main container border (blue thick)
    st.markdown(
        """
        <style>
        .main-container {
            border: 4px solid #0078D7; 
            padding: 20px; 
            border-radius: 8px;
            background-color: white;
        }
        </style>
        """, unsafe_allow_html=True
    )

    with st.container():
        st.markdown('<div class="main-container">', unsafe_allow_html=True)

        # Sidebar inputs
        with st.sidebar:
            st.header("Inputs")

            # Market & portfolio - editable defaults
            oibor_pct = st.number_input("OIBOR %", value=4.1, step=0.01, format="%.2f")
            cost_of_funds_pct = st.number_input("Cost of Funds %", value=5.0, step=0.01, format="%.2f")
            target_nim_pct = st.number_input("Target NIM %", value=2.5, step=0.01, format="%.2f")
            fees_income_pct = st.number_input("Fees Income %", value=0.4, step=0.01, format="%.2f")

            # Product selection
            product = st.selectbox("Product", PRODUCT_LIST)

            # Industry selection
            industry = st.selectbox("Industry", INDUSTRY_LIST)

            # Mala'a Score dropdown
            malaa_score = st.selectbox("Mala’a Score", MALAA_SCORE_LIST, index=MALAA_SCORE_LIST.index(650))

            # Tenor slider
            tenor_months = st.slider("Tenor (months)", TENOR_MIN, TENOR_MAX, 36)

            # Loan Quantum / Working Capital / Sales inputs
            if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                loan_quantum = st.number_input("Loan Quantum (OMR)", min_value=0.0, value=100000.0, step=1000.0, format="%.2f")
                LTV_pct = st.number_input("Loan to Value (LTV) %", min_value=0.0, max_value=100.0, value=80.0, step=0.1, format="%.2f")
                st.markdown(f"Amount in words: *{num2words_omr(loan_quantum)}*")
            else:  # Utilization-based products
                working_capital = st.number_input("Working Capital (OMR)", min_value=0.0, value=50000.0, step=1000.0, format="%.2f")
                sales = st.number_input("Sales (OMR)", min_value=0.0, value=200000.0, step=1000.0, format="%.2f")
                st.markdown(f"Working Capital in words: *{num2words_omr(working_capital)}*")
                st.markdown(f"Sales in words: *{num2words_omr(sales)}*")

            fetch_pricing = st.button("Fetch Pricing")

        # Compute & display results only on click
        if fetch_pricing:
            # Validate input
            if product in ["Asset Backed Loan", "Term Loan", "Export Finance"]:
                if LTV_pct == 0:
                    st.error("LTV must be > 0 for fund-based products.")
                    return
                loan_quantum_val = loan_quantum
                is_fund_based = True
            else:  # utilization-based
                if working_capital <= 0 or sales <= 0:
                    st.error("Working Capital and Sales must be > 0 for utilization-based products.")
                    return
                loan_quantum_val = working_capital
                is_fund_based = False

            # Prepare factors
            product_factor = PRODUCT_RISK_MULTIPLIER.get(product, 0.5)
            industry_factor = INDUSTRY_RISK_MULTIPLIER.get(industry, 0.7)
            malaa_f = malaa_factor(malaa_score)

            # Factors depending on product type
            if is_fund_based:
                ltv_f = ltv_factor(LTV_pct)
                risk_base = calc_risk_base(product_factor, industry_factor, malaa_f, ltv_f=ltv_f, is_fund_based=True)
            else:
                wcs_f = wcs_factor(working_capital, sales)
                u_med = INDUSTRY_MEDIAN_UTILIZATION.get(industry, 0.50)
                util_f = util_factor(u_med)
                risk_base = calc_risk_base(product_factor, industry_factor, malaa_f, wcs_f=wcs_f, util_f=util_f, is_fund_based=False)

            rows = []
            for bucket in ["Low", "Medium", "High"]:
                risk_mult = RISK_MULTIPLIERS[bucket]
                risk_b = clamp(risk_base * risk_mult, 0.4, 2.0)

                base_spread_bps_b = compute_spread_bps(risk_b)
                # Bucket bands for min/max float
                raw_min_bps = base_spread_bps_b - BAND_BPS[bucket]
                raw_max_bps = base_spread_bps_b + BAND_BPS[bucket]

                spread_min_bps_b = max(int(round(raw_min_bps)), MIN_CORE_SPREAD_BPS)
                spread_max_bps_b = max(int(round(raw_max_bps)), spread_min_bps_b + 1)

                rate_min_pct_b = clamp(oibor_pct + spread_min_bps_b / 100, RATE_MIN_CLAMP, RATE_MAX_CLAMP)
                rate_max_pct_b = clamp(oibor_pct + spread_max_bps_b / 100, RATE_MIN_CLAMP, RATE_MAX_CLAMP)

                # Recompute spreads after rate clamp to keep consistency
                spread_min_bps_b = max(int(round((rate_min_pct_b - oibor_pct) * 100)), MIN_CORE_SPREAD_BPS)
                spread_max_bps_b = max(int(round((rate_max_pct_b - oibor_pct) * 100)), spread_min_bps_b + 1)

                r_rep_b = (rate_min_pct_b + rate_max_pct_b) / 2

                # Credit cost proxy (clamped)
                credit_cost_pct_b = clamp(0.4 * risk_b / 100, 0.2, 1.0)

                # Calculate EMI
                if is_fund_based:
                    EMI_OMR = compute_emi(loan_quantum_val, r_rep_b, tenor_months)
                    EMI_display = f"{EMI_OMR:,.2f}"
                else:
                    # Revolving products:
                    # Set EMI = "–" for revolving products as per domain logic
                    EMI_display = "–"

                # Calculate NII and NIM%
                if is_fund_based:
                    NII_annual_b, NIM_pct_b = compute_nim_and_nii_fund_based(
                        loan_quantum_val, r_rep_b, cost_of_funds_pct, credit_cost_pct_b, fees_income_pct,
                        OPEX_PCT_DEFAULT, tenor_months, EMI_OMR
                    )
                else:
                    NII_annual_b, NIM_pct_b = compute_nim_and_nii_utilization(
                        loan_quantum_val, u_med, r_rep_b, cost_of_funds_pct, credit_cost_pct_b, fees_income_pct,
                        OPEX_PCT_DEFAULT
                    )

                # Breakeven months
                if is_fund_based:
                    breakeven_months_b = compute_breakeven_fund_based(
                        loan_quantum_val, r_rep_b, cost_of_funds_pct, credit_cost_pct_b, fees_income_pct,
                        OPEX_PCT_DEFAULT, tenor_months, EMI_OMR
                    )
                else:
                    breakeven_months_b = compute_breakeven_utilization(
                        loan_quantum_val, u_med, NIM_pct_b, tenor_months
                    )

                # Optimal utilization only for utilization-based; else "–"
                if not is_fund_based:
                    optimal_util_pct = find_optimal_utilization(
                        product_factor, industry_factor, malaa_f, wcs_f, oibor_pct,
                        fees_income_pct, cost_of_funds_pct, OPEX_PCT_DEFAULT,
                        target_nim_pct, working_capital, sales
                    )
                else:
                    optimal_util_pct = "–"

                rows.append({
                    "Bucket": bucket,
                    "Float_Min_over_OIBOR_bps": spread_min_bps_b,
                    "Float_Max_over_OIBOR_bps": spread_max_bps_b,
                    "Rate_Min_% (OIBOR+)": f"{rate_min_pct_b:.2f}",
                    "Rate_Max_%": f"{rate_max_pct_b:.2f}",
                    "EMI_OMR": EMI_display,
                    "Net_Interest_Income_OMR": f"{NII_annual_b:,.2f}",
                    "NIM_%": f"{NIM_pct_b:.2f}",
                    "Breakeven_Months": breakeven_months_b,
                    "Optimal_Utilization_%": optimal_util_pct
                })

            df = pd.DataFrame(rows)

            # Show risk categorization card
            borrower_risk, industry_risk, product_risk = determine_risk_category(malaa_score, industry_factor, product_factor)

            st.markdown("<h3>Risk Categorization</h3>", unsafe_allow_html=True)
            st.markdown(f"""
                <div style="border:2px solid #0078D7; padding:10px; width:300px; border-radius:8px;">
                <b>Borrower Risk (Mala’a):</b> {borrower_risk}<br>
                <b>Industry Risk:</b> {industry_risk}<br>
                <b>Product Risk:</b> {product_risk}
                </div>
            """, unsafe_allow_html=True)

            st.markdown("<h3>Pricing Table</h3>", unsafe_allow_html=True)
            st.dataframe(df.style.set_table_styles([
                {'selector': 'th', 'props': [('background-color', '#0078D7'), ('color', 'white'), ('font-weight', 'bold')]},
                {'selector': 'td', 'props': [('text-align', 'center')]}
            ]) , height=300)


        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
