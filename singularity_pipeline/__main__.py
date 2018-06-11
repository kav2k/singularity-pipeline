from .pipeline import Pipeline, ToolError, LoadError, check_singularity
from .eprint import EPrint
from .templates import template_pipeline, template_version
from . import __version__

import colorama
import sys
import argparse


def __main():
    """Main method to be called when running directly.

    Expects CLI arguments."""
    colorama.init()
    eprint = EPrint()

    args = parse_args(sys.argv[1:])

    if args.command == "template":
        print(template_pipeline)
        exit(0)

    try:
        check_singularity()
    except ToolError as e:
        eprint.red("Error when running `singularity`: {}".format(e.error))
        eprint.yellow("Check your Singularity installation!")
        sys.exit(1)

    try:
        try:
            with open(args.pipeline) as f:
                pipeline = Pipeline(f, imagefile=args.image, eprint_instance=eprint, dry_run=args.dry_run)
        except IOError as e:
            eprint.red("\nCannot open pipeline description {0}: {1}".format(args.pipeline, e.strerror))
            raise LoadError()
    except LoadError:
        eprint.yellow("\nUnable to load pipeline description. Aborting.")
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
        eprint.red("ERROR: {}".format(e))
        sys.exit(1)


def parse_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Pipeline, a wrapper around Singularity to build, run and test scientific pipelines."
    )

    try:
        singularity_version = check_singularity()
    except ToolError:
        singularity_version = "Unknown/unsupported"

    parser.add_argument('-v', '--version', action='version', version=template_version.format(
        version=__version__,
        singularity_version=singularity_version
    ))

    parser.add_argument(
        "command",
        help="Command to execute",
        choices=['build', 'run', 'test', 'check', 'template']
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Output the intended command sequence without executing it (default: no)"
    )

    return parser.parse_args(args)


if __name__ == "__main__":
    __main()
