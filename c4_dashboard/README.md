# C4 Dashboard

Веб-панель администрирования для мониторинга узлов безопасности Континент 4. Построена на Django, использует DataTables для фильтрации данных, стиль интерфейса аналогичен FortiGate.

## Возможности

- Обзорная панель: информация о шлюзе, интерфейсы, сертификаты, статус сервисов
- Сеть: интерфейсы, статические маршруты, сетевые сервисы
- Политики и объекты: правила межсетевого экрана, исключения приложений
- Безопасность: правила защиты от DDoS, сертификаты
- VPN: конфигурация L3 IPsec и L2 VPN
- Система: учетные записи администраторов, парольная политика
- Импорт данных: загрузка JSON-файлов конфигурации или синхронизация напрямую из Континент 4 через API c4_config_exporter

## Архитектура

```
                      nginx :8443 (ГОСТ + RSA TLS)
                             |
Браузер -----> nginx ------> Django (c4_dashboard) :8000
                                  |
                                  |--> PostgreSQL :5432 (хранение данных)
                                  |
                                  |--> nginx :8444 (ГОСТ mTLS)
                                          |
                                          |--> FastAPI :8001 (c4_config_exporter API)
                                                    |
                                                    |--> Континент 4 :444 (ГОСТ TLS)
```

- Порт `:8443` — единый порт для доступа к панели, поддерживает одновременно ГОСТ и RSA шифры
- Порт `:8444` — внутренний API экспортера, доступ только по ГОСТ mTLS с клиентским сертификатом
- Все сертификаты (CA, серверные, клиентские) генерируются автоматически при первом запуске контейнера nginx

## Структура проекта

```
c4_dashboard/
├── config/              # Настройки Django, urls, wsgi
├── dashboard/
│   ├── models.py        # Шлюз, интерфейс, правила МЭ, сертификаты, VPN, DDoS и др.
│   ├── views.py         # Представления для всех страниц + синхронизация с К4
│   ├── urls.py          # Маршрутизация URL
│   ├── importer.py      # Импортер JSON-конфигураций
│   ├── admin.py         # Регистрация моделей в Django admin
│   ├── templates/dashboard/
│   │   ├── base.html    # Макет: темная боковая панель, DataTables
│   │   ├── dashboard.html
│   │   ├── interfaces.html
│   │   ├── routes.html
│   │   ├── services.html
│   │   ├── firewall_rules.html
│   │   ├── ddos.html
│   │   ├── app_exceptions.html
│   │   ├── vpn.html
│   │   ├── certificates.html
│   │   ├── admins.html
│   │   ├── password_policy.html
│   │   └── import.html
│   └── static/dashboard/
│       └── style.css
├── requirements.txt
└── manage.py
```

## Предварительные требования

Все сервисы запускаются в Docker-контейнерах. Необходимо:

- Docker с плагином Compose
- Запущенный контейнер PostgreSQL (`dev_env/dev-postgresql`)
- Запущенный контейнер nginx с ГОСТ (`dev_env/dev-nginx-gost`)
- Запущенный контейнер c4_config_exporter API (`dev_env/dev-c4-config-exporter`)

## Быстрый старт

### 1. Запуск PostgreSQL

```bash
cd dev_env/dev-postgresql
docker compose up -d

# Создание базы данных мониторинга (только при первом запуске)
docker exec dev-postgresql psql -U postgres \
  -c "CREATE USER monitoring WITH PASSWORD 'monitoring';" \
  -c "CREATE DATABASE monitoring OWNER monitoring;" \
  -c "GRANT ALL PRIVILEGES ON DATABASE monitoring TO monitoring;"
```

### 2. Запуск nginx с ГОСТ (генерация PKI)

```bash
cd dev_env/dev-nginx-gost
docker compose build
docker compose up -d
```

При первом запуске автоматически генерируются:
- ГОСТ CA-сертификат и ключ
- ГОСТ-сертификаты для nginx, dashboard и exporter (серверные + клиентские)
- RSA CA-сертификат и RSA-сертификат для nginx (для обычных браузеров)

