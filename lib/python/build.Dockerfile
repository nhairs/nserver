FROM python:3.7

ARG SOURCE_UID
ARG SOURCE_GID
ARG SOURCE_UID_GID

RUN mkdir -p /code/src \
 && groupadd --gid ${SOURCE_GID} devuser \
 && useradd --uid ${SOURCE_GID} -g devuser --create-home --shel /bin/bash devuser \
 && chown -R ${SOURCE_UID_GID} /code \
 && su - devuser -c "pip install --user --upgrade pip"

## ^^ copied from common.Dockerfile - try to keep in sync fo caching

# Base stuff
ADD . /code

RUN chown -R ${SOURCE_UID_GID} /code # needed twice because added files

RUN ls -lah /code

RUN su - devuser -c "cd /code && pip install --user setuptools wheel"

CMD echo "docker-compose build python-build complete 🎉"
