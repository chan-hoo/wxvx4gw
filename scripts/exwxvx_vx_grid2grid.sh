#!/usr/bin/env bash

set -xue

ulimit -s unlimited; ulimit -a;

export pgm="wxvx"

. prep_step
time ${pgm} -c wxvx-grid2grid-global.yaml -t plots -f
export err=$?; err_chk
if [[ $err != 0 ]]; then
  err_exit "wxvx: grid2grid failed"
fi

