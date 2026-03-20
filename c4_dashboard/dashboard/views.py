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
    DDoSRule, NetworkObject, AppException, PasswordPolicy, ServiceComponent,
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
def firewall_rules_view(request):
    rules = FirewallRule.objects.prefetch_related('source_objects', 'destination_objects').all()
    return render(request, 'dashboard/firewall_rules.html', {
        'rules': rules,
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
def import_config_view(request):
    imports = ConfigImport.objects.all()[:20]
    if request.method == 'POST':
        uploaded = request.FILES.get('config_file')
        if uploaded:
            data = json.loads(uploaded.read().decode('utf-8'))
            ci = import_config_json(data, uploaded.name)
            messages.success(request, f"Imported {ci.objects_count} objects from {ci.gateway_name}")
            return redirect('import_config')
        messages.error(request, "No file selected")
    return render(request, 'dashboard/import.html', {
        'imports': imports,
        'page': 'import_config',
    })


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


@login_required
def rule_counters_api(request):
    interval = request.GET.get('interval', '1h')
    if interval not in INTERVAL_MAP:
        return JsonResponse({'error': 'invalid interval'}, status=400)

    db_host = settings.C4_MONITOR_DB_HOST
    if not db_host:
        return JsonResponse({'error': 'C4_MONITOR_DB_HOST not configured'}, status=503)

    try:
        conn = psycopg2.connect(
            host=db_host,
            port=settings.C4_MONITOR_DB_PORT,
            dbname=settings.C4_MONITOR_DB_NAME,
            user=settings.C4_MONITOR_DB_USER,
            password=settings.C4_MONITOR_DB_PASSWORD,
            connect_timeout=5,
        )
        cur = conn.cursor()
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
