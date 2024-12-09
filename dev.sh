#!/bin/bash

# NOTICE: dev.sh and it's related files are
# Copyright (c) 2020 Nicholas Hairs
# Licenced under The MIT Licence
# Source: https://github.com/nhairs/python-package-template

# Notes:
# - use shellcheck for bash linter (https://github.com/koalaman/shellcheck)

### SETUP
### ============================================================================
set -e  # Bail at the first sign of trouble

# Notation Reference: https://unix.stackexchange.com/questions/122845/using-a-b-for-variable-assignment-in-scripts#comment685330_122848
: ${DEBUG:=0}
: ${CI:=0}  # Flag for if we are in CI - default to not.

if ! command -v toml &> /dev/null; then
    pip install --user toml-cli
fi

if ! command -v uv &> /dev/null; then
    pip install --user uv
fi

### CONTANTS
### ============================================================================
SOURCE_UID=$(id -u)
SOURCE_GID=$(id -g)
SOURCE_UID_GID="${SOURCE_UID}:${SOURCE_GID}"
GIT_REPOSITORY=$(git remote get-url origin 2>/dev/null | cut -d '/' -f 2 | cut -d '.' -f 1 | grep . || echo -n 'none')
GIT_COMMIT_SHORT=$(git rev-parse --short HEAD 2>/dev/null || echo -n 'none')
GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo -n 'none')
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo -n 'none')
PACKAGE_NAME=$(toml get --toml-path pyproject.toml project.name)
PACKAGE_PYTHON_NAME=$(echo -n "$PACKAGE_NAME" | tr '-' '_')
PACKAGE_VERSION=$(toml get --toml-path pyproject.toml project.version)

: ${AUTOCLEAN_LIMIT:=10}

: ${PYTHON_PACKAGE_REPOSITORY:="pypi"}
: ${TESTPYPI_USERNAME="$USER-test"}

## Python Project Related
## -----------------------------------------------------------------------------
# You may want to customise these for your project
# TODO: this potentially should be moved to manifest.env so that projects can easily
# customise the main dev.sh
PYTHON_MIN_VERSION="py38"

## Build related
## -----------------------------------------------------------------------------
BUILD_TIMESTAMP=$(date +%s)

if [[ "$GIT_BRANCH" == "master" || "$GIT_BRANCH" == "main" ]]; then
    BUILD_VERSION="${PACKAGE_VERSION}"
else
    # Tox doesn't like version labels like
    # python_template-0.0.0+3f2d02f.1667158525-py3-none-any.whl
    #BUILD_VERSION="${PACKAGE_VERSION}+${GIT_COMMIT_SHORT}.${BUILD_TIMESTAMP}"

    # Use PEP 440 non-compliant versions since we know it works
    #BUILD_VERSION="${PACKAGE_VERSION}.${GIT_COMMIT_SHORT}"

    # PEP 440 compliant `.devM` versioning using timestamps
    # Multiple users on the same branch may interfere with eachother
    # But this is fine for now...
    BUILD_VERSION="${PACKAGE_VERSION}.dev${BUILD_TIMESTAMP}"
fi

BUILT_WHEEL="${PACKAGE_PYTHON_NAME}-${BUILD_VERSION}-py3-none-any.whl"

## Load manifests
## -----------------------------------------------------------------------------
if [[ -f "lib/manifest.env" ]]; then
    echo "⚙️  loading lib/manifest.env"
    source lib/manifest.env
fi

if [[ -f "locals.env" ]]; then
    echo "⚙️  loading locals.env"
    source locals.env
fi

## Generate remaining vars

## Insert into .tmp/env
## -----------------------------------------------------------------------------
if [ ! -d .tmp ]; then
    mkdir .tmp
fi

if [[ "$DEBUG" -gt 0 ]]; then
    echo "⚙️  writing .tmp/env"
