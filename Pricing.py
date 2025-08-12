with tab2:
    uploaded_file = st.file_uploader("Upload Loan Book (CSV)", type=["csv"])
    if uploaded_file is not None:
        try:
            loan_book_df = pd.read_csv(uploaded_file)
            st.success(f"Loaded {len(loan_book_df)} loan records.")
            
            all_results = []
            for _, loan in loan_book_df.iterrows():
                # Prepare parameters for your existing pricing functions
                loan_params = {
                    "product": loan["product"],
                    "industry": loan["industry"],
                    "malaa_score": loan["malaa_score"],
                    "stage": loan["stage"],
                    "tenor": loan["tenor_months"],
                    "amount": loan["loan_quantum_omr"],
                    "ltv": loan.get("ltv_pct", None),
                    "working_capital": loan.get("working_capital_omr", None),
                    "sales": loan.get("sales_omr", None)
                }
                
                # Perform risk and pricing calculations as in your single loan function
                risk_base, product_factor, industry_factor = calculate_risk_factors(
                    loan_params["product"], loan_params["industry"], loan_params["malaa_score"],
                    loan_params.get("ltv"), loan_params.get("working_capital"), loan_params.get("sales")
                )
                pd_val, lgd_val = calculate_pd_lgd(
                    risk_base, loan_params["product"], loan_params.get("ltv"), loan_params["stage"]
                )
                fees_pct = 0.4 if loan_params["product"] in ["Supply Chain Finance", "Vendor Finance", "Working Capital", "Export Finance"] else 0.0

                buckets = ["Low", "Medium", "High"]
                pricing_results = []
                
                for bucket in buckets:
                    pricing = calculate_loan_pricing(
                        risk_base, malaa_risk_label(loan_params["malaa_score"]),
                        market_params["oibor_pct"], market_params["cof_pct"],
                        market_params["opex_pct"], fees_pct, bucket, loan_params["product"]
                    )
                    prov_rate = pd_val * lgd_val / 10000
                    nim = pricing["rep_rate"] + fees_pct - (market_params["cof_pct"] + prov_rate * 100 + market_params["opex_pct"])
                    pricing.update({
                        "risk_score": risk_base,
                        "product_factor": product_factor,
                        "industry_factor": industry_factor,
                        "PD": pd_val,
                        "LGD": lgd_val,
                        "Provision_Rate": prov_rate,
                        "NIM": nim,
                        "oibor_pct": market_params["oibor_pct"],
                        "bucket": bucket,
                        "loan_id": loan.get("loan_id", None)
                    })
                    pricing_results.append(pricing)
                
                df_results = pd.DataFrame(pricing_results)
                all_results.append(df_results)
            
            if all_results:
                combined_results = pd.concat(all_results, ignore_index=True)
                combined_results = combined_results.round(2)  # limit decimals for display
                st.dataframe(combined_results.style.format("{:.2f}"))
                
                csv_bytes = combined_results.to_csv(index=False).encode('utf-8')
                st.download_button("Download Pricing Results CSV", data=csv_bytes, file_name="loan_book_pricing_results.csv", mime="text/csv")
        
        except Exception as e:
            st.error(f"Error processing the uploaded file: {e}")
    else:
        st.info("Upload a CSV file with your loan book data to perform batch pricing.")
