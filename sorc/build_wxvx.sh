#!/usr/bin/env bash

set -euo pipefail

# ==============================================================
# Define installation directories
# ==============================================================

INSTALL_ROOT="$(pwd -P)"
INSTALLDIR="$INSTALL_ROOT/conda"

export CONDA_PKGS_DIRS="$INSTALLDIR/pkgs"
export CONDA_ENVS_PATH="$INSTALLDIR/envs"
export XDG_CACHE_HOME="$INSTALLDIR/cache"

echo "Installation root: $INSTALL_ROOT"
echo "Miniforge:         $INSTALLDIR"
echo "Environment:       $CONDA_ENVS_PATH/wxvx"
echo "Package cache:     $CONDA_PKGS_DIRS"

# ==============================================================
# Detect architecture
# ==============================================================

case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)
        ARCH="x86_64"
        ;;
    Linux-aarch64)
        ARCH="aarch64"
        ;;
    *)
        echo "Error: Unsupported operating system or architecture:"
        echo "       $(uname -s)-$(uname -m)"
        exit 1
        ;;
esac
echo "Architecture:      $ARCH"

# ==============================================================
# Install Miniforge locally
# ==============================================================

MINIFORGE_VERSION="26.1.1-3"
INSTALLER="Miniforge3-${MINIFORGE_VERSION}-Linux-${ARCH}.sh"

INSTALLER_URL="https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VERSION}/${INSTALLER}"

if [[ -x "$INSTALLDIR/bin/conda" ]]; then
    echo "Found existing Miniforge installation: $INSTALLDIR"
else
    if [[ -e "$INSTALLDIR" ]]; then
        echo "Error: $INSTALLDIR exists but is not a valid Miniforge installation."
        echo "Please inspect the directory before proceeding."
        exit 1
    fi

    mkdir -p "$INSTALL_ROOT"

    echo "Downloading Miniforge ${MINIFORGE_VERSION}..."

    if command -v wget >/dev/null 2>&1; then
        wget -O "$INSTALL_ROOT/$INSTALLER" "$INSTALLER_URL"
    elif command -v curl >/dev/null 2>&1; then
        curl -fL "$INSTALLER_URL" -o "$INSTALL_ROOT/$INSTALLER"
    else
        echo "Error: Neither wget nor curl is available."
        exit 1
    fi

    echo "Installing Miniforge into $INSTALLDIR..."

    bash "$INSTALL_ROOT/$INSTALLER" -bfp "$INSTALLDIR"

    rm -f "$INSTALL_ROOT/$INSTALLER"
fi

# ==============================================================
# Configure local Conda directories
# ==============================================================

mkdir -p "$CONDA_PKGS_DIRS"
mkdir -p "$CONDA_ENVS_PATH"
mkdir -p "$XDG_CACHE_HOME"

# Use a project-local Conda configuration.
export CONDARC="$INSTALL_ROOT/condarc"

cat > "$CONDARC" <<EOF
channels:
  - conda-forge

envs_dirs:
  - $CONDA_ENVS_PATH

pkgs_dirs:
  - $CONDA_PKGS_DIRS

register_envs: false
EOF

# ==============================================================
# Initialize Conda without conda init
# ==============================================================

source "$INSTALLDIR/etc/profile.d/conda.sh"

# Verify configuration before installing packages.
echo
echo "Conda version:"
conda --version

echo
echo "Effective Conda configuration:"
conda info

# ==============================================================
# Create the wxvx environment
# ==============================================================

WXVX_ENV="$CONDA_ENVS_PATH/wxvx"

if [[ -x "$WXVX_ENV/bin/wxvx" ]]; then
    echo "Found existing wxvx environment: $WXVX_ENV"
else
    echo "Creating wxvx environment..."

    conda create -y \
        --prefix "$WXVX_ENV" \
        --override-channels \
        -c oar-gsl \
        -c ufs-community \
        -c conda-forge \
        wxvx
fi

# ==============================================================
# Verify installation
# ==============================================================

echo
echo "Verifying wxvx installation..."

conda run --prefix "$WXVX_ENV" wxvx --version

echo
echo "Installation completed successfully."
echo "Miniforge:         $INSTALLDIR"
echo "Environment:       $WXVX_ENV"
echo "Package cache:     $CONDA_PKGS_DIRS"
echo "Conda config:      $CONDARC"

# ============================================================
# Create activation script
# ============================================================

cat > "$INSTALL_ROOT/activate_wxvx.sh" <<EOF
#!/usr/bin/env bash

# Activate the locally installed wxvx environment.
# Source this script; do not execute it.

_CONDA_ROOT="$INSTALLDIR"
_WXVX_ENV="\$_CONDA_ROOT/envs/wxvx"

if [[ ! -f "\$_CONDA_ROOT/etc/profile.d/conda.sh" ]]; then
    echo "Error: Local Miniforge installation not found: \$_CONDA_ROOT" >&2
    return 1 2>/dev/null || exit 1
fi

if [[ ! -d "\$_WXVX_ENV" ]]; then
    echo "Error: wxvx environment not found: \$_WXVX_ENV" >&2
    return 1 2>/dev/null || exit 1
fi

source "\$_CONDA_ROOT/etc/profile.d/conda.sh"
conda activate "\$_WXVX_ENV"
conda list | grep -E 'wxvx|met2go|uwtools'
which wxvx
wxvx --help
EOF

chmod +x "$INSTALL_ROOT/activate_wxvx.sh"
echo "Created activation script:   $INSTALL_ROOT/activate_wxvx.sh"
