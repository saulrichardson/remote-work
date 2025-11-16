*====================================================================*
*  spec/user_mechanisms_with_growth.do
*  ------------------------------------------------------------------
*  User-level productivity mechanisms with added ex-post growth
*  measures (endogenous/exogenous) consistent with prior specs.
*
*  • Keeps the mechanism columns from spec/user_mechanisms.do
*    (rent, HHI, seniority and their combinations)
*  • Adds growth mechanisms from spec/growth_mechanisms_simple_final.do:
*      - Endogenous (tile_post_c)
*      - Exogenous (tile_growth_resid) after residualizing on
*        industry/MSA leave-one-out growth, rent, and HHI.
*  • Fixed effects: worker–firm interacted + half-year
*      absorb(firm_id#user_id yh), cluster(user_id)
*  • No fallbacks; assumes required inputs exist
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

// Logging --------------------------------------------------------------

local specname   "user_mechanisms_with_growth_`panel_variant'"
// Globals --------------------------------------------------------------
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
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
cap mkdir "`result_dir'"



// Load user panel ------------------------------------------------------
use "$processed_data/user_panel_`panel_variant'.dta", clear

// FE/cluster choice (kept consistent with prior mechanism specs)
local FE   "absorb(firm_id#user_id yh) vce(cluster user_id)"

// Core mechanism variables (consistent with user_mechanisms.do) --------
gen seniority_4 = !inrange(seniority_levels, 1, 3)

gen var8  = covid*rent
gen var9  = covid*rent*startup

gen var11 = covid*hhi_1000
gen var12 = covid*hhi_1000*startup

gen var14 = covid*seniority_4
gen var15 = covid*seniority_4*startup

// Save the base panel (no growth merges) for specs that do not need growth vars
tempfile panel_plain
save `panel_plain'

// Pre-COVID mean used in reporting (computed on the full baseline sample)
summarize total_contributions_q100 if covid == 0, meanonly
local pre_mean = r(mean)

// ---------------------------------------------------------------------
// Build growth measures (endogenous/exogenous) as in growth_mechanisms
// ---------------------------------------------------------------------

// (A) Endogenous: average post-COVID growth → tile_post_c -------------
preserve
    import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
    gen date_numeric = date(date, "YMD")
    drop date
    rename date_numeric date
    format date %td
    gen yh = hofd(date)
    format yh %th
    // Drop one-off observations in June 2022
    drop if date == 22797
    collapse (last) total_employees date (sum) join leave, by(companyname yh)
    gen byte covid = (yh >= 120)
    encode companyname, gen(firm_n)
    xtset firm_n yh
    sort firm_n yh
    gen growth_yh = (total_employees / L.total_employees) - 1 if _n>1
    winsor2 growth_yh, cuts(1 99) suffix(_we)
    collapse (mean) growth_yh_we if covid, by(companyname)
    rename growth_yh_we growth_rate_we_post_c
    xtile tile_post_c = growth_rate_we_post_c, nq(2)
    tempfile g_postavg
    save `g_postavg'
restore

merge m:1 companyname using `g_postavg', keep(match) nogen
// Endogenous growth interactions (distinct names to avoid collision)
gen var17_e = covid*tile_post_c
gen var18_e = covid*tile_post_c*startup

// Stash the panel with endogenous growth attached so we can return later
tempfile base_panel
save `base_panel'
local panel_growth_endog `base_panel'

// (B) Exogenous: residualized firm growth → tile_growth_resid ---------
// 1) Keys for industry/MSA (from panel)
preserve
    collapse (last) industry (last) company_msa, by(companyname)
    tempfile firmkeys
    save `firmkeys'
restore

// 2) Build post-COVID firm×yh growth series
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    drop v1
    gen date_numeric = date(date, "YMD")
    drop date
    rename date_numeric date
    format date %td
    gen yh = hofd(date)
    format yh %th
    // Drop one-off observations in June 2022
    drop if date == 22797
    collapse (last) total_employees date (sum) join leave, by(companyname yh)
    gen byte covid = (yh >= 120)

merge m:1 companyname using `firmkeys', nogenerate

encode companyname, gen(firm_n)
xtset firm_n yh
sort firm_n yh
gen fg = (total_employees/L.total_employees) - 1 if _n>1
winsor2 fg, cuts(1 99) suffix(_we)
keep if covid
tempfile postcovid
save `postcovid'

// 3) Leave-one-out post-period means (industry and MSA)
use `postcovid', clear
bys industry: egen ind_sum = total(fg_we)
bys industry: egen ind_N   = count(fg_we)
gen ind_growth_postavg_lo = (ind_sum - fg_we) / (ind_N - 1) if ind_N > 1
collapse (mean) ind_growth_postavg_lo, by(industry)
tempfile ind_postavg
save `ind_postavg'

use `postcovid', clear
bys company_msa: egen msa_sum = total(fg_we)
bys company_msa: egen msa_N   = count(fg_we)
gen msa_growth_postavg_lo = (msa_sum - fg_we) / (msa_N - 1) if msa_N > 1
keep company_msa msa_growth_postavg_lo
collapse (mean) msa_growth_postavg_lo, by(company_msa)
tempfile msa_postavg
save `msa_postavg'

// 4) Firm-level average post-COVID growth + firm controls (rent/HHI)
use `postcovid', clear
collapse (mean) fg_we (first) industry company_msa, by(companyname)
rename fg_we growth_rate_we_post_c
gen companyname_c = lower(companyname)

preserve
    use "$processed_data/firm_panel.dta", clear
    keep companyname rent hhi_1000 covid startup
    gen companyname_c = lower(companyname)
    collapse (last) startup (last) rent (last) hhi_1000 if covid, by(companyname_c)
    xtile tile_rent = rent, nq(2)
    xtile tile_hhi  = hhi_1000, nq(2)
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 industry     using `ind_postavg',  keep(match) nogen
merge m:1 company_msa  using `msa_postavg',  keep(match) nogen
merge m:1 companyname_c using `firm_extra',  keep(match) nogen

// First-stage residualization (kept for reporting parity)
reghdfe growth_rate_we_post_c ind_growth_postavg_lo msa_growth_postavg_lo tile_rent tile_hhi
tempfile first_stage
esttab using "`first_stage'", replace  // placeholder; we will capture via predict below
predict growth_resid
xtile tile_growth_resid = growth_resid, nq(2)
keep companyname tile_growth_resid
tempfile firm_measures
save `firm_measures'

// Attach exogenous growth measure to the baseline panel and create interactions
use `panel_plain', clear
merge m:1 companyname using `firm_measures', keep(match) nogen
gen var17_x = covid*tile_growth_resid
gen var18_x = covid*tile_growth_resid*startup

tempfile panel_growth_exog
save `panel_growth_exog'

// ---------------------------------------------------------------------
// Results postfiles (main + optional first-stage summary row counts)
// ---------------------------------------------------------------------
capture postclose handle
tempfile out
postfile handle ///
    str8   model_type  ///  OLS / IV
    str244 spec        ///  spec name
    str40  param       ///  var3 / var5
    double coef se pval pre_mean rkf nobs ///
    using `out', replace

// ---------------------------------------------------------------------
// Spec definitions (kept consistent with user_mechanisms.do semantics)
// ---------------------------------------------------------------------
local specs ///
  baseline ///
  growth_endog growth_exog ///
  rent hhi seniority ///
  rent_hhi rent_seniority hhi_seniority rent_hhi_seniority

// Baseline
local ols_exog_baseline  "var4"
local iv_exog_baseline   "var4"
local instr_baseline     "var6 var7"
local endo_baseline      "var3 var5"

// Growth (endogenous): include growth interactions as exogenous controls
local ols_exog_gendog    "var4 var17_e var18_e"
local iv_exog_gendog     "var4 var17_e var18_e"
local instr_gendog       "var6 var7"
local endo_gendog        "var3 var5"

// Growth (exogenous): residualized growth interactions as exogenous controls
local ols_exog_gexog     "var4 var17_x var18_x"
local iv_exog_gexog      "var4 var17_x var18_x"
local instr_gexog        "var6 var7"
local endo_gexog         "var3 var5"

// Rent (lean spec: include triple as exogenous; only var3/var5 endogenous)
local ols_exog_rent      "var4 var8 var9"
local iv_exog_rent       "var4 var8 var9"
local instr_rent         "var6 var7"
local endo_rent          "var3 var5"

// HHI (lean spec)
local ols_exog_hhi       "var4 var11 var12"
local iv_exog_hhi        "var4 var11 var12"
local instr_hhi          "var6 var7"
local endo_hhi           "var3 var5"

// Seniority (lean spec)
local ols_exog_sen       "var4 var14 var15"
local iv_exog_sen        "var4 var14 var15"
local instr_sen          "var6 var7"
local endo_sen           "var3 var5"

// Rent + HHI (lean spec)
local ols_exog_rent_hhi  "var4 var8 var9 var11 var12"
local iv_exog_rent_hhi   "var4 var8 var9 var11 var12"
local instr_rent_hhi     "var6 var7"
local endo_rent_hhi      "var3 var5"

// Rent + Seniority (lean spec)
local ols_exog_rent_sen  "var4 var8 var9 var14 var15"
local iv_exog_rent_sen   "var4 var8 var9 var14 var15"
local instr_rent_sen     "var6 var7"
local endo_rent_sen      "var3 var5"

// HHI + Seniority (lean spec)
local ols_exog_hhi_sen   "var4 var11 var12 var14 var15"
local iv_exog_hhi_sen    "var4 var11 var12 var14 var15"
local instr_hhi_sen      "var6 var7"
local endo_hhi_sen       "var3 var5"

// Rent + HHI + Seniority (lean spec)
local ols_exog_rent_hhi_sen "var4 var8 var9 var11 var12 var14 var15"
local iv_exog_rent_hhi_sen  "var4 var8 var9 var11 var12 var14 var15"
local instr_rent_hhi_sen    "var6 var7"
local endo_rent_hhi_sen     "var3 var5"

// ---------------------------------------------------------------------
// Run specs
// ---------------------------------------------------------------------

// Iterate
foreach s in `specs' {
    di as text "→ Spec: `s'"

    // Load the appropriate panel for the current specification
    if "`s'" == "growth_endog" {
        use `panel_growth_endog', clear
    }
    else if "`s'" == "growth_exog" {
        use `panel_growth_exog', clear
    }
    else {
        use `panel_plain', clear
    }

    // Map macros per spec
    if "`s'" == "baseline" {
        local OLS_EXOG  "`ols_exog_baseline'"
        local IV_EXOG   "`iv_exog_baseline'"
        local INSTR     "`instr_baseline'"
        local ENDO      "`endo_baseline'"
    }
    else if "`s'" == "growth_endog" {
        local OLS_EXOG  "`ols_exog_gendog'"
        local IV_EXOG   "`iv_exog_gendog'"
        local INSTR     "`instr_gendog'"
        local ENDO      "`endo_gendog'"
    }
    else if "`s'" == "growth_exog" {
        local OLS_EXOG  "`ols_exog_gexog'"
        local IV_EXOG   "`iv_exog_gexog'"
        local INSTR     "`instr_gexog'"
        local ENDO      "`endo_gexog'"
    }
    else if "`s'" == "rent" {
        local OLS_EXOG  "`ols_exog_rent'"
        local IV_EXOG   "`iv_exog_rent'"
        local INSTR     "`instr_rent'"
        local ENDO      "`endo_rent'"
    }
    else if "`s'" == "hhi" {
        local OLS_EXOG  "`ols_exog_hhi'"
        local IV_EXOG   "`iv_exog_hhi'"
        local INSTR     "`instr_hhi'"
        local ENDO      "`endo_hhi'"
    }
    else if "`s'" == "seniority" {
        local OLS_EXOG  "`ols_exog_sen'"
        local IV_EXOG   "`iv_exog_sen'"
        local INSTR     "`instr_sen'"
        local ENDO      "`endo_sen'"
    }
    else if "`s'" == "rent_hhi" {
        local OLS_EXOG  "`ols_exog_rent_hhi'"
        local IV_EXOG   "`iv_exog_rent_hhi'"
        local INSTR     "`instr_rent_hhi'"
        local ENDO      "`endo_rent_hhi'"
    }
    else if "`s'" == "rent_seniority" {
        local OLS_EXOG  "`ols_exog_rent_sen'"
        local IV_EXOG   "`iv_exog_rent_sen'"
        local INSTR     "`instr_rent_sen'"
        local ENDO      "`endo_rent_sen'"
    }
    else if "`s'" == "hhi_seniority" {
        local OLS_EXOG  "`ols_exog_hhi_sen'"
        local IV_EXOG   "`iv_exog_hhi_sen'"
        local INSTR     "`instr_hhi_sen'"
        local ENDO      "`endo_hhi_sen'"
    }
    else if "`s'" == "rent_hhi_seniority" {
        local OLS_EXOG  "`ols_exog_rent_hhi_sen'"
        local IV_EXOG   "`iv_exog_rent_hhi_sen'"
        local INSTR     "`instr_rent_hhi_sen'"
        local ENDO      "`endo_rent_hhi_sen'"
    }

    // OLS
    reghdfe total_contributions_q100 var3 var5 `OLS_EXOG', `FE'
    local N = e(N)
    foreach p in var3 var5 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("OLS") ("`s'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (.) (`N')
    }

    // IV
    ivreghdfe total_contributions_q100 (`ENDO' = `INSTR') `IV_EXOG', `FE' savefirst
    local rkf = e(rkf)
    local N   = e(N)
    foreach p in var3 var5 {
        local b    = _b[`p']
        local se   = _se[`p']
        local t    = `b'/`se'
        local pval = 2*ttail(e(df_r), abs(`t'))
        post handle ("IV") ("`s'") ("`p'") (`b') (`se') (`pval') (`pre_mean') (`rkf') (`N')
    }
}

// Export ---------------------------------------------------------------
postclose handle
use `out', clear
export delimited using "`result_dir'/consolidated_results.csv", replace delimiter(",") quote

di as result "→ CSV written to `result_dir'/consolidated_results.csv"
log close
