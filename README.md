# wxvx4gw

**wxvx for Global Workflow**

This repository provides scripts to install and configure [`wxvx`](https://github.com/NOAA-GSL/wxvx) for use in Global Workflow on the NOAA RDHPCS platforms.

The installation script downloads and installs Miniforge locally, creates a dedicated Conda environment for `wxvx`, and keeps the environment and package cache under the project directory.

## 1. Features

- Local Miniforge installation without requiring an HPC-provided Conda module.
- Dedicated Conda environment for `wxvx`.
- Project-local Conda package cache and configuration.
- No requirement to run `conda init`.
- Shell script for activating the environment.
- Support for Linux x86_64 and aarch64 architectures, subject to package availability and system compatibility.

## 2. Installation Directory Structure

Run the installation script from the `sorc` directory.

The resulting directory structure is:

```text
wxvx4gw/
└── sorc/
    ├── build_wxvx.sh
    ├── wxvx.yaml
    ├── activate_wxvx.sh
    ├── condarc
    └── conda/
        ├── bin/
        ├── envs/
        │   └── wxvx/
        ├── pkgs/
        └── cache/
```

The directories serve the following purposes:

| Path | Description |
|---|---|
| `sorc/conda/` | Local Miniforge installation |
| `sorc/conda/envs/wxvx/` | Dedicated `wxvx` environment |
| `sorc/conda/pkgs/` | Conda package cache |
| `sorc/conda/cache/` | Application cache |
| `sorc/condarc` | Project-local Conda configuration |
| `sorc/activate_wxvx.sh` | Environment activation script |

All paths are relative to the directory where the installation script is executed.

## 3. Build and Installation

### Step 1. Clone the repository

- SSH
```bash
git clone git@github.com:chan-hoo/wxvx4gw.git
```

- HTTPS
```bash
git clone https://github.com/chan-hoo/wxvx4gw.git
```

### Step 2. Run the installation script

```bash
cd wxvx4gw/sorc
./build_wxvx.sh
```

The script performs the following operations:

1. Determines the system architecture.
2. Downloads the specified Miniforge installer if a local installation does not already exist.
3. Installs Miniforge under `sorc/conda/`.
4. Configures the Conda environment directory and package cache.
5. Creates `wxvx` environment from YAML.
6. Verifies the installation.

The installation requires network access to the Miniforge release and Conda package repositories.

**Note:** The first installation may take some time because Miniforge and its dependencies must be downloaded.

## 4. Activate the wxvx Environment

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

