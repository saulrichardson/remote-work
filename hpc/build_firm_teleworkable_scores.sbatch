#!/bin/bash
# Build firm-level teleworkability scores derived from LinkedIn roles & O*NET.
# -----------------------------------------------------------------------------
# Slurm submission script – submit with:
#     sbatch hpc/build_firm_teleworkable_scores.sbatch
# -----------------------------------------------------------------------------

#SBATCH --job-name=firm_tele_scores
#SBATCH --output=hpc/build_firm_teleworkable_scores_%j.out
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=sxr203@nyu.edu
#SBATCH --time=24:00:00
#SBATCH --mem=64G
#SBATCH --cpus-per-task=4

set -euo pipefail

# Move to the repository root (directory above this `hpc` folder)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The .do file uses relative paths assuming it is called from `src/`.
cd "$ROOT_DIR/src"

# Load the required Stata module (adjust version to match your cluster)
module purge
module load stata/17.0

# Run the Stata script in batch mode
stata -b do build_firm_teleworkable_scores.do
