# C4 Dashboard

Веб-панель конфигурации для узлов безопасности Континент 4. Построена на Django, стилизована под FortiGate/FortiManager, использует DataTables для фильтрации данных.

## Возможности

- Обзорная панель: информация о шлюзе, интерфейсы, сертификаты, статус сервисов
- Сеть: интерфейсы, статические маршруты, сетевые сервисы
- Политики и объекты: правила МЭ с онлайн-счетчиком срабатываний, исключения приложений
- Безопасность: правила защиты от DDoS, сертификаты (ГОСТ)
- VPN: конфигурация L3 IPsec и L2 VPN
- Система: учетные записи администраторов, парольная политика
- Импорт данных: синхронизация с Континент 4 через API или загрузка JSON-файлов
- Аутентификация: вход по логину/паролю (настраивается через переменные окружения)
- Локализация: русский (по умолчанию) и английский, переключение в интерфейсе
- Счетчик правил МЭ: онлайн-запрос к БД логов ЦУС с автообновлением (1 мин / 5 мин)

## Архитектура

```
                      nginx :8443 (ГОСТ + RSA TLS)
                             |
Браузер -----> nginx ------> Django (c4_dashboard) :8000
                                  |
                                  |--> PostgreSQL :5432 (хранение данных)
                                  |
                                  |--> PostgreSQL cus-logs (БД логов ЦУС, ids_log)
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
├── config/                    # Настройки Django, urls, wsgi
├── dashboard/
│   ├── models.py              # Шлюз, интерфейс, правила МЭ, сертификаты, VPN, DDoS и др.
│   ├── views.py               # Представления + синхронизация с К4 + API счетчиков
│   ├── urls.py                # Маршрутизация URL
│   ├── importer.py            # Импортер JSON-конфигураций
│   ├── admin.py               # Регистрация моделей в Django admin
│   ├── management/commands/
│   │   └── ensure_admin.py    # Создание/обновление админа из переменных окружения
│   ├── templates/dashboard/
│   │   ├── base.html          # Макет: боковая панель в стиле FortiGate, DataTables
│   │   ├── login.html         # Страница входа
│   │   ├── dashboard.html     # Обзорная панель
│   │   ├── interfaces.html    # Сетевые интерфейсы
│   │   ├── routes.html        # Статические маршруты
│   │   ├── services.html      # Сетевые сервисы
│   │   ├── firewall_rules.html # Правила МЭ со счетчиком
│   │   ├── ddos.html          # Защита от DDoS
│   │   ├── app_exceptions.html # Исключения приложений
│   │   ├── vpn.html           # Конфигурация VPN
│   │   ├── certificates.html  # Сертификаты
│   │   ├── admins.html        # Администраторы
│   │   ├── password_policy.html # Парольная политика
│   │   └── import.html        # Импорт конфигурации
│   └── static/dashboard/
│       └── style.css          # Стили в стиле FortiGate
├── locale/
│   └── ru/LC_MESSAGES/        # Русская локализация
├── requirements.txt
└── manage.py
```

## Предварительные требования

Все сервисы запускаются в Docker-контейнерах. Необходимо:

- Docker с плагином Compose
- Запущенный контейнер PostgreSQL (`dev_env/dev-postgresql`)
- Запущенный контейнер nginx с ГОСТ (`dev_env/dev-nginx-gost`)
- Запущенный контейнер c4_config_exporter API (`dev_env/dev-c4-config-exporter`)

Подробная инструкция по развертыванию — в [README.md](../README.md) корневого каталога.

## Переменные окружения

### Панель управления (`dev-c4-dashboard`)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DB_HOST` | `127.0.0.1` | Хост PostgreSQL (данные панели) |
| `DB_PORT` | `5432` | Порт PostgreSQL |
| `DB_NAME` | `monitoring` | Имя базы данных |
| `DB_USER` | `monitoring` | Пользователь БД |
| `DB_PASSWORD` | `monitoring` | Пароль БД |
| `DASHBOARD_ADMIN_USER` | `admin` | Логин администратора панели |
| `DASHBOARD_ADMIN_PASSWORD` | `admin` | Пароль администратора панели |
| `C4_MONITOR_DB_HOST` | - | Хост БД логов ЦУС (ids_log) |
| `C4_MONITOR_DB_PORT` | `5432` | Порт БД логов ЦУС |
| `C4_MONITOR_DB_NAME` | `cus-logs` | Имя БД логов ЦУС |
| `C4_MONITOR_DB_USER` | `monitoring` | Пользователь БД логов |
| `C4_MONITOR_DB_PASSWORD` | - | Пароль БД логов |
| `C4_EXPORTER_API_URL` | `https://127.0.0.1:8444` | URL FastAPI c4_config_exporter |
| `C4_CA_CERT` | `/etc/c4-certs/ca.crt` | CA-сертификат для mTLS |
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
| `C4_PASSWORD` | - | Пароль К4 |
| `C4_CLIENT_CERT` | `/etc/c4-certs/exporter.crt` | Клиентский сертификат для mTLS |
| `C4_CLIENT_KEY` | `/etc/c4-certs/exporter.key` | Закрытый ключ клиента |
| `C4_CA_CERT` | `/etc/c4-certs/ca.crt` | CA-сертификат |
| `C4_API_PORT` | `8001` | Порт FastAPI-сервиса |

## API-эндпоинты

### Экспортер (через nginx :8444, ГОСТ mTLS)

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/health` | Проверка доступности сервиса |
| GET | `/api/gateways` | Список всех УБ из К4 |
| GET | `/api/configs` | Экспорт конфигураций всех УБ |
| GET | `/api/config/{hwserial}` | Экспорт конфигурации конкретного УБ |

### Панель (внутренние)

| Метод | Эндпоинт | Описание |
|---|---|---|
| GET | `/api/rule-counters/?interval=` | Счетчики срабатываний правил МЭ |

Параметр `interval`: `5m`, `1h`, `1d`, `1w`

## Модели данных

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
