import json
import os
import ssl
import urllib.request
import urllib.error
import psycopg2
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import (
    ConfigImport, Gateway, Domain, NetworkInterface, StaticRoute,
    FirewallRule, Certificate, AdminUser, VPNConfig, DDoSProtection,
    DDoSRule, NetworkObject, ServiceObject, AppException, PasswordPolicy,
    ServiceComponent, CusDbSettings,
)
from .importer import import_config_json


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get('next', 'dashboard'))
        error = True
    return render(request, 'dashboard/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard_view(request):
    gateway = Gateway.objects.first()
    domain = Domain.objects.first()
    interfaces = NetworkInterface.objects.all()
    certs = Certificate.objects.all()
    rules = FirewallRule.objects.all()
    vpns = VPNConfig.objects.all()
    ddos = DDoSProtection.objects.first()
    services = ServiceComponent.objects.all()
    last_import = ConfigImport.objects.first()

    enabled_services = services.filter(is_enabled=True).count()
    total_services = services.count()

    return render(request, 'dashboard/dashboard.html', {
        'gateway': gateway,
        'domain': domain,
        'interfaces': interfaces,
        'certs': certs,
        'rules_count': rules.count(),
        'vpns': vpns,
        'ddos': ddos,
        'enabled_services': enabled_services,
        'total_services': total_services,
        'last_import': last_import,
        'page': 'dashboard',
    })


@login_required
def interfaces_view(request):
    interfaces = NetworkInterface.objects.all()
    return render(request, 'dashboard/interfaces.html', {
        'interfaces': interfaces,
        'page': 'interfaces',
    })


@login_required
def routes_view(request):
    routes = StaticRoute.objects.all()
    return render(request, 'dashboard/routes.html', {
        'routes': routes,
        'page': 'routes',
    })


@login_required
def services_view(request):
    services = ServiceComponent.objects.all()
    return render(request, 'dashboard/services.html', {
        'services': services,
        'page': 'services',
    })


@login_required
def network_objects_view(request):
    objects = NetworkObject.objects.all()
    return render(request, 'dashboard/network_objects.html', {
        'objects': objects,
        'page': 'network_objects',
    })


@login_required
def service_objects_view(request):
    services = ServiceObject.objects.all()
    return render(request, 'dashboard/service_objects.html', {
        'services': services,
        'page': 'service_objects',
    })


@login_required
def firewall_rules_view(request):
    rules = FirewallRule.objects.prefetch_related('source_objects', 'destination_objects', 'source_groups', 'destination_groups', 'services').exclude(position=0)
    cus_ok, cus_msg = test_cus_db_connection()
    return render(request, 'dashboard/firewall_rules.html', {
        'rules': rules,
        'cus_connected': cus_ok,
        'cus_status': cus_msg,
        'page': 'firewall_rules',
    })


@login_required
def ddos_view(request):
    ddos = DDoSProtection.objects.first()
    ddos_rules = DDoSRule.objects.all()
    return render(request, 'dashboard/ddos.html', {
        'ddos': ddos,
        'ddos_rules': ddos_rules,
        'page': 'ddos',
    })


@login_required
def app_exceptions_view(request):
    exceptions = AppException.objects.all()
    return render(request, 'dashboard/app_exceptions.html', {
        'exceptions': exceptions,
        'page': 'app_exceptions',
    })


@login_required
def vpn_view(request):
    vpns = VPNConfig.objects.all()
    return render(request, 'dashboard/vpn.html', {
        'vpns': vpns,
        'page': 'vpn',
    })


@login_required
def certificates_view(request):
    certs = Certificate.objects.all()
    return render(request, 'dashboard/certificates.html', {
        'certs': certs,
        'page': 'certificates',
    })


@login_required
def admins_view(request):
    admins = AdminUser.objects.all()
    return render(request, 'dashboard/admins.html', {
        'admins': admins,
        'page': 'admins',
    })


@login_required
def password_policy_view(request):
    policy = PasswordPolicy.objects.first()
    return render(request, 'dashboard/password_policy.html', {
        'policy': policy,
        'page': 'password_policy',
    })


@login_required
def config_view(request):
    imports = ConfigImport.objects.all()[:20]
    if request.method == 'POST':
        uploaded = request.FILES.get('config_file')
        if uploaded:
            data = json.loads(uploaded.read().decode('utf-8'))
            ci = import_config_json(data, uploaded.name)
            messages.success(request, f"Imported {ci.objects_count} objects from {ci.gateway_name}")
            return redirect('configuration')
        messages.error(request, "No file selected")
    return render(request, 'dashboard/configuration.html', {
        'imports': imports,
        'page': 'configuration',
    })


import_config_view = config_view


@login_required
def export_configs_api(request):
    import io
    import tarfile
    from datetime import datetime
    from django.http import HttpResponse

    api_url = settings.C4_EXPORTER_API_URL.rstrip('/')
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.set_ciphers("ALL:@SECLEVEL=0")
        ca_cert = getattr(settings, 'C4_CA_CERT', '')
        client_cert = getattr(settings, 'C4_CLIENT_CERT', '')
        client_key = getattr(settings, 'C4_CLIENT_KEY', '')
        if ca_cert and os.path.exists(ca_cert):
            ctx.load_verify_locations(ca_cert)
        else:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        if client_cert and os.path.exists(client_cert):
            ctx.load_cert_chain(client_cert, client_key)

        req = urllib.request.Request(f"{api_url}/api/configs", method='GET')
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=502)

    gateways = data.get('gateways', [])
    if not gateways:
        return JsonResponse({'error': 'No configs returned'}, status=404)

    buf = io.BytesIO()
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for gw in gateways:
            name = gw.get('name', gw.get('hwserial', 'unknown'))
            config_json = json.dumps(gw.get('config', {}), indent=2, ensure_ascii=False).encode('utf-8')
            info = tarfile.TarInfo(name=f"{name}_config.json")
            info.size = len(config_json)
            tar.addfile(info, io.BytesIO(config_json))

    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/gzip')
    response['Content-Disposition'] = f'attachment; filename="c4_configs_{ts}.tar.gz"'
    return response


