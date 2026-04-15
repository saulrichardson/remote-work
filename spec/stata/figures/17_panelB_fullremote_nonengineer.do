*============================================================*
* Asset 17: panelB_fullremote_nonengineer.png
*============================================================*

local asset_stem "17_panelB_fullremote_nonengineer"
local target_rhs "NonEngineer"

local __bootstrap "_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") local __bootstrap "../spec/stata/_bootstrap.do"
if !fileexists("`__bootstrap'") {
    di as error "Unable to locate _bootstrap.do. Run from project root or spec/stata."
    exit 601
}
do "`__bootstrap'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`asset_stem'.log", replace text

local panel_path "$processed_data/user_panel_precovid.dta"
local growth_path "$processed_data/eng_noneng_growth.csv"
local result_dir "$results/`asset_stem'/remote1"

cap mkdir "$results/`asset_stem'"
cap mkdir "`result_dir'"

tempfile growth_long analytic irf_estimates

import delimited using "`growth_path'", clear
keep companyname companyname_c year half pct_growth_eng pct_growth_noneng
gen yh = yh(year, half)
keep companyname_c yh pct_growth_eng pct_growth_noneng
save `growth_long'

use "`panel_path'", clear
capture confirm variable remote
if _rc {
    di as error "Remote share variable not found in `panel_path'"
    exit 459
}

capture confirm numeric variable firm_id
if _rc {
    encode firm_id, gen(firm_id_num)
    drop firm_id
    rename firm_id_num firm_id
}

gen companyname_c = lower(companyname)
capture drop _merge
merge m:1 companyname_c yh using `growth_long'
keep if _merge == 3
drop _merge

drop if missing(pct_growth_eng) | missing(pct_growth_noneng)
drop if missing(remote)

xtset user_id yh
forvalues h = 0/4 {
    gen F`h'_prod = F`h'.total_contributions_q100
}
save `analytic'

program define run_irf_asset17
    args analytic_path rhs_label outdir estimates_path

    preserve
        use "`analytic_path'", clear
        keep if remote == 1
        count
        if r(N) == 0 {
            di as error "No observations for remote == 1"
            restore
            exit 2000
        }

        tempname handle
        capture postclose `handle'
        postfile `handle' str12 rhs horizon coef se tstat pval ci_lo ci_hi nobs r2 using "`estimates_path'", replace

        forvalues h = 0/4 {
            quietly capture reghdfe F`h'_prod pct_growth_eng pct_growth_noneng, absorb(user_id#firm_id yh) vce(cluster firm_id)
            if _rc {
                post `handle' ("`rhs_label'") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
                continue
            }

            local rhs_var = cond("`rhs_label'" == "Engineer", "pct_growth_eng", "pct_growth_noneng")
            local b = _b[`rhs_var']
            local se = _se[`rhs_var']
            local t = `b' / `se'
            local p = 2 * ttail(e(df_r), abs(`t'))
            local lo = `b' - invttail(e(df_r), 0.025) * `se'
            local hi = `b' + invttail(e(df_r), 0.025) * `se'
            post `handle' ("`rhs_label'") (`h') (`b') (`se') (`t') (`p') (`lo') (`hi') (e(N)) (e(r2))
        }
        postclose `handle'

        use "`estimates_path'", clear
        gen coef_rebased = coef
        gen ci_lo_rebased = ci_lo
        gen ci_hi_rebased = ci_hi

        quietly summarize coef if rhs == "`rhs_label'" & horizon == 0, meanonly
        if r(N) {
            local base = r(mean)
            replace coef_rebased = coef - `base' if rhs == "`rhs_label'"
            replace ci_lo_rebased = ci_lo - `base' if rhs == "`rhs_label'"
            replace ci_hi_rebased = ci_hi - `base' if rhs == "`rhs_label'"
            replace coef_rebased = 0 if rhs == "`rhs_label'" & horizon == 0
            replace ci_lo_rebased = 0 if rhs == "`rhs_label'" & horizon == 0
            replace ci_hi_rebased = 0 if rhs == "`rhs_label'" & horizon == 0
        }

        save "`outdir'/eng_noneng_irf_estimates.dta", replace
        export delimited using "`outdir'/eng_noneng_irf_results.csv", replace
    restore
end

run_irf_asset17 "`analytic'" "`target_rhs'" "`result_dir'" "`irf_estimates'"

log close
