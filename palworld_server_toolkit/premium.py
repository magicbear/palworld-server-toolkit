from palworld_server_toolkit.palobject import PalObject

PREMIUM_AVAILABLE = True

def MigrateBaseCamp(base_id, group_id, dry_run=False):
    load_skipped_decode(wsd, ['CharacterContainerSaveData', 'MapObjectSaveData'], False)
    base_id = toUUID(base_id)
    group_id = toUUID(group_id)
    if base_id not in MappingCache.BaseCampMapping:
        raise KeyError(f"Base camp id {base_id} not exists")
    if group_id not in MappingCache.GuildSaveDataMap:
        raise KeyError(f"Group id {group_id} not exists")
    basecamp = parse_item(MappingCache.BaseCampMapping[base_id], "BaseCampSaveData")

    orig_group_id = basecamp['value']['RawData']['value']['group_id_belong_to']
    worker_director = basecamp['value']['WorkerDirector']['value']['RawData']['value']['container_id']
    container = parse_item(MappingCache.CharacterContainerSaveData[worker_director], "CharacterContainerSaveData")
    slotItems = container['value']['Slots']['value']['values']
    instance_ids = []
    instances = []
    for idx_slot, _slot in enumerate(slotItems):
        if _slot['RawData']['value']['instance_id'] != PalObject.EmptyUUID:
            instance_ids.append(_slot['RawData']['value']['instance_id'])
            instances.append({
                'guid': PalObject.EmptyUUID,
                'instance_id': _slot['RawData']['value']['instance_id']
            })
    orig_group_data = parse_item(MappingCache.GroupSaveDataMap[toUUID(orig_group_id)], "GroupSaveDataMap")
    orig_group_info = orig_group_data['value']['RawData']['value']
    base_idx = orig_group_info['base_ids'].index(base_id)
    base_map_id = orig_group_info['map_object_instance_ids_base_camp_points'][base_idx]

    refMapObject = FindReferenceMapObject(base_map_id)
    for map_id in refMapObject['MapObject']:
        mapObject = parse_item(MappingCache.MapObjectSaveData[map_id], "MapObjectSaveData")
        orig_map_group_belong = mapObject['Model']['value']['RawData']['value']['group_id_belong_to']
        if orig_map_group_belong == PalObject.EmptyUUID:
            continue
        log.info(f"Migrate MapObject {map_id} from {orig_map_group_belong} to {group_id}")
        if not dry_run:
            mapObject['Model']['value']['RawData']['value']['group_id_belong_to'] = group_id

    for idx, ind_id in enumerate(orig_group_info['individual_character_handle_ids']):
        if ind_id['instance_id'] in instance_ids:
            if not dry_run:
                orig_group_info['individual_character_handle_ids'].pop(idx)
            log.info(f"Migrate WorkDirector {ind_id['instance_id']} from {orig_group_id} to {group_id}")

    group_data = parse_item(MappingCache.GroupSaveDataMap[toUUID(group_id)], "GroupSaveDataMap")
    group_info = group_data['value']['RawData']['value']

    for instanceId in instance_ids:
        character = MappingCache.CharacterSaveParameterMap[instanceId]
        log.info(f"Migrate Character {instanceId} from {character['value']['RawData']['value']['group_id']} to {group_id}")
        if not dry_run:
            character['value']['RawData']['value']['group_id'] = group_id

    if not dry_run:
        orig_group_info['base_ids'].pop(base_idx)
        orig_group_info['map_object_instance_ids_base_camp_points'].pop(base_idx)
        group_info['base_ids'].append(base_id)
        group_info['map_object_instance_ids_base_camp_points'].append(base_map_id)
        group_info['individual_character_handle_ids'] += instances
        basecamp['value']['RawData']['value']['group_id_belong_to'] = group_id


def MigrateBaseCampBuilder(base_id, player_uid):
    base_id = toUUID(base_id)
    player_uid = toUUID(player_uid)
    if base_id not in MappingCache.BaseCampMapping:
        raise KeyError(f"Base camp id {base_id} not exists")

    basecamp = parse_item(MappingCache.BaseCampMapping[base_id], "BaseCampSaveData")
    group_id = basecamp['value']['RawData']['value']['group_id_belong_to']
    group_data = parse_item(MappingCache.GroupSaveDataMap[group_id], "GroupSaveDataMap")
    group_info = group_data['value']['RawData']['value']
    if len(list(filter(lambda player: player['player_uid'] == player_uid, group_info['players']))) == 0:
        raise ValueError(f"Player {player_uid} not in group {group_id}")
    base_idx = group_info['base_ids'].index(base_id)
    map_id = group_info['map_object_instance_ids_base_camp_points'][base_idx]

    refMapObject = FindReferenceMapObject(map_id)
    for map_id in refMapObject['MapObject']:
        mapObject = parse_item(MappingCache.MapObjectSaveData[map_id], "MapObjectSaveData")
        orig_builder = mapObject['Model']['value']['RawData']['value']['build_player_uid']
        base_camp_id_belong_to = mapObject['Model']['value']['RawData']['value']['base_camp_id_belong_to']
        log.info(f"Migrate MapObject {base_camp_id_belong_to} -> {map_id} builder from {orig_builder} to {player_uid}")


