* ----------------------------------------------------------------------
* spec/_bootstrap.do — Resolve project paths robustly
* Include this at the top of every spec before referencing $PROJECT_ROOT
* ----------------------------------------------------------------------

capture confirm global PROJECT_ROOT
if _rc {
    * First try environment variable so batch jobs can override paths
    local env_root: env PROJECT_ROOT
    if "`env_root'" != "" {
        global PROJECT_ROOT "`env_root'"
    }
    else {
        * Derive from the current script location
        mata: st_local("__spec_dir", pathrtrim(pathdirname(st_local("c(filename)"))))

        mata:
        function __find_project_root(string scalar start) {
            string scalar here
            here = start
            while (here != "") {
                if (direxists(here + "/.git") | fileexists(here + "/README.md")) {
                    return(here)
                }
                here = pathrtrim(pathdirname(here))
            }
            return("")
        }
        end

        mata: st_local("__proj_root", __find_project_root(st_local("__spec_dir")))
        if "`__proj_root'" == "" {
            di as error "Unable to locate project root. Set PROJECT_ROOT env var before running."
            exit 198
        }
        global PROJECT_ROOT "`__proj_root'"
    }
}

* Derive commonly used paths from the resolved root
if "$PROJECT_ROOT" == "" {
    di as error "PROJECT_ROOT is empty after bootstrap."
    exit 198
}

scalar __sep = strpos("`c(os)'","Windows") ? "\" : "/"

global RAW_DATA        "$PROJECT_ROOT" + "`__sep'" + "data/raw"
global PROCESSED_DATA  "$PROJECT_ROOT" + "`__sep'" + "data/processed"
global RAW_RESULTS     "$PROJECT_ROOT" + "`__sep'" + "results/raw"
global FINAL_TEX       "$PROJECT_ROOT" + "`__sep'" + "results/final/tex"
global FINAL_FIGURES   "$PROJECT_ROOT" + "`__sep'" + "results/final/figures"

mata: mata drop __find_project_root()


* Backwards-compatible aliases
global results        "$RAW_RESULTS"
global processed_data "$PROCESSED_DATA"
global data_processed "$PROCESSED_DATA"
global clean_results  "$FINAL_TEX"

