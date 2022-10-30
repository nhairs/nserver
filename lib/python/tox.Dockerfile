FROM ubuntu:20.04

# We use deadsnakes ppa to install
# https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa
#
# As noted in the readme, 22.04 supports only 3.7+, so use 20.04 to support some older versions
# This also means we don't install 3.8 as it is already provided

# TZ https://serverfault.com/a/1016972
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt update && apt upgrade --yes \
 && apt install --yes software-properties-common wget \
 && add-apt-repository ppa:deadsnakes/ppa \
 && apt update

RUN apt install --yes python3-pip
RUN apt install --yes \
    python3.6 python3.6-dev python3.6-distutils \
    python3.7 python3.7-dev python3.7-distutils \
    python3.9 python3.9-dev python3.9-distutils \
    python3.10 python3.10-dev python3.10-distutils \
    python3.11 python3.11-dev python3.11-distutils

## pypy
ADD lib/python/install_pypy.sh /tmp
RUN /tmp/install_pypy.sh


ARG SOURCE_UID
ARG SOURCE_GID
ARG SOURCE_UID_GID

RUN mkdir -p /code/dist /code/tests \
 && groupadd --gid ${SOURCE_GID} devuser \
 && useradd --uid ${SOURCE_GID} -g devuser --create-home --shell /bin/bash devuser \
 && chown -R ${SOURCE_UID_GID} /code \
 && su - devuser -c "pip install --user --upgrade pip"

RUN su - devuser -c "pip install --user tox"

CMD echo "docker-compose build python-tox complete 🎉"
