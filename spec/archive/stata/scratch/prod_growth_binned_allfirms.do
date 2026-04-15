*--------------------------------------------------------------------
* prod_growth_binned_allfirms.do
* Cross-section diagnostic (no remote filter): change in worker rank vs firm growth.
* Data prep is done in Python (src/py/prod_growth_deltas.py).
* This script:
*   - runs the firm-level regression (stayer + all workers)
*   - creates a binned scatter and two histograms for each outcome
* Outputs saved under results/diagnostics_allfirms/.
*--------------------------------------------------------------------

local __bootstrap "_bootstrap.do"

if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../../spec/stata/_bootstrap.do"

if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}

do "`__bootstrap'"

capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/prod_growth_binned_allfirms.log", replace text

local diag_dir "$PROJECT_ROOT/results/diagnostics_allfirms"
cap mkdir "`diag_dir'"

use "`diag_dir'/../diagnostics/prod_growth_diff_balanced.dta", clear

keep if !missing(d_rank_med, diff_growth)

*-----------------------------
* Regressions (stayer delta and composition-inclusive level change)
*-----------------------------

tempfile reg_out
capture postclose handle
postfile handle str15 model str20 param double coef se pval nobs r2 using `reg_out', replace

* Model 1: stayer-based median delta
reg d_rank_med diff_growth startup [aw=n_users], vce(robust)
local __N = e(N)
local __r2 = e(r2)
foreach p in diff_growth startup {
    local b = _b[`p']
    local se = _se[`p']
    local t = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("stayer") ("`p'") (`b') (`se') (`pval') (`__N') (`__r2')
}

* Model 2: firm-level mean rank change (composition-inclusive)
reg diff_rank_level diff_growth startup [aw=n_users_all], vce(robust)
local __N2 = e(N)
local __r2_2 = e(r2)
foreach p in diff_growth startup {
    local b = _b[`p']
    local se = _se[`p']
    local t = `b'/`se'
    local pval = 2*ttail(e(df_r), abs(`t'))
    post handle ("level") ("`p'") (`b') (`se') (`pval') (`__N2') (`__r2_2')
}

postclose handle
use `reg_out', clear
export delimited using "`diag_dir'/prod_growth_regression.csv", replace

*-----------------------------
* Binned scatter (stayer metric) — manual by remote for clarity
*-----------------------------
use "`diag_dir'/../diagnostics/prod_growth_diff_balanced.dta", clear
keep if !missing(d_rank_med, diff_growth)

preserve
    keep if remote_flag == 1
    xtile bin = diff_growth [aw=n_users], n(20)
    collapse (mean) x = diff_growth (mean) y = d_rank_med [aw=n_users], by(bin)
    gen group = 1
    tempfile rem1
    save `rem1'
restore

preserve
    keep if remote_flag == 0
    xtile bin = diff_growth [aw=n_users], n(20)
    collapse (mean) x = diff_growth (mean) y = d_rank_med [aw=n_users], by(bin)
    gen group = 0
    tempfile rem0
    save `rem0'
restore

use `rem1', clear
append using `rem0'

twoway ///
    (scatter y x if group==1, msymbol(O) msize(medium) mcolor(navy)) ///
    (lfit y x if group==1, lcolor(navy) lwidth(medthick)) ///
    (scatter y x if group==0, msymbol(Oh) msize(medium) mcolor(maroon)) ///
    (lfit y x if group==0, lcolor(maroon) lwidth(medthick)), ///
    legend(order(1 "Remote = 1" 3 "Remote < 1") cols(1)) ///
    xtitle("Post – Pre growth rate (winsorised)") ///
    ytitle("Median within-user rank change") ///
    title("Change in productivity vs firm growth (stayers, all firms)")

graph export "`diag_dir'/binscatter_prod_growth_stayer.png", replace width(1600) height(1200)

*-----------------------------
* Binned scatter (composition-inclusive mean rank change) — manual by remote
*-----------------------------
use "`diag_dir'/../diagnostics/prod_growth_diff_balanced.dta", clear
keep if !missing(diff_rank_level, diff_growth)

preserve
    keep if remote_flag == 1
    xtile bin = diff_growth [aw=n_users_all], n(20)
    collapse (mean) x = diff_growth (mean) y = diff_rank_level [aw=n_users_all], by(bin)
    gen group = 1
    tempfile rem1b
    save `rem1b'
restore

preserve
    keep if remote_flag == 0
    xtile bin = diff_growth [aw=n_users_all], n(20)
    collapse (mean) x = diff_growth (mean) y = diff_rank_level [aw=n_users_all], by(bin)
    gen group = 0
    tempfile rem0b
    save `rem0b'
restore

use `rem1b', clear
append using `rem0b'

twoway ///
    (scatter y x if group==1, msymbol(O) msize(medium) mcolor(navy)) ///
    (lfit y x if group==1, lcolor(navy) lwidth(medthick)) ///
    (scatter y x if group==0, msymbol(Oh) msize(medium) mcolor(maroon)) ///
    (lfit y x if group==0, lcolor(maroon) lwidth(medthick)), ///
    legend(order(1 "Remote = 1" 3 "Remote < 1") cols(1)) ///
    xtitle("Post – Pre growth rate (winsorised)") ///
    ytitle("Mean rank change (all workers)") ///
    title("Change in productivity vs firm growth (all workers, all firms)")

graph export "`diag_dir'/binscatter_prod_growth_level.png", replace width(1600) height(1200)

*-----------------------------
* Histograms: all firms
*-----------------------------
use "`diag_dir'/../diagnostics/prod_growth_diff_balanced.dta", clear

twoway (hist d_rank_med if startup, color(navy%55) width(2)) ///
       (hist d_rank_med if !startup, color(maroon%55) width(2)), ///
       legend(order(1 "Startups" 2 "Incumbents")) ///
       xtitle("Median within-user rank change") ///
       title("Productivity change distribution (stayers, all firms)")
graph export "`diag_dir'/hist_prod_change_stayer.png", replace width(1600) height(1200)

twoway (hist diff_rank_level if startup, color(teal%55) width(2)) ///
       (hist diff_rank_level if !startup, color(orange%55) width(2)), ///
       legend(order(1 "Startups" 2 "Incumbents")) ///
       xtitle("Mean rank change (all workers)") ///
       title("Productivity change distribution (all workers, all firms)")
graph export "`diag_dir'/hist_prod_change_level.png", replace width(1600) height(1200)

twoway (hist diff_growth if startup, color(navy%55) width(.02)) ///
       (hist diff_growth if !startup, color(maroon%55) width(.02)), ///
       legend(order(1 "Startups" 2 "Incumbents")) ///
       xtitle("Growth rate change") ///
       title("Growth change distribution (all firms)")
graph export "`diag_dir'/hist_growth_change.png", replace width(1600) height(1200)

di as result "Outputs written to `diag_dir'"
log close
end
