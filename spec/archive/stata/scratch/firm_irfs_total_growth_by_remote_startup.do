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
* firm_irfs_total_growth_by_remote_startup.do
* Firm-level growth IRFs on individual productivity, split by
* Remote × Startup groups. Uses canonical growth_rate_we from
* src/build_firm_panel.do via processed firm_panel.dta.
*============================================================*

clear all
set more off
capture log close
log using "firm_irfs_total_growth_by_remote_startup.log", replace text

//---------- Globals ----------//
// Prefer existing globals; otherwise try relative paths; fallback to absolute
capture confirm file "$processed_data/user_panel_precovid.dta"
if _rc {
    capture confirm file "data/processed/user_panel_precovid.dta"
    if !_rc {
        global processed_data "data/processed"
        global base_results  "results"
    }
    else {
        capture confirm file "../data/processed/user_panel_precovid.dta"
        if !_rc {
            global processed_data "../data/processed"
            global base_results  "../results"
        }
        else {
            global processed_data "/Users/saul/Dropbox/Remote Work Startups/main/data/processed"
            global base_results  "/Users/saul/Dropbox/Remote Work Startups/main/results"
        }
    }
}

global results "$base_results/firm_irfs_total_growth"
capture mkdir "$results"

display "========================================================="
display "FIRM IRFs: growth_rate_we → Individual Productivity"
display "Split: Remote (==1) × Startup (==1)"
display "========================================================="

//---------- Load user panel ----------//
display _n "STEP 1: Load user panel"
use "$processed_data/user_panel_precovid.dta", clear
capture drop _merge*
// Expect: user_id, firm_id, yh, total_contributions_q100, companyname
assert !missing(user_id, firm_id, yh, total_contributions_q100)
display "User panel: N=" %9.0fc _N

//---------- Bring firm-level growth and flags ----------//
display _n "STEP 2: Merge firm growth (growth_rate_we) and flags (remote, startup)"
preserve
    use "$processed_data/firm_panel.dta", clear
    // Keep unique firm×time rows with growth and flags
    keep firm_id yh growth_rate_we remote startup
    duplicates drop
    tempfile firm_flags
    save `firm_flags'
restore

merge m:1 firm_id yh using `firm_flags'
display "Merge firm growth/flags:" 
tab _merge
keep if _merge == 3
drop _merge

// Define binary remote per your definition (fully remote only)
gen byte remote_bin = (remote == 1)
label var remote_bin "Fully remote indicator (remote==1)"
label var startup    "Startup indicator (startup==1)"
label var growth_rate_we "Firm headcount growth (winsorized)"

//---------- Panel + leads ----------//
display _n "STEP 3: Panel setup and constructing F-h leads"
xtset user_id yh
forvalues h = 0/4 {
    gen F`h'_prod = F`h'.total_contributions_q100
}

display _n "Sample sizes by horizon (non-missing outcome leads):"
forvalues h = 0/4 {
    count if !missing(F`h'_prod)
    display "  H`h': N=" %9.0fc r(N)
}

// Cache analytic dataset for reuse (as tempfile + global path for program scope)
tempfile ANALYTIC
save `ANALYTIC'
global ANALYTIC "`ANALYTIC'"

//---------- Helper: run IRF for a group ----------//
program define run_firm_irf, rclass
    // Args: if, label(), outdir()
    syntax [if], LABEL(string) OUTDIR(string)

    preserve
        use "$ANALYTIC", clear
        keep `if'
        count
        local N_all = r(N)
        display _n "Estimating IRF for group: `label' (N=" %9.0fc `N_all' ")"

        capture mkdir "`outdir'"

        // Results container
        capture postclose __post
        postfile __post horizon coef se tstat pval ci_lo ci_hi nobs r2 using "`outdir'/irf_estimates.dta", replace

        forvalues h = 0/4 {
            display "  -> Horizon `h'"
            quietly capture reghdfe F`h'_prod growth_rate_we, absorb(user_id#firm_id yh) vce(cluster firm_id)
            if _rc == 0 {
                local b  = _b[growth_rate_we]
                local se = _se[growth_rate_we]
                local t  = `b'/`se'
                local p  = 2*ttail(e(df_r), abs(`t'))
                local lo = `b' - invttail(e(df_r), 0.025)*`se'
                local hi = `b' + invttail(e(df_r), 0.025)*`se'
                local N  = e(N)
                local R2 = e(r2)
                post __post (`h') (`b') (`se') (`t') (`p') (`lo') (`hi') (`N') (`R2')
            }
            else {
                display as error "    Estimation failed (rc=" _rc ") at H`h'"
                post __post (`h') (.) (.) (.) (.) (.) (.) (0) (.)
            }
        }
        postclose __post

        // Export CSV
        use "`outdir'/irf_estimates.dta", clear
        export delimited using "`outdir'/irf_results.csv", replace

        // Plot IRF
        twoway (rcap ci_lo ci_hi horizon, lcolor(gs10) lwidth(medthin)) ///
               (connected coef horizon, lcolor(navy) mcolor(navy) msymbol(circle) lwidth(medthick)), ///
               yline(0, lpattern(dash) lcolor(gs8)) ///
               xlabel(0(1)4, labsize(medium)) ///
               xtitle("Horizon (6-month periods)", size(medium)) ///
               ytitle("Δ Individual Productivity Percentile", size(medium)) ///
               title("Firm Growth IRF — `label'", size(large)) ///
               subtitle("shock: growth_rate_we; FE: user×firm, time; SE: firm-cluster", size(small)) ///
               legend(off) ///
               graphregion(color(white)) plotregion(color(white))
        graph export "`outdir'/irf_plot.png", replace width(900) height(650)
    restore
end

//---------- Run groups ----------//
display _n "STEP 4: Estimating by Remote×Startup groups"

// Group definitions (remote==1 → fully remote; startup==1 → startup)
local g1_if "remote_bin==0 & startup==0"
local g1_lab "Non-Remote, Non-Startup"
local g1_dir "$results/remote0_startup0"

local g2_if "remote_bin==1 & startup==0"
local g2_lab "Remote, Non-Startup"
local g2_dir "$results/remote1_startup0"

local g3_if "remote_bin==0 & startup==1"
local g3_lab "Non-Remote, Startup"
local g3_dir "$results/remote0_startup1"

local g4_if "remote_bin==1 & startup==1"
local g4_lab "Remote, Startup"
local g4_dir "$results/remote1_startup1"

run_firm_irf if `g1_if', label("`g1_lab'") outdir("`g1_dir'")
run_firm_irf if `g2_if', label("`g2_lab'") outdir("`g2_dir'")
run_firm_irf if `g3_if', label("`g3_lab'") outdir("`g3_dir'")
run_firm_irf if `g4_if', label("`g4_lab'") outdir("`g4_dir'")

// (Optional pooled IRF omitted to keep interface simple)

//---------- Summary ----------//
display _n _n "========================================================="
display "FIRM IRFs complete. Outputs under: $results/"
display "  - remote0_startup0/ irf_results.csv, irf_plot.png"
display "  - remote1_startup0/ irf_results.csv, irf_plot.png"
display "  - remote0_startup1/ irf_results.csv, irf_plot.png"
display "  - remote1_startup1/ irf_results.csv, irf_plot.png"
display "  - pooled/             (optional pooled results)"
display "========================================================="

log close
