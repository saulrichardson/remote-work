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



*====================================================================*
*  spec/user_productivity_expost_growth_loop.do
*  ------------------------------------------------------------------
*  Single–pass IV that interacts the remote–work treatment (var5 / var3)
*  with THREE alternative definitions of firms' ex-post scaling:
*      1)  post_covid_growth_we          – pre-vs-post difference
*      2)  growth_rate_we_post_c         – average Δlog employment during
*                                           the post-Covid period
*      3)  growth_yh_we                  – dynamic, half-year specific rate
*  All growth variables are constructed on-the-fly from the raw Scoop
*  head-count history.  Industry & MSA leave-one-out growth means are also
*  built via a jack-knife for completeness (not used in the regression but
*  available for future extensions).
*
*  Controls:
*      • var4  (baseline)
*      • rent_pctile   × yh   – from firm_panel
*      • hhi_hq_fw_lg × yh    – from firm_panel (Lightcast concentration)
*
*  Fixed effects:  user_id  firm_id  industry#yh  msa#yh
*  Cluster:        user_id
*
*  Results (one row per growth definition) are written to
*      $results/remote_x_growth_loop_<panel_variant>.csv
*====================================================================*

*--------------------------------------------------------------------*
* 0. Parse optional panel variant argument  --------------------------*
*--------------------------------------------------------------------*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

*--------------------------------------------------------------------*
* 1. Globals & open main panel --------------------------------------*
*--------------------------------------------------------------------*

do "../globals.do"

use "$processed_data/user_panel_`panel_variant'.dta", clear

gen companyname_c = lower(companyname)

*--------------------------------------------------------------------*
* 2. Bring in rent & HHI controls from the firm panel  --------------*
*--------------------------------------------------------------------*

preserve
    use "$processed_data/firm_panel.dta", clear
// 	gen byte covid = (yh >= 120)
    keep companyname rent hhi_1000 covid startup
	
    gen companyname_c = lower(companyname)
	
	collapse (last) startup (last) rent (last) hhi_1000 if covid, by(companyname_c)
	xtile tile_rent = rent, nq(2)
	xtile tile_hhi = hhi_1000, nq(2)
	
    tempfile firm_extra
    save `firm_extra'
restore

merge m:1 companyname_c using `firm_extra', keep(match) nogen
drop _merge

tempfile main_panel
save `main_panel'

*--------------------------------------------------------------------*
* 3. Construct firm-level growth measures on-the-fly ----------------*
*--------------------------------------------------------------------*

// preserve

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

	// Collapse to have one observation per firm-half-year, and calculate growth & rates:
	collapse (last) total_employees date (sum) join leave, by(companyname yh)

    gen byte covid = (yh >= 120)

    /****************************************************************
    * (a)  Static pre-vs-post difference  – post_covid_growth_we     *
    ****************************************************************/
    preserve
        collapse (mean) total_employees, by(companyname covid)
        reshape wide total_employees, i(companyname) j(covid)
        gen post_covid_growth_we = (total_employees1 - total_employees0) / total_employees0
        winsor2 post_covid_growth_we, cuts(1 99)
        keep companyname post_covid_growth_we
		
		xtile tile_growth = post_covid_growth_we, nq(2)
        tempfile g_static
        save `g_static'
    restore

    /****************************************************************
    * (b)  Average post-Covid half-year growth – growth_rate_we_post_c*
    ****************************************************************/
    preserve
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

    /****************************************************************
    * (c)  Dynamic half-year growth – growth_yh_we                   *
    ****************************************************************/
//     encode companyname, gen(firm_n)
//     xtset firm_n yh
//     sort firm_n yh
//     gen growth_yh = (total_employees / L.total_employees) - 1 if _n>1
//     winsor2 growth_yh, cuts(1 99) suffix(_we)
//     keep companyname yh growth_yh_we
//     tempfile g_dyn
//     save `g_dyn'

// restore   /* → back to user panel */

