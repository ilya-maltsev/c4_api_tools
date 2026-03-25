#!/usr/bin/env python3
# Deluxe edition
import argparse
import os
import sys
import pathlib
import json
import time
import c4_lib

available_types = [
    'service',
    'netobject',
    'timeinterval',
    'group'
]


def draw_progress(i, min_i, max_i, size):
    sys.stdout.write("\033[G")
    i += 1
    progress_percent = (max_i - min_i) / size
    progress = round((i - min_i) / progress_percent)
    str_filler = "█" * progress
    str_emptiness = " " * (size - progress)
    percent = round((i - min_i) / ((max_i - min_i) / 100))
    sys.stdout.write(f"|\033[92m{str_filler}{str_emptiness}\033[0m| \033[1m{i - min_i} / {max_i - min_i} - {percent}%\033[0m")
    if i == max_i:
        sys.stdout.write("\n")
    sys.stdout.flush()


def process_NatRule(obj):
    out_obj = {
        'name': obj['name'],
        'is_enabled': obj['is_enabled'],
        'address_type': obj['address_type'],
        'service': [],
        'port_value': [],
        'port_type': obj['port_type'],
        'interface': None,
        'install_on': [],
        'src': [],
        'dst': [],
        'value': [],
        'nat_type': obj['nat_type'],
    }
    out_obj['description'] = obj.get('description', '')
    return out_obj


def process_FilterRule(obj):
    out_obj = {
        'name': obj['name'],
        'is_enabled': obj['is_enabled'],
        'passips': obj['passips'],
        'logging': obj['logging'],
        'is_inverse_src': obj['is_inverse_src'],
        'is_inverse_dst': obj['is_inverse_dst'],
        'install_on': [],
        'service': [],
        'src': [],
        'dst': [],
        'params': [],
        'rule_action': obj['rule_action'],
    }
    out_obj['description'] = obj.get('description', '')
    return out_obj


def convert_obj(obj):
    out = {'name': obj['name'], 'description': obj.get('description', ''), 'type': obj['type']}

    if obj['type'] == 'service':
        out['src'] = obj['src']
        out['dst'] = obj['dst']
        out['proto'] = obj['proto']
        out['requires_keep_connections'] = obj['requires_keep_connections']

    if obj['type'] == 'netobject':
        out['subtype'] = obj['subtype']
        out['ip'] = obj['ip']

    if obj['type'] == 'timeinterval':
        out['intervals'] = obj['intervals']

    if obj['type'] == 'group':
        out['subtype'] = obj['subtype']

    return out


def process_links(data, links, object_links):
    if links is None:
        return None
    out = {}
    linktypes_dict = {
        "clf_source": "src",
        "clf_destination": "dst",
        "obj_has_param": "params",
        "group_member": "members",
        "clf_service": "service",
        "nat_netobject": "value",
        "nat_service": "port_value",
    }
    for link in links:
        link_type = linktypes_dict.get(link['type'])
        if link_type is None:
            continue
        if link_type not in out.keys():
            out[link_type] = []

        for obj in data['objects']:
            if obj['type'] not in available_types:
                continue

            if obj['type'] == 'group' and obj['subtype'] not in available_types:
                continue

            if 'uuid' in obj.keys() and obj['uuid'] == link['uuid']:
                new_obj = convert_obj(obj)
                new_links = object_links.get(obj['uuid'])
                linked_objs = process_links(data, new_links, object_links)
                if not linked_objs is None:
                    new_obj.update(linked_objs)
                out[link_type].append(new_obj)
                break
    return out


def convert(data):
    out_data = []
    obj_len = len(data['objects'])

    print("[*] Сбор связей из оригинальной конфигурации.")
    object_links = {}
    i = 0
    for obj in data['objects']:
        draw_progress(i, 0, obj_len, 40)
        i += 1
        if obj['type'] == 'link':
            parent_uuid = obj['left_uuid']
            if not parent_uuid in object_links.keys():
                object_links[parent_uuid] = []
            object_links[parent_uuid].append({'uuid': obj['right_uuid'], 'type': obj['linkname']})

    print("[*] Сбор правил и преобразование объектов.")
    rules_process_dict = {
        'fwrule': process_FilterRule,
        'natrule': process_NatRule,
    }
    i = 0
    for obj in data['objects']:
        draw_progress(i, 0, obj_len, 40)
        i += 1
        if obj['type'] in rules_process_dict.keys():
            converted_obj = rules_process_dict[obj['type']](obj)
            links = object_links.get(obj['uuid'])
            linked_objs = process_links(data, links, object_links)
            if not linked_objs is None:
                converted_obj.update(linked_objs)

            out_data.append(converted_obj)

    return out_data