@login_required
def sync_from_c4_view(request):
    if request.method != 'POST':
        return redirect('dashboard')

    api_url = settings.C4_EXPORTER_API_URL.rstrip('/')

    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.set_ciphers("ALL:@SECLEVEL=0")
        ca_cert = getattr(settings, 'C4_CA_CERT', '')
        client_cert = getattr(settings, 'C4_CLIENT_CERT', '')
        client_key = getattr(settings, 'C4_CLIENT_KEY', '')
        if ca_cert and os.path.exists(ca_cert):
            ctx.load_verify_locations(ca_cert)
        else:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        if client_cert and os.path.exists(client_cert):
            ctx.load_cert_chain(client_cert, client_key)

        req = urllib.request.Request(f"{api_url}/api/configs", method='GET')
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.URLError as e:
        messages.error(request, f"Cannot reach C4 Exporter API: {e}")
        return redirect(request.POST.get('next', 'dashboard'))
    except Exception as e:
        messages.error(request, f"Sync failed: {e}")
        return redirect(request.POST.get('next', 'dashboard'))

    gateways = data.get('gateways', [])
    if not gateways:
        messages.warning(request, "No gateway configs returned from C4")
        return redirect(request.POST.get('next', 'dashboard'))

    total = 0
    names = []
    for gw in gateways:
        config = gw.get('config', {})
        name = gw.get('name', gw.get('hwserial', 'unknown'))
        ci = import_config_json(config, f"api-sync:{name}")
        total += ci.objects_count
        names.append(ci.gateway_name or name)

    messages.success(request, f"Synced {len(gateways)} gateway(s): {', '.join(names)} ({total} objects)")
    return redirect(request.POST.get('next', 'dashboard'))


INTERVAL_MAP = {
    '5m': "NOW() - INTERVAL '5 minutes'",
    '1h': "NOW() - INTERVAL '1 hour'",
    '1d': "NOW() - INTERVAL '1 day'",
    '1w': "NOW() - INTERVAL '7 days'",
}


def get_cus_db_connection():
    cfg = CusDbSettings.get()
    if not cfg or not cfg.host:
        return None
    return psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.dbname,
        user=cfg.user,
        password=cfg.password,
        connect_timeout=5,
    )


def test_cus_db_connection():
    try:
        conn = get_cus_db_connection()
        if not conn:
            return False, 'not_configured'
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return True, 'ok'
    except Exception as e:
        return False, str(e)


@login_required
def rule_counters_api(request):
    interval = request.GET.get('interval', '1h')
    if interval not in INTERVAL_MAP:
        return JsonResponse({'error': 'invalid interval'}, status=400)

    conn = get_cus_db_connection()
    if not conn:
        return JsonResponse({'error': 'C4_MONITOR_DB_HOST not configured'}, status=503)

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'ids_log'
        """)
        if not cur.fetchone():
            cur.close()
            conn.close()
            return JsonResponse({'error': 'Table "ids_log" not found in CUS database'}, status=404)
        cur.execute(f"""
            SELECT signature_id, rule_name, COUNT(*) as cnt
            FROM ids_log
            WHERE event_type = 'firewall'
              AND "timestamp" > {INTERVAL_MAP[interval]}
            GROUP BY signature_id, rule_name
            ORDER BY cnt DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        counters = {}
        for sig_id, rule_name, cnt in rows:
            key = rule_name or str(sig_id)
            counters[key] = counters.get(key, 0) + cnt

        return JsonResponse({'interval': interval, 'counters': counters})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=502)


