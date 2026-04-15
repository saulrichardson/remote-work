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

*============================================================*
* verify_graphs.do 
* Verify graph formatting and create summary table
*============================================================*

clear all
set more off

global results "/Users/saul/Dropbox/Remote Work Startups/main/results/composition_irfs"

// Load and display results
use "$results/irf_estimates.dta", clear

display "=== IRF RESULTS VERIFICATION ==="
display ""

// Create summary table
display "Role" _col(15) "H0" _col(25) "H1" _col(35) "H2" _col(45) "H3" _col(55) "H4"
display "--------------------------------------------------------------------"

levelsof role, local(roles)
foreach role of local roles {
    display "`role'" _col(15) _c
    
    forvalues h = 0/4 {
        qui sum coef if role == "`role'" & horizon == `h'
        if r(N) > 0 {
            local coef = r(mean)
            qui sum pval if role == "`role'" & horizon == `h'
            local pval = r(mean)
            
            local stars ""
            if `pval' < 0.01 local stars "***"
            else if `pval' < 0.05 local stars "**"
            else if `pval' < 0.10 local stars "*"
            
            display %7.3f `coef' "`stars'" _col(`=25+10*`h'') _c
        }
        else {
            display "  n/a  " _col(`=25+10*`h'') _c
        }
    }
    display ""
}

display ""
display "*** p<0.01, ** p<0.05, * p<0.10"
display ""

// Verify sample sizes
display "=== SAMPLE SIZES BY HORIZON ==="
forvalues h = 0/4 {
    qui sum nobs if horizon == `h'
    if r(N) > 0 {
        local n = r(mean)
        display "Horizon `h': " %8.0fc `n' " observations"
    }
}

display ""
display "=== GRAPH FILES STATUS ==="
local graph_files "irf_Engineer.png irf_Finance.png irf_Marketing.png irf_Operations.png irf_Sales.png irf_combined.png"

foreach file of local graph_files {
    capture confirm file "$results/`file'"
    if _rc == 0 {
        display "`file': ✓ EXISTS"
    }
    else {
        display "`file': ✗ MISSING"
    }
}

// Create verification plot to double-check Engineer pattern
preserve
    keep if role == "Engineer"
    
    twoway (connected coef horizon, lcolor(navy) mcolor(navy) lwidth(thick)) ///
           (rcap ci_lower ci_upper horizon, lcolor(gs10)), ///
           yline(0, lpattern(dash) lcolor(gs8)) ///
           xlabel(0(1)4) ///
           xtitle("Horizon") ///
           ytitle("Effect on Productivity") ///
           title("Verification: Engineer IRF") ///
           legend(off) ///
           graphregion(color(white)) plotregion(color(white))
    
    graph export "$results/verification_engineer.png", replace width(600) height(400)
    display "Verification plot saved: verification_engineer.png"
restore

display ""
display "=== VERIFICATION COMPLETE ==="