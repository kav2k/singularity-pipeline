#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pipeline, a wrapper around Singularity to build, run and test scientific pipelines."""

import os
import string
import subprocess
import yaml
import re

from .eprint import EPrint
from .constants import SUPPORTED_VERSION, FORMAT_VERSION


class Pipeline():
    """Main Pipeline class."""

    def __init__(self, source, imagefile=None, eprint_instance=None, dry_run=False):
        """Initialize a pipeline instance.

        Requires a YAML-formatted description (string or file handle)."""
        if not eprint_instance:
            eprint_instance = EPrint()
        self.eprint = eprint_instance
        self.dry_run = dry_run

        self.load_description(source)

        if imagefile:
            self.imagefile = make_safe_filename(imagefile)
        else:
            self.imagefile = make_safe_filename(
                "{}-{}.img".format(self.description.get("name"), self.description.get("version"))
            )

        self.eprint.normal("Target image file: {}\n".format(self.imagefile))

    def load_description(self, source):
        """Load pipeline description from a file or a YAML string."""
        self.eprint.bold("# Loading pipeline description...")
        try:
            self.description = yaml.safe_load(source)
            self.validate_description(self.description)

            bind_specs = self.description.get("binds", [])
            self.binds = [
                (spec.split(":")[0], spec.split(":")[1]) for spec in bind_specs
            ]

            self.eprint.normal("Pipeline '{name}' version {version} loaded.".format(
                name=self.description.get("name"),
                version=self.description.get("version")
            ))
        except yaml.YAMLError as e:
            self.eprint.red("\nError parsing pipeline description: {0}".format(e))
            raise LoadError()
        except FormatError as e:
            self.eprint.red("\nPipeline description error: {0}".format(e))
            raise LoadError()

    def validate_description(self, description):
        """Validate dict-parsed pipeline description."""
        format_version = description.get("format_version")
        if not format_version:
            format_version = 1  # Assuming format version 1 if not specified
        
        if format_version != FORMAT_VERSION:
            raise FormatError("Incompatible format version {}; expected {}".format(format_version, FORMAT_VERSION))

        for attribute in ["name", "version", "build", "run", "test"]:
            if not description.get(attribute):
                raise FormatError("Missing attribute '{}'".format(attribute))

    def build(self, force=False):
        """Build pipeline according to description."""
        self.eprint.bold("# Building pipeline...\n")

        if not self.dry_run:
            if os.path.exists(self.imagefile):
                if force:
                    self.eprint.normal("Deleting existing image file {}.".format(self.imagefile))
                    os.remove(self.imagefile)
                else:
                    self.eprint.yellow("Image file {} already exists! Skipping build.".format(self.imagefile))
                    return

        credentials = self.description.get("build").get("credentials")
        if credentials:
            if credentials.get("username"):
                os.environ["SINGULARITY_DOCKER_USERNAME"] = credentials.get("username")
            if credentials.get("password"):
                os.environ["SINGULARITY_DOCKER_PASSWORD"] = credentials.get("password")

        build_type = self.description.get("build").get("type")

        source = self.description.get("build").get("source")
        options = self.description.get("build").get("options", "")
        size = self.description.get("build").get("size")
        if size:
            size = "--size {}".format(size)

        if build_type == "pull":
            build_calls = ["singularity pull {size} {options} --name {image} {source}"]
        elif build_type == "bootstrap":
            build_calls = ["singularity create -F {size} {image}", "sudo singularity bootstrap {options} {image} {source}"]
        elif build_type == "build":
            build_calls = ["sudo singularity build {options} {image} {source}"]
        elif build_type == "docker2singularity":
            build_calls = [
                "sudo docker build -t {docker_name} -f {source} .",
                ("sudo docker run -v /var/run/docker.sock:/var/run/docker.sock -v $(pwd):/output "
                    "--privileged -t --rm singularityware/docker2singularity {docker_name}"),
                "mv {docker_name}-*.img {image}"
            ]
        elif build_type == "custom":
            build_calls = self.description.get("build").get("commands")
        else:
            raise NotImplementedError("Build type {} not implemented.".format(build_type))

        ret_code, _ = self.__run_batch(build_calls, {
            "source": source,
            "options": options,
            "size": size,
            "docker_name": make_safe_filename(make_safe_filename(self.description.get("name"), lower=True))
        })
        if ret_code:
            raise RuntimeError("Singularity build failed (exit code {})".format(ret_code))

        if self.dry_run:
            self.eprint.bold("# Dry-run of building image {} complete.\n".format(self.imagefile))
        else:
            self.eprint.bold("# Successfully built image {}.\n".format(self.imagefile))

    def run(self):
        """Run built pipeline according to description."""
        self.eprint.bold("# Running pipeline...\n")

        if not self.dry_run:
            if not os.path.isfile(self.imagefile):
                raise RuntimeError("Image {} does not exist".format(self.imagefile))

            for spec in self.binds:
                if not os.path.isdir(spec[0]):
                    raise RuntimeError("Bind source {} does not exist".format(spec[0]))

        commands = self.description.get("run").get("commands")

        ret_code, step = self.__run_batch(commands)
        if ret_code:
            raise RuntimeError("Singularity run failed (step {}, exit code {})".format(step + 1, ret_code))

        if self.dry_run:
            self.eprint.bold("# Dry-run of running image {} complete.\n".format(self.imagefile))
        else:
            self.eprint.bold("# Successfully ran {}.\n".format(self.description.get("name")))

    def test(self, force=False, skip_run=False):
        """Run defined tests against the pipeline according to description."""
        self.eprint.bold("# Testing pipeline...\n")

        test_files = self.description.get("test").get("test_files")

        if not self.__check_files_exist(test_files) or force:
            self.eprint.bold("(Re)creating test files...")

            test_prepare = self.description.get("test").get("prepare_commands")
            ret_code, step = self.__run_batch(test_prepare)

            if not self.dry_run and not self.__check_files_exist(test_files):
                raise RuntimeError("Test files not generated by prepare commands")
        else:
            self.eprint.yellow("Test files already exist and will be reused.\n")

        if skip_run:
            self.eprint.bold("# Skipping run stage.\n")
        else:
            self.run()

        self.eprint.bold("# Running validation stage...\n")

        test_validate = self.description.get("test").get("validate_commands")
        ret_code, step = self.__run_batch(test_validate)
        if ret_code:
            raise RuntimeError("Singularity test validation failed (step {}, exit code {})".format(step + 1, ret_code))

        if self.dry_run:
            self.eprint.bold("# Dry-run of validating image {} complete.\n".format(self.imagefile))
        else:
            self.eprint.bold("# Pipeline {} validated successfully!\n".format(self.imagefile))

    def __run_batch(self, commands, substitutions={}):
        if not isinstance(commands, list):
            raise FormatError("Run commands must be a list")

        subs = self.substitution_dictionary(**substitutions)
        if self.description.get("substitutions"):
            subs.update(self.description.get("substitutions"))

        action = "Executing"
        if self.dry_run:
            action = "Displaying"
            self.eprint.yellow("DRY RUN: Commands only displayed, not run.\n")

        for step, command in enumerate(commands):
            command = command.format(**subs)
            self.eprint.bold("{action} step {step}:\n  {command}\n".format(
                action=action,
                step=step + 1,
                command=command
            ))
            if not self.dry_run:
                ret_code = subprocess.call(command, shell=True)
                if ret_code:
                    return ret_code, step + 1  # Failure code + step number

        return 0, 0  # No failures

    def check(self):
        """Validate the pipeline description file."""
        self.eprint.bold("# Checking pipeline file!\n")

        raise NotImplementedError("Checking still in the works.")

    def __bind_flags(self):
        """Return all bind flags for singularity as a string.

        Will contain trailing space if non-empty."""
        bind_flags = ""
        if len(self.binds):
            for spec in self.binds:
                bind_flags += "-B {source}:{dest} ".format(source=spec[0], dest=spec[1])

        return bind_flags

    def check_binds_exist(self):
        """Check that all source folders in binds exist."""
        binds = list(self.description.get("binds"))

        if binds is not None:
            return self.__check_files_exist(
                [bind.split(":")[0] for bind in binds]
            )

    def __check_files_exist(self, file_list):
        """Check that a list of files/folders exists."""
        if not file_list:  # None
            return True
        if not isinstance(file_list, list):
            raise FormatError("List of files to check is not a list")
        for file in file_list:
            if not os.path.exists(file):
                return False
        return True

    def substitution_dictionary(self, **extra):
        """Compile a dictionary of substitutions to be passed to .format() for shell commands.

        extra - Addidtional substitutions to include.
        """
        subs = extra.copy()

        if self.description.get("substitutions"):
            subs.update(self.description.get("substitutions"))

        subs["image"] = self.imagefile

        subs["binds"] = self.__bind_flags()

        subs["exec"] = "singularity exec {binds}{image}".format(**subs)
        subs["run"] = "singularity run {binds}{image}".format(**subs)

        return subs


