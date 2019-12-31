#!/bin/bash

# Notes:
# - use shellcheck for bash linter (https://github.com/koalaman/shellcheck)

### SETUP
### ============================================================================
set -e  # Bail at the first sign of trouble

### CONTANTS
### ============================================================================
GIT_COMMIT=$(git rev-parse --short HEAD)
PACKAGE_NAME=$(grep 'PACKAGE_NAME =' setup.py | cut -d '=' -f 2 | tr -d ' ' | tr -d '"')
PACKAGE_PYTHON_NAME=$(echo -n "$PACKAGE_NAME" | tr '-' '_')

LIB_DIR="lib"  # Just in case "lib" is a bad name

AUTOCLEAN_LIMIT="10"

CI="0"  # Flag for if we are in CI

### FUNCTIONS
### ============================================================================
## Docker Functions
## -----------------------------------------------------------------------------
function get_docker_tag {
    echo -n "${PACKAGE_NAME}-${1}:${GIT_COMMIT}"
}

function docker_build {
    docker build --file "${LIB_DIR}/${1}" --tag "$(get_docker_tag "$2")" .
}

function docker_run {
    docker run --rm \
        --name "$(get_docker_tag "$1" | tr ":" "-")" \
        --volume "$(pwd):/srv" \
        "$(get_docker_tag "$1")"
}


function docker_autoclean {
    if [[ $CI = "0" ]]; then
        COUNT_IMAGES=$(docker images | grep "$PACKAGE_NAME" | grep -v "$GIT_COMMIT" | wc -l)
        if [[ $COUNT_IMAGES > $AUTOCLEAN_LIMIT ]]; then
            heading "Autocleaning docker images"
        fi
    fi
}

## Utility
## -----------------------------------------------------------------------------
function heading {
    # Print a pretty heading
    # https://en.wikipedia.org/wiki/Box-drawing_character#Unicode
    echo "╓─────────────────────────────────────────────────────────────────────"
    echo "║ $1"
    echo "╙───────────────────"
    echo
}

## Debug Functions
## -----------------------------------------------------------------------------
function check_file {
    # Pretty print if a file exists or not.
    if [[ -f "$1" ]]; then
        echo -e "$1 \e[1;32m EXISTS\e[0m"
    else
        echo -e "$1 \e[1;31m MISSING\e[0m"
    fi
}

### MAIN
### ============================================================================
docker_autoclean

case $1 in

    "format")
        if [[ $CI > 0 ]]; then
            echo "ERROR! Do not run format in CI!"
            exit 250
        fi
        heading "black (python)"
        docker_build "python/format/black.Dockerfile" format-black
        docker_run format-black

        ;;

    "lint")
        heading "black - check only (python)"
        docker_build "python/lint/black.Dockerfile" lint-black
        docker_run lint-black

        heading "pylint (python)"
        docker_build "python/lint/pylint.Dockerfile" lint-pylint
        docker_run lint-pylint

        heading "mypy (python)"
        docker_build "python/lint/black.Dockerfile" lint-mypy
        docker_run lint-mypy

        ;;

    "debug")
        heading "Debug"
        echo "GIT_COMMIT=${GIT_COMMIT}"
        echo "PACKAGE_NAME=${PACKAGE_NAME}"
        echo "PACKAGE_PYTHON_NAME=${PACKAGE_PYTHON_NAME}"
        echo
        echo "Checking Directory Layout..."
        check_file "src/${PACKAGE_PYTHON_NAME}/__init__.py"
        check_file "src/${PACKAGE_PYTHON_NAME}/_version.py"
        ;;

    *)
        echo "\e[1;31m Unkown command \"${1}\"\e[0m"
        exit 255
        ;;
esac