*--------------------------------------------------------------------*
* 4. Merge growth measures into the panel ---------------------------*
*--------------------------------------------------------------------*
use `main_panel', clear

merge m:1 companyname using `g_static',   keep(match) nogen
merge m:1 companyname using `g_postavg',  keep(match) nogen

gen var17 = covid*tile_post_c
gen var18 = covid*tile_post_c*startup

// reghdfe total_contributions_q100 var3 var5 var4, ///
//     absorb(firm_id#user_id yh) vce(cluster user_id) 
	
// 	savefirst
	
// reghdfe total_contributions_q100 var3 var5 var4 var17 var18, ///
//     absorb(firm_id#user_id yh) vce(cluster user_id) 
// 	savefirst
	
// ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
//     absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
	
// ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
//     absorb(firm_id#user_id yh) vce(cluster user_id) savefirst
//
// reghdfe total_contributions_q100 growth_rate_we_post_c

*==============================================================*
*  Post-Covid average growth by industry & MSA  (no nesting)   *
*==============================================================*

*------------------------------------------------------------------*
* 1.  Grab firm → (industry, MSA) keys and stash to `firmkeys'      *
*------------------------------------------------------------------*
tempfile firmkeys
preserve
    collapse (last) industry (last) company_msa, by(companyname)
    save `firmkeys'
restore    // original dataset back in memory

*------------------------------------------------------------------*
* 2.  Load head-count history, build fg_we, keep post-Covid rows    *
*------------------------------------------------------------------*
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
    gen date_numeric = date(date, "YMD")
	drop date
    rename date_numeric date
    format date %td

    gen yh = hofd(date)
    format yh %th

	// Drop one-off observations in June 2022
	drop if date == 22797

	// Collapse to have one observation per firm-half-year, and calculate growth & rates:
	collapse (last) total_employees date (sum) join leave, by(companyname yh)
	
gen byte covid = (yh >= 120)

merge m:1 companyname using `firmkeys', nogenerate

encode companyname, gen(firm_n)
xtset firm_n yh
sort firm_n yh

gen fg = (total_employees/L.total_employees) - 1 if _n>1
winsor2 fg, cuts(1 99) suffix(_we)

keep if covid                                  // post-Covid only
tempfile postcovid
save `postcovid'

*------------------------------------------------------------------*
* --- Industry leave-one-out mean over the whole post-Covid period ---
use `postcovid', clear

bys industry: egen ind_sum = total(fg_we)
bys industry: egen ind_N   = count(fg_we)
gen ind_growth_postavg_lo = (ind_sum - fg_we) / (ind_N - 1) if ind_N > 1
// keep companyname yh industry ind_growth_postavg_lo
collapse (mean) ind_growth_postavg_lo, by(industry)
tempfile ind_postavg
save `ind_postavg'

* --- MSA leave-one-out mean over the whole post-Covid period ---
use `postcovid', clear

bys company_msa: egen msa_sum = total(fg_we)
bys company_msa: egen msa_N   = count(fg_we)
gen msa_growth_postavg_lo = (msa_sum - fg_we) / (msa_N - 1) if msa_N > 1
// keep companyname yh company_msa msa_growth_postavg_lo
keep company_msa msa_growth_postavg_lo
collapse (mean) msa_growth_postavg_lo, by(company_msa)
tempfile msa_postavg
save `msa_postavg'

// use `postcovid', clear
// collapse (mean) fg_we, by(companyname)
// bys companyname: egen msa_sum = total(fg_we)
// bys companyname: egen msa_N   = count(fg_we)
// gen comp_growth_postavg_lo = (msa_sum - fg_we) / (msa_N - 1) if msa_N > 1
// // keep companyname yh company_msa msa_growth_postavg_lo
// keep companyname comp_growth_postavg_lo
// tempfile comp_postavg
// save `comp_postavg'

*------------------------------------------------------------------*
* 5.  Attach the two averages back to the firm-half-year panel     *
*------------------------------------------------------------------*
use `postcovid', clear                       // back to firm × yh data

gen companyname_c = lower(companyname)

merge m:1 industry     using `ind_postavg',  keep(match) nogen
merge m:1 company_msa  using `msa_postavg',  keep(match) nogen
merge m:1 companyname using `g_static',   keep(match) nogen
merge m:1 companyname using `g_postavg',  keep(match) nogen
merge m:1 companyname_c using `firm_extra', keep(match) nogen

reghdfe growth_rate_we_post_c ind_growth_postavg_lo msa_growth_postavg_lo tile_rent tile_hhi 

predict growth_resid

xtile tile_growth_resid = growth_resid, nq(2)

collapse  (last) tile_growth_resid, by(companyname)

tempfile firm_measures
save `firm_measures'

use "$processed_data/user_panel_`panel_variant'.dta", clear
capture drop _merge
merge m:1 companyname using `firm_measures'

gen var17 = covid*tile_growth_resid
gen var18 = covid*tile_growth_resid*startup

ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4 var17 var18, ///
        absorb(user_id firm_id yh) vce(cluster user_id) savefirst 
		

		
		
// ivreghdfe total_contributions_q100 (var3 var5 = var6 var7) var4, ///
//         absorb(user_id#firm_id yh) vce(cluster user_id) savefirst     

		

// merge m:1 `comp_postavg'  using `msa_postavg',  keep(match) nogen

// keep companyname yh ind_growth_postavg msa_growth_postavg
// tempfile jack_bartik
// save `jack_bartik', replace

*------------------------------------------------------------------*
* 6.  Merge into the main user panel                               *
*------------------------------------------------------------------*
              // your panel from earlier
