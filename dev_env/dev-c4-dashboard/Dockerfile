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

# Stage 2: Dashboard with GOST support
FROM python:3.10.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        gettext libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=gost-builder /usr/lib/x86_64-linux-gnu/engines-3/gost.so /usr/lib/x86_64-linux-gnu/engines-3/gost.so

COPY dev_env/dev-nginx-gost/openssl-gost.cnf /etc/ssl/openssl.cnf

ENV OPENSSL_CONF="/etc/ssl/openssl.cnf"

WORKDIR /opt/app

COPY c4_lib-2.0 /opt/c4_lib-2.0
COPY c4_dashboard/requirements.txt /opt/app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir /opt/c4_lib-2.0 && \
    cp /usr/lib/x86_64-linux-gnu/engines-3/gost.so \
       $(python -c "import c4_lib; import os; print(os.path.dirname(c4_lib.__file__))")/gost.so && \
    rm -rf /opt/c4_lib-2.0

COPY c4_dashboard /opt/app

EXPOSE 8000

ENV BIND_ADDRESS="127.0.0.1:8000"
CMD ["sh", "-c", "python manage.py compilemessages && python manage.py collectstatic --noinput && python manage.py migrate --noinput && python manage.py ensure_admin && python manage.py runserver $BIND_ADDRESS"]
