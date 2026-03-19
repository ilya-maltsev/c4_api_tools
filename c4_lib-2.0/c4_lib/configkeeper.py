from dataclasses import dataclass
from . import ApiConnector

@dataclass
class Config:
    c4_ip: str
    c4_password: str
    c4_port: str = '444'
    c4_user: str = 'admin'
    verbosity: bool = False
    log = None
    config_uuid: str = ''


class ConfigKeeper:
    def __init__(self, config: Config, api_connector: ApiConnector):
        self._config = config
        self._api = api_connector

    def modify_config_check(self) -> bool:
        """
        Проверяет, корректно ли подготовлена конфигурация для изменений.
        """
        if self._config.config_uuid == '':
            self._api.print_error('Перед внесением изменений необходимо заблокировать и форкнуть конфигурацию (C4Manager.open).')
            return False

        return True

    @property
    def uuid(self) -> str:
        return self._config.config_uuid

    @uuid.setter
    def uuid(self, value: str):
        self._config.config_uuid = value

    @property
    def api(self) -> ApiConnector:
        return self._api

    @api.setter
    def api(self, value: ApiConnector):
        self._api = value
