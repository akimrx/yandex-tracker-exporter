FROM python:3.7-slim
LABEL maintainer="a.faskhutdinov@yclients.tech"
LABEL name="tools/tracker-exporter"

ENV DEBIAN_FRONTEND noninteractive

# Configure timezone
RUN apt-get -qq update
RUN apt-get install -yqq tzdata
ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN dpkg-reconfigure -f noninteractive tzdata

# Configure exporter
RUN mkdir -p /opt/exporter
COPY ./requirements.txt requirements.txt
COPY . /opt/exporter/

# Install exporter
WORKDIR /opt/exporter
RUN python3 setup.py install

CMD ["tracker-exporter"]
