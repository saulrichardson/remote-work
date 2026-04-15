/*-------------------------------------------------------------------
| build_all_users.do — Legacy wrapper (deprecated)
|
| The canonical user-panel build script is now:
|   src/stata/build_all_user_panels.do
|
| This wrapper exists so older notes/commands keep working, but it does
| not maintain an independent pipeline.
*-------------------------------------------------------------------*/

version 17
clear all
set more off

do "../../spec/stata/_bootstrap.do"
di as result "build_all_users.do is deprecated; running build_all_user_panels.do"
do "$PROJECT_ROOT/src/stata/build_all_user_panels.do"