Панель будет доступна по адресу `https://127.0.0.1:8443` (ГОСТ + RSA).

### 3. Запуск c4_config_exporter API

```bash
cd dev_env/dev-c4-config-exporter
docker compose up -d
```

API экспортера доступен через nginx по адресу `https://127.0.0.1:8444` (ГОСТ mTLS).

### 4. Запуск панели управления

```bash
cd dev_env/dev-c4-dashboard
docker compose build
docker compose up -d
```

Миграции базы данных применяются автоматически при запуске контейнера.

## Импорт данных

### Через веб-интерфейс

1. Откройте `https://127.0.0.1:8443/import/`
2. Нажмите **Sync from C4** для загрузки конфигураций напрямую из Континент 4
3. Или загрузите JSON-файл конфигурации, экспортированный через `c4_config_exporter`

### Через главную панель

Нажмите кнопку **Sync from Continent 4** на главной странице панели.

## Переменные окружения

### Панель управления (`dev-c4-dashboard`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DB_HOST` | `127.0.0.1` | Хост PostgreSQL |
| `DB_PORT` | `5432` | Порт PostgreSQL |
| `DB_NAME` | `monitoring` | Имя базы данных |
| `DB_USER` | `monitoring` | Пользователь БД |
| `DB_PASSWORD` | `monitoring` | Пароль БД |
| `C4_EXPORTER_API_URL` | `https://127.0.0.1:8444` | URL FastAPI c4_config_exporter |
| `C4_CA_CERT` | `/etc/c4-certs/ca.crt` | CA-сертификат для проверки сервера |
| `C4_CLIENT_CERT` | `/etc/c4-certs/dashboard.crt` | Клиентский сертификат для mTLS |
| `C4_CLIENT_KEY` | `/etc/c4-certs/dashboard.key` | Закрытый ключ клиента |
| `DJANGO_DEBUG` | `True` | Режим отладки Django |
| `DJANGO_ALLOWED_HOSTS` | `*` | Разрешенные хосты |
| `CSRF_TRUSTED_ORIGINS` | `https://127.0.0.1:8443,...` | Доверенные источники для CSRF |

### API экспортера (`dev-c4-config-exporter`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `C4_HOST` | `192.168.122.200` | IP-адрес сервера Континент 4 |
| `C4_PORT` | `444` | Порт сервера Континент 4 |
| `C4_USER` | `admin` | Имя пользователя К4 |
| `C4_PASSWORD` | `AsdfgTrewq1@` | Пароль К4 |
| `C4_API_PORT` | `8001` | Порт FastAPI-сервиса |

## API-эндпоинты экспортера

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/health` | Проверка доступности сервиса |
| GET | `/api/gateways` | Список всех УБ из К4 |
| GET | `/api/configs` | Экспорт конфигураций всех УБ |
| GET | `/api/config/{hwserial}` | Экспорт конфигурации конкретного УБ |

## Модели данных

Панель хранит следующие сущности, извлеченные из JSON-конфигурации К4:

- **Gateway** — узел безопасности (УБ): платформа, серийный номер
- **Domain** — домен управления
- **NetworkInterface** — сетевые интерфейсы с адресами
- **StaticRoute** — записи таблицы маршрутизации
- **FirewallRule** — правила межсетевого экрана
- **Certificate** — сертификаты X.509 (ГОСТ)
- **AdminUser** — учетные записи администраторов
- **VPNConfig** — настройки L3 IPsec и L2 VPN
- **DDoSProtection** — режим и действие защиты от DDoS
- **DDoSRule** — правила обнаружения отдельных типов атак (16 типов)
- **AppException** — исключения белого списка приложений
- **PasswordPolicy** — политика сложности и срока действия паролей
- **ServiceComponent** — сетевые сервисы (SNMP, NTP, DNS, LLDP и др.)
- **ConfigImport** — история импортов конфигураций
