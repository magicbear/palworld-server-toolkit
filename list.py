import glob, os, datetime, zlib, subprocess
from operator import itemgetter, attrgetter
from rcon.source import Client
import json
import os
import sys

client = Client('127.0.0.1', 25575, passwd='your password', timeout=0.5)
client.connect(True)
# print(client.run('Info'))

uesave_path = "/root/.cargo/bin/uesave"
player_cache = "/data/Pal-Server/player.txt"
mapping = {}

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

def prettySaveStruct(data, level = 0):
    simpleType = ['DateTime', 'Guid', 'LinearColor', 'Quat', 'Vector', 'PalContainerId']
    if "Struct" in data:
        if 'struct_type' in data['Struct']:
            if data['Struct']['struct_type'] == 'DateTime':
                print("%s<Value Type='DateTime'>%d</Value>" % ("  " * level, data['Struct']['value']['DateTime']))
            elif data['Struct']['struct_type'] == 'Guid':
                print("\033[96m%s\033[0m" % (data['Struct']['value']['Guid']), end="")
            elif data['Struct']['struct_type'] == "LinearColor":
                print("%.f %.f %.f %.f" % (data['Struct']['value']['LinearColor']['r'],
                                                                               data['Struct']['value']['LinearColor']['g'],
                                                                               data['Struct']['value']['LinearColor']['b'],
                                                                               data['Struct']['value']['LinearColor']['a']), end="")
            elif data['Struct']['struct_type'] == "Quat":
                print("%.f %.f %.f %.f" % (data['Struct']['value']['Quat']['x'],
                                                                               data['Struct']['value']['Quat']['y'],
                                                                               data['Struct']['value']['Quat']['z'],
                                                                               data['Struct']['value']['Quat']['w']), end="")
            elif data['Struct']['struct_type'] == "Vector":
                print("%.f %.f %.f" % (data['Struct']['value']['Vector']['x'],
                                                                               data['Struct']['value']['Vector']['y'],
                                                                               data['Struct']['value']['Vector']['z']), end="")
            elif "Struct" in data['Struct']['struct_type'] and data['Struct']['struct_type']["Struct"] == "PalContainerId":
                print("\033[36m%s\033[0m" % data['Struct']['value']['Struct']['ID']['Struct']['value']['Guid'], end="")
            elif isinstance(data['Struct']['struct_type'], dict):
                print("%s<%s>" % ("  " * level, data['Struct']['struct_type']['Struct']))
                # prettySaveStruct(data['Struct']['value']['Struct'], level + 1)
                for key in data['Struct']['value']:
                    prettySaveStruct(data['Struct']['value'], level + 1)
                print("%s</%s>" % ("  " * level, data['Struct']['struct_type']['Struct']))
            else:
                print("Unknow Type ", data['Struct']['struct_type'])
        else:
            for key in data['Struct']:
                if 'Struct' in data['Struct'][key] and 'struct_type' in data['Struct'][key]['Struct'] and (data['Struct'][key]['Struct']['struct_type'] in simpleType or
                                                                                                           ("Struct" in data['Struct'][key]['Struct']['struct_type'] and data['Struct'][key]['Struct']['struct_type']['Struct'] in simpleType)):
                    print("%s<%s type='%s'>" % ("  " * level, key, data['Struct'][key]['Struct']['struct_type']), end="")
                    prettySaveStruct(data['Struct'][key], level + 1)
                    print("</%s>" % (key))
                elif "Int" in data['Struct'][key]:
                    print("%s<%s Type='int'>\033[95m%d\033[0m</%s>" % ("  " * level, key, data['Struct'][key]['Int']['value'], key))
                elif "Float" in data['Struct'][key]:
                    print("%s<%s Type='Float'>\033[95m%f\033[0m</%s>" % ("  " * level, key, data['Struct'][key]['Float']['value'], key))
                elif "Bool" in data['Struct'][key]:
                    print("%s<%s Type='Bool'>\033[91m%d\033[0m</%s>" % ("  " * level, key, data['Struct'][key]['Bool']['value'], key))
                elif "Name" in data['Struct'][key]:
                    print("%s<%s Type='Name'>\033[93m%s\033[0m</%s>" % ("  " * level, key, data['Struct'][key]['Name']['value'], key))
                elif "Array" in data['Struct'][key]:
                    print("%s<%s Type='Array' array_type='%s'>%s</%s>" % ("  " * level, key, data['Struct'][key]['Array']['array_type'],
                                                                          data['Struct'][key]['Array']['value']['Base']['Name'],
                                                                          key))
                # elif "Struct" in data['Struct'][key] and 'struct_type' in data['Struct'][key]['Struct'] and "Struct" in data['Struct'][key]['Struct']['struct_type'] and data['Struct'][key]['Struct']['struct_type']['Struct'] == "PalContainerId":
                #     print("%s<%s Type='PalContainerId'>\033[36m%s\033[0m</%s>" % ("  " * level, key, data['Struct'][key]['Struct']['value']['Struct']['ID']['Struct']['value']['Guid'], key))
                else:
                    print("%s<%s Type='\033[31munknow struct\033[0m'>" % ("  " * level, key))
                    prettySaveStruct(data['Struct'][key], level + 1)
                    print("%s</%s>" % ("  " * level, key))
    else:

        print("%s%s" % ("  " * level, data))

