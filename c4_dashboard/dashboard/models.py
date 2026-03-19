from django.db import models


class ConfigImport(models.Model):
    imported_at = models.DateTimeField(auto_now_add=True)
    source_file = models.CharField(max_length=512)
    gateway_name = models.CharField(max_length=255, blank=True)
    objects_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-imported_at']

    def __str__(self):
        return f"{self.gateway_name} @ {self.imported_at:%Y-%m-%d %H:%M}"


class Gateway(models.Model):
    uuid = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    hwserial = models.CharField(max_length=64)
    platform_version = models.CharField(max_length=128, blank=True)
    platform_name = models.CharField(max_length=128, blank=True)
    timezone_name = models.CharField(max_length=128, blank=True)
    mode = models.CharField(max_length=64, blank=True)
    dhcp_status = models.CharField(max_length=32, blank=True)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    revision = models.CharField(max_length=128, blank=True)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.name} ({self.hwserial})"


class Domain(models.Model):
    uuid = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=64, blank=True)
    clid = models.CharField(max_length=64, blank=True)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name


class NetworkInterface(models.Model):
    uuid = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=True)
    mtu = models.IntegerField(default=1500)
    usage = models.CharField(max_length=64, blank=True)
    addresses = models.JSONField(default=list)
    permitted_protocols = models.JSONField(default=list)
    anti_spoofing = models.BooleanField(default=False)
    clear_df_bit = models.BooleanField(default=False)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name

    @property
    def address_display(self):
        return ', '.join(self.addresses) if self.addresses else '-'


class StaticRoute(models.Model):
    uuid = models.UUIDField(primary_key=True)
    dst_ip = models.CharField(max_length=64, blank=True)
    nexthop = models.CharField(max_length=64, blank=True)
    metric = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    def __str__(self):
        dst = self.dst_ip or '0.0.0.0/0'
        return f"{dst} via {self.nexthop}"


class FirewallRule(models.Model):
    uuid = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=True)
    position = models.IntegerField(default=0)
    rule_action = models.CharField(max_length=32)
    logging = models.BooleanField(default=False)
    passips = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)
    is_inverse_src = models.BooleanField(default=False)
    is_inverse_dst = models.BooleanField(default=False)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"#{self.position} {self.name} ({self.rule_action})"


class Certificate(models.Model):
    uuid = models.UUIDField(primary_key=True)
    subject = models.CharField(max_length=512)
    subject_full = models.TextField(blank=True)
    issuer = models.CharField(max_length=512, blank=True)
    role = models.CharField(max_length=32, blank=True)
    is_ca = models.BooleanField(default=False)
    startdate = models.CharField(max_length=64, blank=True)
    enddate = models.CharField(max_length=64, blank=True)
    gosttype = models.CharField(max_length=32, blank=True)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.subject} ({self.role})"


class AdminUser(models.Model):
    uuid = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    login = models.CharField(max_length=128)
    full_name = models.CharField(max_length=255, blank=True)
    email = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    organization = models.CharField(max_length=255, blank=True)
    occupation = models.CharField(max_length=255, blank=True)
    is_enabled = models.BooleanField(default=True)
    password_auth = models.BooleanField(default=True)
    cert_auth = models.BooleanField(default=False)
    password_expired_date = models.CharField(max_length=64, blank=True)
    created_at = models.CharField(max_length=64, blank=True)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.login} ({self.full_name})"


class VPNConfig(models.Model):
    uuid = models.UUIDField(primary_key=True)
    vpn_type = models.CharField(max_length=32)
    is_enabled = models.BooleanField(default=False)
    session_breakup = models.BooleanField(default=False)
    is_log_tunnel_status = models.BooleanField(default=False)
    dynamic_records_lifetime = models.IntegerField(default=0)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"VPN {self.vpn_type}"


class DDoSProtection(models.Model):
    uuid = models.UUIDField(primary_key=True)
    mode = models.CharField(max_length=64, blank=True)
    action = models.CharField(max_length=32, blank=True)
    blocking_time = models.IntegerField(default=0)
    clear_stats = models.BooleanField(default=False)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"DDoS Protection ({self.mode})"


class DDoSRule(models.Model):
    uuid = models.UUIDField(primary_key=True)
    attack_type = models.CharField(max_length=64)
    is_enabled = models.BooleanField(default=False)
    params = models.JSONField(default=dict)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    class Meta:
        ordering = ['attack_type']

    def __str__(self):
        return self.attack_type


class AppException(models.Model):
    uuid = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=True)
    vendor_id = models.CharField(max_length=128, blank=True)
    address = models.CharField(max_length=512, blank=True)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class PasswordPolicy(models.Model):
    uuid = models.UUIDField(primary_key=True)
    min_length = models.IntegerField(default=0)
    diff = models.IntegerField(default=0)
    passwords_diff = models.IntegerField(default=0)
    low_credit = models.IntegerField(default=0)
    up_credit = models.IntegerField(default=0)
    dig_credit = models.IntegerField(default=0)
    oth_credit = models.IntegerField(default=0)
    expired_days = models.IntegerField(default=0)
    expired_notification_days = models.IntegerField(default=0)
    blocked_days = models.IntegerField(default=0)
    wrong_try_count = models.IntegerField(default=0)
    wrong_try_block = models.IntegerField(default=0)
    dictionary_check = models.BooleanField(default=False)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"Password Policy (min {self.min_length} chars)"


class ServiceComponent(models.Model):
    uuid = models.UUIDField(primary_key=True)
    component_type = models.CharField(max_length=64)
    is_enabled = models.BooleanField(default=False)
    params = models.JSONField(default=dict)
    domain_level = models.IntegerField(default=0)
    lastmodified = models.BigIntegerField(default=0)
    config_import = models.ForeignKey(ConfigImport, on_delete=models.CASCADE, null=True)

    class Meta:
        ordering = ['component_type']

    def __str__(self):
        return self.component_type
