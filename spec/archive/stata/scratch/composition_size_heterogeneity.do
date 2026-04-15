// ----------------------------------------------------------------------
// Path bootstrap -------------------------------------------------------
// ----------------------------------------------------------------------
local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"

*=============================================================================*
* Test composition effects by firm size quartiles
* Examines if workforce changes affect small vs large firms differently
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

*-----------------------------------------------------------------------------*
* Part 1: Get firm sizes and create quartiles
*-----------------------------------------------------------------------------*

* Load LinkedIn data to get firm sizes
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1

* Date handling
gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td

gen yh = hofd(date)
format yh %th

* Get pre-COVID average size
keep if yh < 120  // Pre-COVID
collapse (mean) avg_size = total_employees, by(companyname)

* Create size quartiles
xtile size_quartile = avg_size, nq(4)

* Create binary indicators
gen small_firm = (size_quartile <= 2)
gen large_firm = (size_quartile >= 3)

* Save size data
gen companyname_lower = lower(companyname)
keep companyname companyname_lower avg_size size_quartile small_firm large_firm
tempfile firm_sizes
save `firm_sizes'

*-----------------------------------------------------------------------------*
* Part 2: Merge with productivity panel
*-----------------------------------------------------------------------------*

use "$processed_data/user_panel_precovid.dta", clear

* Create lowercase company name
gen companyname_lower = lower(companyname)

* Keep key variables
keep if !missing(var3, var5, var6, var7)
keep user_id firm_id companyname companyname_lower yh total_contributions_q100 ///
     var3 var4 var5 var6 var7 startup covid

* Merge composition data
merge m:1 companyname_lower using "$results/composition_sample.dta", keep(match) nogen

* Merge size data
merge m:1 companyname_lower using `firm_sizes', keep(match) nogen

* Summary of sample
tab size_quartile startup

*-----------------------------------------------------------------------------*
* Part 3: Test composition effects by size
*-----------------------------------------------------------------------------*

di _n "=== COMPOSITION EFFECTS BY FIRM SIZE ==="

* Key SOCs to test
local key_socs "pct_chg_soc1511 pct_chg_soc1320 pct_chg_soc1191"

* Store results by size
capture postclose size_results
tempfile size_out
postfile size_results str20 soc str10 size_group ///
    double b3 se3 p3 ///
    double b5 se5 p5 ///
    double b3_comp se3_comp p3_comp ///
    double b5_comp se5_comp p5_comp ///
    double rkf long nobs ///
    using `size_out', replace

* Run separately by size group
foreach size in "small" "large" {
    preserve
    keep if `size'_firm == 1
    
    di _n "=== " upper("`size'") " FIRMS ==="
    
    foreach soc of local key_socs {
        di _n "Testing " "`soc'" " for " "`size'" " firms..."
        
        * Create interaction terms
        gen var3_comp = var3 * `soc'
        gen var5_comp = var5 * `soc'
        gen var6_comp = var6 * `soc'
        gen var7_comp = var7 * `soc'
        
        * Run IV regression
        capture ivreghdfe total_contributions_q100 ///
            (var3 var5 var3_comp var5_comp = var6 var7 var6_comp var7_comp) ///
            var4 `soc' ///
            , absorb(firm_id#user_id yh) ///
            vce(cluster user_id)
        
        if _rc == 0 {
            post size_results ("`soc'") ("`size'") ///
                (_b[var3]) (_se[var3]) (2*ttail(e(df_r), abs(_b[var3]/_se[var3]))) ///
                (_b[var5]) (_se[var5]) (2*ttail(e(df_r), abs(_b[var5]/_se[var5]))) ///
                (_b[var3_comp]) (_se[var3_comp]) (2*ttail(e(df_r), abs(_b[var3_comp]/_se[var3_comp]))) ///
                (_b[var5_comp]) (_se[var5_comp]) (2*ttail(e(df_r), abs(_b[var5_comp]/_se[var5_comp]))) ///
                (e(rkf)) (e(N))
        }
        
        drop var3_comp var5_comp var6_comp var7_comp
    }
    
    restore
}

postclose size_results

*-----------------------------------------------------------------------------*
* Part 4: Test formal interaction with size
*-----------------------------------------------------------------------------*

di _n "=== FORMAL SIZE INTERACTION TEST ==="

* Focus on most significant SOC
local main_soc "pct_chg_soc1320"

* Create all needed interactions
gen var3_size = var3 * large_firm
gen var5_size = var5 * large_firm
gen var6_size = var6 * large_firm
gen var7_size = var7 * large_firm

gen var3_comp = var3 * `main_soc'
gen var5_comp = var5 * `main_soc'
gen var6_comp = var6 * `main_soc'
gen var7_comp = var7 * `main_soc'

gen var3_comp_size = var3 * `main_soc' * large_firm
gen var5_comp_size = var5 * `main_soc' * large_firm
gen var6_comp_size = var6 * `main_soc' * large_firm
gen var7_comp_size = var7 * `main_soc' * large_firm

* Run full interaction model
ivreghdfe total_contributions_q100 ///
    (var3 var5 var3_size var5_size var3_comp var5_comp var3_comp_size var5_comp_size = ///
     var6 var7 var6_size var7_size var6_comp var7_comp var6_comp_size var7_comp_size) ///
    var4 `main_soc' large_firm c.`main_soc'#c.large_firm ///
    , absorb(firm_id#user_id yh) ///
    vce(cluster user_id)

di _n "Triple interaction results (Remote × Composition × Large Firm):"
di "Coefficient: " %9.3f _b[var3_comp_size] " (p = " %6.4f 2*ttail(e(df_r), abs(_b[var3_comp_size]/_se[var3_comp_size])) ")"

*-----------------------------------------------------------------------------*
* Part 5: Summary and comparison
*-----------------------------------------------------------------------------*

di _n "=== SUMMARY BY FIRM SIZE ==="

use `size_out', clear

* Compare effects
di _n "Composition interaction effects by firm size:"
reshape wide b3* se3* p3* b5* se5* p5* rkf nobs, i(soc) j(size_group) string

list soc b3_compsmall p3_compsmall b3_complarge p3_complarge

* Calculate differences
gen diff_b3_comp = b3_complarge - b3_compsmall
gen diff_b5_comp = b5_complarge - b5_compsmall

di _n "Differences in effects (Large - Small):"
list soc diff_b3_comp diff_b5_comp

* Additional analysis: composition changes by size
use "$processed_data/user_panel_precovid.dta", clear
gen companyname_lower = lower(companyname)
merge m:1 companyname_lower using "$results/composition_sample.dta", keep(match) nogen
merge m:1 companyname_lower using `firm_sizes', keep(match) nogen

collapse (first) pct_chg_soc* avg_size, by(companyname_lower size_quartile)

di _n "Average composition changes by firm size:"
table size_quartile, stat(mean pct_chg_soc1511 pct_chg_soc1320 pct_chg_soc1191)

di _n "Analysis complete!"