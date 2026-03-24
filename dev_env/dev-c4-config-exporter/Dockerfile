# Stage 1: Build gost-engine from source
FROM python:3.10.12-bookworm AS gost-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ gcc make pkg-config git cmake libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN git clone https://github.com/gost-engine/engine.git gost-engine && \
    cd gost-engine && \
    LATEST_TAG=$(git tag --sort=-v:refname | head -1) && \
    git checkout ${LATEST_TAG} && \
    git submodule update --init

RUN cd gost-engine && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr && \
    cmake --build . --config Release -j$(nproc) && \
    cmake --build . --target install --config Release

# Stage 2: Final image
FROM python:3.10.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=gost-builder /usr/lib/x86_64-linux-gnu/engines-3/gost.so /usr/lib/x86_64-linux-gnu/engines-3/gost.so

WORKDIR /opt

COPY c4_lib-2.0 /opt/c4_lib-2.0
COPY c4_config_exporter /opt/c4_config_exporter

RUN pip install --no-cache-dir \
        /opt/c4_lib-2.0 \
        /opt/c4_config_exporter \
        fastapi uvicorn && \
    cp /usr/lib/x86_64-linux-gnu/engines-3/gost.so \
       $(python -c "import c4_lib; import os; print(os.path.dirname(c4_lib.__file__))")/gost.so && \
    rm -rf /opt/c4_lib-2.0 /opt/c4_config_exporter

# c4_lib sets OPENSSL_CONF at import time to its own openssl.cnf
ENV C4_HOST="192.168.122.200"
ENV C4_PORT="444"
ENV C4_USER="admin"
ENV C4_PASSWORD=""
ENV C4_API_PORT="8001"
ENV REQUEST_TIMEOUT="300"

WORKDIR /opt/output

EXPOSE 8001

CMD ["sh", "-c", "uvicorn c4_config_exporter.api:app --host 0.0.0.0 --port $C4_API_PORT --timeout-keep-alive $REQUEST_TIMEOUT"]
