#!/bin/bash

### CONSTANTS
### ============================================================================
BUILD_TIMESTAMP=$(date +%s)
BUILD_DATETIME="datetime.utcfromtimestamp(${BUILD_TIMESTAMP})"
PACKAGE_VERSION=$(grep '^PACKAGE_VERSION' setup.py | cut -d '"' -f 2)

if [[ "$GIT_BRANCH" == "master" ]]; then
    BUILD_VERSION="${PACKAGE_VERSION}.${BUILD_TIMESTAMP}"
else
    BUILD_VERSION="${PACKAGE_VERSION}.${GIT_COMMIT_SHORT}"
fi

### FUNCTIONS
### ============================================================================
function replace_version_var {
    if [ $3 ]; then
        # Quotes
        sed -i "s/^${1} = \"\"/${1} = \"${2}\"/" "src/${PACKAGE_PYTHON_NAME}/_version.py"
    else
        # No Quotes
        sed -i "s/^${1} = \"\"/${1} = ${2}/" "src/${PACKAGE_PYTHON_NAME}/_version.py"
    fi
}

### MAIN
### ============================================================================
## Check constants set
## -----------------------------------------------------------------------------
echo "PACKAGE_NAME=${PACKAGE_NAME}"
echo "PACKAGE_PYTHON_NAME=${PACKAGE_PYTHON_NAME}"
echo "GIT_COMMIT_SHORT=${GIT_COMMIT_SHORT}"
echo "GIT_COMMIT=${GIT_COMMIT}"
echo "GIT_BRANCH=${GIT_BRANCH}"
echo "PYTHON_PACKAGE_REPOSITORY=${PYTHON_PACKAGE_REPOSITORY}"
echo "TESTPYPI_USERNAME=${TESTPYPI_USERNAME}"
echo "SOURCE_UID=${SOURCE_UID}"
echo "SOURCE_GID=${SOURCE_GID}"
# TODO


## Update _version.py
## -----------------------------------------------------------------------------
replace_version_var PACKAGE_VERSION "${PACKAGE_VERSION}" 1
replace_version_var BUILD_VERSION "${BUILD_VERSION}" 1
replace_version_var BUILD_GIT_HASH "${GIT_COMMIT}" 1
replace_version_var BUILD_GIT_HASH_SHORT "${GIT_COMMIT_SHORT}" 1
replace_version_var BUILD_GIT_BRANCH "${GIT_BRANCH}" 1
replace_version_var BUILD_TIMESTAMP "${BUILD_TIMESTAMP}" 1
replace_version_var BUILD_DATETIME "${BUILD_DATETIME}" 0

head -n 22 src/python_template/_version.py | tail -n 7

if [ "$PYTHON_PACKAGE_REPOSITORY" == "testpypi" ]; then
    echo "MODIFYING PACKAGE_NAME"
    # Replace name suitable for test.pypi.org
    # https://packaging.python.org/tutorials/packaging-projects/#creating-setup-py
    sed -i "s/^PACKAGE_NAME = .*/PACKAGE_NAME = \"${PACKAGE_NAME}-${TESTPYPI_USERNAME}\"/" setup.py
    grep "^PACKAGE_NAME = " setup.py
fi

## Build
## -----------------------------------------------------------------------------
python3 setup.py sdist bdist_wheel

## Cleanup
## -----------------------------------------------------------------------------
chown ${SOURCE_UID}:${SOURCE_GID} dist/*
