* ----------------------------------------------------------------------
* spec/_bootstrap.do — Resolve project paths robustly
* Include this at the top of every spec before referencing $PROJECT_ROOT
* ----------------------------------------------------------------------

capture confirm global PROJECT_ROOT
if _rc {
    * First try environment variable so batch jobs can override paths
    local env_root: env PROJECT_ROOT
    if "`env_root'" == "" {
        * Backwards compatibility for legacy STATAROOT env var
        local env_root: env STATAROOT
    }
    if "`env_root'" != "" {
        global PROJECT_ROOT "`env_root'"
    }
    else {
        * Derive from the current script location (this bootstrap file)
        local __bootstrap_self "`c(filename)'"
        if "`__bootstrap_self'" == "" {
            * When invoked interactively, fall back to current directory
            local __bootstrap_self "`c(pwd)'/_bootstrap.do"
        }

        capture mata: mata drop __trim_trailing_sep()
        capture mata: mata drop __parent_dir()
        capture mata: mata drop __find_project_root()

        mata:
        function __trim_trailing_sep(string scalar path) {
            string scalar backslash
            backslash = char(92)
            real scalar len
            len = strlen(path)
            while (len > 1) {
                string scalar last
                last = substr(path, len, 1)
                if (last == "/" | last == backslash) {
                    /* preserve drive roots like C:\ */
                    if (len == 3 & substr(path, 2, 1) == ":") {
                        break
                    }
                    path = substr(path, 1, len - 1)
                    len  = len - 1
                }
                else {
                    break
                }
            }
            return(path)
        }

        function __parent_dir(string scalar path) {
            string scalar backslash
            real scalar i, len
            backslash = char(92)
            string scalar clean, ch

            clean = __trim_trailing_sep(path)
            len   = strlen(clean)
            if (len == 0) return("")

            for (i = len; i >= 1; i--) {
                ch = substr(clean, i, 1)
                if (ch == "/" | ch == backslash) {
                    if (i == 1) return(substr(clean, 1, 1))
                    if (i == 3 & substr(clean, 2, 1) == ":") return(substr(clean, 1, 3))
                    return(substr(clean, 1, i - 1))
                }
            }
            return("")
        }

        function __find_project_root(string scalar start) {
            string scalar here
            here = __trim_trailing_sep(start)
            while (here != "") {
                if (direxists(here + "/.git") | fileexists(here + "/README.md")) {
                    return(here)
                }
                here = __parent_dir(here)
            }
            return("")
        }
        end

        mata: st_local("__bootstrap_self", "`__bootstrap_self'")
        mata: st_local("__spec_dir", __parent_dir(st_local("__bootstrap_self")))
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

local __sep "/"
if strpos("`c(os)'","Windows") local __sep "\"

global RAW_DATA        "$PROJECT_ROOT`__sep'data/raw"
global PROCESSED_DATA  "$PROJECT_ROOT`__sep'data/processed"
global RAW_RESULTS     "$PROJECT_ROOT`__sep'results/raw"
global FINAL_TEX       "$PROJECT_ROOT`__sep'results/final/tex"
global FINAL_FIGURES   "$PROJECT_ROOT`__sep'results/final/figures"

mata: mata drop __find_project_root()
mata: mata drop __parent_dir()
mata: mata drop __trim_trailing_sep()


* Backwards-compatible aliases
global results        "$RAW_RESULTS"
global processed_data "$PROCESSED_DATA"
global data_processed "$PROCESSED_DATA"
global clean_results  "$FINAL_TEX"
