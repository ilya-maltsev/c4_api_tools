from django.contrib import admin
from .models import (
    ConfigImport, Gateway, Domain, NetworkInterface, StaticRoute,
    FirewallRule, Certificate, AdminUser, VPNConfig, DDoSProtection,
    DDoSRule, NetworkObject, ServiceObject, ObjectGroup,
    AppException, PasswordPolicy, ServiceComponent,
)

admin.site.register(ConfigImport)
admin.site.register(Gateway)
admin.site.register(Domain)
admin.site.register(NetworkInterface)
admin.site.register(StaticRoute)
admin.site.register(FirewallRule)
admin.site.register(Certificate)
admin.site.register(AdminUser)
admin.site.register(VPNConfig)
admin.site.register(DDoSProtection)
admin.site.register(DDoSRule)
admin.site.register(NetworkObject)
admin.site.register(ServiceObject)
admin.site.register(ObjectGroup)
admin.site.register(AppException)
admin.site.register(PasswordPolicy)
admin.site.register(ServiceComponent)
