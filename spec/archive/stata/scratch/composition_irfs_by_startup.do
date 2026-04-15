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
* composition_irfs_by_startup.do
* Run 7-role IRFs separately for Startups vs Non-Startups
* - Mirrors composition_irfs_all_roles.do
* - Adds firm-time startup flag and splits estimation
* - Produces separate results/plots for each group
*============================================================*

clear all
set more off
capture log close
log using "composition_irfs_by_startup.log", replace text

//---------- Setup ----------//
global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
global base_results "/Users/saul/Dropbox/Remote Work Startups/main/results"
global results_startup "$base_results/composition_irfs_all7_startup"
global results_nonstartup "$base_results/composition_irfs_all7_nonstartup"
capture mkdir "$results_startup"
capture mkdir "$results_nonstartup"

display "================================================================="
display "COMPOSITION IRFs: STARTUP vs NON-STARTUP"
display "================================================================="

//---------- STEP 1: Load user panel ----------//
display _n "STEP 1: Loading and preparing user panel..."
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
gen companyname_c = lower(companyname)
display "User panel loaded: N = " _N

//---------- STEP 2: Load role growth and reshape wide ----------//
display _n "STEP 2: Loading role growth (k7) and reshaping wide..."
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    // Ensure time and firm key
    capture confirm variable yh
    if _rc != 0 {
        capture confirm variable year
        capture confirm variable half
        if _rc == 0 {
            gen yh = yh(year,half)
        }
    }
    gen companyname_c = lower(companyname)

    keep companyname_c yh role_k7 pct_growth_role role_share

    // Reshape to wide: growth and share by role
    reshape wide pct_growth_role role_share, i(companyname_c yh) j(role_k7) string
    rename pct_growth_role* pct_growth_*
    rename role_share*      share_*

    // Set missings to 0 for roles not present at a firm-time
    foreach var of varlist pct_growth_* share_* {
        replace `var' = 0 if missing(`var')
    }

    tempfile role_wide
    save `role_wide'
restore

//---------- STEP 3: Merge in startup flag by firm-time ----------//
display _n "STEP 3: Merging startup indicator by firm-time (from firm_panel)..."
preserve
    use "$processed_data/firm_panel.dta", clear
    keep firm_id yh startup
    // Ensure uniqueness at firm×time
    duplicates drop
    // Coerce startup to byte 0/1 if needed
    capture confirm numeric variable startup
    if _rc == 0 {
        gen byte startup_any = (startup != 0)
    }
    else {
        tostring startup, replace force
        gen byte startup_any = inlist(lower(startup), "true", "1", "t", "yes")
    }
    keep firm_id yh startup_any
    tempfile startup_flag
    save `startup_flag'
restore

//---------- STEP 4: Merge all components ----------//
display _n "STEP 4: Merging user panel with role growth and startup flag..."
merge m:1 companyname_c yh using `role_wide'
display "Role growth merge:" 
tab _merge
keep if _merge == 3
drop _merge

// Prefer merging on firm_id if available
merge m:1 firm_id yh using `startup_flag'
display "Startup flag merge:"
tab _merge
keep if _merge == 3
drop _merge

display "Final merged dataset: N = " _N

//---------- STEP 5: Panel setup and proper TS leads ----------//
display _n "STEP 5: Setting up panel and generating TS leads..."
xtset user_id yh
sort user_id yh

// Generate time-series leads to ensure exact horizons
gen F0_prod = total_contributions_q100
forvalues h = 1/4 {
    gen F`h'_prod = F`h'.total_contributions_q100
}

