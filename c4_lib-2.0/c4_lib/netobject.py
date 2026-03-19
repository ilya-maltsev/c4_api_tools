from . import ConfigKeeper

class Netobject:
    def __init__(self, config_keeper: ConfigKeeper):
        self.config_keeper = config_keeper
        self.api = config_keeper.api

    def add(self, name, addr, description=''):
        """
        Добавляет сетевой объект в конфиг с определённым uuid, если объект существует, то только возвращет его uuid.

        :Parameters:
            name
                Имя.
            addr
                IP адрес объекта, подсети или диапазона.
            description
                Описание.

        :return:
            Возвращает uuid объекта при успешном добавлении и True, если объект с таким именем уже есть.
        """
        if not self.config_keeper.modify_config_check():
            return None, False

        url = f'{self.api.get_obj_url(self.config_keeper.uuid)}/netobject'

        result = self.api.find_object_by_name(name, url)
        if not result is None:
            return result.get('uuid'), True

        fields = {
            'name': name,
            'description': description,
            'ip': addr
        }

        result = self.api.post_to_endpoint(url, fields)
        if self.api.result_check(result, fields):
            return result.get('uuid'), False
        return None, False