/**************************************************************************/
capture log close
cap mkdir "log"
log using "log/build_avg_employee_distances.log", replace text
*  make_distance.do
*  --------------------------------------------------------------
*  Adds worker ↔ HQ MSA distance to expanded_half_years_2.dta
**************************************************************************/

*------------ 0.  File paths --------------------------------------------
global PANEL  "$data/expanded_half_years_2.dta"
global MODAL  "/Users/saul/Dropbox/Remote Work Startups/New/saul/New/Data/modal_msa_per_firm.dta"
global GAZ    "/Users/saul/Downloads/2020_Gaz_cbsa_national.txt"

*------------ 1.  Bring in the worker-level panel ------------------------
use "$PANEL", clear            // has variables user_id   companyname   msa  ...

rename msa worker_msa          // keep a copy before adding HQ info

*------------ 2.  Merge the firm's modal MSA -----------------------------
merge m:1 companyname using "$MODAL", keep(match master) nogen
/*  assumes the file contributes a string variable named  msa   */
rename msa hq_msa

preserve

*------------ 3.  Build CBSA-centroid lookup from Gazetteer --------------
tempfile lookup
quietly {
    import delimited "$GAZ", delim(tab) clear
    
    keep geoid name cbsa_type intptlat intptlong
    keep if cbsa_type == 1              // keep only metropolitan sas
    rename (geoid intptlat intptlong) (cbsa lat lon)
    
    gen name_key = upper(stritrim(subinstr(subinstr(name,"-"," ",.),",","",.)))
    replace name_key = regexr(name_key," (METRO AREA|MICRO AREA)$","")
    
    keep name_key lat lon
    save "`lookup'"
}


restore


*------------ 4.  Attach coordinates to worker & HQ MSAs -----------------
* (a) worker side
gen worker_key = upper(stritrim(subinstr(subinstr(worker_msa,"-"," ",.),",","",.)))
replace worker_key = regexr(worker_key," MSA$","")

rename worker_key name_key  
merge m:1 name_key using "`lookup'", gen(worker_merge)
rename (lat lon) (lat_w lon_w)
rename (name_key lat lon) (worker_key lat_w lon_w)

* (b) HQ side
gen hq_key = upper(stritrim(subinstr(subinstr(hq_msa,"-"," ",.),",","",.)))
replace hq_key = regexr(hq_key," MSA$","")

rename hq_key name_key  
merge m:1 name_key using "`lookup'", gen(hq_merge)
rename (name_key lat lon) (hq_key lat_hq lon_hq)

*------------ 5.  Great-circle distance (km) -----------------------------
cap which geodist
if _rc ssc install geodist, replace

geodist lat_w lon_w  lat_hq lon_hq, gen(dist_km) 

* firm-level mean (for your split list)
bysort companyname: egen mean_dist_km = mean(dist_km)


*------------ 6.  Save the enriched panel --------------------------------
save "$data/expanded_half_years_2_with_distance.dta", replace

display as txt "✓  Distance variables added and file saved:"
display as txt "   $data/expanded_half_years_2_with_distance.dta"

log close