with open(player_cache,"wb") as f:
    for k in mapping:
        f.write((",".join(mapping[k])+"\n").encode('utf-8'))

savlist = glob.glob("*.sav")
lists = []
for sav in savlist:
    lists.append({'mt': os.stat(sav).st_mtime, 'file': sav})

lists.sort(key=itemgetter('mt'))
for item in lists:
    sav = item['file']
    save_path = item['file']
    #  or int(sav[0:8], 16) not in mapping
    if len(sys.argv) > 1 and sys.argv[1] in sav:
        with open(item['file'], "rb") as f:
            # Read the file
            data = f.read()
            uncompressed_len = int.from_bytes(data[0:4], byteorder="little")
            compressed_len = int.from_bytes(data[4:8], byteorder="little")
            magic_bytes = data[8:11]
            save_type = data[11]
            # Check for magic bytes
            if magic_bytes != b"PlZ":
                raise Exception(
                    f"File {save_path} is not a save file, found {magic_bytes} instead of P1Z"
                )
            # Valid save types
            if save_type not in [0x30, 0x31, 0x32]:
                raise Exception(f"File {save_path} has an unknown save type: {save_type}")
            # We only have 0x31 (single zlib) and 0x32 (double zlib) saves
            if save_type not in [0x31, 0x32]:
                raise Exception(
                    f"File {save_path} uses an unhandled compression type: {save_type}"
                )
            if save_type == 0x31:
                # Check if the compressed length is correct
                if compressed_len != len(data) - 12:
                    raise Exception(
                        f"File {save_path} has an incorrect compressed length: {compressed_len}"
                    )
            # Decompress file
            uncompressed_data = zlib.decompress(data[12:])
            if save_type == 0x32:
                # Check if the compressed length is correct
                if compressed_len != len(uncompressed_data):
                    raise Exception(
                        f"File {save_path} has an incorrect compressed length: {compressed_len}"
                    )
                # Decompress file
                uncompressed_data = zlib.decompress(uncompressed_data)
            # Check if the uncompressed length is correct
            if uncompressed_len != len(uncompressed_data):
                raise Exception(
                    f"File {save_path} has an incorrect uncompressed length: {uncompressed_len}"
                )
            # Convert to json with uesave
            # Run uesave.exe with the uncompressed file piped as stdin
            # stdout will be the json string
            uesave_run = subprocess.run(
                [uesave_path, "to-json"],
                input=uncompressed_data,
                capture_output=True,
            )
            jsondata = uesave_run.stdout.decode("utf-8")
            # print(jsondata)
            data = json.loads(jsondata)
            prettySaveStruct(data['root']['properties']['SaveData'])
            # print(data['root']['properties']['SaveData']['Struct']['value']['Struct']['PlayerUId']['Struct']['value']['Guid'])
            # print('grep -F \'"admin_player_uid": "%s"\' -B 1 -A 10 Level.sav.json' % data['root']['properties']['SaveData']['Struct']['value']['Struct']['PlayerUId']['Struct']['value']['Guid'])
            break
    elif len(sys.argv) == 1:
        print("%s -> %d\t %s\t%s\t %s" % (sav[0:8], int(sav[0:8], 16),
            str(datetime.datetime.fromtimestamp(int(item['mt']))),
            mapping[int(sav[0:8], 16)][0] if int(sav[0:8], 16) in mapping else "",
            "https://steamcommunity.com/profiles/" + mapping[int(sav[0:8], 16)][2] if int(sav[0:8], 16) in mapping else ""))