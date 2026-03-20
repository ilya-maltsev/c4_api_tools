from .models import (
    ConfigImport, Gateway, Domain, NetworkInterface, StaticRoute,
    FirewallRule, Certificate, AdminUser, VPNConfig, DDoSProtection,
    DDoSRule, NetworkObject, ServiceObject, ObjectGroup,
    AppException, PasswordPolicy, ServiceComponent,
)


def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

DDOS_TYPES = {
    'synscan', 'icmpscan', 'udpscan', 'synflood', 'finrstflood',
    'smurfattack', 'fraggleattack', 'fragmentattack', 'landattack',
    'icmpnullpayload', 'packetsanity', 'smallpacketmtu',
    'dnsmaxlength', 'dnsspoofing', 'dnsrequestmismatch', 'dnsreplymismatch',
}

SERVICE_TYPES = {
    'snmpcomponent', 'netflowcomponent', 'logservercomponent',
    'lldpcomponent', 'icmpcomponent', 'proxyarpcomponent',
    'staticarpcomponent', 'sshaccesscomponent', 'whitelistcomponent',
    'webproxycomponent', 'qoscomponent', 'dnscomponent',
    'geoprotectioncomponent', 'authuserscomponent', 'aservcomponent',
    'ntpserversettings', 'dbreplicationcomponent', 'multiwancomponent',
}


