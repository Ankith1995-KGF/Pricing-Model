                "malaa_score": 850,
                "working_capital": 50000,
                "sales": 2000000
            },
            "Medium Risk": {
                "product": "Term Loan", 
                "industry": "Manufacturing",
                "malaa_score": 700,
                "ltv": 70
            },
            "High Risk": {
                "product": "Asset Backed Loan",
                "industry": "Construction",
                "malaa_score": 400,
                "ltv": 85
            }
        }
        
        for i, (name, scenario) in enumerate(scenarios.items()):
            with cols[i]:
                if st.button(f"Load {name} Scenario"):
                    for key, value in scenario.items():
                        st.session_state[key] = value
                    st.rerun()
if __name__ == "__main__":
    main()
