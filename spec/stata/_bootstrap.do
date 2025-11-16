* ----------------------------------------------------------------------
* spec/stata/_bootstrap.do — Compatibility shim for legacy specs
* Delegates to the shared 00_paths.do helper (project root + globals).
* ----------------------------------------------------------------------

local __paths ""
foreach candidate in ///
    00_paths.do ///
    spec/00_paths.do ///
    ../00_paths.do ///
    ../spec/00_paths.do ///
    ../../00_paths.do ///
    ../../spec/00_paths.do ///
    ../../../00_paths.do ///
    ../../../spec/00_paths.do ///
    ../../../../00_paths.do ///
    ../../../../spec/00_paths.do ///
{
    if "`__paths'" == "" {
        if fileexists("`candidate'") {
            local __paths "`candidate'"
        }
    }
}

if "`__paths'" == "" {
    local env_root: env PROJECT_ROOT
    if "`env_root'" == "" {
        local env_root: env STATAROOT
    }
    if "`env_root'" != "" {
        foreach candidate in "`env_root'/00_paths.do" "`env_root'/spec/00_paths.do" {
            if "`__paths'" == "" {
                if fileexists("`candidate'") {
                    local __paths "`candidate'"
                }
            }
        }
    }
}

if "`__paths'" == "" | !fileexists("`__paths'") {
    di as error "spec/stata/_bootstrap.do: unable to locate 00_paths.do."
    di as error "Run from the repository root or set PROJECT_ROOT."
    exit 198
}

do "`__paths'"
