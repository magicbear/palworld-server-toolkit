#!/usr/bin/env python3
# Author: MagicBear
# License: MIT License

import glob, sys, os, datetime, zlib, subprocess
from operator import itemgetter, attrgetter

module_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, module_dir)
sys.path.insert(0, os.path.join(module_dir, "../save_tools"))
sys.path.insert(0, os.path.join(module_dir, "../palworld-save-tools"))

from .rcon.source import Client
import argparse
import json
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.archive import *
from pathlib import Path

def main():
    global output_file, output_path, args, gui, playerMapping, instanceMapping

    parser = argparse.ArgumentParser(
        prog="palworld-playey-list",
        description="List player on the Players Folder",
    )
    parser.add_argument("filename", help="Filename of the player sav", nargs='?')
    parser.add_argument(
        "--host",
        "-H",
        default="127.0.0.1",
        help="Host for PalWorld Server RCON",
    )
    parser.add_argument(
        "--port",
        "-P",
        type=int,
        default=25575,
        help="PalWorld Server RCON Port",
    )
    parser.add_argument(
        "--password",
        "-p",
        help="RCON Password",
    )
    
    args = parser.parse_args()
    
    if not os.path.exists("%s/.config" % Path.home()):
        os.mkdir("%s/.config" % Path.home())
        
    if not os.path.exists("%s/.config/palworld-server-toolkit" % Path.home()):
        os.mkdir("%s/.config/palworld-server-toolkit" % Path.home())
    
    player_cache = "%s/.config/palworld-server-toolkit/player.txt" % Path.home()
    mapping = {}
    
    if os.path.exists(player_cache):
        with open(player_cache,"rb") as f:
            for line in f:
                try:
                    rs = line.decode("utf-8").strip().split(",")
                except UnicodeDecodeError as e:
                    continue
                if len(rs) == 3:
                    try:
                        mapping[int(rs[1])] = rs
                    except ValueError as e:
                        pass

    if args.password:
        client = Client(args.host, args.port, passwd=args.password, timeout=0.5)
        client.connect(True)
    
        try:
            players = client.run('ShowPlayers').split("\n")
            for player in players:
                player = player.split(",")
                if len(player) != 3:
                    break
                if player[0] == "name":
                    continue
                mapping[int(player[1])] = player
        except UnicodeDecodeError as e:
            pass

    with open(player_cache, "wb") as f:
        for k in mapping:
            f.write((",".join(mapping[k]) + "\n").encode('utf-8'))

    savlist = glob.glob("*.sav")
    lists = []
    for sav in savlist:
        lists.append({'mt': os.stat(sav).st_mtime, 'file': sav})

    lists.sort(key=itemgetter('mt'))
    for item in lists:
        sav = item['file']
        save_path = item['file']
        #  or int(sav[0:8], 16) not in mapping
        if args.filename is not None and args.filename in sav:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, os.path.join(module_dir, "save_tools"))
            sys.path.insert(0, os.path.join(module_dir, "palworld-save-tools"))

            with open(item['file'], "rb") as f:
                # Read the file
                data = f.read()

                raw_gvas, _ = decompress_sav_to_gvas(data)
                player_gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
                PrettyPrint(player_gvas_file.properties['SaveData'])
                break
        elif args.filename is None:
            print("%s -> %d\t %s\t%s\t %s" % (sav[0:8], int(sav[0:8], 16),
                                              str(datetime.datetime.fromtimestamp(int(item['mt']))),
                                              mapping[int(sav[0:8], 16)][0] if int(sav[0:8], 16) in mapping else "",
                                              "https://steamcommunity.com/profiles/" + mapping[int(sav[0:8], 16)][
                                                  2] if int(sav[0:8], 16) in mapping else ""))


def PrettyPrint(data, level = 0):
    simpleType = ['DateTime', 'Guid', 'LinearColor', 'Quat', 'Vector', 'PalContainerId']
    if 'struct_type' in data:
        if data['struct_type'] == 'DateTime':
            print("%s<Value Type='DateTime'>%d</Value>" % ("  " * level, data['value']))
        elif data['struct_type'] == 'Guid':
            print("\033[96m%s\033[0m" % (data['value']), end="")
        elif data['struct_type'] == "LinearColor":
            print("%.f %.f %.f %.f" % (data['value']['r'],
                                                                           data['value']['g'],
                                                                           data['value']['b'],
                                                                           data['value']['a']), end="")
        elif data['struct_type'] == "Quat":
            print("%.f %.f %.f %.f" % (data['value']['x'],
                                                                           data['value']['y'],
                                                                           data['value']['z'],
                                                                           data['value']['w']), end="")
        elif data['struct_type'] == "Vector":
            print("%.f %.f %.f" % (data['value']['x'],
                                                                           data['value']['y'],
                                                                           data['value']['z']), end="")
        elif data['struct_type'] == "PalContainerId":
            print("\033[96m%s\033[0m" % (data['value']['ID']['value']), end="")
        elif isinstance(data['struct_type'], dict):
            print("%s<%s>" % ("  " * level, data['struct_type']))
            for key in data['value']:
                PrettyPrint(data['value'], level + 1)
            print("%s</%s>" % ("  " * level, data['struct_type']))
        else:
            PrettyPrint(data['value'], level + 1)
    else:
        for key in data:
            if not isinstance(data[key], dict):
                print("%s<%s type='unknow'>%s</%s>" % ("  " * level, key, data[key], key))
                continue
            if 'struct_type' in data[key] and data[key]['struct_type'] in simpleType:
                print("%s<%s type='%s'>" % ("  " * level, key, data[key]['struct_type']), end="")
                PrettyPrint(data[key], level + 1)
                print("</%s>" % (key))
            elif 'type' in data[key] and data[key]['type'] in ["IntProperty", "Int64Property", "BoolProperty"]:
                print("%s<%s Type='%s'>\033[95m%d\033[0m</%s>" % ("  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] == "FloatProperty":
                print("%s<%s Type='%s'>\033[95m%f\033[0m</%s>" % ("  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] in ["StrProperty", "ArrayProperty", "NameProperty"]:
                print("%s<%s Type='%s'>\033[95m%s\033[0m</%s>" % ("  " * level, key, data[key]['type'], data[key]['value'], key))
            elif isinstance(data[key], list):
                print("%s<%s Type='%s'>%s</%s>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[
                    key] else "\033[31munknow struct\033[0m", str(data[key]), key))
            else:
                print("%s<%s Type='%s'>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[key] else "\033[31munknow struct\033[0m"))
                PrettyPrint(data[key], level + 1)
                print("%s</%s>" % ("  " * level, key))


if __name__ == "__main__":
    main()