@login_required
def maintenance_view(request):
    from .models import (ConfigImport, Gateway, Domain, NetworkInterface,
        StaticRoute, FirewallRule, Certificate, AdminUser, VPNConfig,
        DDoSProtection, DDoSRule, NetworkObject, ServiceObject, ObjectGroup,
        AppException, PasswordPolicy, ServiceComponent)
    counts = {
        'gateways': Gateway.objects.count(),
        'domains': Domain.objects.count(),
        'interfaces': NetworkInterface.objects.count(),
        'routes': StaticRoute.objects.count(),
        'firewall_rules': FirewallRule.objects.count(),
        'network_objects': NetworkObject.objects.count(),
        'service_objects': ServiceObject.objects.count(),
        'object_groups': ObjectGroup.objects.count(),
        'certificates': Certificate.objects.count(),
        'admins': AdminUser.objects.count(),
        'vpn': VPNConfig.objects.count(),
        'ddos_rules': DDoSRule.objects.count(),
        'app_exceptions': AppException.objects.count(),
        'services': ServiceComponent.objects.count(),
        'imports': ConfigImport.objects.count(),
    }
    total = sum(counts.values())
    cus_db = CusDbSettings.get_or_empty()
    cus_ok, cus_msg = test_cus_db_connection()
    return render(request, 'dashboard/maintenance.html', {
        'counts': counts,
        'total': total,
        'cus_db': cus_db,
        'cus_connected': cus_ok,
        'cus_status': cus_msg,
        'page': 'maintenance',
    })


@login_required
def clear_db_view(request):
    if request.method != 'POST':
        return redirect('maintenance')

    from .models import (ConfigImport, Gateway, Domain, NetworkInterface,
        StaticRoute, FirewallRule, Certificate, AdminUser, VPNConfig,
        DDoSProtection, DDoSRule, NetworkObject, ServiceObject, ObjectGroup,
        AppException, PasswordPolicy, ServiceComponent)

    deleted = 0
    for model in [FirewallRule, NetworkObject, ServiceObject, ObjectGroup,
                  AppException, DDoSRule, DDoSProtection, ServiceComponent,
                  Certificate, AdminUser, VPNConfig, PasswordPolicy,
                  StaticRoute, NetworkInterface, Domain, Gateway, ConfigImport]:
        count, _ = model.objects.all().delete()
        deleted += count

    messages.success(request, f"Database cleared: {deleted} records deleted")
    return redirect('maintenance')


@login_required
def save_cus_db_view(request):
    if request.method != 'POST':
        return redirect('maintenance')
    obj = CusDbSettings.get()
    if not obj:
        obj = CusDbSettings()
    obj.host = request.POST.get('host', '').strip()
    obj.port = request.POST.get('port', '5432').strip()
    obj.dbname = request.POST.get('dbname', 'cus-logs').strip()
    obj.user = request.POST.get('user', 'monitoring').strip()
    obj.password = request.POST.get('password', '').strip()
    obj.save()
    messages.success(request, f"CUS database settings saved: {obj}")
    return redirect('maintenance')


@login_required
def test_cus_db_api(request):
    ok, msg = test_cus_db_connection()
    return JsonResponse({'connected': ok, 'message': msg})


@login_required
def cus_db_tables_api(request):
    conn = get_cus_db_connection()
    if not conn:
        return JsonResponse({'error': 'not_configured'}, status=503)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                t.tablename AS name,
                pg_size_pretty(pg_total_relation_size(quote_ident(t.tablename))) AS size,
                pg_total_relation_size(quote_ident(t.tablename)) AS size_bytes,
                COALESCE(s.n_live_tup, 0) AS rows
            FROM pg_tables t
            LEFT JOIN pg_stat_user_tables s ON s.relname = t.tablename
            WHERE t.schemaname = 'public'
            ORDER BY pg_total_relation_size(quote_ident(t.tablename)) DESC
        """)
        tables = []
        for name, size, size_bytes, rows in cur.fetchall():
            has_ts = False
            cur2 = conn.cursor()
            cur2.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s AND column_name = 'timestamp'
            """, [name])
            has_ts = cur2.fetchone() is not None
            cur2.close()
            tables.append({
                'name': name,
                'size': size,
                'size_bytes': size_bytes,
                'rows': rows,
                'has_timestamp': has_ts,
            })
        cur.close()
        conn.close()
        return JsonResponse({'tables': tables})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=502)


