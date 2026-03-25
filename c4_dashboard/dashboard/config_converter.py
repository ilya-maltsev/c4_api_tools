"""
Convert native C4 config JSON to universal JSON format.
Based on c4_config_transfer conversion logic.

Universal format: rules with nested resolved objects (no UUIDs).
"""

AVAILABLE_TYPES = ['service', 'netobject', 'timeinterval', 'group']

LINK_TYPE_MAP = {
    'clf_source': 'src',
    'clf_destination': 'dst',
    'obj_has_param': 'params',
    'group_member': 'members',
    'clf_service': 'service',
    'nat_netobject': 'value',
    'nat_service': 'port_value',
    'install_on': 'install_on',
    'rule_applications': 'applications',
}


def _process_fwrule(obj):
    return {
        'type': 'fwrule',
        'name': obj.get('name', ''),
        'description': obj.get('description', ''),
        'is_enabled': obj.get('is_enabled', True),
        'position': obj.get('position', 0),
        'rule_action': obj.get('rule_action', ''),
        'logging': obj.get('logging', False),
        'passips': obj.get('passips', False),
        'is_inverse_src': obj.get('is_inverse_src', False),
        'is_inverse_dst': obj.get('is_inverse_dst', False),
        'install_on': [],
        'service': [],
        'applications': [],
        'src': [],
        'dst': [],
        'params': [],
    }


def _process_natrule(obj):
    return {
        'type': 'natrule',
        'name': obj.get('name', ''),
        'description': obj.get('description', ''),
        'is_enabled': obj.get('is_enabled', True),
        'address_type': obj.get('address_type', ''),
        'port_type': obj.get('port_type', ''),
        'nat_type': obj.get('nat_type', ''),
        'install_on': [],
        'service': [],
        'src': [],
        'dst': [],
        'value': [],
        'port_value': [],
    }


def _convert_obj(obj):
    out = {
        'name': obj.get('name', ''),
        'description': obj.get('description', ''),
        'type': obj['type'],
    }
    obj_type = obj['type']

    if obj_type == 'service':
        out['src'] = obj.get('src', '')
        out['dst'] = obj.get('dst', '')
        out['proto'] = obj.get('proto', 0)
        out['requires_keep_connections'] = obj.get('requires_keep_connections', False)

    elif obj_type == 'netobject':
        out['subtype'] = obj.get('subtype', '')
        out['ip'] = obj.get('ip', '')

    elif obj_type == 'timeinterval':
        out['intervals'] = obj.get('intervals', [])

    elif obj_type == 'group':
        out['subtype'] = obj.get('subtype', '')

    elif obj_type == 'application':
        out['category'] = obj.get('category', '')

    elif obj_type == 'cgw':
        out['hwserial'] = obj.get('hwserial', '')
        out['mode'] = obj.get('mode', '')

    return out


CONVERT_TYPES = AVAILABLE_TYPES + ['application', 'cgw']

RULE_PROCESSORS = {
    'fwrule': _process_fwrule,
    'natrule': _process_natrule,
}


def convert(data):
    """
    Convert native C4 config to universal JSON format.

    Args:
        data: dict with 'objects' key containing C4 config objects

    Returns:
        list of converted rule dicts with nested resolved objects
    """
    objects = data.get('objects', [])

    # Index objects by UUID for fast lookup
    obj_by_uuid = {}
    for obj in objects:
        if obj.get('type') != 'link' and 'uuid' in obj:
            obj_by_uuid[obj['uuid']] = obj

    # Build link map: parent_uuid -> [{uuid, type}, ...]
    object_links = {}
    for obj in objects:
        if obj.get('type') == 'link':
            parent_uuid = obj['left_uuid']
            if parent_uuid not in object_links:
                object_links[parent_uuid] = []
            object_links[parent_uuid].append({
                'uuid': obj['right_uuid'],
                'type': obj['linkname'],
            })

    def resolve_links(links):
        """Recursively resolve linked objects."""
        if not links:
            return {}
        out = {}
        for link in links:
            link_type = LINK_TYPE_MAP.get(link['type'])
            if link_type is None:
                continue

            target = obj_by_uuid.get(link['uuid'])
            if not target:
                continue

            target_type = target.get('type', '')
            if target_type not in CONVERT_TYPES:
                continue
            if target_type == 'group' and target.get('subtype', '') not in AVAILABLE_TYPES:
                continue

            converted = _convert_obj(target)

            # Recurse into nested links (e.g. group -> members)
            nested_links = object_links.get(target['uuid'])
            if nested_links:
                nested = resolve_links(nested_links)
                converted.update(nested)

            if link_type not in out:
                out[link_type] = []
            out[link_type].append(converted)

        return out

    # Convert rules
    result = []
    for obj in objects:
        processor = RULE_PROCESSORS.get(obj.get('type'))
        if not processor:
            continue

        rule = processor(obj)
        links = object_links.get(obj.get('uuid'))
        resolved = resolve_links(links)
        rule.update(resolved)
        result.append(rule)

    return result
