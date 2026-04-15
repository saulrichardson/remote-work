#!/bin/bash
#SBATCH --job-name=precovid_composition
#SBATCH --output=composition_%j.out
#SBATCH --error=composition_%j.err
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=4
#SBATCH --partition=normal

# Load required modules (adjust based on your HPC)
module load python/3.9
module load pandas/1.3.0

# Set paths (UPDATE THESE FOR YOUR HPC)
BASE_DIR="/path/to/your/project"
INPUT_FILE="${BASE_DIR}/data/raw/Scoop_workers_positions.csv"
OUTPUT_FILE="${BASE_DIR}/results/raw/composition_precovid_2019.csv"
SCRIPT="${BASE_DIR}/py/create_precovid_composition_hpc.py"

# Create output directory if it doesn't exist
mkdir -p $(dirname $OUTPUT_FILE)

# Run the script
echo "Starting composition analysis at $(date)"
echo "Input: $INPUT_FILE"
echo "Output: $OUTPUT_FILE"

# Test run with 1M rows first (optional - comment out for full run)
# python $SCRIPT --input "$INPUT_FILE" --output "${OUTPUT_FILE%.csv}_test.csv" --test 1000000

# Full run
python $SCRIPT --input "$INPUT_FILE" --output "$OUTPUT_FILE"

echo "Completed at $(date)"

# Check if output was created
if [ -f "$OUTPUT_FILE" ]; then
    echo "Success! Output file created:"
    echo "Rows: $(wc -l < $OUTPUT_FILE)"
    head -5 "$OUTPUT_FILE"
else
    echo "Error: Output file not created"
    exit 1
fi