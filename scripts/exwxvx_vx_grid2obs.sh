#!/usr/bin/env bash

set -xue

ulimit -s unlimited; ulimit -a;

# Load the shared YAML utility.
source "${USHwxvx}/yaml_utils.sh"
config_common="${exp_case_path}/configs/config_common.yaml"

# Read common configuration values.
external_data=$(read_yaml "${config_common}" "external_data_vx_grid2obs")
platform=$(read_yaml "${config_common}" "platform")
run_type=$(read_yaml "${config_common}" "run_type")
workflow_type=$(read_yaml "${config_common}" "workflow_type")

# Copy input files to temporary working directory.
if [[ "${run_type}" == "ctest" ]]; then
  cp -rp "${FIXwxvx}/data_${platform}/ctest/${workflow_type}/post_prewxvx" ${DATA}/.
  if [[ "${external_data,,}" == "false" ]]; then
    cp -rp "${FIXwxvx}/data_${platform}/ctest/${workflow_type}/obs" ${DATA}/.
  fi
fi

# Update configuration file with temporary working directory.
config_fn="config_vx_grid2obs.yaml"
cp -p "${exp_case_path}/configs/${config_fn}" "${DATA}/."
sed -i "s|{{ DATA }}|${DATA}|g" ${config_fn}

# Run wxvx.
export pgm="wxvx"

. prep_step
time ${pgm} -c ${config_fn} -t plots -f
export err=$?; err_chk
if [[ $err != 0 ]]; then
  err_exit "wxvx: vx_grid2obs failed"
fi

# Copy result files/directories to COMOUT
cp -rp ${DATA}/plots ${COMOUT}/grid2obs_plots
cp -rp ${DATA}/stats ${COMOUT}/grid2obs_stats
