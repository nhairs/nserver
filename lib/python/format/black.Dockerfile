FROM python:3.6

# Base stuff
RUN mkdir /srv/src
WORKDIR /srv/

ADD setup.py /srv/
RUN pip3 install -e .


# This stuff
RUN pip3 install black
CMD black --line-length 100 --target-version py35 .