def cli():
    parser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter,
            prog = f"\n\n{os.path.basename(sys.argv[0])}",
            description = 'Утилита для экспорта конфигурации из Континент 4 и преобразования в универсальный формат.',
            epilog = f'''example: {os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 -o /path/to/folder
example: {os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 -o /path/to/folder --hwserial 1
example: {os.path.basename(sys.argv[0])} -u user:pass --ip 172.16.10.1 --ip_dst 172.16.11.1 -d user:pass -o /path/to/folder
            ''',
            add_help = False
        )
    parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='Показать текущее сообщение помощи и выйти.')
    parser.add_argument('-u', '--creds', help='Реквизиты в формате user:pass', type=str, required=True)
    parser.add_argument('--ip', help='IP узла.', type=str, required=True)
    parser.add_argument('--port', help='Порт узла.', default='444', type=str)
    parser.add_argument('-d', '--creds_dest', help='Реквизиты назначения в формате user:pass', type=str)
    parser.add_argument('--ip_dst', help='IP узла назначения.', type=str)
    parser.add_argument('--port_dst', help='Порт узла назначения.', default='444', type=str)
    parser.add_argument('-o','--output_path', help='Путь до папки для сохранения конфигураций.', type=str, required=True)
    parser.add_argument('--hwserial', help='hwserial для получения конфигурации конкретного УБ.', type=str)
    args = parser.parse_args(args=None if sys.argv[1:] else ['--help'])

    output_path = pathlib.Path(args.output_path)
    if not output_path.exists():
        print("[*] Директория не существует, создание...")
        output_path.mkdir(parents=True, exist_ok=True)
        return

    colon_index = args.creds.find(':')
    if colon_index < 0:
        print('[\033[91;1m-\033[0m] Неверный формат реквизитов.')
        return

    user = args.creds[:colon_index]
    password = args.creds[colon_index + 1:]
    api = c4_lib.ApiConnector(args.ip, args.port, user, password)

    if api is None:
        print('[\033[91;1m-\033[0m] Ошибка инициализации ApiConnector выход.')
        return

    print("[*] Извлечение конфигураций.")

    original_path = output_path / "original"
    converted_path = output_path / "converted"
    original_path.mkdir(exist_ok=True)
    converted_path.mkdir(exist_ok=True)

    cgws = []
    cgws_obj = None
    if not args.hwserial:
        cgws_obj = api.get_cgw_obj()
        if type(cgws_obj) is dict:
            cgws = cgws_obj.get('data', [])
    else:
        cgws = [{'name': '', 'hwserial': args.hwserial}]

    if cgws is []:
        print('[\033[91;1m-\033[0m] Извлечение не выполнено, выход.')
        if not cgws_obj is None:
            print(f'[!] {cgws_obj}')
        return

    for cgw in cgws:
        name = cgw.get('name', '')
        cluster = cgw.get('cluster')
        if cluster is None:
            hwserial = cgw['hwserial']
        else:
            nodes = cluster.get('nodes', [])
            if len(nodes) > 0:
                hwserial = nodes[0].get('hwserial')
            else:
                print('[-] Пустой кластер.')
                continue

        json_data = api.get_cgw_config_by_hwserial(hwserial)
        with open(original_path / f"{name}_{hwserial}_config.json", 'w') as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)

    del cgws
    del api

    print("[\033[92;1m+\033[0m] Извлечение конфигураций выполнено.")
    print("[*] Преобразование конфигураций.")

    for config_filename in os.listdir(original_path):
        print(f"[*] {config_filename}")
        data = {}
        with open(original_path / config_filename, 'r') as f:
            data = json.load(f)

        if type(data) != dict or "objects" not in data.keys():
            print('[\033[91;1m-\033[0m] Неверный формат входного файла.')
            return

        out_data = convert(data)
        with open(converted_path / config_filename, 'w') as f:
            json.dump(out_data, f, indent=4, ensure_ascii=False)

    print("[\033[92;1m+\033[0m] Преобразование конфигураций завершено.")
    print("[*] Слияние конфигураций.")

    converted_filename = output_path / "final.json"
    merge_list = []
    for config_filename in os.listdir(converted_path):
        with open(converted_path / config_filename, 'r') as f:
            data = json.load(f)
            merge_list.extend(data)

    with open(converted_filename, 'w') as f:
        json.dump(merge_list, f, indent=4, ensure_ascii=False)

    del merge_list
    print("[\033[92;1m+\033[0m] Слияние конфигураций завершено.")

    if not args.creds_dest:
        print('[*] Реквизиты назначения не указаны, пропуск.')
        print("[\033[92;1m+\033[0m] \033[92;1mВыполнено.\033[0m")
        return

    if args.creds_dest.find(':') < 0:
        print('[\033[91;1m-\033[0m] Неверный формат реквизитов назначения.')
        return

    colon_index = args.creds_dest.find(':')
    user = args.creds_dest[:colon_index]
    password = args.creds_dest[colon_index + 1:]
    api = c4_lib.ApiConnector(args.ip_dst, args.port_dst, user, password)

    print("[*] Отправка конфигурации.")
    send_file_str = bytes(str(converted_filename), 'utf-8')

    config_lock_data = api.config_lock_user()
    if config_lock_data.get('admin', None) != None:
        print('[\033[91;1m-\033[0m] Перед использованием убедитесь, что в МК-назначения сохранены все изменения и разорвано соединение с ЦУС. Выход.')
        return

    api.set_config_lock()
    fork_data = api.fork_config()
    if not type(fork_data) is dict or 'uuid' not in fork_data.keys():
        print('[\033[91;1m-\033[0m] Ошибка блокировки конфига.')
        for msg in fork_data.get('__all__', []):
            print(f"[!] {msg.get('message', '')}")
        api.free_config_lock()
        return
    config_uuid = fork_data['uuid']

    def is_done(task_uuid):
        tasks = api.get_task(task_uuid).get('data', [])
        if len(tasks) > 0:
            if tasks[0].get('processed', 100) < 100:
                return False
        return True

    def result_waiting(result):
        # Ожидание завершения задачи
        print(f"[!] Статус: {result['status']}.")
        task_uuid = result['tasks'][0]
        while not is_done(task_uuid):
            time.sleep(2)

        time.sleep(2)
        # Вывод результата выполнения
        tasks = api.get_task(task_uuid).get('data', [])
        for task in tasks:
            status = task.get('status', '')
            print(f"[!] Результат выполнения: {status}.")
            for message in task.get('messages', []):
                print(f"  [!] {message.get('level', '')}: {message.get('message', '')}")

    # импорт правил МЭ
    result = api.import_fw_rules(send_file_str, config_uuid=config_uuid)
    if not type(result) is dict or 'status' not in result.keys():
        print('[\033[91;1m-\033[0m] Ошибка импорта конфигурации МЭ. Выход.')
        for msg in result.get('__all__', []):
            print(f"[!] {msg.get('message', '')}")
        api.free_config_lock()
        return
    result_waiting(result)

    # импорт правил NAT
    result = api.import_nat_rules(send_file_str, config_uuid=config_uuid)
    if not type(result) is dict or 'status' not in result.keys():
        print('[\033[91;1m-\033[0m] Ошибка импорта конфигурации NAT. Выход.')
        for msg in result.get('__all__', []):
            print(f"[!] {msg.get('message', '')}")
        api.free_config_lock()
        return
    result_waiting(result)

    api.commit_config(config_uuid)
    api.free_config_lock()

    print("[\033[92;1m+\033[0m] \033[92;1mВыполнено.\033[0m")

if __name__ == "__main__":
    cli()