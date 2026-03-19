#!/usr/bin/env python3
import argparse
import os
import sys
import pathlib
import time
import c4_lib


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
    """
    Рисует полосу прогресса в stdout
    """
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
    """
    Возвращает UUID РК по имени.

    :Parameters:
        name
            Имя РК.

    :return:
        uuid
    """
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
    url = f'{api._base_url}/api-v1-objects/backup'
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


def create_backup(api, name, description = '', backup_type='config'):
    """
    Запускает задачу по созданию резервной копии.

    :Parameters:
        name
            Имя резервной копии.
        description
            Описание резервной копии.
        full_backup
            Если истина, то в резервную копию включаются данные мониторинга и аудита.
    """
    config_lock_data = api.config_lock_user()
    if config_lock_data.get('admin', None) != None:
        print('[\033[91;1m-\033[0m] Перед использованием убедитесь, что в МК сохранены все изменения и разорвано соединение с ЦУС. Выход.')
        return

    api.set_config_lock()

    url = f'{api._base_url}/api-v1-server/backup'

    # backup_type == 'config'
    components = ["cdc", "cgw", "monitoring"]
    if backup_type == 'full':
        components = ["cdc", "cgw", "logs", "monitoring", "monitoring_data"]

    if backup_type == 'logs':
        components = ["logs"]

    if backup_type == 'monitoring':
        components = ["monitoring", "monitoring_data"]

    data = {'name': name, 'description': description, 'components': components}
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

    url = f'{api._base_url}/api-v1-objects/backup'
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
    url = f"{api._base_url}/api-v1-server/download-backup/{filename}"
    api.get_file_from_endpoint(url, backup_path / filename)


def cli():
    parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter,
            prog = f"\n\n{os.path.basename(sys.argv[0])}",
            description = 'Утилита для работы с резервными копиями в Континент 4.',
            epilog = f'''examples:
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 list
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 create --name backup1 --backup_type logs
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 delete --uuid a479002c-59d0-4c92-b8d6-e25b191c2f3a
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 delete --name backup1
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 download --uuid a479002c-59d0-4c92-b8d6-e25b191c2f3a -o /path/to/folder
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 download --name backup1 -o /path/to/folder
\t{os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 create_and_download --name backup1 -o /path/to/folder --backup_type full
            ''',
            add_help = False
        )
    parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='Показать текущее сообщение помощи и выйти.')
    parser.add_argument('-u', '--creds', help='Реквизиты в формате user:pass.', type=str, required=True)
    parser.add_argument('--ip', help='IP узла.', type=str, required=True)
    parser.add_argument('--port', help='Порт узла.', default='444', type=str)

    parser.add_argument('-n', '--name', help='Имя резервной копии для создания или экспорта.', type=str)
    parser.add_argument('--uuid', help='Идентификатор резервной копии для экспорта.', type=str)
    parser.add_argument('-o','--output_path', help='Путь до папки для сохранения.', type=str)
    parser.add_argument('cmd', choices=['list', 'create', 'delete', 'download', 'create_and_download'], help='Команды для работы с рк:\n  вывести список,\n  создать,\n  удалить,\n  скачать,\n  создать и скачать')
    parser.add_argument('--backup_type', choices=['full', 'config', 'logs', 'monitoring'], help='Выбор содержимого рк при создании.')
    args = parser.parse_args(args=None if sys.argv[1:] else ['--help'])

    if args.cmd is None:
        parser.print_help()
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

    if args.cmd == 'list':
        backups = get_backup_list(api)
        for backup in backups.get('data', []):
            print(f"{backup.get('uuid', '')}: {backup.get('name', '')} - {backup.get('description', '')}")

    if args.cmd == 'create':
        if args.name is None or args.name == '':
            parser.print_help()
            return

        create_backup(api, args.name, '', args.backup_type)

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

        create_backup(api, args.name, '', args.backup_type)

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