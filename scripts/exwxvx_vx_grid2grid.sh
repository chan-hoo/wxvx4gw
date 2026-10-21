#!/usr/bin/env bash

set -xue

ulimit -s unlimited; ulimit -a;

config_fn="config_vx_grid2grid.yaml"
config_path="${exp_case_path}/configs/${config_fn}"

export pgm="wxvx"

. prep_step
time ${pgm} -c ${config_path} -t plots -f
export err=$?; err_chk
if [[ $err != 0 ]]; then
  err_exit "wxvx: vx_grid2grid failed"
fi

