# Based on the work of https://github.com/cheahjs/palworld-save-tools/releases/tag/v0.13.0
# Based on the work of https://gist.github.com/Bluefissure/f277a3409cdaf09cddbad5983fd01f68

import glob, os, datetime, zlib, subprocess
from operator import itemgetter, attrgetter
import json
import os
import sys
from lib.gvas import GvasFile
from lib.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from lib.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
import pprint
import uuid
import argparse

pp = pprint.PrettyPrinter(width=80, compact=True, depth=4)

def main():
    parser = argparse.ArgumentParser(
        prog="palworld-cleanup-tools",
        description="Cleanup the Level.sav",
    )
    parser.add_argument("filename")
    parser.add_argument(
        "--fix-missing",
        action="store_true",
        help="Delete the missing characters",
    )
    parser.add_argument(
        "--statistics",
        action="store_true",
        help="Show the statistics for all key",
    )
    parser.add_argument(
        "--fix-capture",
        action="store_true",
        help="Fix the too many capture logs",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: <filename>_fixed.sav)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.filename):
        print(f"{args.filename} does not exist")
        exit(1)

    if not os.path.isfile(args.filename):
        print(f"{args.filename} is not a file")
        exit(1)

    print(f"Loading {args.filename}...")
    with open(args.filename, "rb") as f:
        # Read the file
        data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)

        print(f"Parsing {args.filename}...", end="", flush=True)
        gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
        print("Done.")

    wsd = gvas_file.properties['worldSaveData']['value']

    if args.statistics:
        for key in wsd:
            print("%40s\t%.3f MB" % (key, len(str(wsd[key])) / 1048576))

    playerMapping = {}
    instanceMapping = {}
    for item in wsd['CharacterSaveParameterMap']['value']:
        instanceMapping[item['key']['InstanceId']['value']] = item
        if "00000000-0000-0000-0000-000000000000" != str(item['key']['PlayerUId']['value']):
            player = item['value']['RawData']['value']['object']['SaveParameter']
            if player['struct_type'] == 'PalIndividualCharacterSaveParameter':
                playerParams = player['value']
                playerMeta = {}
                for player_k in playerParams:
                    playerMeta[player_k] = playerParams[player_k]['value']
                playerMeta['InstanceId'] = item['key']['InstanceId']['value']
                playerMapping[str(item['key']['PlayerUId']['value'])] = playerMeta
            print("%s [\033[32m%s\033[0m] -> Level %2d  %s" % (
                item['key']['PlayerUId']['value'], playerMeta['InstanceId'],
                playerMeta['Level'] if 'Level' in playerMeta else -1, playerMeta['NickName']))
        else:
            # Non Player
            player = item['value']['RawData']['value']['object']['SaveParameter']
            if player['struct_type'] == 'PalIndividualCharacterSaveParameter':
                playerParams = player['value']
                playerMeta = {}
                for player_k in playerParams:
                    playerMeta[player_k] = playerParams[player_k]['value']

    if args.fix_missing:
        # Remove Unused in CharacterSaveParameterMap
        removeItems = []
        for item in wsd['CharacterSaveParameterMap']['value']:
            if "00000000-0000-0000-0000-000000000000" == str(item['key']['PlayerUId']['value']):
                player = item['value']['RawData']['value']['object']['SaveParameter']['value']
                if 'OwnerPlayerUId' in player and str(player['OwnerPlayerUId']['value']) not in playerMapping:
                    print(
                        "\033[31mInvalid item on CharacterSaveParameterMap\033[0m  UUID: %s  Owner: %s  CharacterID: %s" % (
                        str(item['key']['InstanceId']['value']), str(player['OwnerPlayerUId']['value']),
                        player['CharacterID']['value']))

        for item in removeItems:
            wsd['CharacterSaveParameterMap']['value'].remove(item)

    # Remove Unused in GroupSaveDataMap
    for group_data in wsd['GroupSaveDataMap']['value']:
        # print("%s %s" % (group_data['key'], group_data['value']['GroupType']['value']['value']))
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            # pp.pprint(str(group_data['value']['RawData']['value']))
            item = group_data['value']['RawData']['value']
            mapObjectMeta = {}
            for m_k in item:
                mapObjectMeta[m_k] = item[m_k]
            # pp.pprint(mapObjectMeta)
            print("Guild \033[93m%s\033[0m   Admin \033[96m%s\033[0m  Group ID %s  Character Count: %d" % (
            mapObjectMeta['guild_name'], str(mapObjectMeta['admin_player_uid']), str(mapObjectMeta['group_id']),
            len(mapObjectMeta['individual_character_handle_ids'])))
            for player in mapObjectMeta['players']:
                print("    Player \033[93m%s\033[0m [\033[92m%s\033[0m] Last Online: %d" % (
                player['player_info']['player_name'], str(player['player_uid']),
                player['player_info']['last_online_real_time']))
            removeItems = []
            for ind_char in mapObjectMeta['individual_character_handle_ids']:
                if ind_char['instance_id'] in instanceMapping:
                    character = \
                    instanceMapping[ind_char['instance_id']]['value']['RawData']['value']['object']['SaveParameter'][
                        'value']
                    # if 'NickName' in character:
                    #     print("    Player %s -> %s" % (str(ind_char['instance_id']), character['NickName']['value']))
                    # else:
                    #     print("    Character %s -> %s" % (str(ind_char['instance_id']), character['CharacterID']['value']))
                else:
                    print("    \033[31mInvalid Character %s\033[0m" % (str(ind_char['instance_id'])))
                    removeItems.append(ind_char)
            if args.fix_capture:
                for rmitem in removeItems:
                    item['individual_character_handle_ids'].remove(rmitem)
            print("After remove character count: %d" % len(
                group_data['value']['RawData']['value']['individual_character_handle_ids']))
            print()
        # elif str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Neutral":
        #     item = group_data['value']['RawData']['value']
        #     print("Neutral Group ID %s  Character Count: %d" % (str(item['group_id']), len(item['individual_character_handle_ids'])))
        #     for ind_char in item['individual_character_handle_ids']:
        #         if ind_char['instance_id'] not in instanceMapping:
        #             print("    \033[31mInvalid Character %s\033[0m" % (str(ind_char['instance_id'])))

    if not args.output:
        output_path = args.filename.replace(".sav", "_fixed.sav")
    else:
        output_path = args.output

    if args.fix_missing or args.fix_capture:
        print("processing GVAS to Sav file...", end="", flush=True)
        if  "Pal.PalWorldSaveGame" in gvas_file.header.save_game_class_name or "Pal.PalLocalWorldSaveGame" in gvas_file.header.save_game_class_name:
            save_type = 0x32
        else:
            save_type = 0x31
        sav_file = compress_gvas_to_sav(gvas_file.write(PALWORLD_CUSTOM_PROPERTIES), save_type)
        print("Done")

        print("Saving Sav file...", end="", flush=True)
        with open(output_path, "wb") as f:
            f.write(sav_file)
        print("Done")