merge m:1 companyname yh using `jack_bartik', keep(match) nogen

*--------------------------------------------------------------------*
* 6.  Logging & post-file setup ------------------------------------*
*--------------------------------------------------------------------*

local specname  "remote_x_growth_loop_`panel_variant'"
capture log close
cap mkdir "$LOG_DIR"
log using "$LOG_DIR/`specname'.log", replace text


local result_dir "$results/`specname'"
cap mkdir "`result_dir'"

tempfile out
capture postclose handle
postfile handle ///
    str25 gtype ///              growth variable used
    double b5  se5  p5 ///       baseline var5 stats
    double b5g se5g p5g ///      interaction stats
    double rkf nobs ///          first-stage F and obs
    using `out', replace

	*--------------------------------------------------------------------*
* 7.  Estimation loop ----------------------------------------------*
*--------------------------------------------------------------------*

local gvars "post_covid_growth_we growth_rate_we_post_c growth_yh_we"

foreach g of local gvars {

    di as text "=== Growth variable: `g' ==="

    *------------------------------------------------------------*
    * 7a. Residualise growth on rent, HHI, industry#yh, msa#yh   *
    *------------------------------------------------------------*

    preserve
        /* residualise against firm‐specific rent & HHI *and* the 
           leave-one-out industry/MSA growth that the firm faces */
        keep companyname yh `g' rent_pctile hhi_hq_fw_lg ind_growth_favg_yh msa_growth_favg_yh
		
		reghdfe post_covid_growth_we rent_pctile hhi_hq_fw_lg ind_growth_favg_yh msa_growth_favg_yh
		
		
        reghdfe `g' rent_pctile hhi_hq_fw_lg ind_growth_favg_yh msa_growth_favg_yh, absorb()
        predict double g_resid, resid
        keep companyname yh g_resid
        tempfile gres
        save `gres'
    restore

    merge m:1 companyname yh using `gres', keep(match) nogen

    quietly summarize g_resid
    gen double g_c = g_resid - r(mean)

    *--- build interaction block ---------------------------------------*
    foreach v in var3 var5 var6 var7 {
        gen `v'_g = `v' * g_c
    }

    *--- IV regression --------------------------------------------------*
    ivreghdfe total_contributions_q100                             ///
        (var3 var5 var3_g var5_g =                                ///
         var6 var7 var6_g var7_g)                                 ///
        var4  c.g_c                                               /// main effect
        c.rent_pctile##i.yh  c.hhi_hq_fw_lg##i.yh                 /// controls
        absorb(user_id firm_id industry#yh msa#yh)                /// FE stack
        vce(cluster user_id)  savefirst

    *--- post results ---------------------------------------------------*
    local b5   = _b[var5]
    local se5  = _se[var5]
    local p5   = 2*ttail(e(df_r), abs(`b5'/`se5'))

    local b5g  = _b[var5_g]
    local se5g = _se[var5_g]
    local p5g  = 2*ttail(e(df_r), abs(`b5g'/`se5g'))

    post handle ("`g' (cont)") (`b5') (`se5') (`p5') ///
                  (`b5g') (`se5g') (`p5g')      ///
                  (e(rkf)) (e(N))

    *------------------------------------------------------------*
    * High-growth dummy interaction (above median)               *
    *------------------------------------------------------------*

    quietly summarize g_resid, detail
    scalar med_`g' = r(p50)
    gen byte hi_g = (g_resid > med_`g') if !missing(g_resid)

    foreach v in var3 var5 var6 var7 {
        gen `v'_hi = `v' * hi_g
    }

    ivreghdfe total_contributions_q100                             ///
        (var3 var5 var3_hi var5_hi =                              ///
         var6 var7 var6_hi var7_hi)                               ///
        var4  hi_g                                                /// main effect
        c.rent_pctile##i.yh  c.hhi_hq_fw_lg##i.yh                 /// controls
        absorb(user_id firm_id industry#yh msa#yh)                /// FE stack
        vce(cluster user_id) savefirst

    local b5   = _b[var5]
    local se5  = _se[var5]
    local p5   = 2*ttail(e(df_r), abs(`b5'/`se5'))

    local b5g  = _b[var5_hi]
    local se5g = _se[var5_hi]
    local p5g  = 2*ttail(e(df_r), abs(`b5g'/`se5g'))

    post handle ("`g' (dummy)") (`b5') (`se5') (`p5') ///
                  (`b5g') (`se5g') (`p5g')         ///
                  (e(rkf)) (e(N))

    *--- clean up before next growth variable -------------------*
    drop hi_g g_resid
    foreach v in var3 var5 var6 var7 {
        drop `v'_hi
        drop `v'_g
    }
    drop g_c
}

postclose handle
use `out', clear
export delimited using "`result_dir'/results.csv", replace

di as result "✓ Results written to `result_dir'/results.csv"

log close
