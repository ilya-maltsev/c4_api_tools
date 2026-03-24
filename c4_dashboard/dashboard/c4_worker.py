#!/usr/bin/env python3
"""
Standalone worker for C4 API calls.
Runs as a subprocess so c4_lib controls OPENSSL_CONF before ssl module loads.

Usage:
    python c4_worker.py list_gateways
    python c4_worker.py get_config <hwserial>
"""
import sys
import os
import json

# c4_lib MUST be imported before anything that touches ssl
import c4_lib

CONFIDENTIAL_FIELDS = [
    'password', 'password_ssha', 'password_sha512',
    '_auth_pass', 'user', 'auth_login', 'community_name', 'pubkey',
]


def remove_fields(obj, fields):
    if not obj or type(obj) != dict:
        return
    for field in fields:
        obj.pop(field, None)


def get_connector():
    host = os.environ.get('C4_HOST', '')
    port = os.environ.get('C4_PORT', '444')
    user = os.environ.get('C4_USER', 'admin')
    password = os.environ.get('C4_PASSWORD', '')

    if not host:
        raise ConnectionError('C4_HOST not configured')

    api = c4_lib.ApiConnector(host, port, user, password, verbosity=False)
    api.connect_timeout = int(os.environ.get('CONNECT_TIMEOUT', '10'))
    api.read_timeout = int(os.environ.get('REQUEST_TIMEOUT', '300'))
    return api


def cmd_list_gateways():
    api = get_connector()
    cgws_obj = api.get_cgw_obj()
    result = []
    for gw in cgws_obj.get('data', []):
        hwserial = gw.get('hwserial', '')
        if hwserial:
            result.append({'name': gw.get('name', ''), 'hwserial': hwserial})
    return result


def cmd_get_config(hwserial):
    api = get_connector()
    data = api.get_cgw_config_by_hwserial(hwserial)
    if data is None:
        raise LookupError(f'Config not found for {hwserial}')
    if 'objects' in data:
        for obj in data['objects']:
            remove_fields(obj, CONFIDENTIAL_FIELDS)
    return data


def cmd_get_all_configs():
    api = get_connector()
    cgws_obj = api.get_cgw_obj()
    cgws = cgws_obj.get('data', [])
    configs = []
    for cgw in cgws:
        hwserial = cgw.get('hwserial')
        if not hwserial:
            continue
        data = api.get_cgw_config_by_hwserial(hwserial)
        if data is None:
            continue
        if 'objects' in data:
            for obj in data['objects']:
                remove_fields(obj, CONFIDENTIAL_FIELDS)
        configs.append({
            'name': cgw.get('name', ''),
            'hwserial': hwserial,
            'config': data,
        })
    return configs


if __name__ == '__main__':
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else ''

        if cmd == 'list_gateways':
            result = cmd_list_gateways()
        elif cmd == 'get_config':
            hwserial = sys.argv[2]
            result = cmd_get_config(hwserial)
        elif cmd == 'get_all_configs':
            result = cmd_get_all_configs()
        else:
            print(json.dumps({'error': f'Unknown command: {cmd}'}))
            sys.exit(1)

        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'error': str(e)}, ensure_ascii=False))
        sys.exit(1)