def search_keys(dicts, key, level=""):
    if isinstance(dicts, dict):
        if key in dicts:
            print("Found at %s->%s" % (level, key))
        for k in dicts:
            if isinstance(dicts[k], dict) or isinstance(dicts[k], list):
                search_keys(dicts[k], key, level+"->"+k)
    elif isinstance(dicts, list):
        for idx, l in enumerate(dicts):
            if isinstance(l, dict) or isinstance(l, list):
                search_keys(l, key, level+"[%d]" % idx)

def search_values(dicts, key, level=""):
    try:
        uuid_match = uuid.UUID(str(key))
    except ValueError:
        uuid_match = None
    isFound = False
    if isinstance(dicts, dict):
        if key in dicts.values():
            print("Found value at %s['%s']" % (level, list(dicts.keys())[list(dicts.values()).index(key)]))
            isFound = True
        elif uuid_match in dicts.values():
            print("Found UUID  at %s['%s']" % (level, list(dicts.keys())[list(dicts.values()).index(uuid_match)]))
            isFound = True
        for k in dicts:
            if isinstance(dicts[k], dict) or isinstance(dicts[k], list):
                isFound |= search_values(dicts[k], key, level+"['%s']"%k)
    elif isinstance(dicts, list):
        if key in dicts:
            print("Found value at %s[%d]" % (level, dicts.index(key)))
            isFound = True
        elif uuid_match in dicts:
            print("Found UUID  at %s[%d]" % (level, dicts.index(uuid_match)))
            isFound = True
        for idx, l in enumerate(dicts):
            if isinstance(l, dict) or isinstance(l, list):
                isFound |= search_values(l, key, level+"[%d]" % idx)
    return isFound


if __name__ == "__main__":
    main()
# CharacterSaveParameterMap             角色数据
# MapObjectSpawnerInStageSaveData       地图数据
# MapObjectSaveData                     地图数据
# FoliageGridSaveDataMap                树莓
# ItemContainerSaveData                 物品库
# CharacterContainerSaveData
# GroupSaveDataMap
# DynamicItemSaveData
#
# WorkSaveData
# BaseCampSaveData
# CharacterParameterStorageSaveData
# GameTimeSaveData
# BossSpawnerSaveData
# EnemyCampSaveData
# DungeonPointMarkerSaveData
# DungeonSaveData


# Check for ItemContainerSaveData
# for item in wsd['MapObjectSaveData']['value']['values']:
#     # pp.pprint(item['key']['InstanceId']['value'])
#     mapObjectMeta = {}
#     for m_k in item:
#         mapObjectMeta[m_k] = item[m_k]['value']
#     # data from MapObjectSpawnerInStageSaveData
#     print(mapObjectMeta['MapObjectInstanceId'])
#     break
#
# for key in wsd['GroupSaveDataMap']['value']:
#     print("%40s" % key, len(str(wsd['GroupSaveDataMap']['value'][key])) / 1048576)
#
# pp.pprint(wsd['CharacterSaveParameterMap']['value'])
