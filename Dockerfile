FROM python:3.10-slim
LABEL maintainer="akimstrong@yandex.ru"
LABEL name="tools/tracker-exporter"

ENV DEBIAN_FRONTEND noninteractive
ENV TZ=Europe/Moscow

# Prepare environment & packages
RUN apt-get -qq update && \
    apt-get install -yqq tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Configure exporter
RUN mkdir -p /opt/exporter
COPY ./requirements.txt requirements.txt
COPY . /opt/exporter/

# Install exporter
WORKDIR /opt/exporter
RUN python3 setup.py install

CMD ["tracker-exporter"]
