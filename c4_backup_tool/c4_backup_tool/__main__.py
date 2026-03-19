#!/usr/bin/env python3
import argparse
import os
import sys
import pathlib
import time
import c4_lib
import getpass


def result_check(fields, result):
    if not type(result) is dict:
        return False

    if not 'uuid' in result.keys():
        if 'message' in result.keys():
            print(' - '.join([fields.get('name', ''), result['message']]))
        else:
            for key in result.keys():
                msg_obj = result[key][0]
                print(' - '.join([f"{fields.get('name', '')}", f"{key}: {msg_obj['message']}"]))
        return False

    return True


def draw_progress(i, min_i, max_i, size, error=False):
    color = 92 # green
    if error: color = 91 # red
    sys.stdout.write("\033[G")
    i += 1
    progress_percent = (max_i - min_i) / size
    progress = round((i - min_i) / progress_percent)
    str_filler = "█" * progress
    str_emptiness = " " * (size - progress)
    percent = round((i - min_i) / ((max_i - min_i) / 100))
    sys.stdout.write(f"|\033[{color}m{str_filler}{str_emptiness}\033[0m| {i - min_i} / {max_i - min_i} - \033[1m{percent}%\033[0m")
    sys.stdout.flush()
    if i == max_i:
        sys.stdout.write("\n")


def get_backup_uuid(api, name):
    uuid = None
    backups = get_backup_list(api)
    for backup in backups.get('data', []):
        if backup['name'] == name:
            uuid = backup['uuid']
            break

    return uuid


def is_done(api, task_uuid):
    """
    Проверяет, выполнена ли задача

    :Parameters:
        task_uuid
            Идентификатор задачи.

    :return:
        Возвращает False, если процент выполнения не равен 100.
    """
    progress, msgs = api.get_task_result(task_uuid)

    if progress < 100:
        draw_progress(progress, 0, 100, 40)
        return False

    if len(msgs) > 0:
        for msg in msgs:
            print(f"{msg.get('level')} - {msg.get('message')}")

        draw_progress(99, 0, 100, 40, error=True)
        return True

    draw_progress(99, 0, 100, 40)
    return True


def get_backup_list(api):
    """
    Возвращает список резервных копий.
    Формат: {"data": []}

    :return:
        Возвращает словарь.
    """
    url = f'{api._base_url_objects}/backup'
    return api.get_from_endpoint(url)


def get_backup_obj(api, uuid):
    """
    Возвращает объект, описывающий резервную копию с указанным идентификатором.

    :Parameters:
        uuid
            Идентификатор.

    :return:
        Возвращает словарь.
    """
    if uuid is None:
        return {}

    backup_data = get_backup_list(api)
    for obj in backup_data.get('data', []):
        if obj['uuid'] == uuid:
            return obj

    return {}


def create_backup(api, name, description='', full_backup=False, password=None):
    """
    Запускает задачу по созданию резервной копии.

    :Parameters:
        name
            Имя резервной копии.
        description
            Описание резервной копии.
        full_backup
            Если истина, то в резервную копию включаются данные мониторинга и аудита.
        password
            Пароль для шифрования резервной копии.
    """
    config_lock_data = api.config_lock_user()
    if config_lock_data.get('admin', None) != None:
        print('[\033[91;1m-\033[0m] Перед использованием убедитесь, что в МК сохранены все изменения и разорвано соединение с ЦУС. Выход.')
        return

    api.set_config_lock()

    url = f'{api._base_url_server}/backup'
    components = ["cdc", "cgw", "monitoring"]
    if full_backup:
        components = ["cdc", "cgw", "logs", "monitoring", "monitoring_data"]

    data = {
        'name': name,
        'description': description,
        'components': components
    }

    # Добавляем пароль, если он указан
    if password:
         import base64
         encoded_password = base64.b64encode(password.encode('utf-8')).decode('utf-8')
         data['password'] = encoded_password

    task = api.post_to_endpoint(url, data)
    if not task.get('status') == 'ok':
        print(task)
        return

    while not is_done(api, task['tasks'][0]):
        time.sleep(2)

    api.free_config_lock()


def delete_backup(api, uuid):
    """
    Запускает задачу по удалению резервной копии.

    :Parameters:
        uuid
            Идентификатор резервной копии.
    """
    config_lock_data = api.config_lock_user()
    if config_lock_data.get('admin', None) != None:
        print('[\033[91;1m-\033[0m] Перед использованием убедитесь, что в МК сохранены все изменения и разорвано соединение с ЦУС. Выход.')
        return

    api.set_config_lock()

    url = f'{api._base_url_objects}/backup'
    task = api.delete_obj(url, uuid)
    print("delete_backup: ")
    print(task)

    api.free_config_lock()


def download_backup(api, uuid, backup_path: pathlib.Path):
    """
    Экспорт резервной копии.

    :Parameters:
        uuid
            Идентификатор резервной копии для экспорта.
        backup_path
            Путь для сохранения резервной копии.
    """
    obj = get_backup_obj(api, uuid)
    filename = obj.get('filename', '')
    url = f"{api._base_url_server}/download-backup/{filename}"
    api.get_file_from_endpoint(url, backup_path / filename)


