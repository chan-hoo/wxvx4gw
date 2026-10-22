#!/usr/bin/env bash

set -xue

ulimit -s unlimited; ulimit -a;

# Load the shared YAML utility.
source "${USHwxvx}/yaml_utils.sh"
config_common="${exp_case_path}/configs/config_common.yaml"

# Read common configuration values.
platform=$(read_yaml "${config_common}" "platform")
run_type=$(read_yaml "${config_common}" "run_type")
workflow_type=$(read_yaml "${config_common}" "workflow_type")

# Copy input files to temporary working directory.
if [[ "${run_type}" == "ctest" ]]; then
  mkdir -p ${DATA}/grids
  cp -rp "${FIXwxvx}/data_${platform}/ctest/${workflow_type}/grids/truth" ${DATA}/grids/.
  cp -rp "${FIXwxvx}/data_${platform}/ctest/${workflow_type}/post_prewxvx" ${DATA}/.
fi

# Update configuration file with temporary working directory.
config_fn="config_vx_grid2grid.yaml"
cp -p "${exp_case_path}/configs/${config_fn}" "${DATA}/."
sed -i "s|{{ DATA }}|${DATA}|g" ${config_fn}

# Run wxvx.
export pgm="wxvx"

. prep_step
time ${pgm} -c ${config_fn} -t plots -f
export err=$?; err_chk
if [[ $err != 0 ]]; then
  err_exit "wxvx: vx_grid2grid failed"
fi

# Copy result files/directories to COMOUT
cp -rp ${DATA}/plots ${COMOUT}/grid2grid_plots
cp -rp ${DATA}/stats ${COMOUT}/grid2grid_stats
