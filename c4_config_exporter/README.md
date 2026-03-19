# C4 Config Exporter

CLI-инструмент и FastAPI-сервис для экспорта конфигураций с узлов безопасности (УБ) Континент 4.

Подключение к серверу управления Континент 4 выполняется по TLS с поддержкой ГОСТ-шифров (ГОСТ Р 34.10-2012, ГОСТ Р 34.11-2012) через OpenSSL GOST engine, собранный из открытых исходников.

## Назначение инструмента

Экспорт конфигурации всех или выбранных УБ под управлением отдельного ЦУС через API Континент 4.

Инструмент можно использовать для экспорта и последующего анализа конфигурации с использованием сторонних compliance-инструментов (например, Efros CI).

## Основные функции

1. Использование библиотеки `c4_lib` для работы с API Континент 4.
2. Вывод на экран списка УБ под управлением отдельного ЦУС с указанием `HW ID`.
3. Экспорт конфигурации для всех УБ под управлением отдельного ЦУС.
4. Экспорт конфигурации для выбранных УБ под управлением отдельного ЦУС (выбор по `HW ID`).
5. Опциональная очистка экспортированной конфигурации от "чувствительных" (конфиденциальных) данных.
6. FastAPI-сервис для интеграции с c4_dashboard и другими инструментами.

## Приложения

- `c4_json.svg` - описание структуры (схема) экспортируемых данных.

## GOST Engine

