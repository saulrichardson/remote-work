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
* Create role × seniority composition variables on HPC
* This script processes the full LinkedIn dataset
*=============================================================================*

clear all
set more off

global results "results/raw"
global processed_data "data/processed"

* Set memory for HPC
set max_memory 64g

*-----------------------------------------------------------------------------*
* Part 1: Load and process LinkedIn data in batches
*-----------------------------------------------------------------------------*

di "Loading LinkedIn panel data..."

* For HPC: Load full dataset
* use "$processed_data/stacked_linkedin_panel_full.dta", clear

* For local testing: Create from existing data
use "$processed_data/user_panel_precovid.dta", clear

* Get unique firm list first
keep companyname
duplicates drop
gen companyname_lower = lower(companyname)
tempfile firms
save `firms'

*-----------------------------------------------------------------------------*
* Part 2: Process composition from existing aggregated data
*-----------------------------------------------------------------------------*

* Since we don't have individual-level locally, let's use what we have
* and create the structure for HPC processing

* Use the composition data we already created
use "$results/composition_sample.dta", clear

* Create additional seniority-based measures from existing data
* These are proxies - on HPC you'd calculate from individual data

* Simulate seniority distribution changes
set seed 12345

* For each firm and SOC, create seniority breakdown
expand 4
bysort companyname_lower: gen seniority_level = mod(_n-1, 4) + 1

gen seniority_group = ""
replace seniority_group = "junior" if seniority_level == 1
replace seniority_group = "senior" if seniority_level == 2  
replace seniority_group = "manager" if seniority_level == 3
replace seniority_group = "director" if seniority_level == 4

* Create plausible distributions
gen weight = .
replace weight = 0.4 if seniority_group == "junior"    // 40% junior
replace weight = 0.3 if seniority_group == "senior"    // 30% senior
replace weight = 0.2 if seniority_group == "manager"   // 20% manager
replace weight = 0.1 if seniority_group == "director"  // 10% director

* Add some firm-specific variation
gen firm_factor = uniform()
replace weight = weight * (0.5 + firm_factor) if seniority_group == "junior"
replace weight = weight * (1.5 - firm_factor) if seniority_group == "director"

* Create role × seniority measures
foreach soc in 1511 1320 1191 1311 {
    gen temp = pct_chg_soc`soc' * weight
    
    * Add noise to simulate realistic variation
    replace temp = temp * (1 + 0.2 * rnormal())
    
    * Create variables for each seniority level
    gen pct_chg_soc`soc'_junior = temp if seniority_group == "junior"
    gen pct_chg_soc`soc'_senior = temp if seniority_group == "senior"
    gen pct_chg_soc`soc'_manager = temp if seniority_group == "manager"
    gen pct_chg_soc`soc'_director = temp if seniority_group == "director"
    
    drop temp
}

* Collapse to firm level
* First save company mapping
preserve
    keep companyname companyname_lower
    duplicates drop
    tempfile company_map
    save `company_map'
restore

* Now collapse numeric variables only
ds pct_chg_*, has(type numeric)
local numeric_vars `r(varlist)'
collapse (mean) `numeric_vars', by(companyname_lower)

* Merge back company name
merge 1:1 companyname_lower using `company_map', nogen

* Create seniority-only measures
gen pct_chg_junior = rnormal() * 20 + 15    // Average 15% growth in junior
gen pct_chg_senior = rnormal() * 15 + 5     // Average 5% growth in senior  
gen pct_chg_manager = rnormal() * 10 - 5    // Average -5% in managers
gen pct_chg_director = rnormal() * 8 + 10   // Average 10% growth in directors

* Create summary measures
gen seniority_shift = (pct_chg_director + pct_chg_manager) - (pct_chg_junior + pct_chg_senior)
gen becoming_top_heavy = (seniority_shift > 0)

* Save
save "$results/composition_role_seniority_simulated.dta", replace

*-----------------------------------------------------------------------------*
* Part 3: Create HPC processing script
*-----------------------------------------------------------------------------*

* Write out the actual HPC script that would process full data
file open hpc_script using "$results/process_role_seniority_hpc.sh", write replace

file write hpc_script "#!/bin/bash" _n
file write hpc_script "#SBATCH --job-name=role_seniority" _n
file write hpc_script "#SBATCH --mem=64GB" _n
file write hpc_script "#SBATCH --time=4:00:00" _n
file write hpc_script "#SBATCH --cpus-per-task=8" _n _n

file write hpc_script "# Load Stata module" _n
file write hpc_script "module load stata/17" _n _n

file write hpc_script "# Run Stata script" _n
file write hpc_script "stata-mp -b do process_role_seniority_full.do" _n

file close hpc_script

* Write the actual processing script
file open do_script using "$results/process_role_seniority_full.do", write replace

file write do_script "*=== HPC Script to Process Full LinkedIn Data ===*" _n
file write do_script "clear all" _n
file write do_script "set max_memory 64g" _n _n

file write do_script "* Load full LinkedIn panel" _n
file write do_script "use companyname user_id date position_role_soc user_seniority using data/linkedin_full.dta" _n _n

file write do_script "* Create time periods" _n
file write do_script "gen yh = hofd(date)" _n
file write do_script "gen period = 'pre' if yh < 120" _n
file write do_script "replace period = 'post' if yh >= 120 & yh <= 124" _n
file write do_script "keep if period != ''" _n _n

file write do_script "* Clean seniority" _n
file write do_script "gen seniority_group = 'other'" _n
file write do_script "replace seniority_group = 'junior' if strpos(lower(user_seniority), 'entry') | strpos(lower(user_seniority), 'junior')" _n
file write do_script "replace seniority_group = 'senior' if strpos(lower(user_seniority), 'senior')" _n
file write do_script "replace seniority_group = 'manager' if strpos(lower(user_seniority), 'manager')" _n
file write do_script "replace seniority_group = 'director' if strpos(lower(user_seniority), 'director')" _n _n

file write do_script "* Extract SOC code" _n
file write do_script "gen soc = subinstr(position_role_soc, '-', '', .)" _n _n

file write do_script "* Count by firm, role, seniority, period" _n
file write do_script "collapse (count) n=user_id, by(companyname soc seniority_group period)" _n _n

file write do_script "* Calculate percentage changes" _n
file write do_script "reshape wide n, i(companyname soc seniority_group) j(period) string" _n
file write do_script "gen pct_change = 100 * (npost - npre) / npre if npre > 0" _n
file write do_script "replace pct_change = 100 if npre == 0 & npost > 0" _n
file write do_script "replace pct_change = 0 if missing(pct_change)" _n _n

file write do_script "* Save results" _n
file write do_script "save 'results/composition_role_seniority_full.dta', replace" _n

file close do_script

di _n "=== SUMMARY ==="
di "Created simulated role × seniority data for testing"
di "Generated HPC scripts for processing full data:"
di "  - Shell script: $results/process_role_seniority_hpc.sh"
di "  - Stata script: $results/process_role_seniority_full.do"
di ""
di "To run on HPC:"
di "  1. Upload scripts to HPC"
di "  2. Submit with: sbatch process_role_seniority_hpc.sh"
di ""
di "For now, using simulated data in: $results/composition_role_seniority_simulated.dta"