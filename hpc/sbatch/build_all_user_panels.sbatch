#!/bin/bash
# Build *all* user-level panel variants in a single Stata run.
# Submit with:   sbatch hpc/sbatch/build_all_user_panels.sbatch

#SBATCH --time=01:00:00
#SBATCH --mem=10G
#SBATCH --job-name=build_user_panels
#SBATCH --output=build_user_panels_%j.out
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=sxr203@nyu.edu

set -euo pipefail

# Stata .do files expect to be called from ~/main/src
cd "$HOME/main/src"

module purge
module load stata/17.0

stata -b do build_all_user_panels.do