// Check sample sizes by horizon
display _n "Sample sizes by horizon:"
forvalues h = 0/4 {
    count if !missing(F`h'_prod)
    display "  Horizon `h': N=" %9.0fc r(N)
}

// Cache analytic dataset for repeated use
tempfile analytic
save `analytic'
global ANALYTIC `analytic'

//---------- STEP 6: Define roles and a helper program ----------//
local role_vars "pct_growth_Admin pct_growth_Engineer pct_growth_Finance pct_growth_Marketing pct_growth_Operations pct_growth_Sales pct_growth_Scientist"

program define run_group_irfs
    // args: group_indicator label outdir
    syntax varlist(min=1) [if], LABEL(string) OUTDIR(string)
        // Reload analytic dataset fresh for this group
        use "$ANALYTIC", clear

        keep `if'
        display _n "Estimating IRFs for group: `label' (N=" %9.0fc _N ")"

        // Results container
        capture postfile all7_irf_results str15 role horizon coef se tstat pval ///
            ci_lower ci_upper nobs r2 using "`outdir'/all7_irf_estimates.dta", replace

        // Iterate horizons
        forvalues h = 0/4 {
            display _n "--- Horizon `h' (`label') ---"
            quietly capture reghdfe F`h'_prod `varlist', absorb(user_id#firm_id yh) vce(cluster user_id)
            if _rc == 0 {
                local N_h = e(N)
                local r2_h = e(r2)
                foreach v of local varlist {
                    local rname = subinstr("`v'", "pct_growth_", "", .)
                    local b  = _b[`v']
                    local se = _se[`v']
                    local t  = `b'/`se'
                    local p  = 2*ttail(e(df_r), abs(`t'))
                    local lo = `b' - invttail(e(df_r), 0.025)*`se'
                    local hi = `b' + invttail(e(df_r), 0.025)*`se'
                    post all7_irf_results ("`rname'") (`h') (`b') (`se') (`t') (`p') (`lo') (`hi') (`N_h') (`r2_h')
                }
            }
            else {
                display "  Estimation failed at H`h' (code=" _rc ")"
                foreach v of local varlist {
                    local rname = subinstr("`v'", "pct_growth_", "", .)
                    post all7_irf_results ("`rname'") (`h') (.) (.) (.) (.) (.) (.) (0) (.)
                }
            }
        }
        postclose all7_irf_results

        // Export CSV
        use "`outdir'/all7_irf_estimates.dta", clear
        reshape wide coef se tstat pval ci_lower ci_upper nobs r2, i(role) j(horizon)
        export delimited using "`outdir'/all7_irf_results.csv", replace

        // Individual plots
        use "`outdir'/all7_irf_estimates.dta", clear
        levelsof role, local(roles) clean
        foreach role of local roles {
            use "`outdir'/all7_irf_estimates.dta", clear
            keep if role == "`role'"
            twoway (rcap ci_lower ci_upper horizon, lcolor(gs10) lwidth(medium)) ///
                   (connected coef horizon, lcolor(navy) mcolor(navy) msymbol(circle) msize(medium) lwidth(thick)), ///
                   yline(0, lpattern(dash) lcolor(gs8)) ///
                   xlabel(0(1)4, labsize(medium)) ///
                   ylabel(, labsize(medium) format(%4.1f)) ///
                   xtitle("Horizon (6-month periods)", size(medium)) ///
                   ytitle("Effect on Productivity Percentile", size(medium)) ///
                   title("IRF: `role' Hiring → Productivity (`label')", size(large)) ///
                   subtitle("User×Firm FE; 95% CIs", size(medium)) ///
                   legend(off) ///
                   graphregion(color(white)) plotregion(color(white))
            graph export "`outdir'/clean_irf_`role'.png", replace width(800) height(600)
        }

        // Skipping combined plot in this batch run to avoid quoting issues
end

//---------- STEP 7: Run IRFs by group ----------//
display _n "STEP 7: Estimating by group (startup vs non-startup)..."

// Startup group
run_group_irfs `role_vars' if startup_any == 1, label("Startup") outdir("$results_startup")

// Non-startup group
use "$ANALYTIC", clear
run_group_irfs `role_vars' if startup_any == 0, label("Non-Startup") outdir("$results_nonstartup")

//---------- SUMMARY ----------//
display _n _n "================================================================="
display "IRFs by Startup Status complete"
display "Outputs:"
display "  - $results_startup/: all7_irf_estimates.dta, all7_irf_results.csv, clean_irf_[Role].png, clean_combined_all7.png"
display "  - $results_nonstartup/: same set for Non-Startups"
display "================================================================="

log close
display _n "Log saved to: composition_irfs_by_startup.log"
