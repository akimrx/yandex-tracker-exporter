FROM python:3.10-slim as builder

WORKDIR /usr/src/app
COPY ./requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir --prefix=/usr/src/app/dist -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*


FROM python:3.10-slim

COPY --from=builder /usr/src/app/dist /usr/local
WORKDIR /opt/exporter

COPY . .
RUN pip install --no-cache-dir .
RUN rm -rf /opt/exporter

ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    apt-get update && \
    apt-get install -y --no-install-recommends tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/exporter
CMD ["tracker-exporter"]
