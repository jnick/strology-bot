FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

WORKDIR /srv/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY certs/ ./certs/
RUN cp certs/russian-trusted-sub-ca.pem /usr/local/share/ca-certificates/russian-trusted-sub-ca.crt \
    && update-ca-certificates

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["python", "-m", "app.main"]