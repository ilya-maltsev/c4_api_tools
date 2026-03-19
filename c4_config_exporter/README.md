# C4 Config Exporter

CLI tool and FastAPI service for exporting configurations from Continent 4 security gateways.

Connects to Continent 4 management server over TLS with GOST cipher support (GOST R 34.10-2012, GOST R 34.11-2012) via the OpenSSL GOST engine built from open source.

## Назначение инструмента

Экспорт конфигурации всех или выбранных УБ под управлением отдельного ЦУС через API Континент 4.

Инструмент можно использовать для экспорта и последующего анализа конфигурации с использованием сторонних compliance-инструментов (например, Efros CI).

## Основные функции

1. Использование библиотеки `c4_lib` для работы с API Континент 4.
2. Вывод на экран списка УБ под управлением отдельного ЦУС с указанием `HW ID`.
3. Экспорт конфигурации для всех УБ под управлением отдельного ЦУС.
4. Экспорт конфигурации для выбранных УБ под управлением отдельного ЦУС (выбор по `HW ID`).
5. Опциональная очистка экспортированной конфигурации от "чувствительных" (конфиденциальных) данных.
6. FastAPI сервис для интеграции с c4_dashboard и другими инструментами.

## Приложения

- `c4_json.svg` - описание структуры (схема) экспортируемых данных.

## GOST Engine

The Docker image builds the [GOST engine](https://github.com/gost-engine/engine) from source in a multi-stage build. This provides Russian cryptographic algorithm support required for TLS connections to Continent 4:

- Digital signatures: GOST R 34.10-2001, GOST R 34.10-2012
- Hash functions: GOST R 34.11-94, GOST R 34.11-2012
- Symmetric ciphers: GOST 28147-89, Kuznyechik, Magma
- TLS cipher suites: GOST2012-KUZNYECHIK-KUZNYECHIKOMAC, GOST2012-MAGMA-MAGMAOMAC

### Docker Multi-Stage Build

The Dockerfile performs a fully open-source build with no precompiled binaries:

**Stage 1 (gost-builder):**
1. Installs build dependencies: `g++`, `gcc`, `make`, `cmake`, `libssl-dev`
2. Clones the latest release from `https://github.com/gost-engine/engine`
3. Builds with CMake against OpenSSL 3.x
4. Installs to `/usr/lib/x86_64-linux-gnu/engines-3/gost.so`
5. Verifies the engine loads: `openssl engine gost -c`

**Stage 2 (final):**
1. Copies the built `gost.so` from the builder stage
2. Installs `c4_lib` and `c4_config_exporter` in a Python venv
3. Replaces the bundled `gost.so` in `c4_lib` with the source-built one
4. Sets `OPENSSL_CONF` and `OPENSSL_ENGINE_PATH` environment variables

### Building GOST Engine Manually (Debian 12)

If you need to build the GOST engine outside of Docker:

```bash
# Install dependencies
apt-get install g++ gcc make pkg-config git cmake libssl-dev -y

# Verify OpenSSL 3.x
openssl version -v

# Clone and checkout latest release
git clone https://github.com/gost-engine/engine.git gost-engine
cd gost-engine
LATEST_TAG=$(git tag --sort=-v:refname | head -1)
git checkout $LATEST_TAG
git submodule update --init

# Build and install
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build . --config Release -j$(nproc)
cmake --build . --target install --config Release

# Verify
openssl engine gost -c
openssl ciphers | tr ':' '\n' | grep GOST
```

### OpenSSL Configuration

Add to `/etc/ssl/openssl.cnf` (before the first section header):

```ini
openssl_conf = openssl_def
```

Add at the end of the file:

```ini
[openssl_def]
engines = engine_section

[engine_section]
gost = gost_section

[gost_section]
engine_id = gost
dynamic_path = /usr/lib/x86_64-linux-gnu/engines-3/gost.so
default_algorithms = ALL
```

### Verification

```bash
# List engines
openssl engine
# (gost) Reference implementation of GOST engine

# List GOST ciphers
openssl ciphers | tr ':' '\n' | grep GOST
# GOST2012-MAGMA-MAGMAOMAC
# GOST2012-KUZNYECHIK-KUZNYECHIKOMAC
# LEGACY-GOST2012-GOST8912-GOST8912
# IANA-GOST2012-GOST8912-GOST8912
# GOST2001-GOST89-GOST89

# List GOST engine capabilities
openssl engine -c | grep gost | tr -d '[]' | tr ',' '\n'

# Generate a GOST test certificate
openssl req -x509 -newkey gost2012_256 -pkeyopt paramset:A \
  -nodes -keyout key.pem -out cert.pem -md_gost12_256

# Inspect the certificate
openssl x509 -in cert.pem -text -noout
# Signature Algorithm: GOST R 34.10-2012 with GOST R 34.11-2012 (256 bit)
```

## Quick Start (Docker)

### As API Service

```bash
cd dev_env/dev-c4-config-exporter
docker compose build
docker compose up -d
```

The FastAPI service runs on `http://127.0.0.1:8001`.

### As CLI Tool

```bash
cd dev_env/dev-c4-config-exporter

# List gateways
docker compose run --rm c4-config-exporter \
  c4_config_exporter --ip 192.168.122.200 -u admin:password print_cgws

# Export all configs
docker compose run --rm c4-config-exporter \
  c4_config_exporter --ip 192.168.122.200 -u admin:password \
  get_all_cgw_configs --output_path ./
```

## CLI Usage

```
c4_config_exporter [-h] -u CREDS --ip IP [--port PORT]
                   [--client-cert CLIENT_CERT] [--client-key CLIENT_KEY]
                   [--ca-cert CA_CERT] [--output_path OUTPUT_PATH]
                   [--hwserial HWSERIAL] [--with_confidential_data]
                   {get_all_cgw_configs,get_cgw_config_by_hwserial,print_cgws}
```

### Commands

| Command | Description |
|---|---|
| `print_cgws` | List all security gateways with hwserial |
| `get_all_cgw_configs` | Export configs of all gateways to files |
| `get_cgw_config_by_hwserial` | Export config of a specific gateway |

### Options

| Option | Description |
|---|---|
| `-u, --creds` | Credentials in format `user:pass` (required) |
| `--ip` | Server IP (required) |
| `--port` | Server port (default: 444) |
| `--client-cert` | Client certificate for mTLS (PEM) |
| `--client-key` | Client private key for mTLS (PEM) |
| `--ca-cert` | CA certificate for server verification |
| `--output_path` | Directory to save exported configs |
| `--hwserial` | Gateway hwserial for specific export |
| `--with_confidential_data` | Include sensitive fields (default: off) |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/gateways` | List gateways from Continent 4 |
| GET | `/api/configs` | Export all gateway configurations |
| GET | `/api/config/{hwserial}` | Export config for specific gateway |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `C4_HOST` | `192.168.122.200` | Continent 4 server IP |
| `C4_PORT` | `444` | Continent 4 server port |
| `C4_USER` | `admin` | Username |
| `C4_PASSWORD` | - | Password |
| `C4_API_PORT` | `8001` | FastAPI listen port |

## Dependencies

- `c4_lib` — Continent 4 API library with GOST TLS support
- `urllib3 <2` — HTTP client (v1.x required for GOST cipher configuration)
- `requests` — HTTP sessions
- `fastapi` — API framework (for service mode)
- `uvicorn` — ASGI server (for service mode)
