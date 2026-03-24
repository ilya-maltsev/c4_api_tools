"""
Direct connector to Continent 4 API via c4_lib.
Replaces HTTP calls to c4_config_exporter — runs in-process.
"""
import os
import ssl
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

logger = logging.getLogger('dashboard.c4_connector')

CONFIDENTIAL_FIELDS = [
    'password', 'password_ssha', 'password_sha512',
    '_auth_pass', 'user', 'auth_login', 'community_name', 'pubkey',
]


class GostSSLAdapter(HTTPAdapter):
    """HTTPS adapter that forces GOST-compatible SSL context with optional mTLS."""

    def __init__(self, client_cert=None, client_key=None, ca_cert=None, **kwargs):
        self._client_cert = client_cert
        self._client_key = client_key
        self._ca_cert = ca_cert
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.set_ciphers("ALL:@SECLEVEL=0")
        if self._ca_cert and os.path.exists(self._ca_cert):
            ctx.load_verify_locations(self._ca_cert)
        else:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        if self._client_cert and os.path.exists(self._client_cert):
            ctx.load_cert_chain(self._client_cert, self._client_key)
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _remove_fields(obj, fields):
    if not obj or type(obj) != dict:
        return
    for field in fields:
        obj.pop(field, None)


def _get_connector():
    import c4_lib
    from django.conf import settings

    host = os.environ.get('C4_HOST', '')
    port = os.environ.get('C4_PORT', '444')
    user = os.environ.get('C4_USER', 'admin')
    password = os.environ.get('C4_PASSWORD', '')

    if not host:
        raise ConnectionError('C4_HOST not configured')

    api = c4_lib.ApiConnector(host, port, user, password, verbosity=False)
    api.connect_timeout = int(os.environ.get('CONNECT_TIMEOUT', '10'))
    api.read_timeout = getattr(settings, 'REQUEST_TIMEOUT', 300)

    # Mount GOST SSL adapter with optional mTLS for C4 connection
    client_cert = os.environ.get('C4_CONNECT_CERT', '')
    client_key = os.environ.get('C4_CONNECT_KEY', '')
    ca_cert = os.environ.get('C4_CONNECT_CA', '')

    logger.debug('C4 connector: host=%s:%s user=%s', host, port, user)
    if client_cert and os.path.exists(client_cert):
        logger.debug('C4 mTLS: cert=%s key=%s', client_cert, client_key)
    else:
        logger.debug('C4 mTLS: disabled (no C4_CONNECT_CERT)')
    if ca_cert and os.path.exists(ca_cert):
        logger.debug('C4 CA verify: %s', ca_cert)
    else:
        logger.debug('C4 CA verify: disabled (self-signed)')

    api.session.mount('https://', GostSSLAdapter(
        client_cert=client_cert,
        client_key=client_key,
        ca_cert=ca_cert,
    ))

    return api


def list_gateways():
    """Return list of gateways [{name, hwserial}, ...]."""
    api = _get_connector()
    cgws_obj = api.get_cgw_obj()
    result = []
    for gw in cgws_obj.get('data', []):
        hwserial = gw.get('hwserial', '')
        if hwserial:
            result.append({
                'name': gw.get('name', ''),
                'hwserial': hwserial,
            })
    return result


def get_config(hwserial):
    """Fetch config for a single gateway by hwserial. Returns dict."""
    api = _get_connector()
    data = api.get_cgw_config_by_hwserial(hwserial)
    if data is None:
        raise LookupError(f'Config not found for {hwserial}')
    if 'objects' in data:
        for obj in data['objects']:
            _remove_fields(obj, CONFIDENTIAL_FIELDS)
    return data


def get_all_configs():
    """Fetch configs for all gateways. Returns list of {name, hwserial, config}."""
    api = _get_connector()
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
                _remove_fields(obj, CONFIDENTIAL_FIELDS)
        configs.append({
            'name': cgw.get('name', ''),
            'hwserial': hwserial,
            'config': data,
        })
    return configs
