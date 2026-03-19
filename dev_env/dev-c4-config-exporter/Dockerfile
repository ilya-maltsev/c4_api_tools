# Stage 1: Build gost-engine from source
FROM python:3.10.12-bookworm AS gost-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ gcc make pkg-config git cmake libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN git clone https://github.com/gost-engine/engine.git gost-engine && \
    cd gost-engine && \
    LATEST_TAG=$(git tag --sort=-v:refname | head -1) && \
    echo "Building gost-engine ${LATEST_TAG}" && \
    git checkout ${LATEST_TAG} && \
    git submodule update --init

RUN cd gost-engine && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr && \
    cmake --build . --config Release -j$(nproc) && \
    cmake --build . --target install --config Release

# Verify the built engine
RUN openssl engine gost -c

# Stage 2: Final image
FROM python:3.10.12-bookworm

# Copy built gost engine from builder
COPY --from=gost-builder /usr/lib/x86_64-linux-gnu/engines-3/gost.so /usr/lib/x86_64-linux-gnu/engines-3/gost.so

WORKDIR /opt

COPY c4_lib-2.0 /opt/c4_lib-2.0
COPY c4_config_exporter /opt/c4_config_exporter

RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

RUN /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir /opt/c4_lib-2.0 && \
    /opt/venv/bin/pip install --no-cache-dir /opt/c4_config_exporter && \
    /opt/venv/bin/pip install --no-cache-dir fastapi uvicorn

# Replace precompiled gost.so with the one built from source
RUN cp /usr/lib/x86_64-linux-gnu/engines-3/gost.so /opt/venv/lib/python3.10/site-packages/c4_lib/gost.so

ENV OPENSSL_CONF="/opt/venv/lib/python3.10/site-packages/c4_lib/openssl.cnf"
ENV OPENSSL_ENGINE_PATH="/opt/venv/lib/python3.10/site-packages/c4_lib"
ENV C4_HOST="192.168.122.200"
ENV C4_PORT="444"
ENV C4_USER="admin"
ENV C4_PASSWORD="AsdfgTrewq1@"
ENV C4_OUTPUT_PATH="./"
ENV C4_API_PORT="8001"

WORKDIR /opt/output

EXPOSE 8001

CMD ["sh", "-c", "uvicorn c4_config_exporter.api:app --host 0.0.0.0 --port $C4_API_PORT"]
