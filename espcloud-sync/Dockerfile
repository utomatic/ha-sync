# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/i386-base-debian:bullseye
ARG BUILD_ARCH=i386
ARG TEMPIO_VERSION=2021.09.0
FROM $BUILD_FROM

RUN \
    apt-get update \
    # Use pinned versions so that we get updates with build caching
    && apt-get install -y --no-install-recommends \
        python3=3.9.2-3 \
        python3-pip=20.3.4-4+deb11u1 \
        python3-setuptools=52.0.0-4 \
        python3-pil=8.1.2+dfsg-0.3+deb11u1 \
        python3-cryptography=3.3.2-1 \
        iputils-ping=3:20210202-1 \
        git=1:2.30.2-1 \
        curl \
        openssh-client=1:8.4p1-5+deb11u1 \
    && rm -rf \
        /tmp/* \
        /var/{cache,log}/* \
        /var/lib/apt/lists/*

RUN pip3 install aioesphomeapi==13.5.0 esphome==2023.3.0 requests==2.29.0

# Copy root filesystem
COPY rootfs /
