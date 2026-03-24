import os
import json
import c4_lib
from fastapi import FastAPI, HTTPException

app = FastAPI(title="C4 Config Exporter API")

CONFIDENTIAL_FIELDS = [
    'password', 'password_ssha', 'password_sha512',
    '_auth_pass', 'user', 'auth_login', 'community_name', 'pubkey',
]


def get_api_connector():
    host = os.environ.get('C4_HOST', '192.168.122.200')
    port = os.environ.get('C4_PORT', '444')
    user = os.environ.get('C4_USER', 'admin')
    password = os.environ.get('C4_PASSWORD', '')
    api = c4_lib.ApiConnector(host, port, user, password)
    api.connect_timeout = int(os.environ.get('CONNECT_TIMEOUT', '10'))
    api.read_timeout = int(os.environ.get('REQUEST_TIMEOUT', '300'))

    client_cert = os.environ.get('C4_CLIENT_CERT', '')
    client_key = os.environ.get('C4_CLIENT_KEY', '')
    ca_cert = os.environ.get('C4_CA_CERT', '')
    if client_cert and client_key and os.path.exists(client_cert):
        api.session.cert = (client_cert, client_key)
    if ca_cert and os.path.exists(ca_cert):
        api.session.verify = ca_cert

    return api


def remove_fields(obj, fields):
    if not obj or type(obj) != dict:
        return
    for field in fields:
        obj.pop(field, None)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/gateways")
def list_gateways():
    try:
        api = get_api_connector()
        cgws = api.get_cgw_obj()
        return cgws
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/configs")
def get_all_configs():
    try:
        api = get_api_connector()
        cgws_obj = api.get_cgw_obj()
        cgws = cgws_obj.get('data', [])

        configs = []
        for cgw in cgws:
            hwserial = cgw.get('hwserial')
            if not hwserial:
                continue
            json_data = api.get_cgw_config_by_hwserial(hwserial)
            if json_data is None:
                continue
            if 'objects' in json_data:
                for obj in json_data['objects']:
                    remove_fields(obj, CONFIDENTIAL_FIELDS)
            configs.append({
                'name': cgw.get('name', ''),
                'hwserial': hwserial,
                'config': json_data,
            })

        return {"gateways": configs}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/config/{hwserial}")
def get_config_by_hwserial(hwserial: str):
    try:
        api = get_api_connector()
        json_data = api.get_cgw_config_by_hwserial(hwserial)
        if json_data is None:
            raise HTTPException(status_code=404, detail="Config not found")
        if 'objects' in json_data:
            for obj in json_data['objects']:
                remove_fields(obj, CONFIDENTIAL_FIELDS)
        return json_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
