import os
import sys
module_abspath = os.path.dirname(os.path.abspath(__file__))
os.environ['OPENSSL_CONF'] = f'{module_abspath}/openssl.cnf'
os.environ['OPENSSL_ENGINE_PATH'] = module_abspath

import requests
import json
import subprocess
import logging

# curl -u user:pass -k https://172.16.10.1:444/api-v1-objects/config
class ApiConnector:
    def __init__(self, ip='', port='444', user='admin', password='', verbosity=True, log=None, config=None):
        requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = "ALL:@SECLEVEL=1"
        requests.packages.urllib3.disable_warnings()
        if config != None:
            ip = config.c4_ip
            port = config.c4_port
            self._user = config.c4_user
            self._password = config.c4_password
            self.verbosity = config.verbosity
            self.log = config.log
        else:
            self._user = user
            self._password = password
            self.verbosity = verbosity
            self.log = log

        self._base_url_server = f'https://{ip}:{port}/api-v1-server'
        self._base_url_objects = f'https://{ip}:{port}/api-v1-objects'
        self.session = requests.Session()
        self.session.auth = (self._user, self._password)
        self.session.verify = False

        if self.log != None and self.log.isEnabledFor(logging.DEBUG):
            import http.client
            httpclient_logger = logging.getLogger("http.client")
            def http_log(*args):
                httpclient_logger.log(logging.DEBUG, " ".join(args))
            http.client.print = http_log
            http.client.HTTPConnection.debuglevel = 1


    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()

    def __parse_json(self, buffer):
        json_obj = {}
        if not buffer.ok:
            self.print_error(f"\nОшибка: {buffer.status_code} {buffer.reason}")
            try:
                self.print_error(f"{buffer.content.decode('utf-8')}")
            except:
                pass

        try:
            json_obj = json.loads(buffer.content.decode('utf-8'))
        except:
            self.print_error("Ошибка парсинга JSON")

        return json_obj

    def print_error(self, error_string):
        if self.log != None:
            self.log.error(error_string)

        if not self.verbosity:
            return

        print(f'[\033[91;1m-\033[0m] {error_string}')

    def print_info(self, info_string):
        if self.log != None:
            self.log.info(info_string)

        if not self.verbosity:
            return

        print(f"[\033[92;1m+\033[0m] {info_string}")

    def result_check(self, result, fields={}):
        """
        Проверяет ответ от сервера на наличие ошибок и выводит их, если есть.

        :Parameters:
            result
                Возвращаемое значение от C4 API.
            fields
                dict {'name': 'имя объекта'...}.

        :return:
            Возвращает True, если ошибок нет, иначе - False.
        """
        if not type(result) == dict:
            return False

        if not 'uuid' in result.keys():
            if 'message' in result.keys():
                self.print_error(' - '.join([fields.get('name', ''), result['message']]))
            else:
                for key in result.keys():
                    msg_obj = result[key]
                    if len(result[key]) > 0:
                        msg_obj = result[key][0]

                    self.print_error(' - '.join([f"{fields.get('name', '')}", f"{key}: {msg_obj.get('message')}"]))

            return False

        return True

    def get_obj_url(self, config_uuid):
        """
        Возвращает конечную точку api-v1-objects/config.

        :return:
            Возвращает строку.
        """
        if not config_uuid:
            self.print_error("Не указан UUID")
            return
        return f"{self._base_url_objects}/config/{config_uuid}"

    def get_srv_url(self, config_uuid):
        """
        Возвращает конечную точку api-v1-server/config.

        :return:
            Возвращает строку.
        """
        if not config_uuid:
            self.print_error("Не указан UUID")
            return
        return f"{self._base_url_server}/config/{config_uuid}"

    def post_to_endpoint(self, url, obj_dict, obj_files=None):
        """
        Отправляет словарь на указанный URL методом POST.

        :Parameters:
            url
                URL для отправки.
            obj_dict
                объект для отправки.
            obj_files
                необязательный параметр, позволяющий передавать файлы. {"имя файла": файлоподобный объект}

        :return:
            Возвращает словарь.
        """
        buffer = self.session.post(url=url, json=obj_dict, files=obj_files)
        return self.__parse_json(buffer)

    def put_to_endpoint(self, url, obj_dict, obj_files=None):
        """
        Отправляет словарь на указанный URL методом PUT.

        :Parameters:
            url
                URL для отправки.
            obj_dict
                объект для отправки.
            obj_files
                необязательный параметр, позволяющий передавать файлы. {"имя файла": файлоподобный объект}

        :return:
            Возвращает словарь.
        """
        buffer = self.session.put(url=url, json=obj_dict, files=obj_files)
        return self.__parse_json(buffer)

    def delete_obj(self, url, uuid):
        """
        Отправляет запрос на удаление объекта на указанный URL.

        :Parameters:
            url
                URL для отправки.
            uuid
                идентификатор объекта для удаления.

        :return:
            Возвращает словарь.
        """
        buffer = self.session.delete(url=f"{url}/{uuid}")
        return self.__parse_json(buffer)

    def get_from_endpoint(self, url):
        """
        Отправляет запрос на указанный URL методом GET.

        :Parameters:
            url
                URL для отправки.

        :return:
            Возвращает словарь.
        """
        buffer = self.session.get(url=url)
        return self.__parse_json(buffer)

    def get_file_from_endpoint(self, url, filename):
        """
        Отправляет запрос на указанный URL методом GET и записывает ответ в файл.

        :Parameters:
            url
                URL для отправки.
            filename
                полный путь до файла для записи.
        """
        resp = self.session.get(url=url)

        if not resp.status_code == 200:
            self.print_error(f"Статус: {resp.status_code}")
            return

        with open(filename, 'wb') as f:
            f.write(resp.content)

    def config_lock_user(self):
        """
        Возвращает объект, описывающий блокировку конфигурации.

        :return:
            Возвращает словарь.
        """
        url = f'{self._base_url_server}/config-lock-user'
        return self.get_from_endpoint(url)

    def set_config_lock(self):
        """
        Устанавливает блокировку конфигурации.

        :return:
            Возвращает словарь со статусом.
        """
        # url = f'{self._base_url_server}/force-config-lock'
        url = f'{self._base_url_server}/acquire-config-lock'
        return self.post_to_endpoint(url, {})

    def fork_config(self, source='active'):
        """
        Создаёт форк активного конфигурации для изменений.

        :Parameters:
            source
                идентификатор исходного конфигурации. По умолчанию - active.
        :return:
            Возвращает словарь с uuid форка.
        """
        url = f'{self._base_url_objects}/config'
        fields = {'name': 'new_config', 'subtype': 'adminedit', 'source': source}
        return self.post_to_endpoint(url, fields)

    def commit_config(self, config_uuid):
        """
        Запускает процесс слияния конфигурации с идентификатором uuid с активным.

        :Parameters:
            config_uuid
                идентификатор конфигурации для слияния с активным.

        :return:
            Возвращает словарь со статусом.
        """
        if not config_uuid:
            self.print_error("Не указан UUID")
            return

        url = f'{self.get_srv_url(config_uuid)}/commit'
        return self.post_to_endpoint(url, {})

    def delete_config(self, config_uuid):
        """
        Запускает процесс удаления конфигурации с идентификатором uuid.

        :Parameters:
            config_uuid
                идентификатор конфигурации для удаления.

        :return:
            Возвращает словарь со статусом.
        """
        if not config_uuid:
            self.print_error("Не указан UUID")
            return

        buffer = self.session.delete(url=f'{self.get_obj_url(config_uuid)}')
        return self.__parse_json(buffer)

    def free_config_lock(self):
        """
        Снимает блокировку конфигурации.

        :return:
            Возвращает словарь со статусом.
        """
        url = f'{self._base_url_server}/free-config-lock'
        return self.post_to_endpoint(url, {})

    def get_config_obj(self):
        """
        Возвращает объект, определяющий конфигурации.

        :return:
            Возвращает словарь.
        """
        url = f'{self._base_url_objects}/config'
        return self.get_from_endpoint(url)

    def get_master_uuid(self):
        """
         :return:
            Возвращает uuid master-конфигурации.
        """
        url = f'{self._base_url_objects}/config'
        config_obj = self.get_from_endpoint(url)

        master_uuid = None
        for cfg in config_obj['data']:
            if cfg['subtype'] == 'master':
                master_uuid = cfg['uuid']
                break

        return master_uuid

    def get_cgw_obj(self, config_uuid='active'):
        """
        Возвращает объект со свойствами узлов безопасности.

        :Parameters:
            config_uuid
                Идентификатор конфигурации для извлечения объекта.

        :return:
            Возвращает словарь.
        """
        url = f'{self.get_obj_url(config_uuid)}/cgw'
        return self.get_from_endpoint(url)

    def get_config_by_uuid(self, config_uuid='active'):
        """
        Возвращает конфигурацию по идентификатору.

        :Parameters:
            config_uuid
                Идентификатор необходимой конфигурации.

        :return:
            возвращает словарь.
        """
        url = f'{self.get_srv_url(config_uuid)}/export-config?view=full'
        return self.get_from_endpoint(url)

    def get_cgw_config_by_hwserial(self, hwserial, config_uuid='active'):
        """
        Возвращает конфигурацию УБ по hwserial.

        :Parameters:
            hwserial
                Идентификатор УБ.
            config_uuid
                идентификатор конфигурации.

        :return:
            Возвращает словарь.
        """
        if not hwserial:
            self.print_error("Не указан hwserial")
            return

        url = f'{self.get_srv_url(config_uuid)}/export-config-for-cgw/{hwserial}?view=full'
        return self.get_from_endpoint(url)

    def install_policy_cgw(self, hwserial_list, config_uuid='active'):
        """
        Запускает процесс установки политики на УБ c определёнными hwserial.

        :Parameters:
            hwserial_list
                Список hwserial УБ для установки политики.
            config_uuid
                Идентификатор конфигурации.
        """
        url = f'{self.get_srv_url(config_uuid)}/install-policy'
        fields = {'target': hwserial_list}
        return self.post_to_endpoint(url, fields)

    def import_fw_rules(self, objects_file, config_uuid):
        """
        Импортирует правила FW.

        :Parameters:
            objects_file
                Файл с правилами для импорта.
            config_uuid
                Идентификатор конфигурации.

        :return:
            Возвращает словарь со статусом и id задачи в случае успеха.
        """
        url = f'{self.get_srv_url(config_uuid)}/import-fw-rules'
        out_data = {}
        with open(objects_file, 'rb') as f:
            file_dict = {'objects_file': f}
            out_data = self.post_to_endpoint(url, {}, file_dict)

        return out_data

    def import_nat_rules(self, objects_file, config_uuid):
        """
        Импортирует правила NAT.

        :Parameters:
            objects_file
                Файл с правилами для импорта.
            config_uuid
                Идентификатор конфигурации.

        :return:
            Возвращает словарь со статусом и id задачи в случае успеха.
        """
        url = f'{self.get_srv_url(config_uuid)}/import-nat-rules'
        out_data = {}
        with open(objects_file, 'rb') as f:
            file_dict = {'objects_file': f}
            out_data = self.post_to_endpoint(url, {}, file_dict)

        return out_data

    # TODO: поправить скрипты и перенести таски в менеджер
    def get_tasks(self):
        """
        Возвращает словарь со списком задач.
        """
        url = f'{self._base_url_objects}/task'
        return self.get_from_endpoint(url)

    def get_task(self, uuid):
        """
        Возвращает словарь с объектом задачи.
        """
        if uuid is None:
            return {}
        url = f'{self._base_url_objects}/task/{uuid}'
        return self.get_from_endpoint(url)

    def get_task_result(self, task_uuid):
        """
        Проверяет, выполнена ли задача

        :Parameters:
            task_uuid
                Идентификатор задачи.

        :return:
            Возвращает процент выполнения задачи и сообщения об ошибках, если она не завершилась успешно.
        """
        tasks = self.get_task(task_uuid).get('data', [])
        if len(tasks) > 0:
            task = tasks[0]
            progress = task.get('processed', 100)
            if progress < 100:
                return progress, []

            if not task.get('status') == 'done':
                messages = task.get('messages', [])
                return progress, messages

        return 100, []

    def find_object_by_name(self, name, url):
        """Получаем объекты по url и ищем нужный"""
        objects = self.get_from_endpoint(url)
        for obj in objects.get('data', []):
            if obj.get('name') == name:
                return obj
        return None

    def print_debug(self):
        print(sys.path)
        print(f"OPENSSL_CONF: {os.environ['OPENSSL_CONF']}")
        print(f"OPENSSL_ENGINE_PATH: {os.environ['OPENSSL_ENGINE_PATH']}")
        print(f"Конечная точка server: {self._base_url_server}")
        print(f"Конечная точка objects: {self._base_url_objects}")
        print()
        print(requests.ssl.OPENSSL_VERSION)
        print("openssl engine:")
        subprocess.run(["openssl", "engine"])


