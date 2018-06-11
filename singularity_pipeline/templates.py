template_pipeline = r'''## Those will be used in default image name
format_version: 1

name: CowSay
version: 1

## Those are purely informative at the moment
author: Alexander Kashev
author_org: UniBe
source:

## Extra substitutions for commands
## {image} is always available; in some contexts,
## To use literal {foo} in commands, double the braces: {{foo}}
substitutions:
  text: "Moo"

## Bind specifications (souce:destination) to be passed to Singularity
binds:
  - "/var/tmp:/var/tmp"

## Build instructions
build:
  ## Currently supported: build (will run sudo), pull, docker2singularity, custom
  type: pull

  ## Size in MB; optional for pull
  size: 512

  ## Extra options to pass to corresponding singularity build command; string
  # options: "--some-option"

  ## For build, should be a local Singularity file
  ## For pull, shub / docker URL
  ## For docker2singularity, should be a local Dockerfile file
  source: docker://chuanwen/cowsay

  ## Only for build type "custom".
  ## Additional substitutions: {source}, {size} (as "--size XXX") and {options}
  # commands:
  # - "singularity ..."

  ## Credentials for docker regsiteries
  ## Passed to singularity as environment variables
  # credentials:
  #   username: foo
  #   password: bar


## Run instructions
run:
  ## An array of scripts to be executed in shell
  ## Preset substitutions:
  ## * {exec}  for "singularity exec [-B <bind specification>] <image name>"
  ## * {run}   for "singularity run [-B <bind specification>] <image name>"
  ## * {binds} for "[-B <bind specification>]"
  ## * {image} for container file name
  ##  will be substituted; for literal {} (e.g. shell) use {{}}
  commands:
    - "{exec} /usr/games/cowsay {text} > cowsay.txt 2> /dev/null"

## Test instructions
test:
  ## Files required for testing; will run prepare_commands if any doesn't exist or --force specified
  test_files:
    - cowsay.md5
  ## An array of scripts to be executed in shell to prepare test_files
  prepare_commands:
    - "echo '548c5e52a6c1abc728a6b8e27f5abdd4  cowsay.txt' > cowsay.md5"
  ## An array of scripts to be executed in shell after running
  validate_commands:
    - "md5sum -c cowsay.md5"'''

template_version = r'''
%(prog)s version {version}
Singularity version {singularity_version}

Copyright (c) 2017-2018 Alexander Kashev
Created for the EnhanceR project: https://www.enhancer.ch/
'''