@login_required
def cus_db_cleanup_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    table = request.POST.get('table', '')
    days = request.POST.get('days', '7')

    try:
        days = int(days)
        if days < 1:
            return JsonResponse({'error': 'days must be >= 1'}, status=400)
    except ValueError:
        return JsonResponse({'error': 'invalid days'}, status=400)

    conn = get_cus_db_connection()
    if not conn:
        return JsonResponse({'error': 'not_configured'}, status=503)

    try:
        cur = conn.cursor()
        # Verify table exists and has timestamp column
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s AND column_name = 'timestamp'
        """, [table])
        if not cur.fetchone():
            cur.close()
            conn.close()
            return JsonResponse({'error': f'Table "{table}" not found or has no timestamp column'}, status=404)

        # Delete in batches
        total_deleted = 0
        while True:
            cur.execute(f"""
                WITH to_delete AS (
                    SELECT id FROM {table}
                    WHERE "timestamp" < NOW() - INTERVAL '{days} days'
                    LIMIT 10000
                    FOR UPDATE SKIP LOCKED
                ),
                deleted AS (
                    DELETE FROM {table}
                    WHERE id IN (SELECT id FROM to_delete)
                    RETURNING 1
                )
                SELECT count(*) FROM deleted
            """)
            batch = cur.fetchone()[0]
            conn.commit()
            if batch == 0:
                break
            total_deleted += batch

        # Vacuum
        old_isolation = conn.isolation_level
        conn.set_isolation_level(0)
        cur.execute(f"VACUUM ANALYZE {table}")
        conn.set_isolation_level(old_isolation)

        cur.close()
        conn.close()
        return JsonResponse({'deleted': total_deleted, 'table': table, 'days': days})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=502)


LOG_TABLES = {
    'log': {
        'columns': ['id', 'timestamp', 'syslogseverity', 'hostname', 'sourcename', 'message'],
        'order': '"timestamp" DESC',
    },
    'management_log': {
        'columns': ['id', 'timestamp', 'syslogseverity', 'hostname', 'category', 'subject', 'action'],
        'order': '"timestamp" DESC',
    },
    'ids_log': {
        'columns': ['id', 'timestamp', 'event_type', 'src_ip', 'dest_ip', 'proto', 'action', 'signature', 'rule_name', 'hostname'],
        'order': '"timestamp" DESC',
    },
}


@login_required
def logs_view(request):
    cus_ok, cus_msg = test_cus_db_connection()
    return render(request, 'dashboard/logs.html', {
        'cus_connected': cus_ok,
        'cus_status': cus_msg,
        'page': 'logs',
    })


@login_required
def logs_api(request):
    table = request.GET.get('table', 'log')
    if table not in LOG_TABLES:
        return JsonResponse({'error': 'invalid table'}, status=400)

    limit = min(int(request.GET.get('limit', 100)), 1000)
    interval = request.GET.get('interval', '1h')
    if interval not in INTERVAL_MAP:
        return JsonResponse({'error': 'invalid interval'}, status=400)

    conn = get_cus_db_connection()
    if not conn:
        return JsonResponse({'error': 'C4_MONITOR_DB_HOST not configured'}, status=503)

    try:
        cur = conn.cursor()

        # Check if table exists
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        """, [table])
        if not cur.fetchone():
            cur.close()
            conn.close()
            return JsonResponse({'error': f'Table "{table}" does not exist in CUS database'}, status=404)

        # Get actual columns in the table
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, [table])
        existing_cols = {row[0] for row in cur.fetchall()}

        # Use only columns that exist
        cfg = LOG_TABLES[table]
        cols = [c for c in cfg['columns'] if c in existing_cols]
        if not cols:
            cols = sorted(existing_cols)

        cols_sql = ', '.join(f'"{c}"' for c in cols)
        order_col = '"timestamp"' if 'timestamp' in existing_cols else f'"{cols[0]}"'
        where = f'WHERE "timestamp" > {INTERVAL_MAP[interval]}' if 'timestamp' in existing_cols else ''
        cur.execute(f"SELECT {cols_sql} FROM {table} {where} ORDER BY {order_col} DESC LIMIT {limit}")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        records = []
        for row in rows:
            record = {}
            for i, col in enumerate(cols):
                val = row[i]
                record[col] = str(val) if val is not None else ''
            records.append(record)

        return JsonResponse({
            'table': table,
            'interval': interval,
            'columns': cols,
            'records': records,
            'count': len(records),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=502)