def cli():
    parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter,
            prog = f"\n\n{os.path.basename(sys.argv[0])}",
            description = 'Утилита для работы с резервными копиями в Континент 4.',
            epilog = f'''examples:
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 list
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 create --name backup1 --password mypass
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 create --name backup1 --prompt-password
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 delete --uuid a479002c-59d0-4c92-b8d6-e25b191c2f3a
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 delete --name backup1
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 download --uuid a479002c-59d0-4c92-b8d6-e25b191c2f3a -o /path/to/folder
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 download --name backup1 -o /path/to/folder
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 --client-cert cert.pem --client-key key.pem list
            ''',
            add_help = False
        )
    parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='Показать текущее сообщение помощи и выйти.')
    parser.add_argument('-u', '--creds', help='Реквизиты в формате user:pass.', type=str, required=True)
    parser.add_argument('--ip', help='IP узла.', type=str, required=True)
    parser.add_argument('--port', help='Порт узла.', default='444', type=str)

    # mTLS
    parser.add_argument('--client-cert', help='Путь к клиентскому сертификату (PEM).', type=str)
    parser.add_argument('--client-key', help='Путь к закрытому ключу клиента (PEM).', type=str)
    parser.add_argument('--ca-cert', help='Путь к CA сертификату для проверки сервера (по умолчанию проверка отключена).', type=str)

    parser.add_argument('-n', '--name', help='Имя резервной копии для создания.', type=str)
    parser.add_argument('--uuid', help='Идентификатор резервной копии для экспорта.', type=str)
    parser.add_argument('-o','--output_path', help='Путь до папки для сохранения.', type=str)
    parser.add_argument('--password', help='Пароль для шифрования резервной копии.', type=str)
    parser.add_argument('--prompt-password', help='Запросить пароль интерактивно', action='store_true')
    if sys.version_info.major == 3 and sys.version_info.minor < 9:
        parser.add_argument('--full', help='Если указан, резервные копии создаются с логами, в противном случае только с настройками.', action='store_true')
        parser.set_defaults(full=False)
    else:
        parser.add_argument('--full', help='Если указан, резервные копии создаются с логами, в противном случае только с настройками.', action=argparse.BooleanOptionalAction)
    parser.add_argument('cmd', choices=['list', 'create', 'delete', 'download', 'create_and_download'])
    args = parser.parse_args(args=None if sys.argv[1:] else ['--help'])

    if args.cmd is None:
        parser.print_help()
        return

    # Валидация mTLS аргументов
    if bool(args.client_cert) != bool(args.client_key):
        print('[\033[91;1m-\033[0m] --client-cert и --client-key должны быть указаны вместе.')
        return

    colon_index = args.creds.find(':')
    if colon_index < 0:
        print('[\033[91;1m-\033[0m] Неверный формат реквизитов.')
        return

    user = args.creds[:colon_index]
    password = args.creds[colon_index + 1:]
    api = c4_lib.ApiConnector(args.ip, args.port, user, password)

    if api is None:
        print('[\033[91;1m-\033[0m] Ошибка инициализации ApiConnector. Выход.')
        return

    # mTLS: устанавливаем клиентский сертификат на сессию
    if args.client_cert and args.client_key:
        api.session.cert = (args.client_cert, args.client_key)

    # Верификация серверного сертификата (по умолчанию отключена в ApiConnector)
    if args.ca_cert:
        api.session.verify = args.ca_cert

    # Обработка пароля для бэкапа
    backup_password = None
    if args.cmd in ['create', 'create_and_download']:
        if args.password and args.prompt_password:
            print('[\033[91;1m-\033[0m] Нельзя использовать одновременно --password и --prompt-password.')
            return

        if args.password:
            backup_password = args.password
        elif args.prompt_password:
            backup_password = getpass.getpass("Введите пароль для шифрования бэкапа: ")
            confirm_password = getpass.getpass("Подтвердите пароль: ")
            if backup_password != confirm_password:
                print('[\033[91;1m-\033[0m] Пароли не совпадают.')
                return

    if args.cmd == 'list':
        backups = get_backup_list(api)
        for backup in backups.get('data', []):
            print(f"{backup.get('uuid', '')}: {backup.get('name', '')} - {backup.get('description', '')}")

    if args.cmd == 'create':
        if args.name is None or args.name == '':
            parser.print_help()
            return

        create_backup(api, args.name, '', args.full, backup_password)

    if args.cmd == 'delete':
        invalid_name = args.name is None or args.name == ''
        invalid_uuid = args.uuid is None or args.uuid == ''

        if invalid_name and invalid_uuid:
            parser.print_help()
            return

        if not invalid_uuid:
            uuid = args.uuid
        else:
            uuid = get_backup_uuid(api, args.name)
            if uuid is None: return

        delete_backup(api, uuid)

    if args.cmd == 'download':
        invalid_name = args.name is None or args.name == ''
        invalid_uuid = args.uuid is None or args.uuid == ''

        if invalid_name and invalid_uuid:
            parser.print_help()
            return

        output_path = pathlib.Path(args.output_path)
        if not output_path.exists():
            print("[*] Директория не существует, создание.")
            output_path.mkdir(parents=True, exist_ok=True)

        if not invalid_uuid:
            uuid = args.uuid
        else:
            uuid = get_backup_uuid(api, args.name)
            if uuid is None: return

        download_backup(api, uuid, output_path)

    if args.cmd == 'create_and_download':
        if args.name is None or args.name == '' or args.output_path is None:
            parser.print_help()
            return

        create_backup(api, args.name, '', args.full, backup_password)

        uuid = get_backup_uuid(api, args.name)
        if uuid is None: return

        output_path = pathlib.Path(args.output_path)
        if not output_path.exists():
            print("[*] Директория не существует, создание.")
            output_path.mkdir(parents=True, exist_ok=True)

        download_backup(api, uuid, output_path)

    print("[\033[92;1m+\033[0m] \033[92;1mВыполнено.\033[0m")

if __name__ == "__main__":
    cli()
