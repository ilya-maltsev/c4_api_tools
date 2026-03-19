import json
import os
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import (
    ConfigImport, Gateway, Domain, NetworkInterface, StaticRoute,
    FirewallRule, Certificate, AdminUser, VPNConfig, DDoSProtection,
    DDoSRule, AppException, PasswordPolicy, ServiceComponent,
)
from .importer import import_config_json


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


def interfaces_view(request):
    interfaces = NetworkInterface.objects.all()
    return render(request, 'dashboard/interfaces.html', {
        'interfaces': interfaces,
        'page': 'interfaces',
    })


def routes_view(request):
    routes = StaticRoute.objects.all()
    return render(request, 'dashboard/routes.html', {
        'routes': routes,
        'page': 'routes',
    })


def services_view(request):
    services = ServiceComponent.objects.all()
    return render(request, 'dashboard/services.html', {
        'services': services,
        'page': 'services',
    })


def firewall_rules_view(request):
    rules = FirewallRule.objects.all()
    return render(request, 'dashboard/firewall_rules.html', {
        'rules': rules,
        'page': 'firewall_rules',
    })


def ddos_view(request):
    ddos = DDoSProtection.objects.first()
    ddos_rules = DDoSRule.objects.all()
    return render(request, 'dashboard/ddos.html', {
        'ddos': ddos,
        'ddos_rules': ddos_rules,
        'page': 'ddos',
    })


def app_exceptions_view(request):
    exceptions = AppException.objects.all()
    return render(request, 'dashboard/app_exceptions.html', {
        'exceptions': exceptions,
        'page': 'app_exceptions',
    })


def vpn_view(request):
    vpns = VPNConfig.objects.all()
    return render(request, 'dashboard/vpn.html', {
        'vpns': vpns,
        'page': 'vpn',
    })


def certificates_view(request):
    certs = Certificate.objects.all()
    return render(request, 'dashboard/certificates.html', {
        'certs': certs,
        'page': 'certificates',
    })


def admins_view(request):
    admins = AdminUser.objects.all()
    return render(request, 'dashboard/admins.html', {
        'admins': admins,
        'page': 'admins',
    })


def password_policy_view(request):
    policy = PasswordPolicy.objects.first()
    return render(request, 'dashboard/password_policy.html', {
        'policy': policy,
        'page': 'password_policy',
    })


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
