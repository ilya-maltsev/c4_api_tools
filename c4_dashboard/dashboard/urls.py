from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),
    path('network/interfaces/', views.interfaces_view, name='interfaces'),
    path('network/routes/', views.routes_view, name='routes'),
    path('network/services/', views.services_view, name='services'),
    path('firewall/rules/', views.firewall_rules_view, name='firewall_rules'),
    path('security/ddos/', views.ddos_view, name='ddos'),
    path('security/app-exceptions/', views.app_exceptions_view, name='app_exceptions'),
    path('vpn/', views.vpn_view, name='vpn'),
    path('certificates/', views.certificates_view, name='certificates'),
    path('system/admins/', views.admins_view, name='admins'),
    path('system/password-policy/', views.password_policy_view, name='password_policy'),
    path('import/', views.import_config_view, name='import_config'),
    path('sync/', views.sync_from_c4_view, name='sync_from_c4'),
]
