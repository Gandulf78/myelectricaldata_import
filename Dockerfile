FROM python:3.12.7-slim

ARG TARGETPLATFORM
ENV TARGETPLATFORM=$TARGETPLATFORM

ENV LANG=fr_FR.UTF-8 \
    LC_ALL=fr_FR.UTF-8 \
    TZ=Europe/Paris \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    locales git g++ gcc libpq-dev curl && \
    sed -i -e 's/# fr_FR.UTF-8 UTF-8/fr_FR.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    pip install --no-cache-dir --upgrade pip pip-tools setuptools && \
    # INSTALL RUST FOR ARMv7 and orjson lib
    if [ "$TARGETPLATFORM" = "linux/arm/v7" ]; then \
        apt-get install -y --no-install-recommends \
        libc6-armhf-cross libc6-dev-armhf-cross gcc-arm-linux-gnueabihf libdbus-1-dev libdbus-1-dev:armhf && \
        curl -k -o rust-install.tar.gz https://static.rust-lang.org/dist/rust-1.78.0-armv7-unknown-linux-gnueabihf.tar.xz && \
        tar -xvf rust-install.tar.gz && \
        chmod +x rust-1.78.0-armv7-unknown-linux-gnueabihf/install.sh && \
        ./rust-1.78.0-armv7-unknown-linux-gnueabihf/install.sh; \
    elif [ "$TARGETPLATFORM" = "linux/arm/v6" ]; then \
        apt-get install -y --no-install-recommends \
        libc6-armel-cross libc6-dev-armel-cross gcc-arm-linux-gnueabi libdbus-1-dev libdbus-1-dev:armel && \
        curl -k -o rust-install.tar.gz https://static.rust-lang.org/dist/rust-1.78.0-arm-unknown-linux-gnueabi.tar.xz && \
        tar -xvf rust-install.tar.gz && \
        chmod +x rust-1.78.0-arm-unknown-linux-gnueabi/install.sh && \
        ./rust-1.78.0-arm-unknown-linux-gnueabi/install.sh; \
    fi

# Install Rust and Cargo
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy application code and install requirements
COPY ./src /app
RUN pip install --no-cache-dir -r /app/requirements.txt

# Remove Rust if installed
RUN if [ "$TARGETPLATFORM" = "linux/arm/v7" ] || [ "$TARGETPLATFORM" = "linux/arm/v6" ]; then \
    /usr/local/lib/rustlib/uninstall.sh; \
    fi

# Create directories
RUN mkdir -p /data /log

# Cleanup
RUN apt-get remove -y git libpq-dev gcc g++ && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Set metadata labels
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION
LABEL \
    maintainer="Gandulf78 (https://github.com/alexbelgium)" \
    org.opencontainers.image.title="MyElectricalData forked client with EDF Flex" \
    org.opencontainers.image.description="Client to import data from MyElectricalData gateway." \
    org.opencontainers.image.authors="m4dm4rtig4n (https://github.com/m4dm4rtig4n)" \
    org.opencontainers.image.licenses="Apache License 2.0" \
    org.opencontainers.image.url="https://github.com/Gandulf78" \
    org.opencontainers.image.source="https://github.com/Gandulf78/myelectricaldata_import_flex" \
    org.opencontainers.image.documentation="https://github.com/MyElectricalData/myelectricaldata_import/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

WORKDIR /app

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["python", "-u", "/app/main.py"]
