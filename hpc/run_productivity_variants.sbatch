#!/bin/bash
#------------------------------------------------------------------------------
#  Slurm submission script – run all productivity-related specifications
#  (including mechanisms) for every user-panel variant.
#------------------------------------------------------------------------------

# ===== Slurm options =========================================================
# Job name
#SBATCH --job-name=prod_variants

# E-mail notifications
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=sxr203@nyu.edu

# Request a generous wall-clock limit (48 h) and plenty of memory (128 GB).
# Adjust these to fit the cluster’s policy if needed.
#SBATCH --time=48:00:00
#SBATCH --mem=128G

# Number of CPU cores (Stata/MP uses multi-threading; adjust if desired)
#SBATCH --cpus-per-task=4

#=============================================================================

# Fail on any error
set -euo pipefail

# Load required modules -------------------------------------------------------
# (Uncomment / modify according to the HPC environment)
# module purge
# module load stata/18

# Activate project environment if using a virtualenv / conda (optional) -----
# source "$HOME/venvs/your_env/bin/activate"

# Navigate to project root ----------------------------------------------------
cd "$SLURM_SUBMIT_DIR"   # assumes script is submitted from project root

# Path to Stata executable (adjust as needed) --------------------------------
STATA_BIN="stata-mp"      # or /path/to/stata-mp

# Run the driver script -------------------------------------------------------
"${STATA_BIN}" -b do spec/run_productivity_variants.do

echo "Run completed on $(date)"