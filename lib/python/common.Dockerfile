# syntax = docker/dockerfile:1.2
FROM python:3.8


ARG SOURCE_UID
ARG SOURCE_GID
ARG SOURCE_UID_GID

RUN apt update && apt install -y \
    less

RUN mkdir -p /code/src \
 && groupadd --gid ${SOURCE_GID} devuser \
 && useradd --uid ${SOURCE_GID} -g devuser --create-home --shell /bin/bash devuser \
 && chown -R ${SOURCE_UID_GID} /code \
 && su -l devuser -c "pip install --user --upgrade pip"

ADD pyproject.toml /code
RUN chown -R ${SOURCE_UID_GID} /code # needed twice because added files

RUN ls -lah /code /home /home/devuser /home/devuser/.cache /home/devuser/.cache/pip

RUN --mount=type=cache,target=/home/devuser/.cache,uid=1000,gid=1000 \
    su -l devuser -c "cd /code && pip install --user -e .[dev,docs]"

CMD echo "docker-compose build python-common complete 🎉"
