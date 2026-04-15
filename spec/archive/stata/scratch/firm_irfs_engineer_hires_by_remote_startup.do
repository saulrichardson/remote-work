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
* firm_irfs_engineer_hires_by_remote_startup.do
* Engineer hires (levels) IRFs via local projections,
* split by Remote (==1) × Startup (==1) groups.
* Outcome: ΔEngineer hires per 100 pre-shock employees
* Shock:   firm headcount growth (growth_rate_we) at t
* FE:      firm and half-year (yh)       SE: cluster(firm_id)
* Notes:   - Uses pre-COVID baseline (2019) as fixed denominator
*          - Produces rebased plots with shared y-axis across groups
*============================================================*

clear all
set more off
capture log close
log using "firm_irfs_engineer_hires_by_remote_startup.log", replace text

//---------- Globals ----------//
// Prefer existing globals; otherwise try relative paths; fallback to absolute
capture confirm file "$processed_data/firm_panel.dta"
if _rc {
    capture confirm file "data/processed/firm_panel.dta"
    if !_rc {
        global processed_data "data/processed"
        global base_results  "results"
    }
    else {
        capture confirm file "../data/processed/firm_panel.dta"
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

global results_root "$base_results/firm_irfs_engineer_hires"
capture mkdir "$results_root"

display "============================================================="
display "Engineer Hires IRFs: growth_rate_we → ΔEngineer per 100 (pre-shock)"
display "Split: Remote (==1) × Startup (==1)"
display "============================================================="

//---------- STEP 1: Build firm baseline headcount (Emp_pre_i) ----------//
display _n "STEP 1: Loading firm panel and computing baseline headcount"
use "$processed_data/firm_panel.dta", clear
capture drop _merge*

// Expect: firm_id, companyname, yh, year, half, total_employees, remote, startup, growth_rate_we
assert !missing(firm_id, companyname, yh)
gen companyname_c = lower(companyname)

// Define pre-COVID period (2019)
capture confirm variable year
if _rc {
    display as error "Variable 'year' not found; attempting to derive from yh"
    // If yh is encoded as y*10+half, derive year
    capture gen year = floor(yh/10)
}
gen byte pre_covid = (year == 2019)

// Compute firm-specific baseline employees as average over 2019 (fallback to first pre-2020 obs)
tempvar emp_pre_tmp first_pre
bysort firm_id: egen `emp_pre_tmp' = mean(total_employees) if pre_covid
bysort firm_id: egen Emp_pre_i = max(`emp_pre_tmp')
drop `emp_pre_tmp'

// Fallback: if Emp_pre_i missing, take first obs with year <= 2019
gen `first_pre' = total_employees if year <= 2019
bysort firm_id (yh): replace `first_pre' = `first_pre'[_n-1] if missing(`first_pre')
bysort firm_id: replace Emp_pre_i = `first_pre' if missing(Emp_pre_i)
drop `first_pre'

// Keep key vars for later merge (half may not exist in this panel)
capture confirm variable half
if _rc {
    keep firm_id companyname_c yh year total_employees remote startup growth_rate_we Emp_pre_i
}
else {
    keep firm_id companyname_c yh year half total_employees remote startup growth_rate_we Emp_pre_i
}
tempfile FIRM
save `FIRM'

//---------- STEP 2: Construct engineer hire outcomes from role CSV ----------//
display _n "STEP 2: Loading role growths and computing ΔEngineer (levels)"
preserve
    import delimited "$processed_data/role_k7_scaling_growth.csv", clear
    // Role file expected columns: companyname, role_k7, year, half, employee_count, prev_count, total_employees_yh
    keep companyname role_k7 year half employee_count prev_count total_employees_yh
    replace role_k7 = trim(role_k7)
    keep if role_k7 == "Engineer"
    gen companyname_c = lower(companyname)
    gen yh = yh(year, half)

    // Net engineer hires (levels)
    gen d_eng = employee_count - prev_count

    // Keep minimal dataset
    keep companyname_c yh d_eng employee_count prev_count total_employees_yh
    tempfile ENG
    save `ENG'
restore

//---------- STEP 3: Merge outcomes to firm panel; compute per-100(pre) ----------//
display _n "STEP 3: Merging engineer Δlevels to firm panel (companyname×yh)"
use `FIRM', clear
merge 1:1 companyname_c yh using `ENG'
display "Merge engineer outcomes:" 
tab _merge
keep if _merge == 3
drop _merge

// Outcome scaling: per 100 pre-shock employees (fixed denominator)
gen d_eng_per100 = 100 * d_eng / Emp_pre_i
label var d_eng_per100 "ΔEngineer hires per 100 pre-shock employees"

// Guardrails: drop if missing or non-positive Emp_pre_i
drop if missing(Emp_pre_i) | Emp_pre_i <= 0

// Define binary remote as fully remote
gen byte remote_bin = (remote == 1)
label var remote_bin "Fully remote (==1)"
label var startup    "Startup (==1)"

//---------- STEP 4: Panel and TS leads ----------//
display _n "STEP 4: Panel setup and TS leads"
xtset firm_id yh
forvalues h = 0/4 {
    gen F`h'_d_eng_per100 = F`h'.d_eng_per100
}

display _n "Sample sizes by horizon:"
forvalues h = 0/4 {
    count if !missing(F`h'_d_eng_per100)
    display "  H`h': N=" %9.0fc r(N)
}

// Cache analytic dataset
tempfile ANALYTIC
save `ANALYTIC'
global ANALYTIC "`ANALYTIC'"

//---------- STEP 5: Helper to run group IRFs ----------//
program define run_irf_group
    // args: if, label, outdir
    syntax [if], LABEL(string) OUTDIR(string)
    preserve
        use "$ANALYTIC", clear
        keep `if'
        count
        local N_all = r(N)
        display _n "Estimating Engineer-hire IRFs for: `label' (N=" %9.0fc `N_all' ")"
        capture mkdir "`outdir'"

        tempname hdl
        capture postclose `hdl'
        postfile `hdl' horizon coef se tstat pval ci_lo ci_hi nobs r2 using "`outdir'/irf_estimates.dta", replace

        forvalues h = 0/4 {
            display "  -> Horizon `h'"
            quietly capture reghdfe F`h'_d_eng_per100 growth_rate_we, absorb(firm_id yh) vce(cluster firm_id)
            if _rc == 0 {
                local b  = _b[growth_rate_we]
                local se = _se[growth_rate_we]
                local t  = `b'/`se'
                local p  = 2*ttail(e(df_r), abs(`t'))
                local lo = `b' - invttail(e(df_r), 0.025)*`se'
                local hi = `b' + invttail(e(df_r), 0.025)*`se'
                local N  = e(N)
                local R2 = e(r2)
                post `hdl' (`h') (`b') (`se') (`t') (`p') (`lo') (`hi') (`N') (`R2')
            }
            else {
                display as error "    Estimation failed (rc=" _rc ") at H`h'"
                post `hdl' (`h') (.) (.) (.) (.) (.) (.) (0) (.)
            }
        }
        postclose `hdl'

        // Export CSV
        use "`outdir'/irf_estimates.dta", clear
        export delimited using "`outdir'/irf_results.csv", replace

        // Rebase by subtracting H0
        quietly summarize coef if horizon == 0, meanonly
        local b0 = r(mean)
        gen coef_rebased = coef - `b0'
        gen ci_lo_rebased = ci_lo - `b0'
        gen ci_hi_rebased = ci_hi - `b0'
        save "`outdir'/irf_estimates_rebased.dta", replace
        export delimited using "`outdir'/irf_results_rebased.csv", replace

        // Plot original and rebased (per-group)
        twoway (rcap ci_lo ci_hi horizon, lcolor(gs10) lwidth(medthin)) ///
               (connected coef horizon, lcolor(navy) mcolor(navy) msymbol(circle) lwidth(medthick)), ///
               yline(0, lpattern(dash) lcolor(gs8)) ///
               xlabel(0(1)4, labsize(medium)) ///
               xtitle("Horizon (6-month periods)", size(medium)) ///
               ytitle("Δ Engineers per 100 (pre-shock)", size(medium)) ///
               title("Engineer Hire IRF — `label'", size(large)) ///
               subtitle("shock: growth_rate_we; FE: firm, time; SE: firm-cluster", size(small)) ///
               legend(off) ///
               graphregion(color(white)) plotregion(color(white))
        graph export "`outdir'/irf_plot.png", replace width(900) height(650)

        twoway (rcap ci_lo_rebased ci_hi_rebased horizon, lcolor(gs10) lwidth(medthin)) ///
               (connected coef_rebased horizon, lcolor(navy) mcolor(navy) msymbol(circle) lwidth(medthick)), ///
               yline(0, lpattern(dash) lcolor(gs8)) ///
               xlabel(0(1)4, labsize(medium)) ///
               xtitle("Horizon (6-month periods)", size(medium)) ///
               ytitle("Rebased Δ Eng per 100 (pre-shock)", size(medium)) ///
               title("Engineer Hire IRF (Rebased) — `label'", size(large)) ///
               subtitle("rebased at H0; shared y-axis set separately", size(small)) ///
               legend(off) ///
               graphregion(color(white)) plotregion(color(white))
        graph export "`outdir'/irf_plot_rebased.png", replace width(900) height(650)
    restore
end

//---------- STEP 6: Run 4 groups (Remote×Startup 2×2) ----------//
display _n "STEP 6: Estimating by Remote×Startup groups (2×2)"

local g1_if "remote_bin==0 & startup==0"
local g1_lab "Non-Remote, Non-Startup"
local g1_dir "$results_root/remote0_startup0"

local g2_if "remote_bin==1 & startup==0"
local g2_lab "Remote, Non-Startup"
local g2_dir "$results_root/remote1_startup0"

local g3_if "remote_bin==0 & startup==1"
local g3_lab "Non-Remote, Startup"
local g3_dir "$results_root/remote0_startup1"

local g4_if "remote_bin==1 & startup==1"
local g4_lab "Remote, Startup"
local g4_dir "$results_root/remote1_startup1"

run_irf_group if `g1_if', label("`g1_lab'") outdir("`g1_dir'")
run_irf_group if `g2_if', label("`g2_lab'") outdir("`g2_dir'")
run_irf_group if `g3_if', label("`g3_lab'") outdir("`g3_dir'")
run_irf_group if `g4_if', label("`g4_lab'") outdir("`g4_dir'")

//---------- STEP 7: Shared y-axis plots (rebased) ----------//
display _n "STEP 7: Creating combined rebased plots with shared y-axis"
tempfile ALL
clear
// Append all groups' rebased estimates to find common y-range
foreach d in "$results_root/remote0_startup0" "$results_root/remote1_startup0" "$results_root/remote0_startup1" "$results_root/remote1_startup1" {
    capture confirm file "`d'/irf_estimates_rebased.dta"
    if !_rc {
        use "`d'/irf_estimates_rebased.dta", clear
        gen group = "`=subinstr("`d'", "$results_root/", "", .)'"
        capture append using `ALL'
        save `ALL', replace
    }
}
capture use `ALL', clear
if _rc == 0 {
    quietly summarize ci_lo_rebased, meanonly
    local ymin = r(min)
    quietly summarize ci_hi_rebased, meanonly
    local ymax = r(max)

    // Draw each group's graph with shared y-axis and keep as named graphs
    local i = 1
    foreach d in "$results_root/remote0_startup0" "$results_root/remote1_startup0" "$results_root/remote0_startup1" "$results_root/remote1_startup1" {
        capture confirm file "`d'/irf_estimates_rebased.dta"
        if !_rc {
            use "`d'/irf_estimates_rebased.dta", clear
            local ttl = subinstr("`=subinstr("`d'", "$results_root/", "", .)'", "/", " ", .)
            twoway (rcap ci_lo_rebased ci_hi_rebased horizon, lcolor(gs10) lwidth(medthin)) ///
                   (connected coef_rebased horizon, lcolor(navy) mcolor(navy) msymbol(circle) lwidth(medthick)), ///
                   yline(0, lpattern(dash) lcolor(gs8)) ///
                   ylabel(`ymin'(`=( (`ymax'-`ymin')/4 )')`ymax') ///
                   yscale(range(`ymin' `ymax')) ///
                   xlabel(0(1)4) ///
                   title("`ttl' (rebased)") legend(off) name(g`i', replace)
            local ++i
        }
    }
    capture graph combine g1 g2 g3 g4, cols(2) iscale(1) title("Engineer Hire IRFs (Rebased, Shared Y)")
    graph export "$results_root/combined_irf_rebased.png", replace width(1200) height(900)
}

//---------- SUMMARY ----------//
display _n _n "============================================================="
display "Engineer Hires IRFs complete. Outputs under: $results_root/"
display "  - remote0_startup0/ irf_results.csv, plots"
display "  - remote1_startup0/ irf_results.csv, plots"
display "  - remote0_startup1/ irf_results.csv, plots"
display "  - remote1_startup1/ irf_results.csv, plots"
display "  - combined_irf_rebased.png"
display "============================================================="

log close
