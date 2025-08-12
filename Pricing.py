<!DOCTYPE html>
<html>
<head>
    <title>BankRisk Pro - Loan Pricing Model</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .card {
            background: white;
            border: 2px solid #1666d3;
            border-radius: 10px;
            padding: 16px 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        }
        .big {
            font-size:28px;
            font-weight:800;
        }
        .blue {
            color:#1666d3;
        }
        .green {
            color:#18a05e;
        }
        .small {
            color:#6b7280;
            font-size:12px;
        }
    </style>
</head>
<body class="bg-gray-50">
    <div class="container mx-auto px-4 py-8">
        <div class="big mb-8">
            <span class="blue">BankRisk</span> <span class="green">Pro</span> — Advanced Loan Pricing for Financial Institutions
        </div>

        <div class="flex flex-col md:flex-row gap-6">
            <!-- Sidebar -->
            <div class="w-full md:w-1/3 lg:w-1/4">
                <div class="card">
                    <h2 class="text-xl font-bold mb-4">Market & Bank Assumptions</h2>
                    <div class="grid gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">OIBOR (Reference Rate, %)</label>
                            <input type="number" id="oibor" value="4.10" step="0.01" class="w-full p-2 border border-gray-300 rounded">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Cost of Funds (%, annual)</label>
                            <input type="number" id="cof" value="5.00" step="0.01" class="w-full p-2 border border-gray-300 rounded">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Target NIM (%, floor)</label>
                            <input type="number" id="target_nim" value="2.50" step="0.01" class="w-full p-2 border border-gray-300 rounded">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Operating Expense (%, annual)</label>
                            <input type="number" id="opex" value="0.40" step="0.01" class="w-full p-2 border border-gray-300 rounded">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Default Fees (%, WC/SCF/VF/Export)</label>
                            <input type="number" id="fees_default" value="0.40" step="0.01" class="w-full p-2 border border-gray-300 rounded">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Upfront Origination Cost (%, one-time)</label>
                            <input type="number" id="upfront_cost" value="0.50" step="0.01" class="w-full p-2 border border-gray-300 rounded">
                        </div>
                    </div>

                    <hr class="my-4">

                    <h2 class="text-xl font-bold mb-4">Borrower & Product</h2>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Product</label>
                        <select id="product" class="w-full p-2 border border-gray-300 rounded">
                            <option value="Asset Backed Loan">Asset Backed Loan</option>
                            <option value="Term Loan">Term Loan</option>
                            <option value="Export Finance">Export Finance</option>
                            <option value="Working Capital">Working Capital</option>
                            <option value="Trade Finance">Trade Finance</option>
                            <option value="Supply Chain Finance">Supply Chain Finance</option>
                            <option value="Vendor Finance">Vendor Finance</option>
                        </select>
                    </div>
                    <div class="mt-3">
                        <label class="block text-sm font-medium text-gray-700 mb-1">Borrower Industry</label>
                        <select id="industry" class="w-full p-2 border border-gray-300 rounded">
                            <option value="Construction">Construction</option>
                            <option value="Real Estate">Real Estate</option>
                            <option value="Mining">Mining</option>
                            <option value="Hospitality">Hospitality</option>
                            <option value="Retail">Retail</option>
                            <option value="Manufacturing">Manufacturing</option>
                            <option value="Trading">Trading</option>
                            <option value="Logistics">Logistics</option>
                            <option value="Oil & Gas">Oil & Gas</option>
                            <option value="Healthcare">Healthcare</option>
                            <option value="Utilities">Utilities</option>
                            <option value="Agriculture">Agriculture</option>
                        </select>
                    </div>
                    <div class="mt-3">
                        <label class="block text-sm font-medium text-gray-700 mb-1">Mala'a Credit Score (300-900)</label>
                        <input type="number" id="malaa" min="300" max="900" value="750" class="w-full p-2 border border-gray-300 rounded">
                    </div>
                    <div class="mt-3">
                        <label class="block text-sm font-medium text-gray-700 mb-1">IFRS-9 Stage</label>
                        <select id="stage" class="w-full p-2 border border-gray-300 rounded">
                            <option value="1">1=Performing</option>
                            <option value="2">2=Underperforming</option>
                            <option value="3">3=Impaired</option>
                        </select>
                    </div>

                    <hr class="my-4">

                    <h2 class="text-xl font-bold mb-4">Loan Details</h2>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Tenor (months, 6-360)</label>
                        <input type="number" id="tenor" min="6" max="360" value="36" class="w-full p-2 border border-gray-300 rounded">
                    </div>
                    <div class="mt-3">
                        <label class="block text-sm font-medium text-gray-700 mb-1">Loan Quantum (OMR)</label>
                        <input type="number" id="loan_quantum" value="100000.00" step="0.01" class="w-full p-2 border border-gray-300 rounded">
                        <p class="small mt-1 italic" id="loan_in_words">In words: one hundred thousand Omani Rials</p>
                    </div>
                    <div id="ltv_container" class="mt-3">
                        <label class="block text-sm font-medium text-gray-700 mb-1">Loan-to-Value (LTV, %)</label>
                        <input type="number" id="ltv" value="70.00" step="0.01" class="w-full p-2 border border-gray-300 rounded">
                    </div>
                    <div id="sales_container" class="mt-3 hidden">
                        <label class="block text-sm font-medium text-gray-700 mb-1">Annual Sales (OMR)</label>
                        <input type="number" id="sales" value="600000.00" step="0.01" class="w-full p-2 border border-gray-300 rounded">
                        <p class="small mt-1 italic" id="sales_in_words">In words: six hundred thousand Omani Rials</p>
                    </div>

                    <button id="compute" class="w-full mt-6 bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg shadow-md">
                        Calculate Loan Pricing
                    </button>
                </div>
            </div>

            <!-- Main Content -->
            <div class="w-full md:w-2/3 lg:w-3/4">
                <div class="card">
                    <h2 class="text-xl font-bold mb-4">Pricing Buckets (Low / Medium / High)</h2>
                    <div id="results">
                        <div class="text-blue-600">Enter inputs in the left pane and click <strong>Compute Pricing</strong>.</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Number to words function
        function numToWords(n) {
            const units = ["","one","two","three","four","five","six","seven","eight","nine"];
            const teens = ["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"];
            const tens = ["","","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"];
            
            function chunk(x) {
                if(x === 0) return "";
                if(x < 10) return units[x];
                if(x < 20) return teens[x-10];
                if(x < 100) return tens[Math.floor(x/10)] + (x%10 === 0 ? "" : " "+units[x%10]);
                if(x < 1000) return units[Math.floor(x/100)] + " hundred" + (x%100 === 0 ? "" : " " + chunk(x%100));
                return "";
            }
            
            if(n === 0) return "zero";
            const parts = [];
            for(const [div,word] of [[10**9,"billion"],[10**6,"million"],[10**3,"thousand"]]) {
                if(n >= div) {
                    parts.push(chunk(Math.floor(n/div)) + " " + word);
                    n %= div;
                }
            }
            if(n > 0) parts.push(chunk(n));
            return parts.join(" ");
        }

        // Formatters
        function f2(x) {
            try {
                return parseFloat(parseFloat(x).toFixed(2));
            } catch {
                return parseFloat("NaN");
            }
        }

        function fmt2(x) {
            try {
                return f2(parseFloat(x)).toFixed(2);
            } catch {
                return "";
            }
        }

        // Product and industry factors
        const PRODUCTS_FUND = ["Asset Backed Loan","Term Loan","Export Finance"];
        const PRODUCTS_UTIL = ["Working Capital","Trade Finance","Supply Chain Finance","Vendor Finance"];
        
        const productFactor = {
            "Asset Backed Loan":1.35, "Term Loan":1.20, "Export Finance":1.10,
            "Vendor Finance":0.95, "Supply Chain Finance":0.90, "Trade Finance":0.85, "Working Capital":0.95
        };
        
        const industryFactor = {
            "Construction":1.40, "Real Estate":1.30, "Mining":1.30, "Hospitality":1.25,
            "Retail":1.15, "Manufacturing":1.10, "Trading":1.05, "Logistics":1.00,
            "Oil & Gas":0.95, "Healthcare":0.90, "Utilities":0.85, "Agriculture":1.15
        };
        
        const uMedMap = {
            "Trading":0.65,"Manufacturing":0.55,"Construction":0.40,"Logistics":0.60,"Retail":0.50,
            "Healthcare":0.45,"Hospitality":0.35,"Oil & Gas":0.50,"Real Estate":0.30,"Utilities":0.55,
            "Mining":0.45,"Agriculture":0.40
        };

        // Helper functions
        function clamp(x, lo, hi) {
            return Math.max(lo, Math.min(x, hi));
        }

        function malaaFactor(score) {
            return clamp(1.45 - (score-300)*(0.90/600), 0.55, 1.45);
        }

        function ltvFactor(ltv) {
            return clamp(0.55 + 0.0075*ltv, 0.80, 1.50);
        }

        function wcsFactor(wc, sales) {
            if(sales <= 0) return 1.20;
            const ratio = wc / sales;
            return clamp(0.70 + 1.00*Math.min(ratio, 1.2), 0.70, 1.70);
        }

        function compositeRisk(product, industry, malaa, ltv, wc, sales, isFund) {
            const pf = productFactor[product];
            const inf = industryFactor[industry];
            const mf = malaaFactor(malaa);
            const rf = isFund ? ltvFactor(ltv) : wcsFactor(wc, sales);
            return clamp(pf*inf*mf*rf, 0.4, 3.5);
        }

        function pdFromRisk(r, stage) {
            const xs = [0.4,1.0,2.0,3.5];
            const ys = [0.3,1.0,3.0,6.0];
            let pd = 0;
            
            // Linear interpolation
            if(r <= xs[0]) pd = ys[0];
            else if(r >= xs[xs.length-1]) pd = ys[ys.length-1];
            else {
                for(let i = 0; i < xs.length-1; i++) {
                    if(r >= xs[i] && r <= xs[i+1]) {
                        const t = (r - xs[i]) / (xs[i+1] - xs[i]);
                        pd = ys[i] + t * (ys[i+1] - ys[i]);
                        break;
                    }
                }
            }
            
            if(stage == 2) pd *= 2.5;
            if(stage == 3) pd *= 6.0;
            return clamp(pd, 0.10, 60.0);
        }

        function lgdFromProductLtv(prod, ltv, isFund) {
            let base = 32;
            if(prod === "Term Loan") base = 38;
            else if(prod === "Export Finance") base = 35;
            else if(!isFund) base = 30;
            
            let adj = Math.max(0, (isNaN(ltv) ? 0 : ltv)-50.0)*0.25;
            if(!isFund) adj += 8.0;
            return clamp(base+adj, 25.0, 70.0);
        }

        function malaaLabel(score) {
            if(score < 500) return "High (poor score)";
            if(score < 650) return "Medium-High";
            if(score < 750) return "Medium";
            return "Low (good score)";
        }

        // Pricing buckets
        const BUCKETS = ["Low","Medium","High"];
        const BUCKET_MULT = {"Low":0.90,"Medium":1.00,"High":1.25};
        const BUCKET_BAND_BPS = {"Low":60,"Medium":90,"High":140};
        const BUCKET_FLOOR_BPS = {"Low":150,"Medium":225,"High":325};
        const MALAA_FLOOR_BPS = {"High (poor score)":175,"Medium-High":125,"Medium":75,"Low (good score)":0};

        function industryFloorAddon(indFac) {
            return indFac >= 1.25 ? 100 : (indFac >= 1.10 ? 50 : 0);
        }

        function productFloorAddon(prod) {
            return prod === "Asset Backed Loan" ? 125 : (["Term Loan","Export Finance"].includes(prod) ? 75 : 0);
        }

        function baseSpreadFromRisk(risk) {
            return 75 + 350*(risk - 1.0);
        }

        // Cash flow calculations
        function fundFirstYearMetrics(P, tenorM, repRate, feesPct, cofPct, provPct, opexPct) {
            const i = repRate/100.0/12.0;
            if(i <= 0 || tenorM <= 0 || P <= 0) return [0.0,0.0,1.0,0.0];
            
            const EMI = P * i * Math.pow(1+i, tenorM) / (Math.pow(1+i, tenorM) - 1);
            const months = Math.min(12, tenorM);
            let bal = P, sumNet12 = 0, sumBal12 = 0;
            
            for(let m = 0; m < months; m++) {
                const interest = bal * i;
                const fee = P * (feesPct/100.0/12.0);
                const funding = bal * (cofPct/100.0/12.0);
                const prov = bal * (provPct/100.0/12.0);
                const opex = bal * (opexPct/100.0/12.0);
                const net = interest + fee - (funding + prov + opex);
                sumNet12 += net;
                sumBal12 += bal;
                const principal = EMI - interest;
                bal = Math.max(bal - principal, 0.0);
            }
            
            const AEA12 = Math.max(sumBal12/months, 1e-9);
            const NIIannual = sumNet12;
            const NIMpct = (NIIannual/AEA12)*100.0;
            return [f2(EMI), f2(NIIannual), f2(AEA12), f2(NIMpct)];
        }

        function fundBreakevenMonths(P, tenorM, ratePct, feesPct, cofPct, provPct, opexPct, upfrontCostPct) {
            const i = ratePct/100.0/12.0;
            if(i <= 0 || tenorM <= 0 || P <= 0) return "Breakeven not within the tenor";
            
            const EMI = P * i * Math.pow(1+i, tenorM) / (Math.pow(1+i, tenorM) - 1);
            let bal = P;
            let C0 = upfrontCostPct/100.0 * P;
            let cum = -C0;
            
            for(let m = 1; m <= tenorM; m++) {
                const interest = bal * i;
                const fee = P * (feesPct/100.0/12.0);
                const funding = bal * (cofPct/100.0/12.0);
                const prov = bal * (provPct/100.0/12.0);
                const opex = bal * (opexPct/100.0/12.0);
                const net = interest + fee - (funding + prov + opex);
                cum += net;
                const principal = EMI - interest;
                bal = Math.max(bal - principal, 0.0);
                if(cum >= 0) return m;
            }
            
            return "Breakeven not within the tenor";
        }

        function utilMetrics(limitOrWc, industry, repRate, feesPct, cofPct, provPct, opexPct, upfrontCostPct) {
            const u = uMedMap[industry];
            const EAD = Math.max(limitOrWc, 0.0) * u;
            const marginPct = repRate + feesPct - (cofPct + provPct + opexPct);
            const NIMpct = marginPct;
            const NIIannual = (marginPct/100.0) * EAD;
            const C0 = upfrontCostPct/100.0 * Math.max(limitOrWc, 0.0);
            
            if(marginPct > 0 && EAD > 0) {
                const mBe = Math.ceil(C0 / (NIIannual/12.0));
                return [f2(EAD), f2(NIMpct), f2(NIIannual), (mBe > 0 ? mBe : 1), f2(u*100.0)];
            }
            
            return [f2(EAD), f2(NIMpct), f2(NIIannual), "Breakeven not within the tenor", f2(u*100.0)];
        }

        // DOM event handlers
        document.getElementById('product').addEventListener('change', function() {
            const product = this.value;
            const isFund = PRODUCTS_FUND.includes(product);
            
            if(isFund) {
                document.getElementById('ltv_container').classList.remove('hidden');
                document.getElementById('sales_container').classList.add('hidden');
            } else {
                document.getElementById('ltv_container').classList.add('hidden');
                document.getElementById('sales_container').classList.remove('hidden');
            }
        });

        document.getElementById('loan_quantum').addEventListener('input', function() {
            const value = parseInt(this.value) || 0;
            document.getElementById('loan_in_words').textContent = `In words: ${numToWords(value)} Omani Rials`;
        });

        document.getElementById('sales').addEventListener('input', function() {
            const value = parseInt(this.value) || 0;
            document.getElementById('sales_in_words').textContent = `In words: ${numToWords(value)} Omani Rials`;
        });

        // Main computation
        document.getElementById('compute').addEventListener('click', function() {
            // Get all inputs
            const oiborPct = parseFloat(document.getElementById('oibor').value) || 0;
            const cofPct = parseFloat(document.getElementById('cof').value) || 0;
            const targetNimPct = parseFloat(document.getElementById('target_nim').value) || 0;
            const opexPct = parseFloat(document.getElementById('opex').value) || 0;
            const feesDefault = parseFloat(document.getElementById('fees_default').value) || 0;
            const upfrontCostPct = parseFloat(document.getElementById('upfront_cost').value) || 0;
            
            const product = document.getElementById('product').value;
            const industry = document.getElementById('industry').value;
            const malaaScore = parseInt(document.getElementById('malaa').value) || 0;
            const stage = parseInt(document.getElementById('stage').value) || 1;
            const tenorMonths = parseInt(document.getElementById('tenor').value) || 0;
            const loanQuantumOmr = parseFloat(document.getElementById('loan_quantum').value) || 0;
            
            const isFund = PRODUCTS_FUND.includes(product);
            let ltvPct, wcOmr, salesOmr, feesPct;
            
            if(isFund) {
                ltvPct = parseFloat(document.getElementById('ltv').value) || 0;
                wcOmr = 0.0;
                salesOmr = 0.0;
                feesPct = product === "Export Finance" ? feesDefault : 0.00;
            } else {
                ltvPct = NaN;
                wcOmr = loanQuantumOmr;
                salesOmr = parseFloat(document.getElementById('sales').value) || 0;
                feesPct = feesDefault;
            }
            
            // Calculate composite risk
            const riskBase = compositeRisk(product, industry, malaaScore, isFund ? ltvPct : 60.0, wcOmr, salesOmr, isFund);
            const pdPctBase = pdFromRisk(riskBase, stage);
            const lgdPctBase = lgdFromProductLtv(product, ltvPct, isFund);
            const provisionPctBase = f2(pdPctBase * (lgdPctBase/100.0));
            
            // Pricing buckets
            const malaaLbl = malaaLabel(malaaScore);
            const indAdd = industryFloorAddon(industryFactor[industry]);
            const prodAdd = productFloorAddon(product);
            const malaaAdd = MALAA_FLOOR_BPS[malaaLbl];
            const minCoreSpreadBps = 125;
            
            const rows = [];
            
            for(const bucket of BUCKETS) {
                // Scale risk for bucket
                const riskB = clamp(riskBase * BUCKET_MULT[bucket], 0.4, 3.5);
                
                // PD/LGD per bucket
                const pdPct = pdFromRisk(riskB, stage);
                const lgdPct = lgdFromProductLtv(product, isFund ? ltvPct : 60.0, isFund);
                const provPct = f2(pdPct * (lgdPct/100.0));
                
                // Spread calculation
                let rawBps = baseSpreadFromRisk(riskB);
                const floors = BUCKET_FLOOR_BPS[bucket] + malaaAdd + indAdd + prodAdd;
                let baseBps = Math.max(Math.round(rawBps), floors, minCoreSpreadBps);
                const bandBps = BUCKET_BAND_BPS[bucket];
                
                // Initial band → convert to rate band
                let spreadMinBps = Math.max(baseBps - bandBps, floors, minCoreSpreadBps);
                let spreadMaxBps = Math.max(baseBps + bandBps, spreadMinBps + 10);
                
                let rateMin = clamp(oiborPct + spreadMinBps/100.0, 5.00, 12.00);
                let rateMax = clamp(oiborPct + spreadMaxBps/100.0, 5.00, 12.00);
                let repRate = (rateMin + rateMax)/2.0;
                
                // Fund floor first (6.00)
                if(isFund) {
                    rateMin = Math.max(rateMin, 6.00);
                    rateMax = Math.max(rateMax, 6.00);
                    repRate = Math.max(repRate, 6.00);
                }
                
                // Strict Target NIM floor
                const requiredRate = f2(cofPct + provPct + opexPct - feesPct + targetNimPct);
                repRate = Math.max(repRate, requiredRate);
                
                // Rebuild symmetric mini-band around center; clamp
                const halfBand = bandBps/200.0;
                rateMin = clamp(repRate - halfBand, 5.00, 12.00);
                rateMax = clamp(repRate + halfBand, 5.00, 12.00);
                if(rateMax - rateMin < 0.10) {
                    rateMax = clamp(rateMin + 0.10, 5.00, 12.00);
                }
                
                // Floats over OIBOR (bps)
                const flMinBps = Math.max(Math.round((rateMin - oiborPct)*100), minCoreSpreadBps);
                const flMaxBps = Math.max(Math.round((rateMax - oiborPct)*100), flMinBps + 10);
                
                // Cash metrics
                if(isFund) {
                    const [EMI, NIIannual, AEA12, NIMpct] = fundFirstYearMetrics(
                        loanQuantumOmr, tenorMonths, repRate, feesPct, cofPct, provPct, opexPct
                    );
                    
                    const beMin = fundBreakevenMonths(loanQuantumOmr, tenorMonths, rateMin, feesPct, cofPct, provPct, opexPct, upfrontCostPct);
                    const beRep = fundBreakevenMonths(loanQuantumOmr, tenorMonths, repRate, feesPct, cofPct, provPct, opexPct, upfrontCostPct);
                    const beMax = fundBreakevenMonths(loanQuantumOmr, tenorMonths, rateMax, feesPct, cofPct, provPct, opexPct, upfrontCostPct);
                    
                    // Decomposed annual components
                    const annualInterest = f2((repRate/100.0)*AEA12);
                    const annualFee = f2((feesPct/100.0)*loanQuantumOmr);
                    const annualFunding = f2((cofPct/100.0)*AEA12);
                    const annualProv = f2((provPct/100.0)*AEA12);
                    const annualOpex = f2((opexPct/100.0)*AEA12);
                    const nii = f2(annualInterest + annualFee - (annualFunding + annualProv + annualOpex));
                    
                    rows.push({
                        bucket,
                        flMinBps,
                        flMaxBps,
                        rateMin: f2(rateMin),
                        repRate: f2(repRate),
                        rateMax: f2(rateMax),
                        EMI: f2(EMI),
                        annualInterest,
                        annualFee,
                        annualFunding,
                        annualProv,
                        annualOpex,
                        nii,
                        NIMpct: f2(NIMpct),
                        beMin,
                        beRep,
                        beMax,
                        malaaLbl,
                        industryFactor: f2(industryFactor[industry]),
                        productFactor: f2(productFactor[product]),
                        riskBase: f2(riskBase),
                        provPct: f2(provPct)
                    });
                } else {
                    // Utilization loans
                    const [EAD, NIMpct, NIIannual, beRep, uPct] = utilMetrics(
                        loanQuantumOmr, industry, repRate, feesPct, cofPct, provPct, opexPct, upfrontCostPct
                    );
                    
                    function utilBe(rate) {
                        const margin = rate + feesPct - (cofPct + provPct + opexPct);
                        if(margin <= 0 || loanQuantumOmr <= 0) return "Breakeven not within the tenor";
                        const m = Math.ceil((upfrontCostPct/100.0 * loanQuantumOmr) / ((margin/100.0)*(loanQuantumOmr*uMedMap[industry])/12.0));
                        return m <= tenorMonths ? m : "Breakeven not within the tenor";
                    }
                    
                    const beMin = utilBe(rateMin);
                    const beMax = utilBe(rateMax);
                    
                    const annualInterest = f2((repRate/100.0) * EAD);
                    const annualFee = f2((feesPct/100.0) * loanQuantumOmr);
                    const annualFunding = f2((cofPct/100.0) * EAD);
                    const annualProv = f2((provPct/100.0) * EAD);
                    const annualOpex = f2((opexPct/100.0) * EAD);
                    const nii = f2(annualInterest + annualFee - (annualFunding + annualProv + annualOpex));
                    
                    rows.push({
                        bucket,
                        flMinBps,
                        flMaxBps,
                        rateMin: f2(rateMin),
                        repRate: f2(repRate),
                        rateMax: f2(rateMax),
                        EMI: "-",
                        annualInterest,
                        annualFee,
                        annualFunding,
                        annualProv,
                        annualOpex,
                        nii,
                        NIMpct: f2(NIMpct),
                        beMin,
                        beRep,
                        beMax,
                        malaaLbl,
                        industryFactor: f2(industryFactor[industry]),
                        productFactor: f2(productFactor[product]),
                        riskBase: f2(riskBase),
                        provPct: f2(provPct),
                        optimalUtil: f2(uPct)
                    });
                }
            }
            
            // Render results
            let html = `<div class="overflow-x-auto">
                <table class="w-full border-collapse">
                    <thead>
                        <tr class="bg-gray-100">
                            <th class="p-3 text-left border-b">Pricing Bucket</th>
                            <th class="p-3 text-left border-b">Float (Min) over OIBOR (bps)</th>
                            <th class="p-3 text-left border-b">Float (Max) over OIBOR (bps)</th>
                            <th class="p-3 text-left border-b">Min Rate (%)</th>
                            <th class="p-3 text-left border-b">Recommended Rate (%)</th>
                            <th class="p-3 text-left border-b">Max Rate (%)</th>
                            <th class="p-3 text-left border-b">EMI (OMR)</th>
                            <th class="p-3 text-left border-b">NII (OMR)</th>
                            <th class="p-3 text-left border-b">NIM (%)</th>
                            <th class="p-3 text-left border-b">Breakeven (months)</th>
                        </tr>
                    </thead>
                    <tbody>`;
            
            for(const row of rows) {
                html += `
                    <tr class="border-b hover:bg-gray-50">
                        <td class="p-3">${row.bucket}</td>
                        <td class="p-3">${row.flMinBps}</td>
                        <td class="p-3">${row.flMaxBps}</td>
                        <td class="p-3">${row.rateMin}</td>
                        <td class="p-3">${row.repRate}</td>
                        <td class="p-3">${row.rateMax}</td>
                        <td class="p-3">${row.EMI}</td>
                        <td class="p-3">${row.nii}</td>
                        <td class="p-3">${row.NIMpct}</td>
                        <td class="p-3">${row.beRep}</td>
                    </tr>`;
            }
            
            html += `</tbody></table></div>`;
            
            // Risk details
            html += `<div class="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="bg-gray-50 p-4 rounded">
                    <h3 class="font-bold mb-2">Risk Details</h3>
                    <p><strong>Borrower Risk:</strong> ${rows[0].malaaLbl}</p>
                    <p><strong>Industry Factor:</strong> ${rows[0].industryFactor}x</p>
                    <p><strong>Product Factor:</strong> ${rows[0].productFactor}x</p>
                    <p><strong>Composite Risk:</strong> ${rows[0].riskBase}x</p>
                    <p><strong>Provision:</strong> ${rows[0].provPct}% annual</p>
                </div>`;
            
            if(!isFund) {
                html += `<div class="bg-gray-50 p-4 rounded">
                    <h3 class="font-bold mb-2">Utilization Metrics</h3>
                    <p><strong>Optimal Utilization:</strong> ${rows[0].optimalUtil}%</p>
                    <p class="text-sm mt-2 text-gray-600">Based on industry median utilization for ${industry}</p>
                </div>`;
            }
            
            html += `</div>`;
            
            document.getElementById('results').innerHTML = html;
        });

        // Initialize product type visibility
        document.getElementById('product').dispatchEvent(new Event('change'));
        
        // Initialize number to words
        document.getElementById('loan_quantum').dispatchEvent(new Event('input'));
        
        if(document.getElementById('sales').value) {
            document.getElementById('sales').dispatchEvent(new Event('input'));
        }
    </script>
</body>
</html>
