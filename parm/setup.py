#!/usr/bin/env python3
"""
Generate task-specific WXVX configuration files.

Read config_base.yaml, combine the parameter groups specified for
each task, and write flattened config_[task].yaml files.

Expected input structure:

    parm/
    ├── config_base.yaml
    └── setup.py

Expected output structure:

    ../exp_cases/<exp_case_name>/config/
        ├── config_<task1>.yaml
        └── config_<task2>.yaml

Usage:
    python setup.py
    python setup.py --config config_base.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Configuration generator
# ---------------------------------------------------------------------

class ConfigGenerator:
    """Generate flattened YAML configuration files for WXVX tasks."""

    def __init__(
        self,
        config_file: str | Path = "config_base.yaml",
    ) -> None:
        """
        Initialize the configuration generator.

        Parameters
        ----------
        config_file : str or pathlib.Path
            Path to config_base.yaml. Relative paths are resolved
            relative to the directory containing this script.
        """
        self.script_dir = Path(__file__).resolve().parent

        config_path = Path(config_file).expanduser()

        if not config_path.is_absolute():
            config_path = self.script_dir / config_path

        self.config_file = config_path.resolve()

        # The wxvx4gw repository root is the parent of parm/.
        self.repo_dir = self.script_dir.parent

        # Experiment cases directory under the repository root.
        self.exp_cases_dir = self.repo_dir / "exp_cases"
        
        # Default OPS directory under the repository root.
        self.default_ops_path = self.repo_dir / "PTMP"

        self.config: dict[str, Any] = {}

    # -----------------------------------------------------------------
    # Read the base configuration
    # -----------------------------------------------------------------

    def load_config(self) -> dict[str, Any]:
        """Load and validate config_base.yaml."""
        if not self.config_file.is_file():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}"
            )

        logger.info("Reading configuration: %s", self.config_file)

        with self.config_file.open("r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream)

        if not isinstance(config, dict):
            raise ValueError(
                "config_base.yaml must contain a YAML mapping at "
                "the top level."
            )

        if "tasks" not in config:
            raise ValueError(
                "Missing required 'tasks' group in config_base.yaml."
            )

        if not isinstance(config["tasks"], dict):
            raise ValueError(
                "The 'tasks' group must be a mapping of task names "
                "to lists of parameter group names."
            )

        self.config = config

        logger.info(
            "Found %d task(s).",
            len(self.config["tasks"]),
        )

        return self.config

    # -----------------------------------------------------------------
    # Resolve configuration parms when set to AUTO
    # -----------------------------------------------------------------

    def resolve_auto_paths(self) -> None:
        """Resolve configuration parameters that use the AUTO keyword."""
    
        nco_vars = self.config.get("nco_vars", {})
    
        if not isinstance(nco_vars, dict):
            raise ValueError(
                "The 'nco_vars' group must be a YAML mapping."
            )
    
        ops_path = nco_vars.get("OPS_PATH")
    
        if isinstance(ops_path, str) and ops_path.strip().upper() == "AUTO":
            nco_vars["OPS_PATH"] = str(self.default_ops_path)
    
            logger.info(
                "Resolved OPS_PATH=AUTO to %s",
                nco_vars["OPS_PATH"],
            )

    # -----------------------------------------------------------------
    # Determine the output directory
    # -----------------------------------------------------------------

    def get_output_dir(self) -> Path:
        """
        Determine the output directory using app.exp_case_name.

        Expected path:
            wxvx4gw/../exp_cases/<exp_case_name>/config/
        """
        if "app" not in self.config:
            raise ValueError(
                "Missing required 'app' parameter group."
            )

        app_config = self.config["app"]

        if not isinstance(app_config, dict):
            raise ValueError(
                "The 'app' group must be a mapping."
            )

        exp_case_name = app_config.get("exp_case_name")

        if not isinstance(exp_case_name, str) or not exp_case_name.strip():
            raise ValueError(
                "'exp_case_name' must be a non-empty string "
                "in the 'app' group."
            )

        exp_case_name = exp_case_name.strip()

        # Prevent absolute paths and directory traversal.
        case_name_path = Path(exp_case_name)

        if (
            case_name_path.is_absolute()
            or len(case_name_path.parts) != 1
            or exp_case_name in {".", ".."}
        ):
            raise ValueError(
                f"Invalid exp_case_name: {exp_case_name!r}"
            )

        output_dir = (
            self.exp_cases_dir
            / exp_case_name
            / "configs"
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Output directory: %s", output_dir)

        return output_dir

    # -----------------------------------------------------------------
    # Build a flattened configuration for one task
    # -----------------------------------------------------------------

    def build_task_config(
        self,
        task_name: str,
        group_names: list[str],
    ) -> dict[str, Any]:
        """
        Combine the parameter groups specified for a task.

        Group names are not included in the resulting dictionary.

        If a parameter occurs in multiple groups, the value from
        the last group takes precedence.
        """
        if not isinstance(group_names, list):
            raise ValueError(
                f"Task '{task_name}' must specify a list of "
                "parameter group names."
            )

        task_config: dict[str, Any] = {}

        for group_name in group_names:
            if not isinstance(group_name, str):
                raise ValueError(
                    f"Task '{task_name}' contains an invalid "
                    f"group name: {group_name!r}"
                )

            if group_name == "tasks":
                raise ValueError(
                    f"Task '{task_name}' must not include the "
                    "'tasks' group as a parameter group."
                )

            if group_name not in self.config:
                raise ValueError(
                    f"Task '{task_name}' references the undefined "
                    f"parameter group '{group_name}'."
                )

            group_config = self.config[group_name]

            if not isinstance(group_config, dict):
                raise ValueError(
                    f"Parameter group '{group_name}' must be "
                    "a YAML mapping."
                )

            logger.debug(
                "Task '%s': adding group '%s'.",
                task_name,
                group_name,
            )

            # Flatten the group into the task configuration.
            # Later groups override earlier groups on key conflicts.
            task_config.update(group_config)

        logger.info(
            "Task '%s': combined %d parameter group(s), "
            "resulting in %d parameter(s).",
            task_name,
            len(group_names),
            len(task_config),
        )

        return task_config

    # -----------------------------------------------------------------
    # Write a task configuration
    # -----------------------------------------------------------------

    @staticmethod
    def write_task_config(
        task_name: str,
        task_config: dict[str, Any],
        output_dir: Path,
    ) -> Path:
        """Write one flattened task configuration to a YAML file."""
        output_file = output_dir / f"config_{task_name}.yaml"

        with output_file.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(
                task_config,
                stream,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=float("inf"),
            )

        logger.info("Generated: %s", output_file)

        return output_file

    # -----------------------------------------------------------------
    # Generate configurations for all tasks
    # -----------------------------------------------------------------

    def generate(self) -> list[Path]:
        """Generate a configuration file for every configured task."""
        self.load_config()

        # Resolve AUTO parameters before building task configurations.
        self.resolve_auto_paths()

        output_dir = self.get_output_dir()

        generated_files: list[Path] = []

        tasks = self.config["tasks"]

        for task_name, group_names in tasks.items():
            if not isinstance(task_name, str) or not task_name.strip():
                raise ValueError(
                    f"Invalid task name: {task_name!r}"
                )

            if (
                Path(task_name).name != task_name
                or task_name in {".", ".."}
            ):
                raise ValueError(
                    f"Invalid task name: {task_name!r}"
                )

            task_config = self.build_task_config(
                task_name=task_name,
                group_names=group_names,
            )

            output_file = self.write_task_config(
                task_name=task_name,
                task_config=task_config,
                output_dir=output_dir,
            )

            generated_files.append(output_file)

        logger.info(
            "Successfully generated %d configuration file(s).",
            len(generated_files),
        )

        return generated_files


# ---------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------

def main() -> int:
    """Parse command-line arguments and generate configurations."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate flattened WXVX task configuration files "
            "from config_base.yaml."
        )
    )

    parser.add_argument(
        "--config",
        default="config_base.yaml",
        help=(
            "Input YAML configuration file. Relative paths are "
            "resolved relative to the parm directory."
        ),
    )

    args = parser.parse_args()

    try:
        generator = ConfigGenerator(config_file=args.config)
        generator.generate()

    except (OSError, ValueError, yaml.YAMLError) as exc:
        logger.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
