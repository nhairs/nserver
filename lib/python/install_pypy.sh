#!/bin/bash
set -e

PYPY_VERSION="7.3.9"
PYTHON_VERSIONS="3.7 3.8 3.9"

cd /tmp

for PYTHON_VERSION in $PYTHON_VERSIONS; do
    FULLNAME="pypy${PYTHON_VERSION}-v${PYPY_VERSION}-linux64"
    FILENAME="${FULLNAME}.tar.bz2"

    echo "Fetching ${FILENAME}"
    wget -q "https://downloads.python.org/pypy/${FILENAME}"

    echo "Extracting ${FILENAME} to /opt/${FULLNAME}"
    tar xf ${FILENAME} --directory=/opt

    echo "Removing temp file"
    rm -f ${FILENAME}

    echo "sanity check"
    ls /opt

    echo "Linking ${FULLNAME}/bin/pypy${PYTHON_VERSION} to /usr/bin"
    ln -s "/opt/${FULLNAME}/bin/pypy${PYTHON_VERSION}" /usr/bin/

    echo ""

done
