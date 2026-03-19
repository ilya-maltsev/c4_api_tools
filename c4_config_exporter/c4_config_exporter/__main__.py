import argparse
import os
import sys
import json
import c4_lib

confidential_fields = [
    'password',
    'password_ssha',
    'password_sha512',
    '_auth_pass',
    'user',
    'auth_login',
    'community_name',
    'pubkey'
]

def remove_fields(obj, fields):
    if not obj or type(obj) != dict:
        return

    for field in fields:
        if field in obj.keys(): del obj[field]

def draw_progress(i, min_i, max_i, size):
    sys.stdout.write("\033[G")
    i += 1
    progress_percent = (max_i - min_i) / size
    progress = round((i - min_i) / progress_percent)
    str_filler = "█" * progress
    str_emptiness = " " * (size - progress)
    percent = round((i - min_i) / ((max_i - min_i) / 100))
    sys.stdout.write(f"|\033[92m{str_filler}{str_emptiness}\033[0m| \033[1m{i - min_i} / {max_i - min_i} - {percent}%\033[0m")
    sys.stdout.flush()
    if i == max_i:
        sys.stdout.write("\n")

def get_all_cgw_configs(api, configs_write_path, remove_confidential_fields = True):
    """
    Собирает конфигурации всех УБ и записывает в файлы.

    :Parameters:
        configs_write_path
            Путь до директории, в которой будут созданы файлы с конфигурациями.
        remove_confidential_fields
            Логический параметр, отвечающий за удаление чувствительных полей. По умолчанию True.
    """
    if not configs_write_path:
        print("[\033[91;1m-\033[0m] Не задана директория.")
        return

    if not os.path.exists(configs_write_path):
        print("[\033[91;1m-\033[0m] Директория не существует.")
        return

    no_hwserial_found = False
    cgws_obj = api.get_cgw_obj()
    cgws = cgws_obj.get('data', [])
    len_cgws = len(cgws)
    i = -1
    for cgw in cgws:
        i += 1
        draw_progress(i, 0, len_cgws, 40)
        if cgw['hwserial'] in ['', None]:
            no_hwserial_found = True
            continue

        filename = f"{cgw['name']}_{cgw['hwserial']}_config.json"
        with open(os.path.join(configs_write_path, filename), 'w') as f:
            json_data = api.get_cgw_config_by_hwserial(cgw['hwserial'])
            if json_data == None:
                continue

            if remove_confidential_fields and 'objects' in json_data.keys():
                for obj in json_data['objects']:
                    remove_fields(obj, confidential_fields)

            json.dump(json_data, f, indent=4, ensure_ascii=False)

    if no_hwserial_found:
        print("Для некоторых узлов отсутствует hwserial, их конфигурации не выгружены.")

    print("[\033[92;1m+\033[0m] \033[92;1mВыполнено.\033[0m")

def print_cgws(api):
    """
    Печатает список УБ.
    """
    cgws = api.get_cgw_obj()
    for cgw in cgws['data']:
        print(f"Name: {cgw['name']}, hwserial: {cgw['hwserial']}")


def cli():
    parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter,
            prog = f"\n\n{os.path.basename(sys.argv[0])}",
            description = 'Утилита для экспорта конфигурации из Континент 4.\n\tprint_cgws - вывести список УБ с их hwserial.\n\tget_all_cgw_configs - получить конфигурации всех УБ.\n\tget_cgw_config_by_hwserial - получить конфигурацию УБ по hwserial.',
            epilog = f'''example: {os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 print_cgws
example: {os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 get_all_cgw_configs --output_path /path/to/folder
example: {os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 get_cgw_config_by_hwserial --hwserial 1 --output_path /path/to/folder
            ''',
            add_help = False
        )
    parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='Показать текущее сообщение помощи и выйти.')
    parser.add_argument('-u', '--creds', help='Реквизиты в формате user:pass', type=str, required=True)
    parser.add_argument('--ip', help='IP сервера.', type=str, required=True)
    parser.add_argument('--port', help='Порт сервера.', default='444', type=str)
    parser.add_argument('cmd', choices=['get_all_cgw_configs', 'get_cgw_config_by_hwserial', 'print_cgws'])
    parser.add_argument('--output_path', help='Путь до папки для сохранения конфигураций.\n(get_all_cgw_configs, get_cgw_config_by_hwserial)', type=str)
    parser.add_argument('--hwserial', help='hwserial для получения конфигурации конкретного УБ. (get_cgw_config_by_hwserial)', type=str)
    if sys.version_info.major == 3 and sys.version_info.minor < 9:
        parser.add_argument('--with_confidential_data', help='Выгружать конфигурацию с чувствительной информацией. По умолчанию выключено.', action='store_true')
        parser.set_defaults(with_confidential_data=False)
    else:
        parser.add_argument('--with_confidential_data', help='Выгружать конфигурацию с чувствительной информацией. По умолчанию выключено.', action=argparse.BooleanOptionalAction)
    args = parser.parse_args(args=None if sys.argv[1:] else ['--help'])

    if not args.cmd:
        parser.print_help()
        return

    colon_index = args.creds.find(':')
    if colon_index < 0:
        print('[\033[91;1m-\033[0m] Неверный формат реквизитов')
        return

    user = args.creds[:colon_index]
    password = args.creds[colon_index + 1:]
    api = c4_lib.ApiConnector(args.ip, args.port, user, password)

    remove_confidential_fields = not args.with_confidential_data

    if args.cmd == 'print_cgws':
        print_cgws(api)

    if args.cmd == 'get_all_cgw_configs':
        get_all_cgw_configs(api, args.output_path,  remove_confidential_fields)

    if args.cmd == 'get_cgw_config_by_hwserial':
        full_path = os.path.join(args.output_path, f"{args.hwserial}_config.json")
        with open(full_path, 'w') as f:
            json_data = api.get_cgw_config_by_hwserial(args.hwserial)

            if remove_confidential_fields and 'objects' in json_data.keys():
                for obj in json_data['objects']:
                    remove_fields(obj, confidential_fields)

            json.dump(json_data, f, indent=4, ensure_ascii=False)