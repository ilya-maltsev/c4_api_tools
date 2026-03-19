# C4 Dashboard

Web-based admin dashboard for monitoring Continent 4 security gateways. Built with Django, uses DataTables for data filtering, styled after FortiGate web UI.

## Features

- Dashboard overview: gateway info, interfaces, certificates, services status
- Network: interfaces, static routes, service components
- Policy & Objects: firewall rules, application exceptions
- Security: DDoS protection rules, certificates
- VPN: L3 IPsec and L2 VPN configuration
- System: administrator accounts, password policy
- Data import: upload JSON config files or sync directly from Continent 4 via c4_config_exporter API

## Architecture

```
Browser :8000 --> Django (c4_dashboard)
                      |
                      |--> PostgreSQL :5432 (data storage)
                      |
                      |--> FastAPI :8001 (c4_config_exporter API)
                                |
                                |--> Continent 4 :444 (GOST TLS)
```

## Project Structure

```
c4_dashboard/
├── config/              # Django settings, urls, wsgi
├── dashboard/
│   ├── models.py        # Gateway, Interface, FW Rule, Cert, VPN, DDoS, etc.
│   ├── views.py         # Views for all dashboard pages + sync from C4
│   ├── urls.py          # URL routing
│   ├── importer.py      # JSON config importer
│   ├── admin.py         # Django admin registrations
│   ├── templates/dashboard/
│   │   ├── base.html    # Layout: dark sidebar, DataTables
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

## Prerequisites

All services run in Docker containers. Required:

- Docker with Compose plugin
- Running PostgreSQL container (`dev_env/dev-postgresql`)
- Running c4_config_exporter API container (`dev_env/dev-c4-config-exporter`)

## Quick Start

### 1. Start PostgreSQL

```bash
cd dev_env/dev-postgresql
docker compose up -d

# Create the monitoring database (first run only)
docker exec dev-postgresql psql -U postgres \
  -c "CREATE USER monitoring WITH PASSWORD 'monitoring';" \
  -c "CREATE DATABASE monitoring OWNER monitoring;" \
  -c "GRANT ALL PRIVILEGES ON DATABASE monitoring TO monitoring;"
```

### 2. Start c4_config_exporter API

```bash
cd dev_env/dev-c4-config-exporter
docker compose up -d
```

The exporter API will be available at `http://127.0.0.1:8001`.

### 3. Start the Dashboard

```bash
cd dev_env/dev-c4-dashboard
docker compose build
docker compose up -d
```

The dashboard will be available at `http://127.0.0.1:8000`.

Migrations are applied automatically on container start.

## Importing Data

### Via Web UI

1. Open `http://127.0.0.1:8000/import/`
2. Click **Sync from C4** to pull configs directly from Continent 4
3. Or upload a JSON config file exported by `c4_config_exporter`

### Via Dashboard

Click the **Sync from Continent 4** button on the main dashboard page.

## Environment Variables

### Dashboard (`dev-c4-dashboard`)

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `127.0.0.1` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `monitoring` | Database name |
| `DB_USER` | `monitoring` | Database user |
| `DB_PASSWORD` | `monitoring` | Database password |
| `C4_EXPORTER_API_URL` | `http://127.0.0.1:8001` | c4_config_exporter FastAPI URL |
| `DJANGO_DEBUG` | `True` | Django debug mode |
| `DJANGO_ALLOWED_HOSTS` | `*` | Allowed hosts |
| `CSRF_TRUSTED_ORIGINS` | `http://127.0.0.1:8000,...` | Trusted origins for CSRF |

### Exporter API (`dev-c4-config-exporter`)

| Variable | Default | Description |
|---|---|---|
| `C4_HOST` | `192.168.122.200` | Continent 4 server IP |
| `C4_PORT` | `444` | Continent 4 server port |
| `C4_USER` | `admin` | C4 username |
| `C4_PASSWORD` | `AsdfgTrewq1@` | C4 password |
| `C4_API_PORT` | `8001` | FastAPI listen port |

## Exporter API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/gateways` | List all gateways from C4 |
| GET | `/api/configs` | Export all gateway configurations |
| GET | `/api/config/{hwserial}` | Export configuration for a specific gateway |

## Data Models

The dashboard stores the following entities parsed from C4 configuration JSON:

- **Gateway** — security gateway (CGW) info, platform, serial
- **Domain** — management domain
- **NetworkInterface** — ethernet interfaces with addresses
- **StaticRoute** — routing table entries
- **FirewallRule** — firewall policy rules
- **Certificate** — X.509 certificates (GOST)
- **AdminUser** — administrator accounts
- **VPNConfig** — L3 IPsec and L2 VPN settings
- **DDoSProtection** — DDoS protection mode and action
- **DDoSRule** — individual attack type detection rules (16 types)
- **AppException** — application whitelist exceptions
- **PasswordPolicy** — password complexity and expiration policy
- **ServiceComponent** — network services (SNMP, NTP, DNS, LLDP, etc.)
- **ConfigImport** — import history tracking
