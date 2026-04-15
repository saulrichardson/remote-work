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
*  Test MSA coefficient difference
*  Compare our approach vs original loop approach
*====================================================================*

args panel_variant
if "`panel_variant'" == "" local panel_variant "precovid"

do "../globals.do"

*--------------------------------------------------------------------*
* Run exactly as in user_productivity_expost_growth_loop.do
*--------------------------------------------------------------------*
di _n "=== ORIGINAL APPROACH FROM LOOP SCRIPT ==="

* Load and prepare data exactly as in loop script
use "$processed_data/user_panel_`panel_variant'.dta", clear
gen companyname_c = lower(companyname)

preserve
    use "$processed_data/firm_panel.dta", clear
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

* Get firm keys
tempfile firmkeys
preserve
    collapse (last) industry (last) company_msa, by(companyname)
    save `firmkeys'
restore

* Load Scoop data
import delimited "$processed_data/Scoop_Positions_Firm_Collapse2.csv", clear
drop v1
gen date_numeric = date(date, "YMD")
drop date
rename date_numeric date
format date %td
gen yh = hofd(date)
format yh %th
drop if date == 22797

collapse (last) total_employees date (sum) join leave, by(companyname yh)
gen byte covid = (yh >= 120)

* Average post-Covid growth
preserve
    encode companyname, gen(firm_n)
    xtset firm_n yh
    sort firm_n yh
    gen growth_yh = (total_employees / L.total_employees) - 1 if _n>1
    winsor2 growth_yh, cuts(1 99) suffix(_we)
    collapse (mean) growth_yh_we if covid, by(companyname)
    rename growth_yh_we growth_rate_we_post_c
    tempfile g_postavg
    save `g_postavg'
restore

* Merge firm keys and compute growth
merge m:1 companyname using `firmkeys', nogenerate
encode companyname, gen(firm_n)
xtset firm_n yh
sort firm_n yh
gen fg = (total_employees/L.total_employees) - 1 if _n>1
winsor2 fg, cuts(1 99) suffix(_we)
keep if covid
tempfile postcovid
save `postcovid'

* Industry leave-one-out
use `postcovid', clear
bys industry: egen ind_sum = total(fg_we)
bys industry: egen ind_N = count(fg_we)
gen ind_growth_postavg_lo = (ind_sum - fg_we) / (ind_N - 1) if ind_N > 1
collapse (mean) ind_growth_postavg_lo, by(industry)
tempfile ind_postavg
save `ind_postavg'

* MSA leave-one-out  
use `postcovid', clear
bys company_msa: egen msa_sum = total(fg_we)
bys company_msa: egen msa_N = count(fg_we)
gen msa_growth_postavg_lo = (msa_sum - fg_we) / (msa_N - 1) if msa_N > 1
keep company_msa msa_growth_postavg_lo
collapse (mean) msa_growth_postavg_lo, by(company_msa)
tempfile msa_postavg
save `msa_postavg'

* Final merge and regression
use `postcovid', clear
gen companyname_c = lower(companyname)
merge m:1 industry using `ind_postavg', keep(match) nogen
merge m:1 company_msa using `msa_postavg', keep(match) nogen
merge m:1 companyname using `g_postavg', keep(match) nogen
merge m:1 companyname_c using `firm_extra', keep(match) nogen

* Check sample before regression
di _n "Sample size before regression:"
count
di _n "Missing values check:"
count if missing(growth_rate_we_post_c)
count if missing(ind_growth_postavg_lo)
count if missing(msa_growth_postavg_lo)
count if missing(tile_rent)
count if missing(tile_hhi)

* Run regression without any duplicates handling
di _n "First-stage regression (original approach):"
reghdfe growth_rate_we_post_c ind_growth_postavg_lo msa_growth_postavg_lo tile_rent tile_hhi

* Now try with duplicate handling as in our script
bysort companyname: keep if _n == 1
di _n "Sample size after removing duplicates:"
count

di _n "First-stage regression (with duplicate removal):"
reghdfe growth_rate_we_post_c ind_growth_postavg_lo msa_growth_postavg_lo tile_rent tile_hhi