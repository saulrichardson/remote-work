#!/bin/bash
# Build *all* user-level panel variants (unbalanced, balanced, precovid, etc.)
# in a single Stata run.
# -----------------------------------------------------------------------------
# Slurm submission script – submit with:
#   sbatch hpc/build_all_user_panels.sbatch
# -----------------------------------------------------------------------------

#SBATCH --job-name=build_user_panels
#SBATCH --output=hpc/build_all_user_panels_%j.out
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=sxr203@nyu.edu
#SBATCH --time=48:00:00
#SBATCH --mem=128G
#SBATCH --cpus-per-task=4

set -euo pipefail

# Move to the repository root (directory above this `hpc` folder)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Stata scripts inside `src/` expect to be launched *from* that folder, so
# change into it before invoking Stata.
cd "$ROOT_DIR/src"

# Load the required Stata module (version may need adjusting to your cluster)
module purge
module load stata/17.0

# Run the Stata build script in batch mode
stata -b do build_all_user_panels.do
