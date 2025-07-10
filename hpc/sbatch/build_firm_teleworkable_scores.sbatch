#!/bin/bash
# Build firm-level teleworkability scores.
# Submit with: sbatch hpc/sbatch/build_firm_teleworkable_scores.sbatch

#SBATCH --time=24:00:00
#SBATCH --mem=80G
#SBATCH --job-name=firm_tele_scores
#SBATCH --output=build_firm_teleworkable_scores.out
#SBATCH --error=build_firm_teleworkable_scores.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=sxr203@nyu.edu

set -euo pipefail

cd "$HOME/main/src"

module purge
module load stata/17.0

stata -b do build_firm_teleworkable_scores.do
