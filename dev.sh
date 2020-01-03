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

AUTOCLEAN_LIMIT=10

# Notation Reference: https://unix.stackexchange.com/questions/122845/using-a-b-for-variable-assignment-in-scripts#comment685330_122848
: ${CI:=0}  # Flag for if we are in CI - default to not.

### FUNCTIONS
### ============================================================================
## Docker Functions
## -----------------------------------------------------------------------------
function get_docker_tag {
    echo -n "${PACKAGE_NAME}-${1}:${GIT_COMMIT}"
}

function docker_build {
    docker build \
        --quiet \
        --file "lib/${1}" \
        --build-arg "PACKAGE_NAME=${PACKAGE_NAME}" \
        --build-arg "PACKAGE_PYTHON_NAME=${PACKAGE_PYTHON_NAME}" \
        --tag "$(get_docker_tag "$2")" \
        .
    echo
}

function docker_run {
    docker run --rm \
        --name "$(get_docker_tag "$1" | tr ":" "-")" \
        --volume "$(pwd):/srv" \
        "$(get_docker_tag "$1")"
}

function docker_run_interactive {
    docker run --rm \
        --interactive \
        --tty \
        --name "$(get_docker_tag "$1" | tr ":" "-")" \
        --volume "$(pwd):/srv" \
        "$(get_docker_tag "$1")"
}


function docker_autoclean {
    if [[ $CI = 0 ]]; then
        COUNT_IMAGES=$(docker images | grep "$PACKAGE_NAME" | grep -vc "$GIT_COMMIT")
        if [[ $COUNT_IMAGES -gt $AUTOCLEAN_LIMIT ]]; then
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
        if [[ $CI -gt 0 ]]; then
            echo "ERROR! Do not run format in CI!"
            exit 250
        fi
        heading "black 🐍"
        docker_build "python/format/black.Dockerfile" format-black
        docker_run format-black

        ;;

    "lint")
        heading "black - check only 🐍"
        docker_build "python/lint/black.Dockerfile" lint-black
        docker_run lint-black

        heading "pylint 🐍"
        docker_build "python/lint/pylint.Dockerfile" lint-pylint
        docker_run lint-pylint

        heading "mypy 🐍"
        docker_build "python/lint/mypy.Dockerfile" lint-mypy
        docker_run lint-mypy

        ;;

    "test")
        echo "WARNING: Not implemented"
        ;;

    "build")
        echo "WARNING: Not implemented"
        ;;

    "upload")
        echo "WARNING: Not implemented"
        ;;

    "repl")
        heading "repl 🐍"
        docker_build "python/repl/repl.Dockerfile" repl-python
        docker_run_interactive repl-python
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

        echo
        ;;

    "help")
        echo "dev.sh - development utility"
        echo "Usage: ./dev.sh COMMAND"
        echo
        echo "Commands:"
        echo "    build     Build python packages"
        echo "    debug     Display debug / basic health check information"
        echo "    format    Format files"
        echo "    help      Show this text"
        echo "    lint      Lint files. You probably want to format first."
        echo "    upload    Upload files to pypi server"
        echo "    repl      Open Python interactive shell with package imported"
        echo "    test      Run unit tests"
        echo
        echo ""

        ;;

    *)
        echo -e "\e[1;31mUnknown command \"${1}\"\e[0m"
        exit 255
        ;;
esac
