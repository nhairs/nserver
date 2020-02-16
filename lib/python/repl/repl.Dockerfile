FROM python:3.6

# Base stuff
RUN mkdir /srv/src
WORKDIR /srv/

ADD setup.py /srv/
RUN pip3 install -e .

ARG PACKAGE_PYTHON_NAME

ADD src /srv/

# This stuff
RUN echo "import ${PACKAGE_PYTHON_NAME}; import ${PACKAGE_PYTHON_NAME}._version; print(${PACKAGE_PYTHON_NAME}._version.get_version_info_full())" > /tmp/repl.py

CMD python3 -i /tmp/repl.py
