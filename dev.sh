#!/bin/bash

# Notes:
# - use shellcheck for bash linter (https://github.com/koalaman/shellcheck)

### SETUP
### ============================================================================
set -e  # Bail at the first sign of trouble

### CONTANTS
### ============================================================================
SOURCE_UID=$(id -u)
SOURCE_GID=$(id -g)
GIT_COMMIT_SHORT=$(git rev-parse --short HEAD)
GIT_COMMIT=$(git rev-parse HEAD)
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
PACKAGE_NAME=$(grep 'PACKAGE_NAME =' setup.py | cut -d '=' -f 2 | tr -d ' ' | tr -d '"')
PACKAGE_PYTHON_NAME=$(echo -n "$PACKAGE_NAME" | tr '-' '_')

AUTOCLEAN_LIMIT=10

# Notation Reference: https://unix.stackexchange.com/questions/122845/using-a-b-for-variable-assignment-in-scripts#comment685330_122848
: ${CI:=0}  # Flag for if we are in CI - default to not.

PYTHON_PACKAGE_REPOSITORY="testpypi"
TESTPYPI_USERNAME="nhairs-test"

### FUNCTIONS
### ============================================================================
## Docker Functions
## -----------------------------------------------------------------------------
function get_docker_tag {
    echo -n "${PACKAGE_NAME}-${1}:${GIT_COMMIT}"
}

function docker_build {
    echo "🐋 Building $2"
    docker build \
        --quiet \
        --file "lib/${1}" \
        --build-arg "PACKAGE_NAME=${PACKAGE_NAME}" \
        --build-arg "PACKAGE_PYTHON_NAME=${PACKAGE_PYTHON_NAME}" \
        --build-arg "GIT_COMMIT_SHORT=${GIT_COMMIT_SHORT}" \
        --build-arg "GIT_COMMIT=${GIT_COMMIT}" \
        --build-arg "GIT_BRANCH=${GIT_BRANCH}" \
        --build-arg "PYTHON_PACKAGE_REPOSITORY=${PYTHON_PACKAGE_REPOSITORY}" \
        --build-arg "TESTPYPI_USERNAME=${TESTPYPI_USERNAME}" \
        --build-arg "SOURCE_UID=${SOURCE_UID}" \
        --build-arg "SOURCE_GID=${SOURCE_GID}" \
        --tag "$(get_docker_tag "$2")" \
        .
}

function docker_run {
    echo "🐋 running $1"
    docker run --rm \
        --name "$(get_docker_tag "$1" | tr ":" "-")" \
        --volume "$(pwd):/srv" \
        "$(get_docker_tag "$1")"
}

function docker_run_build {
    # Specialised function for build
    # mounts only dist instead of .
    echo "🐋 running $1"
    docker run --rm \
        --name "$(get_docker_tag "$1" | tr ":" "-")" \
        --volume "$(pwd)/dist:/srv/dist" \
        "$(get_docker_tag "$1")"
}

function docker_run_interactive {
    echo "🐋 running $1"
    docker run --rm \
        --interactive \
        --tty \
        --name "$(get_docker_tag "$1" | tr ":" "-")" \
        --volume "$(pwd):/srv" \
        "$(get_docker_tag "$1")"
}


function docker_clean {
    echo "🐋 Removing ${PACKAGE_NAME} images"
    COUNT_IMAGES=$(docker images | grep "$PACKAGE_NAME" | wc -l)
    if [[ $COUNT_IMAGES -gt 0 ]]; then
        docker images | grep "$PACKAGE_NAME" | awk '{OFS=":"} {print $1, $2}' | xargs docker rmi
    fi
}

function docker_clean_unused {
    docker images | \
        grep "$PACKAGE_NAME" | \
        grep -v "$GIT_COMMIT" | \
        awk '{OFS=":"} {print $1, $2}' | \
        xargs docker rmi
}

function docker_autoclean {
    if [[ $CI = 0 ]]; then
        COUNT_IMAGES=$(docker images | grep "$PACKAGE_NAME" | grep -v "$GIT_COMMIT" | wc -l)
        if [[ $COUNT_IMAGES -gt $AUTOCLEAN_LIMIT ]]; then
            heading "Removing unused ${PACKAGE_NAME} images 🐋"
            docker_clean_unused
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
        heading "pytest 🐍"
        docker_build "python/test/pytest.Dockerfile" test-pytest
        docker_run test-pytest

        heading "tox 🐍"
        docker_build "python/test/tox.Dockerfile" test-tox
        docker_run test-tox

        ;;

    "build")
        # TODO: unstashed changed guard
        if [ ! -d dist ]; then
            heading "setup 📜"
            mkdir dist
        fi

        heading "build 🐍"
        docker_build "python/build/build.Dockerfile" build
        docker_run_build build
        ;;

    "upload")
        heading "Upload to ${PYTHON_PACKAGE_REPOSITORY}"
        heading "setup 📜"
        pip3 install --user keyrings.alt
        pip3 install --user twine

        if [ ! -d dist_uploaded ]; then
            mkdir dist_uploaded
        fi

        heading "upload 📜"
        twine upload --repository "${PYTHON_PACKAGE_REPOSITORY}" dist/*

        echo "📜 cleanup"
        mv dist/* dist_uploaded
        ;;

    "repl")
        heading "repl 🐍"
        docker_build "python/repl/repl.Dockerfile" repl-python
        docker_run_interactive repl-python
        ;;

    "clean")
        heading "Cleaning 📜"
        docker_clean

        echo "🐍 pyclean"
        pyclean src
        pyclean tests

        echo "🐍 remove build artifacts"
        rm -rf build dist "src/${PACKAGE_PYTHON_NAME}.egg-info"

        ;;

    "debug")
        heading "Debug 📜"
        echo "PACKAGE_NAME=${PACKAGE_NAME}"
        echo "PACKAGE_PYTHON_NAME=${PACKAGE_PYTHON_NAME}"
        echo "GIT_COMMIT_SHORT=${GIT_COMMIT_SHORT}"
        echo "GIT_COMMIT=${GIT_COMMIT}"
        echo "GIT_BRANCH=${GIT_BRANCH}"
        echo "PYTHON_PACKAGE_REPOSITORY=${PYTHON_PACKAGE_REPOSITORY}"
        echo "TESTPYPI_USERNAME=${TESTPYPI_USERNAME}"
        echo "SOURCE_UID=${SOURCE_UID}"
        echo "SOURCE_GID=${SOURCE_GID}"
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
        echo "    clean     Cleanup clutter"
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
