date
export PS4='+ $SECONDS + '
set -xue

# Variables needed for communication with ecFlow
export ECF_HOST=%ECF_HOST%
export ECF_JOB=%ECF_JOB%
export ECF_JOBOUT=%ECF_JOBOUT%
export ECF_NAME=%ECF_NAME%
export ECF_PASS=%ECF_PASS%
export ECF_PORT=%ECF_PORT%
export ECF_RID=$$
export ECF_TRYNO=%ECF_TRYNO%

# Tell ecFlow we have started
ecflow_client --init=$$

# Define error handler
ERROR() {
  set +ex
  if [ "$1" -eq 0 ]; then
     msg="Killed by signal (likely via qdel)"
  else
     msg="Killed by signal $1"
  fi
  ecflow_client --abort="$msg"
  echo $msg
  trap $1; exit $1
}
# Trap all error and exit signals
trap 'ERROR $?' ERR EXIT
