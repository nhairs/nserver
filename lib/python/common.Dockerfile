FROM python:3.7


ARG SOURCE_UID
ARG SOURCE_GID
ARG SOURCE_UID_GID

RUN mkdir -p /code/src \
 && groupadd --gid ${SOURCE_GID} devuser \
 && useradd --uid ${SOURCE_GID} -g devuser --create-home --shel /bin/bash devuser \
 && chown -R ${SOURCE_UID_GID} /code \
 && su - devuser -c "pip install --user --upgrade pip"

ADD setup.py /code
RUN chown -R ${SOURCE_UID_GID} /code # needed twice because added files

RUN ls -lah /code

RUN su - devuser -c "cd /code && pip install --user -e .[dev]"

CMD echo "docker-compose build python-common complete 🎉"
