TODO
====

Sanity checks
-------------

* Check that Singularity is installed (and Docker, for `docker2singularity`)
* Check that Singularity is of appropriate version
* Check that pipeline file has all required fields of correct types
* Check that optional fields are of correct types

Adaptation for Singularity 2.4
------------------------------

* Add pipeline file version
* Replace `bootstrap` with `build`
* Add an extra step to `docker2singularity` build type to produce squashfs, if needed
* Review use of (deprecated) `--size`

Additional functionality (high priority)
----------------------------------------

* `template` command to generate a fresh pipeline file **DONE**
* `--dry-run` option to show commands executed instead of running them
* Require top-level `sudo`
    * Detect elevation in code
    * Review use of `subprocess.call`'s `shell` argument
* Choice for output image type (sandbox, ext3, squashfs) ― should be on metadata level, so that other commands load the appropriate image file
* Add support for custom flags in `{run}`/`{exec}` macros.

Testing (urgent)
----------------
* Manual testing of all functionality
* Testing of PyPi install on a "bare" VM
* Python 2/3 compatibility testing

Wishlist
========

Testing
-------

* Test pipelines for every build type
* "Broken" pipelines to test sanity checks

Additional functionality (low priority)
---------------------------------------

* Make sure it's possible to load and use `singularity-pipeline` as a module
* Overlay support
* Passing of metadata into the built image

Documentation
-------------

* Include documentation on the repo
* Write documentation on PyPi
* Include some documentation with the package
    * A `man` file would be ideal

Moving
------

* Would prefer being moved to GitHub