fi
cat > .tmp/env <<EOF
PACKAGE_NAME=${PACKAGE_NAME}
PACKAGE_PYTHON_NAME=${PACKAGE_PYTHON_NAME}
PACKAGE_VERSION=${PACKAGE_VERSION}
GIT_REPOSITORY=${GIT_REPOSITORY}
GIT_COMMIT_SHORT=${GIT_COMMIT_SHORT}
GIT_COMMIT=${GIT_COMMIT}
GIT_BRANCH=${GIT_BRANCH}
PYTHON_PACKAGE_REPOSITORY=${PYTHON_PACKAGE_REPOSITORY}
TESTPYPI_USERNAME=${TESTPYPI_USERNAME}
SOURCE_UID=${SOURCE_UID}
SOURCE_GID=${SOURCE_GID}
SOURCE_UID_GID=${SOURCE_UID_GID}
BUILD_TIMESTAMP=${BUILD_TIMESTAMP}
BUILD_VERSION=${BUILD_VERSION}
BUILD_DIR=.tmp/dist  # default
BUILT_WHEEL=${BUILT_WHEEL}
EOF

# workaround for old docker-compose versions
cp .tmp/env .env

### FUNCTIONS
### ============================================================================
## Utility
## -----------------------------------------------------------------------------
function heading {
    # Print a pretty heading
    # https://en.wikipedia.org/wiki/Box-drawing_character#Unicode
    echo "╓─────────────────────────────────────────────────────────────────────"
    echo "║ $@"
    echo "╙───────────────────"
    echo
}