from .configkeeper import ConfigKeeper, Config
from .netobject import Netobject

class C4Manager:
    def __init__(self, config: Config):
        api = ApiConnector(config=config)
        self.config_keeper = ConfigKeeper(config, api)
        self.__init_modules__()

    def __init_modules__(self):
        self.netobjects = Netobject(self.config_keeper)

    def open(self) -> bool:
        """
        Устанавливает блокировку и форкает конфигурацию.
        """
        api = self.config_keeper.api
        config_lock_data = api.config_lock_user()
        if config_lock_data['admin'] != None:
            if not config_lock_data['is_current_user']:
                api.print_error('Конфигурация заблокирована другим пользователем')
                return False

            if not config_lock_data['is_current_session']:
                api.print_error('Конфигурация заблокирована в другой сессии')
                return False

        api.set_config_lock()
        fork_data = api.fork_config()
        if not type(fork_data) == dict or 'uuid' not in fork_data.keys():
            api.print_error('Ошибка блокировки конфигурации')
            for msg in fork_data.get('__all__', []):
                api.print_error(f"\t{msg.get('message', '')}")

            api.free_config_lock()
            return False

        self.config_keeper.uuid = fork_data['uuid']
        return True

    def save(self) -> bool:
        """
        Сохраняет изменения и снимает блокировку.
        """
        if not self.config_keeper.modify_config_check():
            return False

        api = self.config_keeper.api
        response = api.commit_config(self.config_keeper.uuid)
        self.config_keeper.uuid = ''
        api.free_config_lock()
        if type(response) == None:
            api.print_error('Ошибка сохранения конфигурации')
            return False

        if type(response) == dict and response.get('status') != 'ok':
            api.print_error('Ошибка сохранения конфигурации')
            for msg in response.get('__all__', []):
                api.print_error(f"\t{msg.get('message', '')}")

            return False
        return True

    def cancel(self) -> bool:
        """
        Удаляет изменения и снимает блокировку.
        """
        if not self.config_keeper.modify_config_check():
            return False

        api = self.config_keeper.api
        response = api.delete_config(self.config_keeper.uuid)
        self.config_keeper.uuid = ''
        api.free_config_lock()
        if type(response) == None:
            api.print_error('Ошибка удаления конфигурации')
            return False

        if type(response) == dict and 'uuid' not in response.keys():
            api.print_error('Ошибка удаления конфигурации')
            for msg in response.get('__all__', []):
                api.print_error(f"\t{msg.get('message', '')}")

            return False

        return True