def check_singularity():
    """Check that Singularity is installed and is of >= SUPPORTED_VERSION version"""
    def to_int(s):
        """Converts string to int, or 0 if not convertible"""
        try:
            return int(s)
        except ValueError:
            return 0

    def compare_version(test, target):
        """Compare that test version (loose semver format) is >= target version."""
        # Can't use e.g. semver as Singularity is not following SemVer spec
        test_array = list(map(to_int, re.split("[\.-]", test)))
        target_array = list(map(to_int, re.split("[\.-]", target)))

        return test_array >= target_array

    try:
        version = subprocess.check_output(["singularity", "--version"]).strip().decode("utf-8")
        if not compare_version(version, SUPPORTED_VERSION):
            raise ToolError("Singularity version {} is less than minimum supported ({})".format(version, SUPPORTED_VERSION))
        return version
    except subprocess.CalledProcessError as e:
        raise ToolError(e.output)
    except OSError as e:
        raise ToolError(e.strerror)
    except ValueError as e:
        raise ToolError("Unexpected format for Singularity version string ({})".format(version))


def make_safe_filename(name, lower=False):
    """Convert filename-unsafe characters to '_'.

    Parameter:
    lower (bool) - whether to lowercase the filename."""
    safe = string.ascii_letters + string.digits + "_-./"
    if lower:
        name = name.lower()
    return "".join(map(lambda c: c if (c in safe) else '_', name))


class LoadError(RuntimeError):
    """Exception class for failed file load or parse."""

    pass


class FormatError(ValueError):
    """Exception class for non-conforming file format."""

    def __init__(self, error):
        """Store specific error description."""
        self.error = error

    def __str__(self):
        """Print out specific error description as string representation."""
        return self.error


class ToolError(RuntimeError):
    """Exception class for unexpected response from external tools."""

    def __init__(self, error):
        """Store specific error description."""
        self.error = error

    def __str__(self):
        """Print out specific error description as string representation."""
        return self.error