Docker-образ собирает [GOST engine](https://github.com/gost-engine/engine) из исходного кода в многоэтапной сборке. Это обеспечивает поддержку российских криптографических алгоритмов, необходимых для TLS-соединений с Континент 4:

- Электронная подпись: ГОСТ Р 34.10-2001, ГОСТ Р 34.10-2012
- Хеш-функции: ГОСТ Р 34.11-94, ГОСТ Р 34.11-2012
- Симметричное шифрование: ГОСТ 28147-89, Кузнечик, Магма
- TLS cipher suites: GOST2012-KUZNYECHIK-KUZNYECHIKOMAC, GOST2012-MAGMA-MAGMAOMAC

### Многоэтапная сборка Docker

Dockerfile выполняет полностью открытую сборку без предкомпилированных бинарных файлов:

**Этап 1 (gost-builder):**
1. Установка зависимостей для сборки: `g++`, `gcc`, `make`, `cmake`, `libssl-dev`
2. Клонирование последнего релиза из `https://github.com/gost-engine/engine`
3. Сборка с CMake для OpenSSL 3.x
4. Установка в `/usr/lib/x86_64-linux-gnu/engines-3/gost.so`
5. Проверка загрузки движка: `openssl engine gost -c`

**Этап 2 (финальный образ):**
1. Копирование собранного `gost.so` из этапа сборки
2. Установка `c4_lib` и `c4_config_exporter` в Python venv
3. Замена встроенного `gost.so` в `c4_lib` на собранный из исходников
4. Установка переменных окружения `OPENSSL_CONF` и `OPENSSL_ENGINE_PATH`

### Ручная сборка GOST Engine (Debian 12)

Если необходимо собрать GOST engine вне Docker:

```bash
# Установка зависимостей
apt-get install g++ gcc make pkg-config git cmake libssl-dev -y

# Проверка версии OpenSSL (должна быть 3.x)
openssl version -v

# Клонирование и переключение на последний релиз
git clone https://github.com/gost-engine/engine.git gost-engine
cd gost-engine
LATEST_TAG=$(git tag --sort=-v:refname | head -1)
git checkout $LATEST_TAG
git submodule update --init

# Сборка и установка
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
cmake --build . --config Release -j$(nproc)
cmake --build . --target install --config Release

# Проверка
openssl engine gost -c
openssl ciphers | tr ':' '\n' | grep GOST
```

### Настройка OpenSSL

Добавить в `/etc/ssl/openssl.cnf` (перед первым заголовком секции в квадратных скобках):

```ini
openssl_conf = openssl_def
```

Добавить в конец файла:

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

### Проверка

```bash
# Список движков
openssl engine
# (gost) Reference implementation of GOST engine

# Список ГОСТ-шифров
openssl ciphers | tr ':' '\n' | grep GOST
# GOST2012-MAGMA-MAGMAOMAC
# GOST2012-KUZNYECHIK-KUZNYECHIKOMAC
# LEGACY-GOST2012-GOST8912-GOST8912
# IANA-GOST2012-GOST8912-GOST8912
# GOST2001-GOST89-GOST89

# Возможности ГОСТ-движка
openssl engine -c | grep gost | tr -d '[]' | tr ',' '\n'

# Генерация тестового ГОСТ-сертификата
openssl req -x509 -newkey gost2012_256 -pkeyopt paramset:A \
  -nodes -keyout key.pem -out cert.pem -md_gost12_256

# Просмотр информации о сертификате
openssl x509 -in cert.pem -text -noout
# Signature Algorithm: GOST R 34.10-2012 with GOST R 34.11-2012 (256 bit)
```

## Быстрый старт (Docker)

### Режим API-сервиса

```bash
cd dev_env/dev-c4-config-exporter
docker compose build
docker compose up -d
```

FastAPI-сервис будет доступен по адресу `http://127.0.0.1:8001`.

### Режим CLI-инструмента

```bash
cd dev_env/dev-c4-config-exporter

# Список УБ
docker compose run --rm c4-config-exporter \
  c4_config_exporter --ip 192.168.122.200 -u admin:password print_cgws

# Экспорт всех конфигураций
docker compose run --rm c4-config-exporter \
  c4_config_exporter --ip 192.168.122.200 -u admin:password \
  get_all_cgw_configs --output_path ./
```

## Использование CLI

```
c4_config_exporter [-h] -u CREDS --ip IP [--port PORT]
                   [--client-cert CLIENT_CERT] [--client-key CLIENT_KEY]
                   [--ca-cert CA_CERT] [--output_path OUTPUT_PATH]
                   [--hwserial HWSERIAL] [--with_confidential_data]
                   {get_all_cgw_configs,get_cgw_config_by_hwserial,print_cgws}
```

### Команды

| Команда | Описание |
|---|---|
| `print_cgws` | Вывод списка всех УБ с hwserial |
| `get_all_cgw_configs` | Экспорт конфигураций всех УБ в файлы |
| `get_cgw_config_by_hwserial` | Экспорт конфигурации конкретного УБ |

### Параметры

| Параметр | Описание |
|---|---|
| `-u, --creds` | Реквизиты в формате `user:pass` (обязательный) |
| `--ip` | IP-адрес сервера (обязательный) |
| `--port` | Порт сервера (по умолчанию: 444) |
| `--client-cert` | Клиентский сертификат для mTLS (PEM) |
| `--client-key` | Закрытый ключ клиента для mTLS (PEM) |
| `--ca-cert` | CA-сертификат для проверки сервера |
| `--output_path` | Директория для сохранения экспортированных конфигураций |
| `--hwserial` | hwserial УБ для выборочного экспорта |
| `--with_confidential_data` | Включить конфиденциальные поля (по умолчанию: выключено) |

## API-эндпоинты

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/health` | Проверка доступности сервиса |
| GET | `/api/gateways` | Список УБ из Континент 4 |
| GET | `/api/configs` | Экспорт конфигураций всех УБ |
| GET | `/api/config/{hwserial}` | Экспорт конфигурации конкретного УБ |

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `C4_HOST` | `192.168.122.200` | IP-адрес сервера Континент 4 |
| `C4_PORT` | `444` | Порт сервера Континент 4 |
| `C4_USER` | `admin` | Имя пользователя |
| `C4_PASSWORD` | - | Пароль |
| `C4_API_PORT` | `8001` | Порт FastAPI-сервиса |

## Зависимости

- `c4_lib` — библиотека для работы с API Континент 4 с поддержкой ГОСТ TLS
- `urllib3 <2` — HTTP-клиент (требуется v1.x для настройки ГОСТ-шифров)
- `requests` — HTTP-сессии
- `fastapi` — фреймворк API (для режима сервиса)
- `uvicorn` — ASGI-сервер (для режима сервиса)