function heading2 {
    # Print a pretty heading-2
    # https://en.wikipedia.org/wiki/Box-drawing_character#Unicode
    echo "╓ $@"
    echo "╙───────────────────"
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

function check_pyproject_toml {
    # Pretty print if the given key exists in pyproject.toml.
    if toml get --toml-path pyproject.toml $1 1>/dev/null 2>/dev/null; then
        echo -e "$1 \e[1;32m EXISTS\e[0m"
    else
        echo -e "$1 \e[1;31m MISSING\e[0m"
    fi
}

## Command Functions
## -----------------------------------------------------------------------------

function display_usage {
    echo "dev.sh - development utility"
    echo "Usage: ./dev.sh COMMAND"
    echo
    echo "           build    Build python packages"
    echo "      build-docs    Build documentation"
    echo "           clean    Cleanup clutter"
    echo "           debug    Display debug / basic health check information"
    echo "            docs    Preview docs locally"
    echo "          format    Format files"
    echo "            help    Show this text"
    echo "            lint    Lint files. You probably want to format first."
    echo "       push-docs    Push docs"
    echo "            repl    Open Python interactive shell with the package imported"
    echo "                    If repl.py exists will use this file instead of default template."
    echo "             run    Run the given file in the python-common container"
    echo "             tag    Tag commit with current version"
    echo "            test    Run unit tests"
    echo "       test-full    Run unit tests on all python versions"
    echo "          upload    Upload built files to where they are distributed from (e.g. PyPI)"
    if [[ "$ENABLE_COMMANDS" = 1 ]]; then
        # find extra commands
        for COMMAND_PATH in lib/commands/*.sh; do
            COMMAND=$(basename "$COMMAND_PATH" .sh)
            COMMAND_HELP_PATH="lib/commands/${COMMAND}.txt"
            if [[ ! -f "$COMMAND_HELP_PATH" ]]; then
                printf "%16s\n" "$COMMAND"
            else
                COMMAND_HELP=$(head -n 1 "$COMMAND_HELP_PATH")
                printf "%16s    %s\n" "$COMMAND" "$COMMAND_HELP"
                if [[ "$(wc -l $COMMAND_HELP_PATH | cut -d ' ' -f 1)" -gt 1 ]]; then
                    for HELP_LINE in $(tail -n +2 $COMMAND_HELP_PATH); do
                        echo "                    $HELP_LINE"
                    done
                fi
            fi
        done
    fi
    echo
    echo
}

### MAIN
### ============================================================================
case $1 in

    "format")
        if [[ $CI = 1 ]]; then
            echo "ERROR! Do not run format in CI!"
            exit 250
        fi
        heading "tox 🐍 - format"
        uvx tox -e format || true

        ;;

    "lint")
        heading "tox 🐍 - lint"
        uvx tox -e lint || true
        ;;

    "test")
        heading "tox 🐍 - single"
        uvx tox -e py312 || true

        ;;

    "test-full")
        heading "tox 🐍 - all"
        uvx tox || true

        ;;

    "build")
        source ./lib/python/build.sh

        ;;

    "upload")
        heading "Upload to ${PYTHON_PACKAGE_REPOSITORY}"
        heading "setup 📜"
        if [[ -z $(pip3 list | grep keyrings.alt) ]]; then
            pip3 install --user keyrings.alt
            pip3 install --user twine
        fi

        if [ ! -d dist_uploaded ]; then
            mkdir dist_uploaded
        fi

        heading "upload 📜"
        twine upload --repository "${PYTHON_PACKAGE_REPOSITORY}" dist/*.whl

        echo "📜 cleanup"
        mv dist/* dist_uploaded

        ;;

    "repl")
        heading "REPL 🐍"
        if [[ -f "repl.py" ]]; then
            echo "Using provided repl.py"
            echo
            cp repl.py .tmp/repl.py
        else
            echo "Using default repl.py"
            echo
            cat > .tmp/repl.py <<EOF
import ${PACKAGE_PYTHON_NAME}
print('Your package is already imported 🎉\nPress ctrl+d to exit')
EOF
        fi

        uv run python -i .tmp/repl.py

        ;;

    "docs")
        heading "Preview Docs 🐍"
        uv run --extra dev mkdocs serve -w docs

        ;;

    "build-docs")
        heading "Building Docs 🐍"

        uv run --extra dev mike deploy "$PACKAGE_VERSION" "latest" \
            --update-aliases \
            --prop-set-string "git_branch=${GIT_BRANCH}" \
            --prop-set-string "git_commit=${GIT_COMMIT}" \
            --prop-set-string "git_commit_short=${GIT_COMMIT_SHORT}" \
            --prop-set-string "build_timestamp=${BUILD_TIMESTAMP}"

        ;;

    "push-docs")
        heading "Pushing docs 📜"
        git push origin gh-pages

        ;;

    "clean")
        heading "Cleaning 📜"

        echo "🐍 pyclean"
        if ! command -v pyclean &> /dev/null; then
            pip3 install --user pyclean
        fi
        pyclean src
        pyclean tests

        echo "🐍 clear .tox"
        rm -rf .tox

        echo "🐍 remove build artifacts"
        rm -rf build dist "src/${PACKAGE_PYTHON_NAME}.egg-info"

        echo "cleaning .tmp"
        rm -rf .tmp/*

        ;;

    "debug")
        heading "Debug 📜"
        cat .tmp/env
        echo
        echo "Checking Directory Layout..."
        check_file "pyproject.toml"
        check_file "src/${PACKAGE_PYTHON_NAME}/py.typed"
        check_file "src/${PACKAGE_PYTHON_NAME}/__init__.py"
        check_file "src/${PACKAGE_PYTHON_NAME}/_version.py"
        echo
        echo "Checking pyproject.toml"
        check_pyproject_toml project.optional-dependencies.dev
        check_pyproject_toml tool.setuptools.package-data.${PACKAGE_PYTHON_NAME}

        echo

        ;;

    "tag")
        heading "Tagging Git Commit 🛠️"
        TAG="v${PACKAGE_VERSION}"
        git tag "$TAG"

        ;;

    "help")
        display_usage

        ;;

    *)
        if [[ "$ENABLE_COMMANDS" = 1 ]]; then
            COMMAND_FILE="lib/commands/${1}.sh"
            if [[ -f "$COMMAND_FILE" ]]; then
                source "$COMMAND_FILE"
                exit 0
            fi
        fi
        echo -e "\e[1;31mUnknown command \"${1}\"\e[0m"
        display_usage
        exit 255

        ;;
esac
