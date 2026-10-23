# wxvx4ufs

**Weather Verification (wxvx) for Unified Forecat System (UFS) including Global Workflow, EAGLE, and RRFS**

This repository provides scripts to install and configure [`wxvx`](https://github.com/NOAA-GSL/wxvx) for use with UFS applications, including Global workflow and RRFS workflow, on NOAA RDHPCS platforms.

## 1. Build and Installation

### Step 1. Clone the repository

Choose one of the following methods to clone the repository.

- SSH (if you have configured an SSH key for GitHub):
```bash
git clone git@github.com:chan-hoo/wxvx4ufs.git
```

- HTTPS:
```bash
git clone https://github.com/chan-hoo/wxvx4ufs.git
```

### Step 2. Run the installation script

```bash
cd wxvx4ufs/sorc
./build_wxvx.sh
```

The script performs the following operations:

1. Determines the system architecture.
2. Downloads the specified Miniforge installer if a local installation does not already exist.
3. Installs Miniforge under `sorc/conda/`.
4. Configures the Conda environment directory and package cache.
5. Creates `wxvx` environment from YAML.

The installation requires network access to the Miniforge release and Conda package repositories.

## 2. Activate the wxvx Environment

After installation, activate the environment by sourcing the activation script:

```bash
source activate_wxvx.sh
```

Verify the active environment:

```bash
echo "$CONDA_PREFIX"
which python
which wxvx
```

The Python interpreter and `wxvx` executable should point to the local environment under:

```text
sorc/conda/envs/wxvx/
```

### Deactivate the Environment

If the environment is active and Conda is initialized in your current shell:

```bash
conda deactivate
```

## 3. Configuration

The configuration YAML files and set-up script are located in the `parm` directory:

```bash
cd wxvx4ufs/parm
```

The main configuration files are:
- `config_base.yaml`: Define the basic configuration parameters
- `config_platform.yaml`: Define the platform-specific configuration parameters

Before proceeding, review the parameters `account` ,`exp_case_name`, and `platform`.

```bash
vim config_base.yaml
```
You can check the list of tasks `task_list` selected from the available tasks under the `tasks` group.

Run the set-up script to generate the experimental case configuration and supporting directories:

```bash
./setup.py
```

By default, the script generates the `exp_cases` and `PTMP` directories under the `parm` directory.

## 4. Job Submission

Until `ecFlow` integration is available, jobs must be submitted manually.

Navigate to the job cards directory for your experimental case:

```bash
cd exp_cases/[app.exp_case_name]/job_cards
```

Submit the desired task:

```bash
sbatch jwxvx_[task_name]
```

## 5. Results and Log Files

After the job completes, check the following directories for output files and execution logs:
- `com_dir`: symlink to the directory containing the result files
- `log_dir`: symlink to the directory containing the log files
- `tmp_dir`: symlink to the directory containing the working directories