def import_config_json(data, filename=''):
    objects = data.get('objects', [])

    ci = ConfigImport.objects.create(source_file=filename, objects_count=len(objects))
    count = 0

    for obj in objects:
        obj_type = obj.get('type', '')
        if obj_type == 'link':
            continue

        uuid = obj.get('uuid')
        if not uuid:
            continue

        base = {
            'domain_level': safe_int(obj.get('domain_level', 0)),
            'lastmodified': safe_int(obj.get('lastmodified', 0)),
            'config_import': ci,
        }

        if obj_type == 'cgw':
            platform = obj.get('platform', {})
            Gateway.objects.update_or_create(uuid=uuid, defaults={
                'name': obj.get('name', ''),
                'hwserial': obj.get('hwserial', ''),
                'platform_version': platform.get('version', ''),
                'platform_name': platform.get('platform', ''),
                'timezone_name': obj.get('timezone_name', ''),
                'mode': obj.get('mode', ''),
                'dhcp_status': obj.get('dhcp_status', ''),
                'revision': str(obj.get('revision', '')),
                **base,
            })
            ci.gateway_name = obj.get('name', '')
            ci.save()

        elif obj_type == 'domain':
            Domain.objects.update_or_create(uuid=uuid, defaults={
                'name': obj.get('name', ''),
                'status': obj.get('status', ''),
                'clid': obj.get('clid', ''),
                **base,
            })

        elif obj_type == 'interfaceether':
            NetworkInterface.objects.update_or_create(uuid=uuid, defaults={
                'name': obj.get('name', ''),
                'is_enabled': obj.get('is_enabled', True),
                'mtu': obj.get('mtu', 1500),
                'usage': obj.get('usage', ''),
                'addresses': obj.get('addresses', []),
                'permitted_protocols': obj.get('permitted_protocols', []),
                'anti_spoofing': obj.get('anti_spoofing', False),
                'clear_df_bit': obj.get('clear_df_bit', False),
                **base,
            })

        elif obj_type == 'routingtableentry':
            StaticRoute.objects.update_or_create(uuid=uuid, defaults={
                'dst_ip': obj.get('dst_ip', ''),
                'nexthop': obj.get('nexthop', ''),
                'metric': obj.get('metric', 0),
                'is_default': obj.get('is_default', False),
                **base,
            })

        elif obj_type == 'fwrule':
            FirewallRule.objects.update_or_create(uuid=uuid, defaults={
                'name': obj.get('name', ''),
                'description': obj.get('description', ''),
                'is_enabled': obj.get('is_enabled', True),
                'position': obj.get('position', 0),
                'rule_action': obj.get('rule_action', ''),
                'logging': obj.get('logging', False),
                'passips': obj.get('passips', False),
                'priority': obj.get('priority', 0),
                'is_inverse_src': obj.get('is_inverse_src', False),
                'is_inverse_dst': obj.get('is_inverse_dst', False),
                **base,
            })

        elif obj_type == 'cert':
            Certificate.objects.update_or_create(uuid=uuid, defaults={
                'subject': obj.get('subject', ''),
                'subject_full': obj.get('subjectfull', ''),
                'issuer': obj.get('issuer', ''),
                'role': obj.get('role', ''),
                'is_ca': obj.get('ca', False),
                'startdate': obj.get('startdate', ''),
                'enddate': obj.get('enddate', ''),
                'gosttype': obj.get('gosttype', ''),
                **base,
            })

        elif obj_type == 'admin':
            AdminUser.objects.update_or_create(uuid=uuid, defaults={
                'name': obj.get('name', ''),
                'login': obj.get('login', ''),
                'full_name': obj.get('full_name', ''),
                'email': obj.get('email', ''),
                'phone': obj.get('phone', ''),
                'organization': obj.get('organization', ''),
                'occupation': obj.get('occupation', ''),
                'is_enabled': obj.get('is_enabled', True),
                'password_auth': obj.get('password_auth', True),
                'cert_auth': obj.get('cert_auth', False),
                'password_expired_date': obj.get('password_expired_date', ''),
                'created_at': obj.get('created_at', ''),
                **base,
            })

        elif obj_type == 'vpnl3ipseccomponent':
            VPNConfig.objects.update_or_create(uuid=uuid, defaults={
                'vpn_type': 'L3 IPsec',
                'is_enabled': obj.get('is_enabled', False),
                'session_breakup': obj.get('session_breakup', False),
                'is_log_tunnel_status': obj.get('is_log_ipsec_tunnel_status', False),
                **base,
            })

        elif obj_type == 'vpnl2component':
            VPNConfig.objects.update_or_create(uuid=uuid, defaults={
                'vpn_type': 'L2',
                'is_enabled': obj.get('is_enabled', False),
                'dynamic_records_lifetime': obj.get('dynamic_records_lifetime', 0),
                **base,
            })

        elif obj_type == 'dosprotectcomponent':
            DDoSProtection.objects.update_or_create(uuid=uuid, defaults={
                'mode': obj.get('mode', ''),
                'action': obj.get('action', ''),
                'blocking_time': obj.get('blocking_time', 0),
                'clear_stats': obj.get('clear_stats', False),
                **base,
            })

        elif obj_type in DDOS_TYPES:
            params = {k: v for k, v in obj.items()
                      if k not in ('uuid', 'type', 'is_deleted', 'lastmodified',
                                   'domain_level', 'is_enabled', 'revision')}
            DDoSRule.objects.update_or_create(uuid=uuid, defaults={
                'attack_type': obj_type,
                'is_enabled': obj.get('is_enabled', False),
                'params': params,
                **base,
            })

        elif obj_type == 'appexception':
            AppException.objects.update_or_create(uuid=uuid, defaults={
                'name': obj.get('name', ''),
                'is_enabled': obj.get('is_enabled', True),
                'vendor_id': obj.get('vendor_id', ''),
                'address': obj.get('address', ''),
                **base,
            })

        elif obj_type == 'passwordpolicy':
            PasswordPolicy.objects.update_or_create(uuid=uuid, defaults={
                'min_length': obj.get('min_length', 0),
                'diff': obj.get('diff', 0),
                'passwords_diff': obj.get('passwords_diff', 0),
                'low_credit': obj.get('low_credit', 0),
                'up_credit': obj.get('up_credit', 0),
                'dig_credit': obj.get('dig_credit', 0),
                'oth_credit': obj.get('oth_credit', 0),
                'expired_days': obj.get('expired_days', 0),
                'expired_notification_days': obj.get('expired_notification_days', 0),
                'blocked_days': obj.get('blocked_days', 0),
                'wrong_try_count': obj.get('wrong_try_count', 0),
                'wrong_try_block': obj.get('wrong_try_block', 0),
                'dictionary_check': obj.get('dictionary_check', False),
                **base,
            })

        elif obj_type in SERVICE_TYPES:
            params = {k: v for k, v in obj.items()
                      if k not in ('uuid', 'type', 'is_deleted', 'lastmodified',
                                   'domain_level', 'is_enabled', 'revision')}
            ServiceComponent.objects.update_or_create(uuid=uuid, defaults={
                'component_type': obj_type,
                'is_enabled': obj.get('is_enabled', False),
                'params': params,
                **base,
            })

        elif obj_type == 'netobject':
            NetworkObject.objects.update_or_create(uuid=uuid, defaults={
                'name': obj.get('name', ''),
                'description': obj.get('description', ''),
                'is_enabled': obj.get('is_enabled', True),
                'ip': obj.get('ip', ''),
                'subtype': obj.get('subtype', ''),
                **base,
            })

        elif obj_type == 'service':
            ServiceObject.objects.update_or_create(uuid=uuid, defaults={
                'name': obj.get('name', ''),
                'proto': safe_int(obj.get('proto', 0)),
                'src_port': obj.get('src', ''),
                'dst_port': obj.get('dst', ''),
                **base,
            })

        elif obj_type == 'group':
            ObjectGroup.objects.update_or_create(uuid=uuid, defaults={
                'name': obj.get('name', ''),
                'subtype': obj.get('subtype', ''),
                **base,
            })
        else:
            continue

        count += 1

    # Second pass: process links
    links = [o for o in objects if o.get('type') == 'link']
    for link in links:
        linkname = link.get('linkname', '')
        left_uuid = link.get('left_uuid')
        right_uuid = link.get('right_uuid')
        if not left_uuid or not right_uuid:
            continue

        # fwrule -> netobject (source/destination)
        if linkname in ('clf_source', 'clf_destination'):
            try:
                rule = FirewallRule.objects.get(uuid=left_uuid)
            except FirewallRule.DoesNotExist:
                continue

            # Try netobject first
            try:
                netobj = NetworkObject.objects.get(uuid=right_uuid)
                if linkname == 'clf_source':
                    rule.source_objects.add(netobj)
                else:
                    rule.destination_objects.add(netobj)
                continue
            except NetworkObject.DoesNotExist:
                pass

            # Try group
            try:
                group = ObjectGroup.objects.get(uuid=right_uuid)
                if linkname == 'clf_source':
                    rule.source_groups.add(group)
                else:
                    rule.destination_groups.add(group)
                continue
            except ObjectGroup.DoesNotExist:
                pass

        # fwrule -> service
        elif linkname == 'clf_service':
            try:
                rule = FirewallRule.objects.get(uuid=left_uuid)
                svc = ServiceObject.objects.get(uuid=right_uuid)
                rule.services.add(svc)
            except (FirewallRule.DoesNotExist, ServiceObject.DoesNotExist):
                pass

        # group -> netobject (members)
        elif linkname == 'group_member':
            try:
                group = ObjectGroup.objects.get(uuid=left_uuid)
                member = NetworkObject.objects.get(uuid=right_uuid)
                group.members.add(member)
            except (ObjectGroup.DoesNotExist, NetworkObject.DoesNotExist):
                pass

    ci.objects_count = count
    ci.save()
    return ci