def MoveCharacterContainer(instanceId, new_container_id):
    instanceId = toUUID(instanceId)
    new_container_id = toUUID(new_container_id)
    if instanceId not in MappingCache.CharacterSaveParameterMap:
        raise KeyError(f"Character Instance {instanceId} invalid")
    character = MappingCache.CharacterSaveParameterMap[instanceId]
    characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
    characterContainerId = characterData['SlotID']['value']['ContainerId']['value']['ID']['value']
    if new_container_id not in MappingCache.CharacterContainerSaveData:
        raise KeyError(f"Target Container {new_container_id} Invalid")

    emptySlot = None
    emptySlotIndex = None
    characterContainer = parse_item(MappingCache.CharacterContainerSaveData[new_container_id], "CharacterContainerSaveData")
    for slotIndex, slotItem in enumerate(characterContainer['value']['Slots']['value']['values']):
        if slotItem['RawData']['value']['instance_id'] in [instanceId, PalObject.EmptyUUID]:
            emptySlotIndex = slotIndex
            emptySlot = slotItem
            slotItem['RawData']['value']['instance_id'] = instanceId
            break
    if emptySlot is None:
        raise ValueError(f"Target Container {new_container_id} no empty slot")

    if characterContainerId in MappingCache.CharacterContainerSaveData:
        characterContainer = parse_item(MappingCache.CharacterContainerSaveData[characterContainerId], "CharacterContainerSaveData")
        for slotItem in characterContainer['value']['Slots']['value']['values']:
            if slotItem['RawData']['value']['instance_id'] == instanceId:
                emptySlot['PermissionTribeID']['value']['value'] = slotItem['PermissionTribeID']['value']['value']
                slotItem['PermissionTribeID']['value']['value'] = "EPalTribeID::None"
                slotItem['RawData']['value']['instance_id'] = PalObject.EmptyUUID
                log.info(
                    f"Delete Character {instanceId} from CharacterContainer {characterData['SlotID']['value']['ContainerId']['value']['ID']['value']}")
                break
    else:
        log.warning(f"Source Container {new_container_id} not in save")
    characterData['SlotID']['value']['ContainerId']['value']['ID']['value'] = new_container_id
    characterData['SlotID']['value']['SlotIndex']['value'] = emptySlotIndex
    emptySlot['RawData']['value']['instance_id'] = instanceId
    log.info(
        f"Migrate Character {instanceId} to CharacterContainer {new_container_id} -> {emptySlotIndex}")

def MoveCharacterToBaseCampWorker(instanceId, basecamp_id):
    basecamp_id = toUUID(basecamp_id)
    if basecamp_id not in MappingCache.BaseCampMapping:
        raise KeyError(f"Basecamp Instance {basecamp_id} invalid")
    basecamp = MappingCache.BaseCampMapping[basecamp_id]
    MoveCharacterContainer(instanceId, basecamp['value']['WorkerDirector']['value']['RawData']['value']['container_id'])


def MigrateAllToNoSteam(dry_run=False):
    migrate_sets = []
    skip_player_id = []
    for player_uid in MappingCache.PlayerIdMapping:
        new_uuid = toUUID(PlayerUid2NoSteam(
            int.from_bytes(player_uid.raw_bytes[0:4], byteorder='little')) + "-0000-0000-0000-000000000000")
        migrate_sets.append((player_uid, new_uuid))
        if new_uuid in MappingCache.PlayerIdMapping:
            skip_player_id.append(new_uuid)
            log.warning(f"Replaced Player {new_uuid}")
        else:
            log.info(f"Migrate from {player_uid} to {new_uuid}")
    if not dry_run:
        for src_uuid, new_uuid in migrate_sets:
            if src_uuid not in skip_player_id:
                MigratePlayer(src_uuid, new_uuid)
