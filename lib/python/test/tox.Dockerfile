FROM python:3.6

# Base stuff
RUN mkdir /srv/src
WORKDIR /srv/

ADD setup.py /srv/
RUN pip3 install -e .


# This stuff

# https://tox.readthedocs.io/en/latest/example/pytest.html
CMD echo "this is a placeholder"
