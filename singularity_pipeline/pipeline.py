#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pipeline, a wrapper around Singularity to build, run and test scientific pipelines."""

from __future__ import print_function

import argparse
import os
import string
import subprocess
import sys
import yaml


class Pipeline():
    """Main Pipeline class."""

    def __init__(self, source, imagefile=None, print_func=print):
        """Initialize a pipeline instance.

        Requires a YAML-formatted description (string or file handle)."""
        self.print_func = print_func

        self.load_description(source)

        if imagefile:
            self.imagefile = make_safe_filename(imagefile)
        else:
            self.imagefile = make_safe_filename(
                "{}-{}.img".format(self.description.get("name"), self.description.get("version"))
            )

        self.print_func("Target image file: {}".format(self.imagefile))

    def load_description(self, source):
        """Load pipeline description from a file or a YAML string."""
        self.print_func("Loading pipeline description...")
        try:
            self.description = yaml.safe_load(source)
            self.validate_description(self.description)

            bind_specs = self.description.get("binds", [])
            self.binds = [
                (spec.split(":")[0], spec.split(":")[1]) for spec in bind_specs
            ]

            self.print_func("Pipeline '{name}' {version} loaded.".format(
                name=self.description.get("name"),
                version=self.description.get("version")
            ))
        except yaml.YAMLError as e:
            self.print_func("Error parsing pipeline description: {0}".format(e))
            raise LoadError()
        except FormatError as e:
            self.print_func("Pipeline description error: {0}".format(e))
            raise LoadError()

    def validate_description(self, description):
        """Validate dict-parsed pipeline description."""
        for attribute in ["name", "version", "build", "run", "test"]:
            if not self.description.get(attribute):
                raise FormatError("Missing attribute '{}'".format(attribute))

    def build(self, force=False):
        """Build pipeline according to description."""
        self.print_func("\nBuilding pipeline...\n")

        if os.path.exists(self.imagefile):
            if force:
                self.print_func("Deleting existing image file {}.".format(self.imagefile))
                os.remove(self.imagefile)
            else:
                self.print_func("Image file {} already exists! Skipping build.".format(self.imagefile))
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

        self.print_func("\nSuccessfully built image {}.\n".format(self.imagefile))

    def run(self):
        """Run built pipeline according to description."""
        self.print_func("\nRunning pipeline...\n")

        if not os.path.isfile(self.imagefile):
            raise RuntimeError("Image {} does not exist".format(self.imagefile))

        for spec in self.binds:
            if not os.path.isdir(spec[0]):
                raise RuntimeError("Bind source {} does not exist".format(spec[0]))

        commands = self.description.get("run").get("commands")

        ret_code, step = self.__run_batch(commands)
        if ret_code:
            raise RuntimeError("Singularity run failed (step {}, exit code {})".format(step + 1, ret_code))

        self.print_func("Successfully ran {}.\n".format(self.description.get("name")))

    def test(self, force=False, skip_run=False):
        """Run defined tests against the pipeline according to description."""
        self.print_func("\nTesting pipeline...\n")

        test_files = self.description.get("test").get("test_files")

        if not self.__check_files_exist(test_files) or force:
            self.print_func("(Re)creating test files...")

            test_prepare = self.description.get("test").get("prepare_commands")
            ret_code, step = self.__run_batch(test_prepare)

            if not self.__check_files_exist(test_files):
                raise RuntimeError("Test files not generated by prepare commands")
        else:
            self.print_func("Test files already exist and will be reused.\n")

        if skip_run:
            self.print_func("Skipping run stage.\n")
        else:
            self.run()

        self.print_func("Running validation stage...")

        test_validate = self.description.get("test").get("validate_commands")
        ret_code, step = self.__run_batch(test_validate)
        if ret_code:
            raise RuntimeError("Singularity test validation failed (step {}, exit code {})".format(step + 1, ret_code))

        self.print_func("\nPipeline validated successfully!\n")

    def __run_batch(self, commands, substitutions={}):
        if not isinstance(commands, list):
            raise FormatError("Run commands must be a list")

        subs = self.substitution_dictionary(**substitutions)
        if self.description.get("substitutions"):
            subs.update(self.description.get("substitutions"))

        for step, command in enumerate(commands):
            command = command.format(**subs)
            self.print_func("\nExecuting step {}: {}\n".format(step + 1, command))
            ret_code = subprocess.call(command, shell=True)
            if ret_code:
                return ret_code, step + 1  # Failure code + step number

        return 0, 0  # No failures

    def check(self):
        """Validate the pipeline description file."""
        self.print_func("\nChecking pipeline file!\n")

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


def __main():
    """Main method to be called when running directly.

    Expects CLI arguments."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Pipeline, a wrapper around Singularity to build, run and test scientific pipelines."
    )

    parser.add_argument(
        "command",
        help="Command to execute",
        choices=['build', 'run', 'test', 'check']
    )
    parser.add_argument(
        "-p", "--pipeline",
        default="pipeline.yaml",
        help="Pipeline description file (default: '%(default)s')"
    )
    parser.add_argument(
        "-i", "--image",
        help="Singularity image file (default: as defined in pipeline description)"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force rebuilding the image or test data for validation (default: no)"
    )
    parser.add_argument(
        "--no-bind",
        action="store_true",
        help="Omit runtime bind arguments (default: no). Useful in cases when user-supplied path binding is not allowed."
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="For testing, skip the run phase, only validating existing output (default: no)"
    )

    args = parser.parse_args()

    try:
        with open(args.pipeline) as f:
            pipeline = Pipeline(f, imagefile=args.image, print_func=eprint)
    except IOError as e:
        eprint("Cannot open pipeline description {0}: {1}".format(args.file, e.strerror))
        raise LoadError()
    except LoadError:
        eprint("\nUnable to load pipeline description. Aborting.")
        sys.exit(1)

    try:
        if args.command == "build":
            pipeline.build(force=args.force)
        elif args.command == "run":
            pipeline.run()
        elif args.command == "test":
            pipeline.test(force=args.force, skip_run=args.skip_run)
        elif args.command == "check":
            pipeline.check()
        else:
            raise RuntimeError("Unknown command specified")
    except RuntimeError as e:
        eprint("ERROR: " + e.message)
        sys.exit(1)


def eprint(*args, **kwargs):
    """Print to STDERR.

    Follows same format as print."""
    print(*args, file=sys.stderr, **kwargs)


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


if __name__ == "__main__":
    __main()
