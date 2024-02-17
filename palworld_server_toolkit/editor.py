#!/usr/bin/env python3
# Author: MagicBear
# License: MIT License
import json
import os, datetime, time
import pathlib
import sys
import threading
import pprint
import uuid
import argparse
import copy
import importlib.metadata
import traceback
from functools import reduce
import multiprocessing
import tarfile

module_dir = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists("%s/resources/gui.json" % module_dir) and getattr(sys, 'frozen', False):
    module_dir = os.path.dirname(sys.executable)

sys.path.insert(0, module_dir)
sys.path.insert(0, os.path.join(module_dir, "../"))
sys.path.insert(0, os.path.join(module_dir, "../save_tools"))
from palworld_server_toolkit.palobject import *
from palworld_save_tools.gvas import GvasFile, GvasHeader
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS
from palworld_save_tools.archive import *

try:
    from palworld_save_tools.rawdata import map_concrete_model_module
except ImportError as e:
    raise ImportError("Please update palworld_save_tools to >=0.18.0")

sys.path.insert(0, os.path.join(module_dir, "PalEdit"))

try:
    import tkinter as tk
    import tkinter.font
    from tkinter import ttk
    from tkinter import messagebox
    from tkinter import filedialog
    from tkinter import simpledialog
except ImportError:
    print("ERROR: Without Tkinter Environment, GUI not work")
    pass

try:
    import PalInfo
    from PalEdit import PalEditConfig, PalEdit
except ImportError as e:
    print("ERROR: Include PalEdit failed")
    traceback.print_exception(e)
    pass

try:
    from typing import Self
except ImportError:
    class Self:
        EmptyObject = None

wsd: Optional[dict] = None
output_file = None
gvas_file = None
backup_gvas_file = None
backup_wsd = None
backup_file_path = None
playerMapping = None
output_path = None
args = None
player = None
filetime = -1
gui = None
backup_path: Optional[str] = None
delete_files = []
loadingStatistics = {}


class MappingCacheObject:
    __slots__ = ("_worldSaveData",
                 "PlayerIdMapping", "CharacterSaveParameterMap", "MapObjectSaveData", "MapObjectSpawnerInStageSaveData",
                 "ItemContainerSaveData", "DynamicItemSaveData", "CharacterContainerSaveData", "GroupSaveDataMap",
                 "WorkSaveData", "BaseCampMapping", "GuildSaveDataMap", "GuildInstanceMapping",
                 "FoliageGridSaveDataMap")

    _MappingCacheInstances = {

    }

    @staticmethod
    def get(worldSaveData) -> Self:
        if id(worldSaveData) not in MappingCacheObject._MappingCacheInstances:
            MappingCacheObject._MappingCacheInstances[id(worldSaveData)] = MappingCacheObject(worldSaveData)
        return MappingCacheObject._MappingCacheInstances[id(worldSaveData)]

    def __init__(self, worldSaveData):
        self._worldSaveData = worldSaveData

    def __getattr__(self, item):
        if item == 'WorkSaveData':
            self.LoadWorkSaveData()
            return self.WorkSaveData
        elif item == 'MapObjectSaveData':
            self.LoadMapObjectMaps()
            return self.MapObjectSaveData
        elif item == 'MapObjectSpawnerInStageSaveData':
            self.LoadMapObjectMaps()
            return self.MapObjectSpawnerInStageSaveData
        elif item == 'PlayerIdMapping':
            self.LoadCharacterSaveParameterMap()
            return self.PlayerIdMapping
        elif item == 'CharacterSaveParameterMap':
            self.LoadCharacterSaveParameterMap()
            return self.CharacterSaveParameterMap
        elif item == 'ItemContainerSaveData':
            self.LoadItemContainerMaps()
            return self.ItemContainerSaveData
        elif item == 'DynamicItemSaveData':
            self.LoadItemContainerMaps()
            return self.DynamicItemSaveData
        elif item == 'CharacterContainerSaveData':
            self.LoadCharacterContainerMaps()
            return self.CharacterContainerSaveData
        elif item == 'GroupSaveDataMap':
            self.LoadGroupSaveDataMap()
            return self.GroupSaveDataMap
        elif item == 'GuildSaveDataMap':
            self.LoadGroupSaveDataMap()
            return self.GuildSaveDataMap
        elif item == 'BaseCampMapping':
            self.LoadBaseCampMapping()
            return self.BaseCampMapping
        elif item == 'GuildInstanceMapping':
            self.LoadGuildInstanceMapping()
            return self.GuildInstanceMapping
        elif item == 'FoliageGridSaveDataMap':
            self.LoadMapObjectMaps()
            return self.FoliageGridSaveDataMap

    def LoadWorkSaveData(self):
        load_skipped_decode(self._worldSaveData, ['WorkSaveData'], False)
        self.WorkSaveData = {wrk['RawData']['value']['id']: wrk for wrk in
                             self._worldSaveData['WorkSaveData']['value']['values']}

    def LoadMapObjectMaps(self):
        load_skipped_decode(self._worldSaveData, ['MapObjectSaveData', 'MapObjectSpawnerInStageSaveData'], False)
        self.MapObjectSaveData = {
            mapobj['MapObjectInstanceId']['value']: mapobj for mapobj in
            self._worldSaveData['MapObjectSaveData']['value']['values']}
        self.MapObjectSpawnerInStageSaveData = {
            mapObj['key']: mapObj
            for mapObj in
            self._worldSaveData['MapObjectSpawnerInStageSaveData']['value'][0]['value'][
                'SpawnerDataMapByLevelObjectInstanceId']['value']
        }
        self.FoliageGridSaveDataMap = {

        }
        # for foliage in self._worldSaveData['FoliageGridSaveDataMap']['value']:
        #     modelMaps = foliage['value']['ModelMap']['value']
        #     for model in modelMaps:
        #         self.FoliageGridSaveDataMap.update({
        #             inst['key']['Guid']['value']: foliage for inst in model['value']['InstanceDataMap']['value']
        #         })

    def LoadCharacterSaveParameterMap(self):
        self.CharacterSaveParameterMap = {character['key']['InstanceId']['value']: character for character in
                                          self._worldSaveData['CharacterSaveParameterMap']['value']}
        self.PlayerIdMapping = {character['key']['PlayerUId']['value']: character for character in
                                filter(lambda x: 'IsPlayer' in
                                                 x['value']['RawData']['value']['object']['SaveParameter']['value'],
                                       self._worldSaveData['CharacterSaveParameterMap']['value'])}

    def LoadItemContainerMaps(self):
        load_skipped_decode(self._worldSaveData, ['ItemContainerSaveData', 'DynamicItemSaveData'], False)
        self.ItemContainerSaveData = {container['key']['ID']['value']: container for container in
                                      self._worldSaveData['ItemContainerSaveData']['value']}
        self.DynamicItemSaveData = {dyn_item_data['ID']['value']['LocalIdInCreatedWorld']['value']: dyn_item_data
                                    for
                                    dyn_item_data in self._worldSaveData['DynamicItemSaveData']['value']['values']}

    def LoadCharacterContainerMaps(self):
        load_skipped_decode(self._worldSaveData, ['CharacterContainerSaveData'], False)
        self.CharacterContainerSaveData = {container['key']['ID']['value']: container for container in
                                           self._worldSaveData['CharacterContainerSaveData']['value']}

    def LoadGroupSaveDataMap(self):
        self.GroupSaveDataMap = {group['key']: group for group in self._worldSaveData['GroupSaveDataMap']['value']}
        self.GuildSaveDataMap = {group['key']: group for group in
                                 filter(lambda x: x['value']['GroupType']['value']['value'] == "EPalGroupType::Guild",
                                        self._worldSaveData['GroupSaveDataMap']['value'])}

    def LoadBaseCampMapping(self):
        self.BaseCampMapping = {base['key']: base for base in self._worldSaveData['BaseCampSaveData']['value']}

    def LoadGuildInstanceMapping(self):
        self.GuildInstanceMapping = {}
        for group_id in self.GuildSaveDataMap:
            group_data = parse_item(self.GuildSaveDataMap[group_id], "GroupSaveDataMap")
            item = group_data['value']['RawData']['value']
            self.GuildInstanceMapping.update(
                {ind_char['guid']: ind_char['instance_id'] for ind_char in item['individual_character_handle_ids']})

    def __del__(self):
        for key in wsd:
            if isinstance(self._worldSaveData[key]['value'], MPMapProperty):
                self._worldSaveData[key]['value'].close()
                self._worldSaveData[key]['value'].release()
            elif isinstance(self._worldSaveData[key]['value'], dict) and 'values' in self._worldSaveData[key][
                'value'] and isinstance(
                self._worldSaveData[key]['value']['values'], MPArrayProperty):
                self._worldSaveData[key]['value']['values'].close()
                self._worldSaveData[key]['value']['values'].release()


MappingCache: MappingCacheObject = None

loadingTitle = ""


def set_loadingTitle(title):
    loadingTitle = title
    print("\033]0;%s\a" % loadingTitle, end="", flush=True)


class skip_loading_progress(threading.Thread):
    def __init__(self, reader, size):
        super().__init__()
        self.reader = reader
        self.size = size

    def run(self) -> None:
        try:
            while not self.reader.eof():
                print("\033]0;%s - %3.1f%%\a" % (loadingTitle, 100 * self.reader.progress() / self.size), end="",
                      flush=True)
                print("%3.0f%%" % (100 * self.reader.progress() / self.size), end="\b\b\b\b", flush=True)
                try:
                    if gui is not None:
                        gui.progressbar['value'] = 100 * self.reader.data.tell() / self.size
                except AttributeError:
                    pass
                except RuntimeError:
                    pass
                time.sleep(0.05)
        except ValueError:
            pass
        try:
            if gui is not None:
                gui.progressbar['value'] = 100
        except AttributeError:
            pass
        except RuntimeError:
            pass


class ProgressGvasFile(GvasFile):
    @staticmethod
    def read(
            data: bytes,
            type_hints: dict[str, str] = {},
            custom_properties: dict[str, tuple[Callable, Callable]] = {},
            allow_nan: bool = True,
    ) -> "ProgressGvasFile":
        gvas_file = GvasFile()
        with FProgressArchiveReader(
                data,
                type_hints=type_hints,
                custom_properties=custom_properties,
                allow_nan=allow_nan,
                reduce_memory=getattr(args, "reduce_memory", False),
                check_err=getattr(args, "check_file", False),
        ) as reader:
            skip_loading_progress(reader, len(data)).start()
            gvas_file.header = GvasHeader.read(reader)
            gvas_file.properties = reader.properties_until_end()
            gvas_file.trailer = reader.read_to_end()
            if gvas_file.trailer != b"\x00\x00\x00\x00":
                print(
                    f"{len(gvas_file.trailer)} bytes of trailer data, file may not have fully parsed"
                )
        return gvas_file


def parse_item(properties, skip_path):
    if isinstance(properties, dict):
        if 'skip_type' in properties:
            # print("Parsing worldSaveData.%s..." % skip_path, end="", flush=True)
            properties_parsed = parse_skiped_item(properties, skip_path, False, True)
            for k in properties_parsed:
                properties[k] = properties_parsed[k]
            # print("Done")
        else:
            for key in properties:
                call_skip_path = skip_path + "." + key[0].upper() + key[1:]
                properties[key] = parse_item(properties[key], call_skip_path)
    elif isinstance(properties, list):
        top_skip_path = ".".join(skip_path.split(".")[:-1])
        for idx, item in enumerate(properties):
            properties[idx] = parse_item(item, top_skip_path)
    return properties


def parse_skiped_item(properties, skip_path, progress=True, recursive=True, mp=None):
    if "skip_type" not in properties:
        return properties

    writer = FArchiveWriter(PALWORLD_CUSTOM_PROPERTIES)
    if properties["skip_type"] == "ArrayProperty":
        writer.fstring(properties["array_type"])
        writer.optional_guid(properties.get("id", None))
        writer.write(properties['value'])
    elif properties["skip_type"] == "MapProperty":
        writer.fstring(properties["key_type"])
        writer.fstring(properties["value_type"])
        writer.optional_guid(properties.get("id", None))
        writer.write(properties["value"])
    elif properties["skip_type"] == "StructProperty":
        writer.fstring(properties["struct_type"])
        writer.guid(properties["struct_id"])
        writer.optional_guid(properties.get("id", None))
        writer.write(properties["value"])

    keep_custom_type = False
    if recursive:
        localProperties = copy.deepcopy(PALWORLD_CUSTOM_PROPERTIES)
    else:
        localProperties = copy.deepcopy(SKP_PALWORLD_CUSTOM_PROPERTIES)
    if ".worldSaveData.%s" % skip_path in PALWORLD_CUSTOM_PROPERTIES:
        localProperties[".worldSaveData.%s" % skip_path] = PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.%s" % skip_path]
        keep_custom_type = True
    elif ".worldSaveData.%s" % skip_path in localProperties:
        del localProperties[".worldSaveData.%s" % skip_path]

    with FProgressArchiveReader(
            writer.bytes(), PALWORLD_TYPE_HINTS,
            localProperties,
            reduce_memory=getattr(args, "reduce_memory", False)
    ) as reader:
        if progress:
            skip_loading_progress(reader, len(properties['value'])).start()
        if reader.mp_loading and mp is not None and properties["skip_type"] == "MapProperty":
            mp[f".worldSaveData.{skip_path}"] = reader.load_mp_map(properties, f".worldSaveData.{skip_path}",
                                                                   len(properties['value']))
        elif reader.mp_loading and mp is not None and properties["skip_type"] == "ArrayProperty":
            mp[f".worldSaveData.{skip_path}"] = reader.load_mp_array(properties, f".worldSaveData.{skip_path}",
                                                                     len(properties['value']))
        else:
            decoded_properties = reader.property(properties["skip_type"], len(properties['value']),
                                                 ".worldSaveData.%s" % skip_path)
            for k in decoded_properties:
                properties[k] = decoded_properties[k]
    if not keep_custom_type:
        del properties['custom_type']
    del properties["skip_type"]
    return properties


#
# import json
# from palworld_save_tools.json_tools import  CustomEncoder

def load_skipped_decode(_worldSaveData, skip_paths, recursive=True):
    if isinstance(skip_paths, str):
        skip_paths = [skip_paths]

    mp = {}
    t2 = time.time()
    parsed = 0
    skip_paths.sort()
    for skip_path in sorted(skip_paths,
                            key=lambda x: 'Z' + x if f".worldSaveData.{x}" in PALWORLD_CUSTOM_PROPERTIES else x):
        properties = _worldSaveData[skip_path]

        if "skip_type" not in properties:
            continue
        parsed += 1
        print("Parsing .worldSaveData.%s..." % skip_path, end="", flush=True)
        t1 = time.time()
        parse_skiped_item(properties, skip_path, True, recursive,
                          None if f".worldSaveData.{skip_path}" in PALWORLD_CUSTOM_PROPERTIES else mp)
        print("Done in %.2fs" % (time.time() - t1))

    while mp is not None and len(mp.keys()) > 0:
        s = len(mp.keys())
        for mp_path in mp:
            mp[mp_path].join(timeout=0)
            t3 = time.time() - t2
            if mp[mp_path].is_alive():
                continue
            if mp_path in PALWORLD_CUSTOM_PROPERTIES:
                with FProgressArchiveReader(
                        b"", PALWORLD_TYPE_HINTS,
                        PALWORLD_CUSTOM_PROPERTIES
                ) as reader:
                    reader.fallbackData = _worldSaveData[mp_path[15:]]
                    _worldSaveData[mp_path[15:]] = PALWORLD_CUSTOM_PROPERTIES[mp_path][0](reader,
                                                                                          _worldSaveData[mp_path[15:]][
                                                                                              'type'], -1, mp_path)
                    _worldSaveData[mp_path[15:]]["custom_type"] = mp_path
            print("Loading %s in %.2fs, extra parse %.2fs" % (mp_path, t3, time.time() - t2 - t3))
            del mp[mp_path]
            break
        if len(mp.keys()) - s == 0:
            time.sleep(0.01)
    if parsed > 0:
        print("Parse skipped data in %.2fs" % (time.time() - t2))


# ArrayProperty: -> .Value
# MapProperty: -> Duplicate with Parent Name ['KeyName']
SKP_PALWORLD_CUSTOM_PROPERTIES = copy.deepcopy(PALWORLD_CUSTOM_PROPERTIES)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.MapObjectSaveData"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldLocation"] = (
    skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldRotation"] = (
    skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.MapObjectSaveData.MapObjectSaveData.Model.Value.EffectMap"] = (
    skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldScale3D"] = (
    skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.FoliageGridSaveDataMap"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.MapObjectSpawnerInStageSaveData"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.DynamicItemSaveData"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.CharacterContainerSaveData"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.CharacterContainerSaveData.Value.Slots"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.CharacterContainerSaveData.Value.RawData"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.ItemContainerSaveData"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.ItemContainerSaveData.Value.BelongInfo"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.ItemContainerSaveData.Value.Slots"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.ItemContainerSaveData.Value.RawData"] = (skip_decode, skip_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.GroupSaveDataMap"] = (group_decode, group_encode)
SKP_PALWORLD_CUSTOM_PROPERTIES[".worldSaveData.GroupSaveDataMap.Value.RawData"] = (skip_decode, skip_encode)


def gui_thread():
    try:
        global gui
        gui = GUI()
        gui.load()
        gui.mainloop()
    except tk.TclError:
        print(f"{tcl(31)}Failed to create GUI{tcl(0)}")
        pass


def main():
    global output_file, output_path, args, gui, playerMapping

    parser = argparse.ArgumentParser(
        prog="palworld-save-editor",
        description="Editor for the Level.sav",
    )
    parser.add_argument("filename")
    parser.add_argument(
        "--statistics",
        action="store_true",
        help="Show the statistics for all key",
    )
    parser.add_argument(
        "--fix-duplicate",
        action="store_true",
        help="Fix duplicate user data",
    )
    parser.add_argument(
        "--del-unref-item",
        action="store_true",
        help="Delete Unref Item",
    )
    parser.add_argument(
        "--del-damage-object",
        action="store_true",
        help="Delete Damage Object",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: <filename>_fixed.sav)",
    )
    parser.add_argument(
        "--gui",
        "-g",
        action="store_true",
        help="Open GUI",
    )
    parser.add_argument(
        "--reduce-memory",
        "-r",
        action="store_true",
        help="Reduce Memory",
    )
    parser.add_argument(
        "--check-file",
        "-c",
        action="store_true",
        help="Check error on the file",
    )
    parser.add_argument(
        "--dot",
        "-d",
        action="store_true",
        help="dump graphviz dot file",
    )

    if len(sys.argv) == 1:
        bk_f = filedialog.askopenfilename(filetypes=[("Level.sav file", "*.sav")], title="Open Level.sav")
        if bk_f:
            args = type('', (), {})()
            args.filename = bk_f
            args.gui = True
            args.statistics = False
            args.output = None
        else:
            args = parser.parse_args(sys.argv[1:])
    else:
        args = parser.parse_args(sys.argv[1:])

    modify_to_file = reduce(lambda x, b: x or getattr(args, b, False),
                            filter(lambda x: 'del_' in x or 'fix_' in x, dir(args)),
                            False)
    if not modify_to_file and not sys.flags.interactive and not getattr(args, "dot", False):
        # Open GUI for no any edit flags
        args.gui = True

    if not os.path.exists(args.filename):
        print(f"{args.filename} does not exist")
        exit(1)

    if not os.path.isfile(args.filename):
        print(f"{args.filename} is not a file")
        exit(1)

    t1 = time.time()
    LoadFile(args.filename)

    if args.gui and sys.platform == 'darwin':
        if sys.flags.interactive:
            print("Error: Mac OS python not support interactive with GUI")
            gui = GUI()
            gui.load()
            gui.gui.update()
    #         gui_thread()
    #         sys.exit(0)
    elif args.gui and sys.flags.interactive:
        threading.Thread(target=gui_thread, daemon=True).start()

    if args.statistics:
        Statistics()

    if args.output is None:
        output_path = args.filename
    else:
        output_path = args.output

    if getattr(args, "dot", False):
        buildDotImage()

    try:
        ShowGuild()
        playerMapping = LoadPlayers(data_source=wsd)
        ShowPlayers()
    except KeyError as e:
        traceback.print_exception(e)
        print("ERROR: Corrupted Save File")
        Statistics()

    print("Total load in %.3fms" % (1000 * (time.time() - t1)))

    if getattr(args, "fix_duplicate", False):
        FixDuplicateUser()
    if getattr(args, "del_unref_item", False):
        BatchDeleteUnreferencedItemContainers()
    if getattr(args, 'del_damage_object', False):
        FixBrokenDamageRefContainer()

    if sys.flags.interactive:
        print("Go To Interactive Mode (no auto save), we have follow command:")
        print("  ShowPlayers()                              - List the Players")
        print("  FixDuplicateUser(dry_run=False)            - Remove duplicate player instance")
        print("  ShowGuild()                                - List the Guild and members")
        print("  BindGuildInstanceId(uid,instance_id)       - Update Guild binding instance for user")
        print("  RenamePlayer(uid,new_name)                 - Rename player to new_name")
        print("  DeletePlayer(uid,InstanceId=None,          ")
        print("               dry_run=False)                - Wipe player data from save")
        print("                                               InstanceId: delete specified InstanceId")
        print("                                               dry_run: only show how to delete")
        print("  DeleteGuild(gid)                           - Delete Guild")
        print("  DeleteBaseCamp(base_id)                    - Delete Guild Base Camp")
        print("  EditPlayer(uid)                            - Allocate player base meta data to variable 'player'")
        print("  OpenBackup(filename)                       - Open Backup Level.sav file and assign to backup_wsd")
        print("  MigratePlayer(old_uid,new_uid)             - Migrate the player from old PlayerUId to new PlayerUId")
        print("                                               Note: the PlayerUId is use in the Sav file,")
        print("                                               when use to fix broken save, you can rename the old ")
        print("                                               player save to another UID and put in old_uid field.")
        print("  CopyPlayer(old_uid,new_uid, backup_wsd)    - Copy the player from old PlayerUId to new PlayerUId ")
        print("  CopyBaseCamp(base_id,new_group_id, backup_wsd) ")
        print("                                             - Copy the basecamp base_id to new guild group id ")
        print("  BatchDeleteUnreferencedItemContainers()    - Delete Unref Item")
        print("  FixBrokenDamageRefContainer()              - Delete Damage Object")
        print("  CleanupWorkerSick()                        - Cleanup WorkerSick flags for all Pals")
        print("  Statistics()                               - Counting wsd block data size")
        print("  Save()                                     - Save the file and exit")
        print()
        print("Advance feature:")
        print("  search_key(wsd, '<value>')                 - Locate the key in the structure")
        print("  search_values(wsd, '<value>')              - Locate the value in the structure")
        print("  PrettyPrint(value)                         - Use XML format to show the value")
        return
    elif args.gui:
        gui_thread()
    elif modify_to_file:
        Save()


try:
    class AutocompleteCombobox(ttk.Combobox):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._hits = None
            self._hit_index = None
            self._completion_list = None
            self.position = None
            if kwargs.get('values'):
                self.set_completion_list(kwargs.get('values'))

        def __setitem__(self, key, value):
            if key == 'value':
                self.set_completion_list(value)
            return super().__setitem__(key, value)

        def set_completion_list(self, completion_list):
            """Use our completion list as our drop down selection menu, arrows move through menu."""
            self._completion_list = sorted(filter(lambda x: x is not None, completion_list),
                                           key=str.lower)  # Work with a sorted list
            self._hits = []
            self._hit_index = 0
            self.position = 0
            self.bind('<KeyRelease>', self.handle_keyrelease)
            self['values'] = self._completion_list  # Setup our popup menu

        def autocomplete(self, delta=0):
            """autocomplete the Combobox, delta may be 0/1/-1 to cycle through possible hits"""
            if delta:  # need to delete selection otherwise we would fix the current position
                self.delete(self.position, tk.constants.END)
            else:  # set position to end so selection starts where textentry ended
                self.position = len(self.get())
            # collect hits
            _hits = []
            for element in self['values']:
                if element.lower().startswith(self.get().lower()):  # Match case insensitively
                    _hits.append(element)
            # if we have a new hit list, keep this in mind
            if _hits != self._hits:
                self._hit_index = 0
                self._hits = _hits
            # only allow cycling if we are in a known hit list
            if _hits == self._hits and self._hits:
                self._hit_index = (self._hit_index + delta) % len(self._hits)
            # now finally perform the auto completion
            if self._hits:
                self.delete(0, tk.constants.END)
                self.insert(0, self._hits[self._hit_index])
                self.select_range(self.position, tk.constants.END)

        def handle_keyrelease(self, event):
            """event handler for the keyrelease event on this widget"""
            # if event.keysym == "BackSpace":
            #     self.delete(self.index(tk.constants.INSERT), tk.constants.END)
            #     self.position = self.index(tk.constants.END)
            # if event.keysym == "Left":
            #     if self.position < self.index(tk.constants.END): # delete the selection
            #         self.delete(self.position, tk.constants.END)
            #     else:
            #         self.position = self.position-1 # delete one character
            #         self.delete(self.position, tk.constants.END)
            # if event.keysym == "Right":
            #     self.position = self.index(tk.constants.END) # go to end (no selection)
            if len(event.keysym) == 1 and event.keysym in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b',
                                                           'c',
                                                           'd', 'e', 'f']:
                self.autocomplete()
            # No need for up/down, we'll jump to the popup
            # list at the position of the autocompletion


    class AutocompleteComboBoxPopup(AutocompleteCombobox):
        def __init__(self, parent, iid, column, **kw):
            ''' If relwidth is set, then width is ignored '''
            super().__init__(master=parent, **kw)
            self._textvariable = kw['textvariable']
            self.tv = parent
            self.iid = iid
            self.column = column
            self['exportselection'] = False
            self.focus_force()
            self.bind("<Return>", self.on_return)
            self.bind("<Control-a>", self.select_all)
            self.bind("<Escape>", lambda *ignore: self.destroy())

        def destroy(self) -> None:
            super().destroy()
            self.tv.set(self.iid, column=self.column, value=self._textvariable.get())

        def on_return(self, event):
            self.tv.item(self.iid, text=self.get())
            self.destroy()

        def select_all(self, *ignore):
            ''' Set selection on the whole text '''
            self.selection_range(0, 'end')
            # returns 'break' to interrupt default key-bindings
            return 'break'


    class EntryPopup(tk.Entry):
        def __init__(self, parent, iid, column, **kw):
            ''' If relwidth is set, then width is ignored '''
            super().__init__(parent, **kw)
            self._textvariable = kw['textvariable']
            self.tv = parent
            self.iid = iid
            self.column = column
            self['exportselection'] = False
            self.focus_force()
            self.bind("<Return>", self.on_return)
            self.bind("<Control-a>", self.select_all)
            self.bind("<Escape>", lambda *ignore: self.destroy())

        def destroy(self) -> None:
            super().destroy()
            self.tv.set(self.iid, column=self.column, value=self._textvariable.get())

        def on_return(self, event):
            self.tv.item(self.iid, text=self.get())
            self.destroy()

        def select_all(self, *ignore):
            ''' Set selection on the whole text '''
            self.selection_range(0, 'end')
            # returns 'break' to interrupt default key-bindings
            return 'break'


    class ParamEditor(tk.Toplevel):
        def __init__(self):
            super().__init__(master=gui.gui)
            self.var_options = None
            self.gui = self
            self.parent = self
            #
            # tk.font.Font(family=
            self.__font = ("Courier New", 12)
            with open(f"{module_dir}/resources/enum.json", "r", encoding="utf-8") as f:
                self.enum_options = json.load(f)
            self.geometry("950x800")

        def delete_select_attribute(self, master, cmbx, attrib):
            if cmbx.current() == -1:
                return
            del attrib[cmbx.get()]
            global ss
            ss = master.children
            for child in master.children:
                child_obj = master.children[child]
                cfg_text = list(child_obj.children.values())[0].config("text")
                if cfg_text[4] == cmbx.get():
                    child_obj.destroy()
                    break
            cmbx['value'] = list(attrib.keys())

        def build_delete_attrib_gui(self, master, attrib):
            g_frame = tk.Frame(master=master)
            g_frame.pack(anchor=tk.constants.W, fill=tk.constants.X, expand=True)
            gp(self)
            tk.Label(master=g_frame, text="Attribute", font=self.__font).pack(side="left")
            cmb_box = AutocompleteCombobox(master=g_frame, font=self.__font, width=30, values=list(attrib.keys()))
            cmb_box.pack(side=tk.RIGHT)

            ttk.Button(master=g_frame, style="custom.TButton", text="❌", width=3, padding=0,
                       command=lambda: self.delete_select_attribute(master, cmb_box, attrib)).pack(side=tk.RIGHT)

        def create_base_frame(self):
            # master = tk.Frame(master=self.gui)
            canvas = tk.Canvas(self.gui)
            y_scroll = tk.Scrollbar(self.gui, orient=tk.VERTICAL, command=canvas.yview)
            scrollable_frame = tk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox("all")
                )
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=y_scroll.set)
            y_scroll.pack(side=tk.constants.RIGHT, fill=tk.constants.Y)

            # tables = ttk.Treeview(master, yscrollcommand=y_scroll.set)
            # tables.pack(fill=tk.constants.BOTH, expand=True)
            canvas.pack(fill=tk.constants.BOTH, expand=True)
            self.maxsize(self.winfo_screenwidth(), self.winfo_screenheight() - 100)
            return scrollable_frame

        def delete_select_item(self, g_frame, attribute_key, attrib_var, attrib, cmbx):
            if cmbx.current() == -1:
                return
            if len(attrib['value']['values']) == 1:
                messagebox.showwarning("At lease keep one variable")
                return
            del attrib['value']['values'][cmbx.current()]
            del attrib_var[cmbx.current()]
            cmbx['values'] = ["Item %d" % i for i in range(len(attrib['value']['values']))]

        def add_select_item(self, g_frame, attribute_key, attrib_var, attrib, cmbx):
            if cmbx.current() == -1:
                return
            attrib['value']['values'].append(copy.deepcopy(attrib['value']['values'][cmbx.current()]))
            attrib_var.append({})
            cmbx['values'] = ["Item %d" % i for i in range(len(attrib['value']['values']))]
            cmbx.current(len(attrib['value']['values']) - 1)

        def build_subgui(self, g_frame, attribute_key, attrib_var, attrib):
            sub_frame = ttk.Frame(master=g_frame, borderwidth=1, relief=tk.constants.GROOVE, padding=2)
            sub_frame.pack(side="right")
            sub_frame_c = ttk.Frame(master=sub_frame)

            sub_frame_item = ttk.Frame(master=sub_frame)
            tk.Label(master=sub_frame_item, font=self.__font, text=attrib['array_type']).pack(side="left")
            cmbx = ttk.Combobox(master=sub_frame_item, font=self.__font, width=20, state="readonly",
                                values=["Item %d" % i for i in range(len(attrib['value']['values']))])
            cmbx.bind("<<ComboboxSelected>>",
                      lambda evt: self.cmb_array_selected(evt, sub_frame_c, attribute_key, attrib_var, attrib))
            cmbx.pack(side=tk.LEFT)
            ttk.Button(master=sub_frame_item, style="custom.TButton", text="✳️", width=3, padding=0,
                       command=lambda: self.add_select_item(g_frame, attribute_key, attrib_var, attrib, cmbx)).pack(
                side=tk.LEFT)
            ttk.Button(master=sub_frame_item, style="custom.TButton", text="❌", width=3, padding=0,
                       command=lambda: self.delete_select_item(g_frame, attribute_key, attrib_var, attrib, cmbx)).pack(
                side=tk.LEFT)

            sub_frame_item.pack(side=tk.TOP, anchor=tk.NE)
            sub_frame_c.pack(side="bottom")

        def valid_int(self, value):
            try:
                int(value)
                return True
            except ValueError as e:
                return False

        def valid_float(self, value):
            try:
                float(value)
                return True
            except ValueError as e:
                return False

        @staticmethod
        def make_attrib_var(master, attrib):
            if not isinstance(attrib, dict):
                return None
            if attrib['type'] in ["IntProperty", "StrProperty", "NameProperty", "FloatProperty", "EnumProperty"]:
                return tk.StringVar(master)
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "FixedPoint64" and \
                    attrib['value']['Value']['type'] == "Int64Property":
                return tk.StringVar(master)
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] in ["DateTime", "Guid", "PalContainerId"]:
                return tk.StringVar(master)
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "Vector":
                return [tk.StringVar(master), tk.StringVar(master), tk.StringVar(master)]
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "LinearColor":
                return [tk.StringVar(master), tk.StringVar(master), tk.StringVar(master), tk.StringVar(master)]
            elif attrib['type'] == "BoolProperty":
                return tk.BooleanVar(master=master)
            elif attrib['type'] == "ArrayProperty" and attrib['array_type'] == "StructProperty":
                attrib_var = []
                for x in range(len(attrib['value']['values'])):
                    attrib_var.append({})
                return attrib_var
            elif attrib['type'] == "ArrayProperty" and attrib['array_type'] == "NameProperty":
                attrib_var = []
                for x in range(len(attrib['value']['values'])):
                    attrib_var.append({})
                return attrib_var

        def assign_attrib_var(self, var, attrib):
            if attrib['type'] in ["IntProperty", "StrProperty", "NameProperty", "FloatProperty"]:
                try:
                    var.set(str(attrib['value']))
                except UnicodeEncodeError:
                    var.set(repr(attrib['value']))
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "FixedPoint64" and \
                    attrib['value']['Value']['type'] == "Int64Property":
                var.set(str(attrib['value']['Value']['value']))
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] in ["DateTime"]:
                var.set(str(attrib['value']))
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "Guid":
                var.set(str(attrib['value']))
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "PalContainerId":
                var.set(str(attrib['value']['ID']['value']))
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] in ["Vector", "Quat"]:
                var[0].set(str(attrib['value']['x']))
                var[1].set(str(attrib['value']['y']))
                var[2].set(str(attrib['value']['z']))
                if attrib['struct_type'] == "Quat":
                    var[2].set(str(attrib['value']['w']))
            elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "LinearColor":
                var[0].set(str(attrib['value']['r']))
                var[1].set(str(attrib['value']['g']))
                var[2].set(str(attrib['value']['b']))
                var[3].set(str(attrib['value']['a']))
            elif attrib['type'] == "BoolProperty":
                var.set(attrib['value'])
            elif attrib['type'] == "EnumProperty":
                var.set(attrib['value']['value'])

        def save(self, attribs, attrib_var, path=""):
            for attribute_key in attribs:
                attrib = attribs[attribute_key]
                if attribute_key not in attrib_var or attrib_var[attribute_key] is None:
                    continue
                if not isinstance(attrib, dict):
                    continue
                if 'type' in attrib:
                    storage_object = attrib
                    storage_key = 'value'
                    if 'value' in attrib:
                        storage_key = 'value'
                    elif 'values' in attrib and 'value_idx' in attrib:
                        storage_object = attrib['values']
                        storage_key = attrib['value_idx']

                    if attrib['type'] == "IntProperty":
                        print("%s%s [%s] = %d -> %d" % (
                            path, attribute_key, attrib['type'], storage_object[storage_key],
                            int(attrib_var[attribute_key].get())))
                        storage_object[storage_key] = int(attrib_var[attribute_key].get())
                    elif attrib['type'] == "FloatProperty":
                        print("%s%s [%s] = %f -> %f" % (
                            path, attribute_key, attrib['type'], storage_object[storage_key],
                            float(attrib_var[attribute_key].get())))
                        storage_object[storage_key] = float(attrib_var[attribute_key].get())
                    elif attrib['type'] == "BoolProperty":
                        print(
                            "%s%s [%s] = %d -> %d" % (
                                path, attribute_key, attrib['type'], storage_object[storage_key],
                                attrib_var[attribute_key].get()))
                        storage_object[storage_key] = attrib_var[attribute_key].get()
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] in ["DateTime"]:
                        print("%s%s [%s.%s] = %d -> %d" % (
                            path, attribute_key, attrib['type'], attrib['struct_type'],
                            storage_object[storage_key],
                            int(attrib_var[attribute_key].get())))
                        storage_object[storage_key] = int(attrib_var[attribute_key].get())
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "FixedPoint64":
                        if attrib['value']['Value']['type'] == "Int64Property":
                            print("%s%s [%s.%s] = %d -> %d" % (
                                path, attribute_key, attrib['type'], attrib['value']['Value']['type'],
                                storage_object[storage_key]['Value']['value'],
                                int(attrib_var[attribute_key].get())))
                            storage_object[storage_key]['Value']['value'] = int(attrib_var[attribute_key].get())
                        else:
                            print("Error: unsupported property type -> %s[%s.%s]" % (
                                attribute_key, attrib['type'], attrib['value']['Value']['type']))
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "Guid":
                        print("%s%s [%s.%s] = %s -> %s" % (
                            path, attribute_key, attrib['type'], attrib['struct_type'],
                            str(storage_object[storage_key]),
                            str(attrib_var[attribute_key].get())))
                        storage_object[storage_key] = toUUID(uuid.UUID(attrib_var[attribute_key].get()))
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "PalContainerId":
                        print("%s%s [%s.%s] = %s -> %s" % (
                            path, attribute_key, attrib['type'], attrib['struct_type'],
                            str(storage_object[storage_key]['ID']['value']),
                            str(attrib_var[attribute_key].get())))
                        storage_object[storage_key]['ID']['value'] = toUUID(uuid.UUID(attrib_var[attribute_key].get()))
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "Vector":
                        print("%s%s [%s.%s] = %f,%f,%f -> %f,%f,%f" % (
                            path, attribute_key, attrib['type'], attrib['struct_type'],
                            storage_object[storage_key]['x'], storage_object[storage_key]['y'],
                            storage_object[storage_key]['z'], float(attrib_var[attribute_key][0].get()),
                            float(attrib_var[attribute_key][1].get()), float(attrib_var[attribute_key][2].get())))
                        storage_object[storage_key]['x'] = float(attrib_var[attribute_key][0].get())
                        storage_object[storage_key]['y'] = float(attrib_var[attribute_key][1].get())
                        storage_object[storage_key]['z'] = float(attrib_var[attribute_key][2].get())
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "Quat":
                        print("%s%s [%s.%s] = %f,%f,%f,%f -> %f,%f,%f,%f" % (
                            path, attribute_key, attrib['type'], attrib['struct_type'],
                            storage_object[storage_key]['x'], storage_object[storage_key]['y'],
                            storage_object[storage_key]['z'], storage_object[storage_key]['w'],
                            float(attrib_var[attribute_key][0].get()), float(attrib_var[attribute_key][1].get()),
                            float(attrib_var[attribute_key][2].get()), float(attrib_var[attribute_key][3].get())))
                        storage_object[storage_key]['x'] = float(attrib_var[attribute_key][0].get())
                        storage_object[storage_key]['y'] = float(attrib_var[attribute_key][1].get())
                        storage_object[storage_key]['z'] = float(attrib_var[attribute_key][2].get())
                        storage_object[storage_key]['w'] = float(attrib_var[attribute_key][3].get())
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "LinearColor":
                        print("%s%s [%s.%s] = %f,%f,%f,%f -> %f,%f,%f,%f" % (
                            path, attribute_key, attrib['type'], attrib['struct_type'],
                            storage_object[storage_key]['r'], storage_object[storage_key]['g'],
                            storage_object[storage_key]['b'], storage_object[storage_key]['a'],
                            float(attrib_var[attribute_key][0].get()), float(attrib_var[attribute_key][1].get()),
                            float(attrib_var[attribute_key][2].get()), float(attrib_var[attribute_key][3].get())))
                        storage_object[storage_key]['r'] = float(attrib_var[attribute_key][0].get())
                        storage_object[storage_key]['g'] = float(attrib_var[attribute_key][1].get())
                        storage_object[storage_key]['b'] = float(attrib_var[attribute_key][2].get())
                        storage_object[storage_key]['a'] = float(attrib_var[attribute_key][3].get())
                    elif attrib['type'] in ["StrProperty", "NameProperty"]:
                        try:
                            print(
                                "%s%s [%s] = %s -> %s" % (
                                    path, attribute_key, attrib['type'], storage_object[storage_key],
                                    attrib_var[attribute_key].get()))
                        except UnicodeEncodeError:
                            pass
                        if self.var_options is not None and attribute_key in self.var_options:
                            try:
                                index = list(self.var_options[attribute_key].values()).index(
                                    attrib_var[attribute_key].get())
                                attrib_var[attribute_key].set(list(self.var_options[attribute_key].keys())[index])
                            except ValueError:
                                if len(attrib_var[attribute_key].get().split(": ")) >= 2:
                                    attrib_var[attribute_key].set(
                                        attrib_var[attribute_key].get().split(": ")[-1].strip())
                                pass
                        storage_object[storage_key] = attrib_var[attribute_key].get()
                    elif attrib['type'] == "EnumProperty":
                        print(
                            "%s%s [%s - %s] = %s -> %s" % (path, attribute_key, attrib['type'], attrib['value']['type'],
                                                           storage_object[storage_key]['value'],
                                                           attrib_var[attribute_key].get()))
                        storage_object[storage_key]['value'] = attrib_var[attribute_key].get()
                    elif attrib['type'] == "ArrayProperty" and attrib['array_type'] == "NameProperty":
                        for idx, item in enumerate(attrib['value']['values']):
                            print("%s%s [%s] = " % (path, attribute_key, attrib['type']))
                            self.save({
                                'Name': {
                                    'type': attrib['array_type'],
                                    'values': attrib['value']['values'],
                                    'value_idx': idx
                                }}, attrib_var[attribute_key][idx], "%s[%d]." % (attribute_key, idx))
                    elif attrib['type'] == "ArrayProperty" and attrib['array_type'] == "StructProperty":
                        for idx, item in enumerate(attrib['value']['values']):
                            print("%s%s [%s] = " % (path, attribute_key, attrib['type']))
                            self.save({
                                attrib['value']['prop_name']: {
                                    'type': attrib['value']['prop_type'],
                                    'struct_type': attrib['value']['type_name'],
                                    'values': attrib['value']['values'],
                                    'value_idx': idx
                                }}, attrib_var[attribute_key][idx], "%s[%d]." % (attribute_key, idx))
                    elif attrib['type'] == "StructProperty":
                        if attrib_var[attribute_key] is None:
                            continue
                        gp(attrib)
                        for key in storage_object[storage_key]:
                            self.save({key: storage_object[storage_key][key]}, attrib_var[attribute_key],
                                      "%s[\"%s\"]." % (attribute_key, key))
                    else:
                        print("Error: unsupported property type -> %s[%s]" % (attribute_key, attrib['type']))

        def build_variable_gui(self, parent, attrib_var, attribs, with_labelframe=True):
            for attribute_key in attribs:
                attrib = attribs[attribute_key]
                if not isinstance(attrib, dict):
                    continue
                if 'type' in attrib:
                    if with_labelframe:
                        g_frame = tk.Frame(master=parent)
                        g_frame.pack(anchor=tk.constants.W, fill=tk.constants.X, expand=True)
                        tk.Label(master=g_frame, text=attribute_key, font=self.__font).pack(side="left")
                    else:
                        g_frame = parent

                    attrib_var[attribute_key] = self.make_attrib_var(master=parent, attrib=attrib)
                    if attrib['type'] == "BoolProperty":
                        tk.Checkbutton(master=g_frame, text="Enabled", variable=attrib_var[attribute_key],
                                       width=40).pack(
                            side=tk.RIGHT)
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "EnumProperty" and attrib['value']['type'] in self.enum_options:
                        if attrib['value']['value'] not in self.enum_options[attrib['value']['type']]:
                            self.enum_options[attrib['value']['type']].append(attrib['value']['value'])
                        AutocompleteCombobox(master=g_frame, font=self.__font, width=40,
                                             textvariable=attrib_var[attribute_key],
                                             values=self.enum_options[attrib['value']['type']]).pack(side="right")
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "ArrayProperty" and attrib['array_type'] in ["StructProperty",
                                                                                        "NameProperty"]:
                        self.build_subgui(g_frame, attribute_key, attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] in ["Guid", "PalContainerId"]:
                        tk.Entry(font=self.__font, master=g_frame, width=50,
                                 textvariable=attrib_var[attribute_key]).pack(
                            side="right", fill=tk.constants.X)
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "Vector":
                        valid_cmd = (self.register(self.valid_float), '%P')
                        tk.Entry(font=self.__font, master=g_frame, width=16,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][2]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.__font, master=g_frame, width=16,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][1]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.__font, master=g_frame, width=16,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][0]).pack(side="right", fill=tk.constants.X)
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] in ["Quat", "LinearColor"]:
                        valid_cmd = (self.register(self.valid_float), '%P')
                        tk.Entry(font=self.__font, master=g_frame, width=12,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][3]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.__font, master=g_frame, width=12,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][2]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.__font, master=g_frame, width=12,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][1]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.__font, master=g_frame, width=12,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][0]).pack(side="right", fill=tk.constants.X)
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib_var[attribute_key] is not None:
                        valid_cmd = None
                        if attrib['type'] in ["IntProperty"] or \
                                (attrib['type'] == "StructProperty" and attrib['struct_type'] == "FixedPoint64" and
                                 attrib['value']['Value']['type'] == "Int64Property"):
                            valid_cmd = (self.register(self.valid_int), '%P')
                        elif attrib['type'] == "FloatProperty":
                            valid_cmd = (self.register(self.valid_float), '%P')

                        tk.Entry(font=self.__font, master=g_frame,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key],
                                 width=50).pack(
                            side="right", fill=tk.constants.X)
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "StructProperty":
                        attrib_var[attribute_key] = {}
                        sub_f = tk.Frame(master=g_frame)
                        sub_f.pack(side="right", fill=tk.constants.X)
                        try:
                            for key in attrib['value']:
                                try:
                                    attrib_var[attribute_key][key] = self.make_attrib_var(master=sub_f,
                                                                                          attrib=attrib['value'][key])
                                    if attrib_var[attribute_key][key] is not None:
                                        self.build_variable_gui(sub_f, attrib_var[attribute_key],
                                                                {key: attrib['value'][key]})
                                    else:
                                        print("cannot create Struct %s" % key)
                                except TypeError as e:
                                    print("Error attribute [%s]->%s " % (key, attribute_key), attrib)
                        except Exception as e:
                            traceback.print_exception(e)
                            gp(attrib)
                            print("----------------------------")
                    else:
                        print("  ", attribute_key, attrib['type'] + (
                            ".%s" % attrib['struct_type'] if attrib['type'] == "StructProperty" else ""),
                              attrib['value'])
                else:
                    print(attribute_key, attribs[attribute_key])
                    continue

        def cmb_array_selected(self, evt, g_frame, attribute_key, attrib_var, attrib):
            for item in g_frame.winfo_children():
                item.destroy()
            print("Binding to %s[%d]" % (attribute_key, evt.widget.current()))
            if attrib['type'] == 'ArrayProperty' and attrib['array_type'] == 'NameProperty':
                self.build_variable_gui(g_frame, attrib_var[evt.widget.current()], {
                    'Name': {
                        'type': attrib['array_type'],
                        'value': attrib['value']['values'][evt.widget.current()]
                    }}, with_labelframe=False)
            else:
                self.build_variable_gui(g_frame, attrib_var[evt.widget.current()], {
                    attrib['value']['prop_name']: {
                        'type': attrib['value']['prop_type'],
                        'struct_type': attrib['value']['type_name'],
                        'value': attrib['value']['values'][evt.widget.current()]
                    }}, with_labelframe=False)

        @staticmethod
        def on_table_gui_dblclk(event, popup_set, columns, attrib_var, var_options):
            """ Executed, when a row is double-clicked. Opens
            read-only EntryPopup above the item's column, so it is possible
            to select text """
            if popup_set.entryPopup is not None:
                popup_set.entryPopup.destroy()
                popup_set.entryPopup = None
            # what row and column was clicked on
            rowid = event.widget.identify_row(event.y)
            column = event.widget.identify_column(event.x)
            col_name = columns[int(column[1:]) - 1]
            # get column position info
            x, y, width, height = event.widget.bbox(rowid, column)
            # y-axis offset
            # pady = height // 2
            pady = height // 2
            # AutocompleteComboBoxPopup
            if var_options is not None and col_name in var_options:
                popup_set.entryPopup = AutocompleteComboBoxPopup(event.widget, rowid, column,
                                                                 values=list(filter(lambda x: x is not None,
                                                                                    var_options[col_name].values())),
                                                                 textvariable=attrib_var[int(rowid)][col_name])
            else:
                popup_set.entryPopup = EntryPopup(event.widget, rowid, column,
                                                  textvariable=attrib_var[int(rowid)][col_name])
            popup_set.entryPopup.place(x=x, y=y + pady, anchor=tk.constants.W, width=width)

        def build_array_gui_item(self, tables, idx, attrib_var, attrib_list):
            values = []
            for key in attrib_list:
                attrib = attrib_list[key]
                attrib_var[key] = self.make_attrib_var(tables, attrib)
                if attrib_var[key] is not None:
                    self.assign_attrib_var(attrib_var[key], attrib)
                    if self.var_options is not None and key in self.var_options \
                            and attrib_var[key].get() in self.var_options[key]:
                        attrib_var[key].set(self.var_options[key][attrib_var[key].get()])
                values.append(attrib_var[key].get())
            tables.insert(parent='', index='end', iid=idx, text='',
                          values=values)

        def build_array_gui(self, master, columns, attrib_var, var_options=None):
            self.var_options = var_options
            popup_set = type('', (), {})()
            popup_set.entryPopup = None
            y_scroll = tk.Scrollbar(master)
            y_scroll.pack(side=tk.constants.RIGHT, fill=tk.constants.Y)
            x_scroll = tk.Scrollbar(master, orient='horizontal')
            x_scroll.pack(side=tk.constants.BOTTOM, fill=tk.constants.X)
            tables = ttk.Treeview(master, yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
            tables.pack(fill=tk.constants.BOTH, expand=True)
            y_scroll.config(command=tables.yview)
            x_scroll.config(command=tables.xview)
            tables['columns'] = columns
            # format our column
            tables.column("#0", width=0, stretch=tk.constants.NO)
            for col in columns:
                tables.column(col, anchor=tk.constants.CENTER, width=10)
            # Create Headings
            tables.heading("#0", text="", anchor=tk.constants.CENTER)
            for col in columns:
                tables.heading(col, text=col, anchor=tk.constants.CENTER)
            tables.bind("<Double-1>",
                        lambda event: self.on_table_gui_dblclk(event, popup_set, columns, attrib_var, var_options))
            return tables


    class PlayerItemEdit(ParamEditor):
        def __init__(self, player_uid, i18n='en-US'):
            self.i18n = i18n
            self.item_containers = {}
            self.item_container_vars = {}

            err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
            if err:
                messagebox.showerror("Player Itme Editor", "Player Sav file Not exists: %s" % player_gvas)
                return
            super().__init__()
            self.player_uid = player_uid
            self.player = MappingCache.PlayerIdMapping[toUUID(player_uid)]['value']['RawData']['value']['object'][
                'SaveParameter']['value']
            self.gui.title("Player Item Edit - %s" % player_uid)
            tabs = self.create_base_frame()
            tabs.pack(anchor=tk.constants.N, fill=tk.constants.BOTH, expand=True)
            ttk.Button(master=self.gui, style="custom.TButton", text="Save", command=self.savedata).pack(
                fill=tk.constants.X,
                anchor=tk.constants.S,
                expand=False)
            threading.Thread(target=self.load, args=[tabs, player_gvas]).start()

        def create_base_frame(self):
            return ttk.Notebook(master=self)

        def load(self, tabs, player_gvas):
            if not os.path.exists(module_dir + "/resources/item_%s.json" % self.i18n):
                self.i18n = 'en-US'
            with open(module_dir + "/resources/item_%s.json" % self.i18n, "r", encoding='utf-8') as f:
                item_list = json.load(f)
            for itemCodeName in item_list:
                if item_list[itemCodeName] is None:
                    item_list[itemCodeName] = f": {itemCodeName}"
                else:
                    item_list[itemCodeName] = f"{item_list[itemCodeName]}: {itemCodeName}"
            frame_index = {}
            for idx_key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                            'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
                if player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value'] \
                        in MappingCache.ItemContainerSaveData:
                    tab = tk.Frame(tabs)
                    tabs.add(tab, text=idx_key[:-11])
                    frame_index[idx_key] = tab
            for idx_key in frame_index:
                tab = frame_index[idx_key]
                self.item_container_vars[idx_key[:-11]] = []
                item_container = parse_item(
                    MappingCache.ItemContainerSaveData[player_gvas['inventoryInfo']['value'][idx_key]['value']['ID'][
                        'value']], "ItemContainerSaveData")
                self.item_containers[idx_key[:-11]] = [{
                    'SlotIndex': item['SlotIndex'],
                    'ItemId': item['ItemId']['value']['StaticId'],
                    'StackCount': item['StackCount']
                } for item in item_container['value']['Slots']['value']['values']]
                tables = self.build_array_gui(tab, ("SlotIndex", "ItemId", "StackCount"),
                                              self.item_container_vars[idx_key[:-11]],
                                              {"ItemId": item_list})
                for idx, item in enumerate(self.item_containers[idx_key[:-11]]):
                    self.item_container_vars[idx_key[:-11]].append({})
                    self.build_array_gui_item(tables, idx, self.item_container_vars[idx_key[:-11]][idx], item)
            self.geometry("640x800")

        def savedata(self):
            for idx_key in self.item_containers:
                for idx, item in enumerate(self.item_containers[idx_key]):
                    self.save(self.item_containers[idx_key][idx], self.item_container_vars[idx_key][idx])
            self.destroy()


    class PlayerSaveEdit(ParamEditor):
        def __init__(self, player_uid):

            err, player_gvas, self.player_sav_file, self.player_gvas_file = GetPlayerGvas(player_uid)
            if err:
                messagebox.showerror("Player Itme Editor", "Player Sav file Not exists: %s" % player_gvas)
                return
            super().__init__()
            self.player_uid = player_uid
            self.player = player_gvas
            self.gui_attribute = {}
            self.gui.title("Player Save Edit - %s" % player_uid)
            base_frame = self.create_base_frame()
            self.build_delete_attrib_gui(base_frame, self.player)
            self.build_variable_gui(base_frame, self.gui_attribute, self.player)

            ttk.Button(master=self.gui, style="custom.TButton", text="Save", command=self.savedata).pack(
                fill=tk.constants.X)

        def savedata(self):
            self.save(self.player, self.gui_attribute)
            backup_file(self.player_sav_file, True)
            with open(self.player_sav_file, "wb") as f:
                if "Pal.PalWorldSaveGame" in self.player_gvas_file.header.save_game_class_name or \
                        "Pal.PalLocalWorldSaveGame" in self.player_gvas_file.header.save_game_class_name:
                    save_type = 0x32
                else:
                    save_type = 0x31
                sav_file = compress_gvas_to_sav(self.player_gvas_file.write(PALWORLD_CUSTOM_PROPERTIES), save_type)
                f.write(sav_file)
            self.destroy()


    class PlayerEditGUI(ParamEditor):
        def __init__(self, player_uid=None, instanceId=None):
            super().__init__()
            self.player = MappingCache.CharacterSaveParameterMap[
                playerMapping[player_uid]['InstanceId'] if instanceId is None else toUUID(instanceId)]['value'][
                'RawData'][
                'value']['object']['SaveParameter']['value']
            gp(self.player)
            self.gui.title(
                "Player Edit - %s" % player_uid if player_uid is not None else "Character Edit - %s" % instanceId)
            self.gui_attribute = {}
            base_frame = self.create_base_frame()
            self.build_delete_attrib_gui(base_frame, self.player)
            self.build_variable_gui(base_frame, self.gui_attribute, self.player)
            ttk.Button(master=self.gui, style="custom.TButton", text="Save", command=self.savedata).pack(
                fill=tk.constants.X)

        def savedata(self):
            self.save(self.player, self.gui_attribute)
            self.destroy()


    class GuildEditGUI(ParamEditor):
        def __init__(self, group_id):
            super().__init__()
            self.group_id = group_id
            groupMapping = {str(group['key']): group for group in wsd['GroupSaveDataMap']['value']}
            if group_id not in groupMapping:
                messagebox.showerror("Guild Edit", "Guild not exists")
                self.destroy()
                return
            self.group_data = groupMapping[group_id]['value']['RawData']
            self.gui.title("Guild Edit - %s" % group_id)
            self.gui_attribute = {}
            self.build_variable_gui(self.create_base_frame(), self.gui_attribute, self.group_data)
            ttk.Button(master=self.gui, style="custom.TButton", text="Save", command=self.savedata).pack(
                fill=tk.constants.X)

        def savedata(self):
            self.save(self.group_data, self.gui_attribute)
            self.destroy()

    # g = GuildEditGUI("5cbf2999-92db-40e7-be6d-f96faf810453")

except NameError:
    pass

try:
    class PalEditGUI(PalEdit):
        def createWindow(self):
            root = tk.Toplevel()
            root.title(f"PalEdit v{PalEditConfig.version}")
            return root

        def load(self, file=None):
            self.data = {
                'gvas_file': gvas_file,
                'properties': gvas_file.properties
            }
            paldata = self.data['properties']['worldSaveData']['value']['CharacterSaveParameterMap']['value']
            self.palguidmanager = PalInfo.PalGuid(self.data)
            self.loadpal(paldata)

        def build_menu(self):
            self.menu = tk.Menu(self.gui)
            tools = self.menu
            self.gui.config(menu=tools)
            toolmenu = tk.Menu(tools, tearoff=0)
            toolmenu.add_command(label="Debug", command=self.toggleDebug)
            toolmenu.add_command(label="Generate GUID", command=self.generateguid)
            tools.add_cascade(label="Tools", menu=toolmenu, underline=0)

except NameError:
    print("Warning: PalEdit not found, PalEdit will not work")


class GUI():
    def __init__(self):
        self.lang_data = {}
        self.language = None
        self.pal_i18n = {}
        self.g_move_guild_owner = None
        try:
            if tk is None:
                pass
        except NameError:
            print("ERROR: Without Tkinter Environment, GUI not work")
            return
        self.i18n = {}
        self.gui = None
        self.src_player = None
        self.target_player = None
        self.data_source = None
        self.btn_migrate = None
        self.font = None
        self.build_gui()

    def mainloop(self):
        self.gui.mainloop()

    def gui_parse_uuid(self):
        src_uuid = self.src_player.get().split(" - ")[0]
        target_uuid = self.target_player.get().split(" - ")[0]
        if len(src_uuid) == 8:
            src_uuid += "-0000-0000-0000-000000000000"
        if len(target_uuid) == 8:
            target_uuid += "-0000-0000-0000-000000000000"
        try:
            uuid.UUID(src_uuid)
        except Exception as e:
            messagebox.showerror("Src Player Error", "UUID: \"%s\"\n%s" % (target_uuid, str(e)))
            return None, None

        try:
            uuid.UUID(target_uuid)
        except Exception as e:
            messagebox.showerror("Target Player Error", "UUID: \"%s\"\n%s" % (target_uuid, str(e)))
            return None, None

        return src_uuid, target_uuid

    def migrate_to_local(self):
        src_uuid = self.parse_source_uuid(True, True)
        if src_uuid is None:
            return
        try:
            MigratePlayer(src_uuid, "00000000-0000-0000-0000-000000000001")
            messagebox.showinfo("Result", "Migrate to local success")
            self.load_players()
        except Exception as e:
            messagebox.showerror("Migrate Error", str(e))

    def migrate(self):
        src_uuid, target_uuid = self.gui_parse_uuid()
        if src_uuid is None:
            return
        _playerMapping = LoadPlayers(wsd if self.data_source.current() == 0 else backup_wsd)
        for player_uid in _playerMapping:
            if player_uid[0:8] == src_uuid[0:8]:
                src_uuid = player_uid
                break
        if src_uuid not in _playerMapping:
            messagebox.showerror("Copy Error", "Source Player not exists")
            return
        if src_uuid == target_uuid:
            messagebox.showerror("Error", "Src == Target ")
            return
        try:
            MigratePlayer(src_uuid, target_uuid)
            messagebox.showinfo("Result", "Migrate success")
            self.load_players()
        except Exception as e:
            messagebox.showerror("Migrate Error", str(e))

    def open_file(self):
        bk_f = filedialog.askopenfilename(filetypes=[("Level.sav file", "*.sav")], title="Open Level.sav")
        if bk_f:
            if self.data_source.current() == 0:
                LoadFile(bk_f)
            else:
                OpenBackup(bk_f)
            self.change_datasource(None)
            self.load_guilds()

    def set_guild_owner(self):
        src_uuid = self.parse_source_uuid()
        if src_uuid is None:
            return
        target_guild_uuid = self.target_guild.get().split(" - ")[0]
        try:
            target_guild_uuid = uuid.UUID(target_guild_uuid)
        except Exception as e:
            traceback.print_exception(e)
            messagebox.showerror("Target Guild Error", "\n".join(traceback.format_exception(e)))
            return None

        try:
            SetGuildOwner(target_guild_uuid, src_uuid)
            messagebox.showinfo("Move Guild Success", "Move Guild Successed")
        except Exception as e:
            traceback.print_exception(e)
            messagebox.showerror("Target Guild Error", "\n".join(traceback.format_exception(e)))
            return None

    def copy_player(self):
        src_uuid, target_uuid = self.gui_parse_uuid()
        if src_uuid is None:
            return
        if not os.path.exists(os.path.dirname(os.path.abspath(args.filename)) + "/Players/"):
            messagebox.showerror("Cleanup", self.lang_data['msg_player_folder_not_exists'])
            return
        _playerMapping = LoadPlayers(wsd if self.data_source.current() == 0 else backup_wsd)
        for player_uid in _playerMapping:
            if player_uid[0:8] == src_uuid[0:8]:
                src_uuid = player_uid
                break
        if src_uuid not in _playerMapping:
            messagebox.showerror("Copy Error", "Source Player not exists")
            return
        if src_uuid == target_uuid and self.data_source.current() == 0:
            messagebox.showerror("Error", "Src == Target ")
            return
        if self.data_source.current() == 1 and backup_wsd is None:
            messagebox.showerror("Error", "Backup file is not loaded")
            return
        try:
            CopyPlayer(src_uuid, target_uuid, wsd if self.data_source.current() == 0 else backup_wsd)
            messagebox.showinfo("Result", "Copy success")
            self.load_players()
        except Exception as e:
            messagebox.showerror("Copy Error", "\n".join(traceback.format_exception(e)))

    def load_players(self):
        _playerMapping = LoadPlayers(wsd if self.data_source.current() == 0 else backup_wsd)
        src_value_lists = []
        for player_uid in _playerMapping:
            _player = _playerMapping[player_uid]
            try:
                _player['NickName'].encode('utf-8')
                src_value_lists.append(player_uid[0:8] + " - " + _player['NickName'])
            except UnicodeEncodeError:
                src_value_lists.append(player_uid[0:8] + " - *** ERROR ***")
            except KeyError:
                src_value_lists.append(player_uid[0:8] + " - *** CHEATER ***")

        self.src_player.set("")
        self.src_player['value'] = src_value_lists

        _playerMapping = LoadPlayers(wsd)
        target_value_lists = []
        for player_uid in _playerMapping:
            _player = _playerMapping[player_uid]
            try:
                _player['NickName'].encode('utf-8')
                target_value_lists.append(player_uid[0:8] + " - " + _player['NickName'])
            except UnicodeEncodeError:
                target_value_lists.append(player_uid[0:8] + " - *** ERROR ***")
            except KeyError:
                src_value_lists.append(player_uid[0:8] + " - *** CHEATER ***")

        self.target_player['value'] = target_value_lists
        self.load_instances()

    def isCharacterRelativeToUID(self, instance, uuid):
        saveParameter = instance['value']['RawData']['value']['object']['SaveParameter']['value']
        if 'IsPlayer' in saveParameter:
            # ignore player item in
            return False
        elif uuid is None:
            return True
        elif 'OwnerPlayerUId' in saveParameter and saveParameter['OwnerPlayerUId']['value'] == uuid:
            return True
        return False

    def load_instances(self, specified_parent=None):
        self.target_instance['value'] = sorted([
            "%s - %s" % (str(k), self.characterInstanceName(MappingCache.CharacterSaveParameterMap[k]))
            for k in
            filter(lambda x: self.isCharacterRelativeToUID(MappingCache.CharacterSaveParameterMap[x], specified_parent),
                   MappingCache.CharacterSaveParameterMap.keys())
        ])

    def load_guilds(self):
        guild_list = []
        for group_data in wsd['GroupSaveDataMap']['value']:
            if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
                group_info = group_data['value']['RawData']['value']
                guild_list.append("%s - %s" % (group_info['group_id'], group_info['guild_name']))
        self.target_guild['value'] = guild_list
        self.target_guild.set("")

    def change_datasource(self, x):
        if self.data_source.current() == 0:
            self.btn_migrate_local["state"] = "normal"
            self.btn_migrate["state"] = "normal"
        else:
            self.btn_migrate_local["state"] = "disabled"
            self.btn_migrate["state"] = "disabled"
        self.load_players()

    def parse_source_uuid(self, checkExists=True, showmessage=True):
        target_uuid = self.src_player.get().split(" - ")[0]
        if len(target_uuid) == 8:
            target_uuid += "-0000-0000-0000-000000000000"
        try:
            uuid.UUID(target_uuid)
        except Exception as e:
            if showmessage:
                messagebox.showerror("Source Player Error", "UUID: \"%s\"\n%s" % (target_uuid, str(e)))
            return None
        if checkExists:
            for player_uid in playerMapping:
                if player_uid[0:8] == target_uuid[0:8]:
                    target_uuid = player_uid
                    break
            if target_uuid not in playerMapping:
                if showmessage:
                    messagebox.showerror("Source Player Error", "Source Player Not exists")
                return None
        return target_uuid

    def parse_target_uuid(self, checkExists=True, showmessage=True):
        target_uuid = self.target_player.get().split(" - ")[0]
        if len(target_uuid) == 8:
            target_uuid += "-0000-0000-0000-000000000000"
        try:
            uuid.UUID(target_uuid)
        except Exception as e:
            if showmessage:
                messagebox.showerror("Target Player Error", "UUID: \"%s\"\n%s" % (target_uuid, str(e)))
            return None
        if checkExists:
            for player_uid in playerMapping:
                if player_uid[0:8] == target_uuid[0:8]:
                    target_uuid = player_uid
                    break
            if target_uuid not in playerMapping:
                if showmessage:
                    messagebox.showerror("Target Player Error", "Target Player Not exists")
                return None
        return target_uuid

    def rename_player(self):
        target_uuid = self.parse_target_uuid()
        if target_uuid is None:
            return
        try:
            new_player_name = simpledialog.askstring(title="Rename Player", prompt="New player name",
                                                     initialvalue=playerMapping[target_uuid]['NickName'])
        except UnicodeEncodeError:
            new_player_name = simpledialog.askstring(title="Rename Player", prompt="New player name",
                                                     initialvalue=repr(playerMapping[target_uuid]['NickName']))
        except KeyError:
            new_player_name = simpledialog.askstring(title="Rename Player", prompt="New player name",
                                                     initialvalue="*** CHEATER PLAYER ***")
        if new_player_name:
            try:
                RenamePlayer(target_uuid, new_player_name)
                messagebox.showinfo("Result", "Rename success")
                self.load_players()
            except Exception as e:
                messagebox.showerror("Rename Error", "\n".join(traceback.format_exception(e)))

    def delete_player(self):
        target_uuid = self.parse_target_uuid()
        if target_uuid is None:
            return
        if 'yes' == messagebox.showwarning("Delete Player", "Confirm to delete player %s" % target_uuid,
                                           type=messagebox.YESNO):
            try:
                DeletePlayer(target_uuid)
                messagebox.showinfo("Result", "Delete success")
                self.load_players()
            except Exception as e:
                traceback.print_exception(e)
                messagebox.showerror("Delete Error", "\n".join(traceback.format_exception(e)))

    def move_guild(self):
        target_uuid = self.parse_target_uuid()
        if target_uuid is None:
            return
        target_guild_uuid = self.target_guild.get().split(" - ")[0]
        try:
            uuid.UUID(target_guild_uuid)
        except Exception as e:
            traceback.print_exception(e)
            messagebox.showerror("Target Guild Error", "\n".join(traceback.format_exception(e)))
            return None

        target_guild = None
        for group_data in wsd['GroupSaveDataMap']['value']:
            if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
                group_info = group_data['value']['RawData']['value']
                if group_info['group_id'] == target_guild_uuid:
                    target_guild = group_info
                    break
        if target_guild is None:
            messagebox.showerror("Target Guild is not found")
            return None
        try:
            MoveToGuild(target_uuid, target_guild_uuid)
            messagebox.showinfo("Result", "Move Guild success")
            self.load_players()
            self.load_guilds()
        except Exception as e:
            traceback.print_exception(e)
            messagebox.showerror("Move Guild Error", "\n".join(traceback.format_exception(e)))

    def save(self):
        if 'yes' == messagebox.showwarning("Save", "Confirm to save file?", type=messagebox.YESNO):
            try:
                Save(False)
                messagebox.showinfo("Result", "Save to %s success" % output_path)
                print()
                sys.exit(0)
            except Exception as e:
                traceback.print_exception(e)
                messagebox.showerror("Save Error", "\n".join(traceback.format_exception(e)))

    def edit_player(self):
        target_uuid = self.parse_target_uuid()
        if target_uuid is None:
            return
        PlayerEditGUI(player_uid=target_uuid)

    def edit_instance(self):
        target_uuid = self.target_instance.get()[:36]
        if target_uuid is None:
            return
        if toUUID(target_uuid) not in MappingCache.CharacterSaveParameterMap:
            messagebox.showerror("Edit Instance Error", "Instance Not Found")
            return
        PlayerEditGUI(instanceId=target_uuid)

    def copy_instance(self):
        target_uuid = self.target_instance.get()[:36]
        if target_uuid is None:
            return
        if toUUID(target_uuid) not in MappingCache.CharacterSaveParameterMap:
            messagebox.showerror("Copy Instance Error", "Instance Not Found")
            return
        if not os.path.exists(os.path.dirname(os.path.abspath(args.filename)) + "/Players/"):
            messagebox.showerror("Cleanup", self.lang_data['msg_player_folder_not_exists'])
            return
        instance = MappingCache.CharacterSaveParameterMap[toUUID(target_uuid)]['value']['RawData']['value']['object'][
            'SaveParameter']['value']
        if 'OwnerPlayerUId' not in instance:
            messagebox.showerror("Copy Instance Error", "Only Pals can be use for Copy Instance")
            return
        err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(instance['OwnerPlayerUId']['value'])
        if err:
            messagebox.showerror("Copy Instance Error", f"Player sav file not exists: {player_sav_file}")
            return
        new_uuid = CopyCharacter(target_uuid, wsd, player_gvas['PalStorageContainerId']['value']['ID']['value'])
        if new_uuid:
            messagebox.showinfo("Copy Instance", "Copy Instance Success")
        else:
            messagebox.showerror("Copy Instance Error", "Copy Instance Failed")
            return
        self.load_instances(instance['OwnerPlayerUId']['value'])
        self.target_instance.set(str(new_uuid))

    def edit_player_item(self):
        target_uuid = self.parse_target_uuid()
        if target_uuid is None:
            return
        if not os.path.exists(os.path.dirname(os.path.abspath(args.filename)) + "/Players/"):
            messagebox.showerror("Cleanup", self.lang_data['msg_player_folder_not_exists'])
            return
        PlayerItemEdit(target_uuid, self.language)

    def edit_player_save(self):
        target_uuid = self.parse_target_uuid()
        if target_uuid is None:
            return
        if not os.path.exists(os.path.dirname(os.path.abspath(args.filename)) + "/Players/"):
            messagebox.showerror("Cleanup", self.lang_data['msg_player_folder_not_exists'])
            return
        PlayerSaveEdit(target_uuid)

    def repair_player(self):
        target_uuid = self.parse_target_uuid()
        if target_uuid is None:
            return
        if not os.path.exists(os.path.dirname(os.path.abspath(args.filename)) + "/Players/"):
            messagebox.showerror("Cleanup", self.lang_data['msg_player_folder_not_exists'])
            return
        try:
            RepairPlayer(target_uuid)
            messagebox.showinfo("Result", "Repair success")
            self.load_players()
        except Exception as e:
            messagebox.showerror("Repair Error", "\n".join(traceback.format_exception(e)))

    def pal_edit(self):
        PalEditConfig.font = self.font
        global paledit
        try:
            if paledit is not None:
                paledit.gui.destroy()
        except NameError:
            pass
        paledit = PalEditGUI()
        paledit.load_i18n(self.language)
        paledit.load(None)
        paledit.mainloop()

    def delete_base(self):
        target_guild_uuid = self.target_guild.get().split(" - ")[0]
        try:
            uuid.UUID(target_guild_uuid)
        except Exception as e:
            target_guild_uuid = None
        if DeleteBaseCamp(self.target_base.get(), group_id=target_guild_uuid):
            messagebox.showinfo("Result", "Delete Base Camp Success")
        else:
            messagebox.showerror("Delete Base", "Failed to delete")

    def select_target_player(self, evt):
        target_uuid = self.parse_target_uuid(showmessage=False)
        if target_uuid is not None:
            gid = MappingCache.PlayerIdMapping[toUUID(target_uuid)]['value']['RawData']['value']['group_id']
            for idx, grp_msg in enumerate(self.target_guild['values']):
                if str(gid) == grp_msg[0:36]:
                    self.target_guild.current(idx)
                    self.select_guild(evt)
                    break
            self.load_instances(target_uuid)

    def select_guild(self, evt):
        target_guild_uuid = self.target_guild.get().split(" - ")[0]
        try:
            uuid.UUID(target_guild_uuid)
        except Exception as e:
            traceback.print_exception(e)
            messagebox.showerror("Target Guild Error", "\n".join(traceback.format_exception(e)))
            self.target_base['value'] = []
            self.target_base.set("ERROR")
            return None
        self.target_base.set("")
        groupMapping = {str(group['key']): group for group in wsd['GroupSaveDataMap']['value']}
        if target_guild_uuid in groupMapping:
            self.target_base['value'] = [str(x) for x in
                                         groupMapping[target_guild_uuid]['value']['RawData']['value']['base_ids']]

    def cleanup_item(self):
        if not os.path.exists(os.path.dirname(os.path.abspath(args.filename)) + "/Players/"):
            messagebox.showerror("Cleanup", self.lang_data['msg_player_folder_not_exists'])
            return

        answer = messagebox.showwarning("Cleanup",
                                        self.lang_data['msg_confirm_delete_objs']
                                        .replace("{COUNT}",
                                                 "%d" % (len(FindAllUnreferencedItemContainerIds()))),
                                        type=messagebox.YESNO)

        if answer != 'yes':
            return

        BatchDeleteUnreferencedItemContainers()

    def cleanup_character(self):
        if not os.path.exists(os.path.dirname(os.path.abspath(args.filename)) + "/Players/"):
            messagebox.showerror("Cleanup", self.lang_data['msg_player_folder_not_exists'])
            return

        answer = messagebox.showwarning("Cleanup",
                                        self.lang_data['msg_confirm_delete_objs']
                                        .replace("{COUNT}",
                                                 "%d" % (len(FindAllUnreferencedCharacterContainerIds()))),
                                        type=messagebox.YESNO)

        if answer != 'yes':
            return
        BatchDeleteUnreferencedCharacterContainers()

    def delete_damage_container(self):
        if not os.path.exists(os.path.dirname(os.path.abspath(args.filename)) + "/Players/"):
            messagebox.showerror("Cleanup", self.lang_data['msg_player_folder_not_exists'])
            return

        delete_objects = FixBrokenObject(True)
        BrokenObjects = FindDamageRefContainer(True)

        delete_sets = set(BrokenObjects['Character']['Owner'])
        delete_sets.update(BrokenObjects['Character']['CharacterContainer'])

        answer = messagebox.showwarning("Cleanup",
                                        self.lang_data['msg_confirm_fix_mapobject']
                                        .replace("{MAP_COUNT}",
                                                 "%d" % (len(BrokenObjects['MapObject']) + len(delete_objects)))
                                        .replace("{SAVE_COUNT}",
                                                 "%d" % (len(BrokenObjects['Character']['SaveContainers'])))
                                        .replace("{CHARACTER_COUNT}",
                                                 "%d" % (len(delete_sets)))
                                        .replace("{BASECAMP_COUNT}",
                                                 "%d" % (len(BrokenObjects['BaseCamp'])))
                                        .replace("{WORKDATA_COUNT}",
                                                 "%d" % (len(BrokenObjects['WorkData'])))
                                        .replace("{SPAWNER_COUNT}",
                                                 "%d" % (len(BrokenObjects['MapObjectSpawnerInStage'])))
                                        .replace("{FOLIAGE_COUNT}",
                                                 "%d" % (len(BrokenObjects['FoliageGrid']))),
                                        type=messagebox.YESNO)
        if answer != 'yes':
            return
        FixBrokenObject()
        FixBrokenDamageRefContainer()
        self.load_players()

    def delete_old_player(self):
        if not os.path.exists(os.path.dirname(os.path.abspath(args.filename)) + "/Players/"):
            messagebox.showerror("Cleanup", self.lang_data['msg_player_folder_not_exists'])
            return
        days = simpledialog.askinteger("Delete Old Player", self.lang_data['prompt_howlong_day'])
        if days is not None:
            players = FindPlayersFromInactiveGuild(days)
            if 'yes' == messagebox.showwarning("Cleanup", self.lang_data['msg_confirm_delete'].replace("{COUNT}",
                                                                                                       "%d" % len(
                                                                                                           players)),
                                               type=messagebox.YESNO):
                for idx, player_id in enumerate(players):
                    self.progressbar['value'] = 100 * idx / len(players)
                    self.gui.update()
                    DeletePlayer(player_id)
                self.progressbar['value'] = 100
                self.gui.update()
                self.load_players()
                messagebox.showinfo("Result", "Delete Success")

    def repair_all_player(self):
        for playerid in MappingCache.PlayerIdMapping:
            RepairPlayer(playerid)
        messagebox.showinfo("Result", "Repair success")

    def getPalTranslatedName(self, saveParameter):
        internal_name = saveParameter['CharacterID']['value']
        name = ''
        if 'NickName' in saveParameter:
            name = " - %s" % saveParameter['NickName']['value']
        try_split = internal_name.split("BOSS_", 1)
        if len(try_split) > 1 and try_split[1] in self.pal_i18n:
            return "%s%s" % ('[BOSS] %s' % self.pal_i18n[try_split[1]], name)
        if internal_name in self.pal_i18n:
            return "%s%s" % (self.pal_i18n[internal_name], name)
        return "%s%s" % (internal_name, name)

    def characterInstanceName(self, instance):
        saveParameter = instance['value']['RawData']['value']['object']['SaveParameter']['value']
        if 'IsPlayer' in saveParameter:
            try:
                return 'Player:%s' % repr(saveParameter['NickName']['value'])
            except UnicodeEncodeError:
                return 'Player:%s' % repr(saveParameter['NickName']['value'])
            except KeyError:
                print("Invalid Player")
                gp(saveParameter)
                print()
                return 'Invalid Player'
        else:
            try:
                return 'Pal:%s' % self.getPalTranslatedName(saveParameter)
            except UnicodeEncodeError:
                return 'Pal:%s' % repr(saveParameter['CharacterID']['value'])
            except KeyError:
                print("Invalid Pal")
                gp(saveParameter)
                print()
                return 'Invalid Pal'

    def build_gui(self):
        #
        self.gui = tk.Tk()

        self.gui.iconphoto(True, tk.PhotoImage(file=f'{module_dir}/resources/palworld-save-editor.png'))

        self.gui.parent = self
        try:
            __version__ = importlib.metadata.version('palworld-server-toolkit')
        except importlib.metadata.PackageNotFoundError:
            __version__ = "0.0.1"
            with open(f"{module_dir}/resources/version.txt", "r") as f:
                __version__ = f.read().strip()
        self.gui.title(f'PalWorld Save Editor v{__version__} - Author by MagicBear')
        # self.gui.geometry('640x200')
        #
        self.font = ("Courier New", 12)
        self.mono_font = tk.font.Font(family="Courier New")
        mono_font_list = ('Dejavu Sans', 'Courier New')
        #
        for font in mono_font_list:
            if font in tkinter.font.families():
                self.mono_font = tk.font.Font(family=font)
                break

        self.gui.option_add('*TCombobox*Listbox.font', self.mono_font)
        # window.resizable(False, False)
        with open(module_dir + "/resources/gui.json", "r", encoding='utf-8') as f:
            i18n_list = json.load(f)
        f_i18n = tk.Frame()
        tk.Label(master=f_i18n, text="Language", font=self.font).pack(side="left")
        b_i18n = ttk.Combobox(master=f_i18n, font=self.font, width=20, values=list(i18n_list.values()),
                              state="readonly")
        b_i18n.pack(side="left")
        b_i18n.current(0)
        b_i18n.bind("<<ComboboxSelected>>", lambda evt: self.set_i18n(list(i18n_list.keys())[b_i18n.current()]))

        f_src = tk.Frame()
        self.i18n['data_source'] = tk.Label(master=f_src, text="Source Player Data Source", font=self.font)
        self.i18n['data_source'].pack(side="left")
        self.data_source = ttk.Combobox(master=f_src, font=self.font, width=20, values=['Main File', 'Backup File'],
                                        state="readonly")
        self.i18n['data_source_list'] = self.data_source
        self.data_source.pack(side="left")
        self.data_source.current(0)
        self.data_source.bind("<<ComboboxSelected>>", self.change_datasource)
        g_open_file = ttk.Button(master=f_src, style="custom.TButton", text="Open File", command=self.open_file)
        self.i18n['open_file'] = g_open_file
        g_open_file.pack(side="left")
        #
        f_src_player = tk.Frame()
        self.i18n['src_player'] = tk.Label(master=f_src_player, text="Source Player", font=self.font)
        self.i18n['src_player'].pack(side="left")
        self.src_player = AutocompleteCombobox(master=f_src_player, font=self.mono_font, width=50)
        self.src_player.pack(side="left")
        self.g_move_guild_owner = ttk.Button(master=f_src_player, text="Set Guild Owner", style="custom.TButton",
                                             command=self.set_guild_owner)
        self.i18n['set_guild_owner'] = self.g_move_guild_owner
        self.g_move_guild_owner.pack(side="left")
        #
        f_target_player = tk.Frame()
        self.i18n['target_player'] = tk.Label(master=f_target_player, text="Target Player", font=self.font)
        self.i18n['target_player'].pack(side="left")
        self.target_player = AutocompleteCombobox(master=f_target_player, font=self.mono_font, width=50)
        self.target_player.pack(side="left")
        self.target_player.bind("<<ComboboxSelected>>", self.select_target_player)

        f_target_guild = tk.Frame()
        self.i18n['target_guild'] = tk.Label(master=f_target_guild, text="Target Guild", font=self.font)
        self.i18n['target_guild'].pack(side="left")
        self.target_guild = AutocompleteCombobox(master=f_target_guild, font=self.mono_font, width=80)
        self.target_guild.pack(side="left", fill=tk.constants.X)
        self.target_guild.bind("<<ComboboxSelected>>", self.select_guild)

        f_target_guildbase = tk.Frame()
        self.i18n['target_base'] = tk.Label(master=f_target_guildbase, text="Target Base", font=self.font)
        self.i18n['target_base'].pack(side="left")
        self.target_base = AutocompleteCombobox(master=f_target_guildbase, font=self.mono_font, width=50)
        self.target_base.pack(side="left")
        self.i18n['delete_base'] = g_delete_base = ttk.Button(master=f_target_guildbase, text="Delete Base Camp",
                                                              style="custom.TButton",
                                                              command=self.delete_base)
        g_delete_base.pack(side="left")
        #
        f_target_instance = tk.Frame()
        self.i18n['target_instance'] = tk.Label(master=f_target_instance, text="Target Instance", font=self.font)
        self.i18n['target_instance'].pack(side="left")
        self.target_instance = AutocompleteCombobox(master=f_target_instance, font=self.mono_font, width=60)
        self.target_instance.pack(side="left")
        self.i18n['edit_instance'] = ttk.Button(master=f_target_instance, text="Edit", style="custom.TButton",
                                                command=self.edit_instance)
        self.i18n['edit_instance'].pack(side="left")
        self.i18n['copy_instance'] = ttk.Button(master=f_target_instance, text="Copy", style="custom.TButton",
                                                command=self.copy_instance)
        self.i18n['copy_instance'].pack(side="left")

        g_multi_button_frame = tk.Frame()

        self.btn_migrate_local = ttk.Button(master=g_multi_button_frame, text="Migrate To Local",
                                            style="custom.TButton",
                                            command=self.migrate_to_local)
        self.i18n['migrate_to_local'] = self.btn_migrate_local
        self.btn_migrate_local.pack(side="left")

        self.btn_migrate = ttk.Button(master=g_multi_button_frame, text="⬆️ Migrate Player ⬇️", style="custom.TButton",
                                      command=self.migrate)
        self.i18n['migrate_player'] = self.btn_migrate
        self.btn_migrate.pack(side="left")
        g_copy = ttk.Button(master=g_multi_button_frame, text="⬆️ Copy Player ⬇️", style="custom.TButton",
                            command=self.copy_player)
        self.i18n['copy_player'] = g_copy
        g_copy.pack(side="left")

        g_pal = ttk.Button(master=g_multi_button_frame, text="Pal Edit", style="custom.TButton", command=self.pal_edit)
        self.i18n['edit_pal'] = g_pal
        g_pal.pack(side="left")

        #
        # g_target_player_frame = tk.Frame(borderwidth=1, relief=tk.constants.GROOVE, pady=5)
        g_button_frame = tk.Frame(borderwidth=1, relief=tk.constants.GROOVE, pady=5)
        self.i18n['op_for_target'] = tk.Label(master=g_button_frame, text="Operate for Target Player", font=self.font)
        self.i18n['op_for_target'].pack(fill="x", side="top")
        g_move = ttk.Button(master=g_button_frame, text="Move To Guild", style="custom.TButton",
                            command=self.move_guild)
        self.i18n['move_to_guild'] = g_move
        g_move.pack(side="left")
        g_rename = ttk.Button(master=g_button_frame, text="Rename", style="custom.TButton", command=self.rename_player)
        self.i18n['rename_player'] = g_rename
        g_rename.pack(side="left")
        g_delete = ttk.Button(master=g_button_frame, text="Delete", style="custom.TButton", command=self.delete_player)
        self.i18n['delete_player'] = g_delete
        g_delete.pack(side="left")
        g_edit = ttk.Button(master=g_button_frame, text="Edit", style="custom.TButton", command=self.edit_player)
        self.i18n['edit_player'] = g_edit
        g_edit.pack(side="left")
        g_edit_item = ttk.Button(master=g_button_frame, text="Edit Item", style="custom.TButton",
                                 command=self.edit_player_item)
        self.i18n['edit_item'] = g_edit_item
        g_edit_item.pack(side="left")
        g_edit_save = ttk.Button(master=g_button_frame, text="Edit Save", style="custom.TButton",
                                 command=self.edit_player_save)
        self.i18n['edit_save'] = g_edit_save
        g_edit_save.pack(side="left")

        g_repair = ttk.Button(master=g_button_frame, text="Repair", style="custom.TButton",
                              command=self.repair_player)
        self.i18n['repair_user'] = g_repair
        g_repair.pack(side="left")

        f_i18n.pack(anchor=tk.constants.W)
        f_src.pack(anchor=tk.constants.W)
        f_src_player.pack(anchor=tk.constants.W)
        g_multi_button_frame.pack()
        f_target_player.pack(anchor=tk.constants.W)
        g_button_frame.pack(fill=tk.constants.X)
        f_target_guild.pack(anchor=tk.constants.W)
        f_target_guildbase.pack(anchor=tk.constants.W)
        f_target_instance.pack(anchor=tk.constants.W)

        g_wholefile = tk.Frame(borderwidth=1, relief=tk.constants.GROOVE, pady=5)
        self.i18n['op_for_all'] = tk.Label(master=g_wholefile, text="Operate for All", font=self.font)
        self.i18n['op_for_all'].pack(fill="x", side="top")

        g_wholefile.pack(fill=tk.X)

        g_wholefile_btngrp = tk.Frame(master=g_wholefile, pady=5)
        g_wholefile_btngrp.pack(side=tk.TOP, fill=tk.X)
        g_del_unref_item = ttk.Button(master=g_wholefile_btngrp, text="Delete Unref Item", style="custom.TButton",
                                      command=self.cleanup_item)
        self.i18n['del_unreference_item'] = g_del_unref_item
        g_del_unref_item.pack(side="left")

        g_cleanup_character = ttk.Button(master=g_wholefile_btngrp, text="Cleanup character", style="custom.TButton",
                                         command=self.cleanup_character)
        self.i18n['cleanup_character'] = g_cleanup_character
        g_cleanup_character.pack(side=tk.LEFT)
        g_del_damange_container_obj = ttk.Button(master=g_wholefile_btngrp, text="Del Damage Object",
                                                 style="custom.TButton",
                                                 command=self.delete_damage_container)
        self.i18n['del_damage_obj'] = g_del_damange_container_obj
        g_del_damange_container_obj.pack(side=tk.LEFT)

        g_del_old_player = ttk.Button(master=g_wholefile_btngrp, text="Del Old Player", style="custom.TButton",
                                      command=self.delete_old_player)
        self.i18n['del_old_player'] = g_del_old_player
        g_del_old_player.pack(side=tk.LEFT)

        g_repair_all = ttk.Button(master=g_wholefile, text="Repair All Player", style="custom.TButton",
                                  command=self.repair_all_player)
        self.i18n['repair_all_user'] = g_repair_all
        g_repair_all.pack(side=tk.LEFT)

        g_save = ttk.Button(text="Save & Exit", style="custom.TButton", command=self.save)
        self.i18n['save'] = g_save
        g_save.pack()

        self.progressbar = ttk.Progressbar()
        self.progressbar.pack(fill=tk.constants.X)

        self.set_i18n(list(i18n_list.keys())[0])

    def load(self):
        self.load_players()
        self.load_guilds()

    def set_i18n(self, lang):
        self.language = lang
        with open("%s/resources/gui_%s.json" % (module_dir, lang), encoding='utf-8') as f:
            self.lang_data.update(json.load(f))
        if os.path.exists("%s/resources/pal_%s.json"):
            with open("%s/resources/pal_%s.json" % (module_dir, lang), encoding='utf-8') as f:
                self.pal_i18n.update(json.load(f))

        font_list = self.lang_data['font_order']
        for font in font_list:
            if font in tkinter.font.families():
                self.font = tk.font.Font(family=font)
                ttk.Style().configure("custom.TButton",
                                      font=(font, 12))
                break
        for item in self.i18n:
            if item in self.lang_data:
                if isinstance(self.i18n[item], ttk.Combobox):
                    index = self.i18n[item].current()
                    self.i18n[item]['values'] = self.lang_data[item]
                    self.i18n[item].current(index)
                else:
                    self.i18n[item].config(text=self.lang_data[item])

                if isinstance(self.i18n[item], tk.Label) or isinstance(self.i18n[item], ttk.Combobox):
                    self.i18n[item].config(font=self.font)

        if self.target_instance['value'] != '':
            self.load_players()


def DumpSavDecompressData(filename):
    with open(filename, "rb") as f:
        data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)

    with open(filename + ".raw", "wb") as f:
        f.write(raw_gvas)


def LoadFile(filename):
    global filetime, gvas_file, wsd, MappingCache, backup_path
    print(f"Loading {filename}...", end="", flush=True)
    filetime = os.stat(filename).st_mtime
    backup_path = os.path.join(os.path.dirname(os.path.abspath(filename)),
                               "backup/%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    with open(filename, "rb") as f:
        # Read the file
        start_time = time.time()
        data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)
        print("Done in %.2fs." % (time.time() - start_time))

        print(f"Parsing {filename}...", end="", flush=True)
        start_time = time.time()
        gvas_file = ProgressGvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES)
        print("Done in %.2fs." % (time.time() - start_time))

    wsd = gvas_file.properties['worldSaveData']['value']
    MappingCache = MappingCacheObject.get(wsd)


def Statistics():
    for key in wsd:
        val_type = "Bytes" if isinstance(wsd[key]['value'], bytes) else "Keys "
        vals = len(wsd[key]['value'])
        if 'type' in wsd[key] and wsd[key]['type'] == 'ArrayProperty' and isinstance(wsd[key]['value'], dict):
            vals = len(wsd[key]['value']['values'])
            val_type = "Items"
        print("%40s\t%.3f MB\t%20s\t%s: %d" % (key, len(str(wsd[key])) / 1048576,
                                               wsd[key]['type'] if 'type' in wsd[key] else "",
                                               val_type,
                                               vals))


def GetPlayerGvas(player_uid, src_file=None):
    player_sav_rel = "/Players/" + str(player_uid).upper().replace("-", "") + ".sav"
    player_sav_file = os.path.dirname(os.path.abspath(args.filename)) + player_sav_rel
    if src_file is not None:
        if os.path.exists(os.path.dirname(os.path.abspath(src_file)) + player_sav_rel):
            player_sav_file = os.path.dirname(os.path.abspath(src_file)) + player_sav_rel
    if not os.path.exists(player_sav_file):
        return player_sav_file, None, player_sav_file, None

    with open(player_sav_file, "rb") as f:
        raw_gvas, _ = decompress_sav_to_gvas(f.read())
        player_gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
    player_gvas = player_gvas_file.properties['SaveData']['value']

    return None, player_gvas, player_sav_file, player_gvas_file


def EditPlayer(player_uid):
    global player
    for item in wsd['CharacterSaveParameterMap']['value']:
        if str(item['key']['PlayerUId']['value']) == player_uid:
            player = item['value']['RawData']['value']['object']['SaveParameter']['value']
            print("Player has allocated to 'player' variable, you can use player['Property']['value'] = xxx to modify")
            pp.pprint(player)


def RenamePlayer(player_uid, new_name):
    try:
        playerInfo = MappingCache.PlayerIdMapping[toUUID(player_uid)]
    except KeyError:
        print(f"Error: invalid player {player_uid}")
        return False

    player = playerInfo['value']['RawData']['value']['object']['SaveParameter']['value']
    print(
        f"{tcl(32)}Rename User{tcl(0)}  UUID: %s  {tcl(93)}%s{tcl(0)} -> %s" % (
            str(playerInfo['key']['InstanceId']['value']), CharacterDescription(playerInfo), new_name))
    player['NickName']['value'] = new_name
    group_data = MappingCache.GuildSaveDataMap[playerInfo['value']['RawData']['value']['group_id']]
    item = group_data['value']['RawData']['value']
    for g_player in item['players']:
        if str(g_player['player_uid']) == player_uid:
            print(
                f"{tcl(32)}Rename Guild {item['guild_name']} User  {tcl(93)}{repr(g_player['player_info']['player_name'])}{tcl(0)}  -> {new_name}")
            g_player['player_info']['player_name'] = new_name


def GetPlayerItems(player_uid):
    load_skipped_decode(wsd, ["ItemContainerSaveData"])
    item_containers = {}
    for item_container in wsd["ItemContainerSaveData"]['value']:
        item_containers[str(item_container['key']['ID']['value'])] = [{
            'ItemId': x['ItemId']['value']['StaticId']['value'],
            'SlotIndex': x['SlotIndex']['value'],
            'StackCount': x['StackCount']['value']
        }
            for x in item_container['value']['Slots']['value']['values']
        ]

    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print(f"{tcl(33)}Warning: Player Sav file Not exists: %s{tcl(0)}" % player_sav_file)
        return
    for idx_key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                    'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
        print("  %s" % player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value'])
        pp.pprint(item_containers[str(player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value'])])
        print()


def OpenBackup(filename):
    global backup_gvas_file, backup_wsd, backup_file_path
    print(f"Loading {filename}...")
    backup_file_path = filename
    with open(filename, "rb") as f:
        # Read the file
        data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)

        print(f"Parsing {filename}...", end="", flush=True)
        start_time = time.time()
        backup_gvas_file = ProgressGvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES)
        print("Done in %.2fs." % (time.time() - start_time))
    backup_wsd = backup_gvas_file.properties['worldSaveData']['value']
    ShowPlayers(backup_wsd)
    ShowGuild(backup_wsd)


def SetGuildOwner(group_id, new_player_uid):
    new_player_uid = toUUID(new_player_uid)
    if new_player_uid not in MappingCache.PlayerIdMapping:
        raise Exception("Error: target player not exists")
    if toUUID(group_id) not in MappingCache.GroupSaveDataMap:
        raise Exception("Error: Guild not exists")
    MoveToGuild(new_player_uid, group_id)
    MappingCache.GroupSaveDataMap[toUUID(group_id)]['value']['RawData']['value']['admin_player_uid'] = new_player_uid
    return True


def CopyItemContainers(src_containers, targetInstanceId):
    load_skipped_decode(wsd, ['ItemContainerSaveData'], False)
    new_containers = parse_item(copy.deepcopy(src_containers), "ItemContainerSaveData")
    new_containers['key']['ID']['value'] = targetInstanceId
    wsd['ItemContainerSaveData']['value'].append(new_containers)


def CopyPlayer(player_uid, new_player_uid, old_wsd, dry_run=False):
    load_skipped_decode(wsd, ['DynamicItemSaveData', 'CharacterSaveParameterMap', 'GroupSaveDataMap'], False)
    # load_skiped_decode(old_wsd, ['DynamicItemSaveData', 'CharacterSaveParameterMap', 'GroupSaveDataMap'], False)
    srcMappingCache = MappingCacheObject.get(old_wsd)
    MappingCache.LoadItemContainerMaps()

    print("Loading for player file")
    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid,
                                                                        backup_file_path if id(old_wsd) != id(
                                                                            wsd) else args.filename)
    if err:
        print(f"{tcl(33)}Warning: Player Sav file Not exists: %s{tcl(0)}" % player_sav_file)
        return
    new_player_sav_file = os.path.dirname(
        os.path.abspath(args.filename)) + "/Players/" + new_player_uid.upper().replace("-", "") + ".sav"
    instances = []
    container_id_mapping = {}
    new_player_uid = toUUID(new_player_uid)

    while new_player_uid in MappingCache.PlayerIdMapping:
        DeletePlayer(new_player_uid,
                     InstanceId=MappingCache.PlayerIdMapping[new_player_uid]['key']['InstanceId']['value'])
        MappingCache.LoadCharacterSaveParameterMap()

    player_uid = player_gvas['PlayerUId']['value']
    if player_uid not in srcMappingCache.PlayerIdMapping:
        print(f"{tcl(31)}Error, player {tcl(32)} {str(player_uid)} %s {tcl(31)} not exists {tcl(0)}")
        return False

    player_gvas['PlayerUId']['value'] = new_player_uid
    player_gvas['IndividualId']['value']['PlayerUId']['value'] = player_gvas['PlayerUId']['value']
    player_gvas['IndividualId']['value']['InstanceId']['value'] = toUUID(uuid.uuid4())
    # Clone Item from CharacterContainerSaveData
    for idx_key in ['OtomoCharacterContainerId', 'PalStorageContainerId']:
        if player_gvas[idx_key]['value']['ID']['value'] in srcMappingCache.CharacterContainerSaveData:
            container = parse_item(
                srcMappingCache.CharacterContainerSaveData[player_gvas[idx_key]['value']['ID']['value']],
                "CharacterContainerSaveData")
            new_item = copy.deepcopy(container)
            IsFound = False
            container_id = player_gvas[idx_key]['value']['ID']['value']
            if container_id in MappingCache.CharacterContainerSaveData:
                player_gvas[idx_key]['value']['ID']['value'] = toUUID(uuid.uuid4())
                new_item['key']['ID']['value'] = player_gvas[idx_key]['value']['ID']['value']
                IsFound = True
                container_id_mapping[container_id] = player_gvas[idx_key]['value']['ID']['value']
            if not dry_run:
                wsd['CharacterContainerSaveData']['value'].append(new_item)
            if IsFound:
                print(f"{tcl(32)}Copy Character Container{tcl(0)} %s UUID: %s -> %s" %
                      (idx_key, str(container['key']['ID']['value']), str(new_item['key']['ID']['value'])))
            else:
                print(f"{tcl(32)}Copy Character Container{tcl(0)} %s UUID: %s" % (
                    idx_key, str(container['key']['ID']['value'])))

    MappingCache.LoadCharacterContainerMaps()

    cloneDynamicItemIds = []
    for idx_key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                    'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
        container_id = player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value']
        if container_id in srcMappingCache.ItemContainerSaveData:
            container = parse_item(srcMappingCache.ItemContainerSaveData[container_id], "ItemContainerSaveData")
            new_item = copy.deepcopy(container)
            if container_id in MappingCache.ItemContainerSaveData:
                player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value'] = toUUID(uuid.uuid4())
                new_item['key']['ID']['value'] = player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value']
                print(f"{tcl(32)}Create Item Container{tcl(0)} %s UUID: %s -> %s" % (
                    idx_key, str(container['key']['ID']['value']), str(new_item['key']['ID']['value'])))
            else:
                print(f"{tcl(32)}Copy Item Container{tcl(0)} %s UUID: %s" % (idx_key,
                                                                             str(container['key'][
                                                                                     'ID'][
                                                                                     'value'])))
            containerSlots = container['value']['Slots']['value']['values']
            for slotItem in containerSlots:
                dynamicItemId = slotItem['ItemId']['value']['DynamicId']['value']['LocalIdInCreatedWorld']['value']
                if dynamicItemId == PalObject.EmptyUUID:
                    continue
                if dynamicItemId not in srcMappingCache.DynamicItemSaveData:
                    print(
                        f"{tcl(31)}  Error missed DynamicItemContainer UUID [{tcl(33)} {str(dynamicItemId)}{tcl(0)}  Item {tcl(32)} {slotItem['ItemId']['value']['StaticId']['value']} {tcl(0)}")
                    continue
                if dynamicItemId not in MappingCache.ItemContainerSaveData:
                    print(
                        f"{tcl(32)}  Copy DynamicItemContainer  {tcl(33)} {str(dynamicItemId)}{tcl(0)}  Item {tcl(32)} {slotItem['ItemId']['value']['StaticId']['value']} {tcl(0)}")
                    if not dry_run:
                        wsd['DynamicItemSaveData']['value']['values'].append(
                            srcMappingCache.DynamicItemSaveData[dynamicItemId])
            dynamicItemIds = list(filter(lambda x: str(x) != PalObject.EmptyUUID,
                                         [x['ItemId']['value']['DynamicId']['value']['LocalIdInCreatedWorld'][
                                              'value'] for x in
                                          containerSlots]))
            if len(dynamicItemIds) > 0:
                print(f"  {tcl(33)}Dynamic IDS: {tcl(0)} %s" % ",".join(
                    [str(x) for x in dynamicItemIds]))
            if not dry_run:
                wsd['ItemContainerSaveData']['value'].append(new_item)

    if new_player_uid in MappingCache.PlayerIdMapping:
        print(
            f"{tcl(36)}Player {tcl(32)} {str(new_player_uid)} {tcl(31)} exists, update new player information {tcl(0)}")
        userInstance = MappingCache.PlayerIdMapping[new_player_uid]
        if not dry_run:
            userInstance['value'] = copy.deepcopy(srcMappingCache.PlayerIdMapping[player_uid])['value']
    else:
        print(
            f"{tcl(36)}Copy Player {tcl(32)} {str(new_player_uid)} %s {tcl(31)} {tcl(0)}")
        userInstance = copy.deepcopy(srcMappingCache.PlayerIdMapping[player_uid])
        if not dry_run:
            wsd['CharacterSaveParameterMap']['value'].append(userInstance)

    userInstance['key']['PlayerUId']['value'] = new_player_uid
    userInstance['key']['InstanceId']['value'] = player_gvas['IndividualId']['value']['InstanceId']['value']
    instances.append(
        {'guid': new_player_uid, 'instance_id': player_gvas['IndividualId']['value']['InstanceId']['value']})

    MappingCache.LoadCharacterContainerMaps()

    for item in old_wsd['CharacterSaveParameterMap']['value']:
        player = item['value']['RawData']['value']['object']['SaveParameter']['value']
        if 'IsPlayer' not in player and 'OwnerPlayerUId' in player and player['OwnerPlayerUId']['value'] == player_uid:
            isFound = item['key']['InstanceId']['value'] in MappingCache.CharacterSaveParameterMap
            new_item = copy.deepcopy(item)
            newCharacterData = new_item['value']['RawData']['value']['object']['SaveParameter']['value']
            newCharacterData['OwnerPlayerUId']['value'] = player_gvas['PlayerUId']['value']
            container_id = newCharacterData['SlotID']['value']['ContainerId']['value']['ID']['value']
            if container_id in container_id_mapping:
                container_id = container_id_mapping[container_id]
                newCharacterData['SlotID']['value']['ContainerId']['value']['ID']['value'] = container_id
            elif not container_id in MappingCache.CharacterContainerSaveData:
                container_id = player_gvas['PalStorageContainerId']['value']['ID']['value']
                print(
                    f"Error: Container ID {newCharacterData['SlotID']['value']['ContainerId']['value']['ID']['value']}"
                    f" not exists, move to PalStorage {container_id}")
                newCharacterData['SlotID']['value']['ContainerId']['value']['ID']['value'] = container_id
            if isFound:
                if 'EquipItemContainerId' in player:
                    newCharacterData['EquipItemContainerId']['value']['ID']['value'] = toUUID(uuid.uuid4())
                    print(
                        f"Copy EquipItemContainerId Containers {player['EquipItemContainerId']['value']['ID']['value']} -> {newCharacterData['EquipItemContainerId']['value']['ID']['value']}")
                    if player['EquipItemContainerId']['value']['ID']['value'] in srcMappingCache.ItemContainerSaveData:
                        cloneItemContainers = srcMappingCache.ItemContainerSaveData[
                            player['EquipItemContainerId']['value']['ID']['value']]
                        CopyItemContainers(cloneItemContainers,
                                           newCharacterData['EquipItemContainerId']['value']['ID']['value'])
                if 'ItemContainerId' in player:
                    newCharacterData['ItemContainerId']['value']['ID']['value'] = toUUID(uuid.uuid4())
                    print(
                        f"Copy ItemContainerId Containers {player['ItemContainerId']['value']['ID']['value']} -> {newCharacterData['ItemContainerId']['value']['ID']['value']}")
                    if player['ItemContainerId']['value']['ID']['value'] in srcMappingCache.ItemContainerSaveData:
                        cloneItemContainers = srcMappingCache.ItemContainerSaveData[
                            player['ItemContainerId']['value']['ID']['value']]
                        CopyItemContainers(cloneItemContainers,
                                           newCharacterData['ItemContainerId']['value']['ID']['value'])
                new_item['key']['InstanceId']['value'] = toUUID(uuid.uuid4())
                # Assign Character Container ID to new InstanceID
                container = parse_item(MappingCache.CharacterContainerSaveData[container_id],
                                       "CharacterContainerSaveData")
                slotItems = container['value']['Slots']['value']['values']
                slotIndex = -1
                emptySlotIndex = -1
                for _slotIndex, slot in enumerate(slotItems):
                    if slot['RawData']['value']['instance_id'] in [item['key']['InstanceId']['value'], new_item['key']['InstanceId']['value']]:
                        slotIndex = _slotIndex
                        break
                    elif slot['RawData']['value']['instance_id'] == PalObject.EmptyUUID and emptySlotIndex == -1:
                        emptySlotIndex = _slotIndex

                if slotIndex == -1 and emptySlotIndex != -1:
                    slotInex = emptySlotIndex
                if slotIndex == -1:
                    print("Error: failed to copy the pal to slot, no empty slots")
                    continue
                newCharacterData['SlotID']['value']['SlotIndex']['value'] = slotIndex
                slotItem = slotItems[slotIndex]
                slotItem['RawData']['value']['instance_id'] = new_item['key']['InstanceId']['value']
                print(
                    f"{tcl(32)}Copy Pal{tcl(0)}  UUID: %s -> %s  Owner: %s  CharacterID: %s" % (
                        str(item['key']['InstanceId']['value']), str(new_item['key']['InstanceId']['value']),
                        str(player['OwnerPlayerUId']['value']),
                        player['CharacterID']['value']))
            else:
                print(
                    f"{tcl(32)}Copy Pal{tcl(0)}  UUID: %s  Owner: %s  CharacterID: %s" % (
                        str(item['key']['InstanceId']['value']), str(player['OwnerPlayerUId']['value']),
                        player['CharacterID']['value']))
            if not dry_run:
                wsd['CharacterSaveParameterMap']['value'].append(new_item)
            instances.append(
                {'guid': PalObject.EmptyUUID,
                 'instance_id': new_item['key']['InstanceId']['value']})
    # Copy Item from GroupSaveDataMap
    player_group = None
    group_id = userInstance['value']['RawData']['value']['group_id']
    if group_id in MappingCache.GuildSaveDataMap:
        player_group = MappingCache.GuildSaveDataMap[group_id]
        item = player_group['value']['RawData']['value']
        print(f"{tcl(32)}Copy User {tcl(93)} %s {tcl(0)}  to Guild{tcl(0)} {tcl(32)} %s {tcl(0)}  UUID %s" % (
            userInstance['value']['RawData']['value']['object']['SaveParameter']['value']['NickName']['value'],
            item['guild_name'], item['group_id']))
        item['players'].append({
            'player_uid': new_player_uid,
            "player_info": {
                'last_online_real_time': 0,
                'player_name':
                    userInstance['value']['RawData']['value']['object']['SaveParameter']['value']['NickName']['value']
            }
        })
    if player_group is None:
        src_player_group = srcMappingCache.GuildSaveDataMap[group_id]
        player_group = PalObject.GroupSaveData(group_id, src_player_group['value']['RawData']['value']['guild_name'],
                                               new_player_uid,
                                               userInstance['value']['RawData']['value']['object']['SaveParameter'][
                                                   'value']['NickName']['value'])
        print(f"{tcl(32)}Create Guild{tcl(0)} Group ID [{tcl(92)}%s{tcl(0)}]" % (str(player_group['key'])))
        if not dry_run:
            wsd['GroupSaveDataMap']['value'].append(player_group)

    player_group['value']['RawData']['value']['individual_character_handle_ids'] += instances
    MappingCache.LoadItemContainerMaps()
    MappingCache.LoadCharacterSaveParameterMap()
    MappingCache.LoadCharacterContainerMaps()
    MappingCache.LoadGroupSaveDataMap()
    MappingCache.LoadGuildInstanceMapping()
    if not dry_run:
        if id(old_wsd) != id(wsd) and player_uid not in MappingCache.PlayerIdMapping:
            backup_file(player_sav_file, True)
            if os.path.dirname(player_sav_file) == os.path.dirname(new_player_sav_file):
                delete_files.append(player_sav_file)
        if new_player_sav_file in delete_files:
            delete_files.remove(new_player_sav_file)
        backup_file(new_player_sav_file, True)
        with open(new_player_sav_file, "wb") as f:
            print("Saving new player sav %s" % (new_player_sav_file))
            if "Pal.PalWorldSaveGame" in player_gvas_file.header.save_game_class_name or "Pal.PalLocalWorldSaveGame" in player_gvas_file.header.save_game_class_name:
                save_type = 0x32
            else:
                save_type = 0x31
            sav_file = compress_gvas_to_sav(player_gvas_file.write(PALWORLD_CUSTOM_PROPERTIES), save_type)
            f.write(sav_file)


def MoveToGuild(player_uid, group_id):
    player_uid = toUUID(player_uid)
    if toUUID(group_id) not in MappingCache.GroupSaveDataMap:
        print(f"{tcl(31)}Error: cannot found target guild{tcl(0)}")
        return

    instances = []
    remove_instance_ids = []
    playerInstance = None

    for item in wsd['CharacterSaveParameterMap']['value']:
        player = item['value']['RawData']['value']['object']['SaveParameter']['value']
        if item['key']['PlayerUId']['value'] == player_uid and 'IsPlayer' in player and player['IsPlayer']['value']:
            playerInstance = player
            instances.append({
                'guid': item['key']['PlayerUId']['value'],
                'instance_id': item['key']['InstanceId']['value']
            })
            remove_instance_ids.append(item['key']['InstanceId']['value'])
        elif 'OwnerPlayerUId' in player and player['OwnerPlayerUId']['value'] == player_uid:
            instances.append({
                'guid': PalObject.EmptyUUID,
                'instance_id': item['key']['InstanceId']['value']
            })
            remove_instance_ids.append(item['key']['InstanceId']['value'])

    for _group_id in MappingCache.GroupSaveDataMap:
        group_data = parse_item(MappingCache.GroupSaveDataMap[_group_id], "GroupSaveDataMap")
        if group_data['value']['GroupType']['value']['value'] == "EPalGroupType::Guild":
            group_info = group_data['value']['RawData']['value']
            delete_g_players = []
            for g_player in group_info['players']:
                if g_player['player_uid'] == player_uid:
                    delete_g_players.append(g_player)
                    print(
                        f"{tcl(31)}Delete player {tcl(93)} %s {tcl(31)} on guild {tcl(93)} %s {tcl(0)} [{tcl(92)} %s {tcl(0)}] " % (
                            g_player['player_info']['player_name'], group_info['guild_name'], group_info['group_id']))

            for g_player in delete_g_players:
                group_info['players'].remove(g_player)

            if len(group_info['players']) == 0 and group_info['group_id'] != toUUID(group_id):
                DeleteGuild(group_info['group_id'])

            remove_items = []
            for ind_id in group_info['individual_character_handle_ids']:
                if ind_id['instance_id'] in remove_instance_ids:
                    remove_items.append(ind_id)
                    print(
                        f"{tcl(31)}Delete guild [{tcl(92)} %s {tcl(31)}] character handle GUID {tcl(92)} %s {tcl(0)} [InstanceID {tcl(92)} %s {tcl(0)}] " % (
                            group_info['group_id'], ind_id['guid'], ind_id['instance_id']))
            for item in remove_items:
                group_info['individual_character_handle_ids'].remove(item)

    MappingCache.PlayerIdMapping[player_uid]['value']['RawData']['value']['group_id'] = toUUID(group_id)
    group_data = parse_item(MappingCache.GroupSaveDataMap[toUUID(group_id)], "GroupSaveDataMap")
    group_info = group_data['value']['RawData']['value']
    print(f"{tcl(32)}Append character and players to Guild {group_info['guild_name']}{tcl(0)}")
    group_info['players'].append({
        'player_uid': player_uid,
        'player_info': {
            'last_online_real_time': 0,
            'player_name':
                playerInstance['NickName']['value']
        }
    })
    group_info['individual_character_handle_ids'] += instances
    MappingCache.LoadGroupSaveDataMap()


def CleanupWorkerSick():
    for instanceId in MappingCache.CharacterSaveParameterMap:
        characterData = \
            MappingCache.CharacterSaveParameterMap[instanceId]['value']['RawData']['value']['object']['SaveParameter'][
                'value']
        if 'WorkerSick' in characterData:
            print("Delete WorkerSick on %s" % CharacterDescription(MappingCache.CharacterSaveParameterMap[instanceId]))
            del characterData['WorkerSick']


def FindInactivePlayer(days):
    player_list = []
    for group_id in MappingCache.GuildSaveDataMap:
        guild = MappingCache.GuildSaveDataMap[group_id]
        group_data = guild['value']['RawData']['value']
        for g_player in group_data['players']:
            if (wsd['GameTimeSaveData']['value']['RealDateTimeTicks']['value'] -
                g_player['player_info']['last_online_real_time']) / 1e7 > days * 86400:
                player_list.append(g_player['player_uid'])

    return player_list


def FindPlayersFromInactiveGuild(days):
    player_list = []
    for group_id in MappingCache.GuildSaveDataMap:
        guild = MappingCache.GuildSaveDataMap[group_id]
        group_data = guild['value']['RawData']['value']
        players_list_guild = []  # Current guild's players list
        for g_player in group_data['players']:
            # If any member is active, skip this guild
            if (wsd['GameTimeSaveData']['value']['RealDateTimeTicks']['value'] -
                g_player['player_info']['last_online_real_time']) / 1e7 <= days * 86400:
                break
            else:
                players_list_guild.append(g_player['player_uid'])
        else:
            player_list.extend(players_list_guild)

    return player_list


def RepairPlayer(player_uid):
    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print(f"{tcl(31)}Error: Player Sav file Not exists: {player_sav_file}{tcl(0)}")
        return

    player_uid = toUUID(player_uid)
    replace_anyway = False

    if player_uid != player_gvas['IndividualId']['value']['PlayerUId']['value']:
        print(f"{tcl(31)}Error: Player {tcl(93)}{player_uid}{tcl(31)} not matched with save file "
              f"{tcl(93)}{player_gvas['IndividualId']['value']['PlayerUId']['value']}{tcl(31)}, failed to repair{tcl(0)}")
        return

    if player_uid not in MappingCache.PlayerIdMapping:
        print(f"{tcl(31)}Error: Player {tcl(93)}{player_uid}{tcl(31)} not exists, failed to repair{tcl(0)}")
        return

    player_instance_id = MappingCache.PlayerIdMapping[player_uid]['key']['InstanceId']['value']
    if not MappingCache.PlayerIdMapping[player_uid] is MappingCache.CharacterSaveParameterMap[player_instance_id]:
        print(f"{tcl(31)}Error: Player {tcl(93)}{player_uid}{tcl(31)} duplicated, please delete first{tcl(0)}")
        return

    if MappingCache.PlayerIdMapping[player_uid]['key']['InstanceId']['value'] != \
            player_gvas['IndividualId']['value']['InstanceId']['value']:
        print(f"{tcl(33)}Error: Instance ID not matched {tcl(93)}{player_instance_id}{tcl(33)} with save file "
              f"{tcl(93)}{player_gvas['IndividualId']['value']['InstanceId']['value']}{tcl(0)}")
        if player_gvas['IndividualId']['value']['InstanceId']['value'] in MappingCache.CharacterSaveParameterMap:
            sav_instance_id = player_gvas['IndividualId']['value']['InstanceId']['value']
            sav_instance = MappingCache.CharacterSaveParameterMap[sav_instance_id]
            if sav_instance['key']['PlayerUId']['value'] != player_uid:
                print(f"{tcl(31)}Error: Save file for {tcl(93)}{player_uid}{tcl(31)} "
                      f"Instance ID {tcl(93)}{player_instance_id}{tcl(31)} is ref to player "
                      f"{tcl(93)}{sav_instance['key']['PlayerUId']['value']}{tcl(31)}, fail to repair {tcl(0)}")
                return
            else:
                print(f"{tcl(31)}Duplicate Instance, delete the instance "
                      f"{tcl(93)}{MappingCache.PlayerIdMapping[player_uid]['key']['InstanceId']['value']}{tcl(0)}")
                DeleteCharacter(MappingCache.PlayerIdMapping[player_uid]['key']['InstanceId']['value'])
                MappingCache.LoadCharacterSaveParameterMap()
        MappingCache.PlayerIdMapping[player_uid]['key']['InstanceId']['value'] = \
            player_gvas['IndividualId']['value']['InstanceId']['value']
        replace_anyway = True

    load_skipped_decode(wsd, ['DynamicItemSaveData', 'ItemContainerSaveData', 'CharacterContainerSaveData'], False)
    emptySlots = {
        "CommonContainerId": 42,
        "DropSlotContainerId": 4,
        "EssentialContainerId": 100,
        "FoodEquipContainerId": 5,
        "PlayerEquipArmorContainerId": 6,
        "WeaponLoadOutContainerId": 4,

        "OtomoCharacterContainerId": 5,
        "PalStorageContainerId": 480
    }
    anyFix = False
    for key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
        if player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'] not in MappingCache.ItemContainerSaveData:
            print(f"{tcl(33)}Error: Player {tcl(93)}{player_uid}{tcl(33)} Item Container {tcl(36)}{key[:-11]}{tcl(0)} "
                  f"{tcl(32)}{player_gvas['inventoryInfo']['value'][key]['value']['ID']['value']}{tcl(0)} Not exists")
            n = PalObject.ItemContainerSaveData_Array(
                player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'],
                emptySlots[key])
            wsd['ItemContainerSaveData']['value'].append(n)
            anyFix = True

    loaded_instance = set()
    if player_gvas['OtomoCharacterContainerId']['value']['ID']['value'] in MappingCache.CharacterContainerSaveData:
        container_id = player_gvas['OtomoCharacterContainerId']['value']['ID']['value']
        container = parse_item(MappingCache.CharacterContainerSaveData[container_id], "CharacterContainerSaveData")
        for slot in container['value']['Slots']['value']['values']:
            if slot['RawData']['value']['instance_id'] != PalObject.EmptyUUID:
                loaded_instance.add(slot['RawData']['value']['instance_id'])

    rebuildPalStorageContainerId = False
    if player_gvas['PalStorageContainerId']['value']['ID']['value'] in MappingCache.CharacterContainerSaveData:
        container_id = player_gvas['PalStorageContainerId']['value']['ID']['value']
        container = parse_item(MappingCache.CharacterContainerSaveData[container_id], "CharacterContainerSaveData")
        if len(container['value']['Slots']['value']['values']) < emptySlots['PalStorageContainerId']:
            print(
                f"{tcl(33)}Error: PalStorage Slots {len(container['value']['Slots']['value']['values'])} lower then default{tcl(0)}")
            rebuildPalStorageContainerId = True

    standbySlots = []
    unloadedSlots = []
    unknowContainers = set()
    baseWorkerContainers = set()
    workerSlots = set()
    for instanceId in MappingCache.CharacterSaveParameterMap:
        item = MappingCache.CharacterSaveParameterMap[instanceId]
        player = item['value']['RawData']['value']['object']['SaveParameter']['value']
        if 'OwnerPlayerUId' in player and player['OwnerPlayerUId']['value'] == player_uid:
            if 'SlotID' in player and player['SlotID']['value']['ContainerId']['value']['ID']['value'] == \
                    player_gvas['OtomoCharacterContainerId']['value']['ID']['value']:
                if item['key']['InstanceId']['value'] not in loaded_instance:
                    loaded_instance.add(item['key']['InstanceId']['value'])
            elif 'SlotID' in player and player['SlotID']['value']['ContainerId']['value']['ID']['value'] == \
                    player_gvas['PalStorageContainerId']['value']['ID']['value']:
                standbySlots.append(item['key']['InstanceId']['value'])
            elif 'SlotID' in player:
                slot_id = player['SlotID']['value']['ContainerId']['value']['ID']['value']
                unknowContainers.add(slot_id)
                if slot_id not in MappingCache.CharacterContainerSaveData:
                    print(f"{tcl(33)} Player {tcl(93)}{player_uid}{tcl(33)} SlotID "
                          f"{tcl(93)}{slot_id}{tcl(33)} invalid{tcl(0)}")
                    player['SlotID']['value']['ContainerId']['value']['ID']['value'] = \
                        player_gvas['PalStorageContainerId']['value']['ID']['value']
                    standbySlots.append(item['key']['InstanceId']['value'])
                    rebuildPalStorageContainerId = True
                else:
                    container = parse_item(MappingCache.CharacterContainerSaveData[slot_id],
                                           "CharacterContainerSaveData")
                    slotItems = container['value']['Slots']['value']['values']
                    try:
                        slotItem = slotItems[player['SlotID']['value']['SlotIndex']['value']]
                        if slotItem['RawData']['value']['instance_id'] != item['key']['InstanceId']['value']:
                            print(f"{tcl(33)} Player {tcl(93)}{player_uid}{tcl(33)} SlotID "
                                  f"{tcl(93)}{slot_id}{tcl(33)} ItemIndex not matched -> "
                                  f"{player['SlotID']['value']['SlotIndex']['value']}{tcl(0)}")
                            raise IndexError()
                    except IndexError:
                        for idx_slot, _slot in enumerate(slotItems):
                            if _slot['RawData']['value']['instance_id'] == item['key']['InstanceId']['value']:
                                player['SlotID']['value']['SlotIndex']['value'] = idx_slot
                                slotItem = _slot
                                break

                    if slotItem['PermissionTribeID']['value']['value'] == "EPalTribeID::GrassMammoth":
                        workerSlots.add(item['key']['InstanceId']['value'])
                        baseWorkerContainers.add(slot_id)
                    else:
                        if slotItem['PermissionTribeID']['value']['value'] not in ["EPalTribeID::None", "None"]:
                            gp(slotItem)
                        unloadedSlots.append(item['key']['InstanceId']['value'])

            if 'OldOwnerPlayerUIds' in player:
                if player_uid not in player['OldOwnerPlayerUIds']['value']['values']:
                    print(
                        f"Player {tcl(93)}{player_uid}{tcl(33)} Character {tcl(93)}{item['key']['InstanceId']['value']}{tcl(0)} "
                        f"Old Owner Player invalid -> %s" % ",".join(
                            "%s" % x for x in player['OldOwnerPlayerUIds']['value']['values']))
                player['OldOwnerPlayerUIds']['value']['values'] = [player_uid]
            # elif item['key']['InstanceId']['value'] not in loaded_instance and \
            #     item['key']['InstanceId']['value'] not in standbySlots:

    if rebuildPalStorageContainerId and \
            player_gvas['PalStorageContainerId']['value']['ID']['value'] in MappingCache.CharacterContainerSaveData:
        print(f"{tcl(33)}Rebuild Player {tcl(93)}{player_uid}{tcl(33)} Character Container "
              f"{player_gvas['PalStorageContainerId']['value']['ID']['value']}f{0}")
        wsd['CharacterContainerSaveData']['value'].remove(
            MappingCache.CharacterContainerSaveData[player_gvas['PalStorageContainerId']['value']['ID']['value']])
        del MappingCache.CharacterContainerSaveData[player_gvas['PalStorageContainerId']['value']['ID']['value']]

    for idx_key in ['OtomoCharacterContainerId', 'PalStorageContainerId']:
        container_id = player_gvas[idx_key]['value']['ID']['value']
        if container_id not in MappingCache.CharacterContainerSaveData:
            print(
                f"{tcl(33)}Error: Player {tcl(93)}{player_uid}{tcl(33)} Character Container {tcl(36)}{idx_key[:-11]}{tcl(0)} "
                f"{tcl(32)}{container_id}{tcl(0)} Not exists")
            n = PalObject.CharacterContainerSaveData_Array(container_id, emptySlots[idx_key], list(loaded_instance) if
            idx_key == 'OtomoCharacterContainerId' else standbySlots)
            wsd['CharacterContainerSaveData']['value'].append(n)
            anyFix = True

    if len(unloadedSlots) > 0:
        print(f"{tcl(33)}Warning: Player {tcl(93)}{player_uid}{tcl(33)} Have {tcl(32)}{len(unloadedSlots)}{tcl(33)} "
              f"character not in player containers, worker in base: {tcl(32)}{len(workerSlots)}{tcl(33)}, "
              f"loaded: {tcl(32)}{len(loaded_instance)}{tcl(33)} / standby: {tcl(32)}{len(standbySlots)}{tcl(0)}")
        print(f"Container ids:")
        unknowContainers.update(baseWorkerContainers)
        unknowContainers.add(player_gvas['OtomoCharacterContainerId']['value']['ID']['value'])
        unknowContainers.add(player_gvas['PalStorageContainerId']['value']['ID']['value'])
        for container_id in unknowContainers:
            container = parse_item(MappingCache.CharacterContainerSaveData[container_id], "CharacterContainerSaveData")
            container_type = f"{tcl(31)}Unknow Container"
            if container_id in baseWorkerContainers:
                container_type = f"{tcl(36)}Worker Container"
            elif container_id == player_gvas['OtomoCharacterContainerId']['value']['ID']['value']:
                container_type = f"{tcl(33)}Player Otomo Character"
            elif container_id == player_gvas['PalStorageContainerId']['value']['ID']['value']:
                container_type = f"{tcl(33)}Player Idle Character"
            print(
                f"  {container_type}{tcl(0)}: {container_id}{tcl(0)}: {len(container['value']['Slots']['value']['values'])}")
            # gp(container)

    player = MappingCache.PlayerIdMapping[player_uid]
    group_id = player['value']['RawData']['value']['group_id']
    if group_id in MappingCache.GroupSaveDataMap:
        group = MappingCache.GroupSaveDataMap[group_id]['value']['RawData']['value']
        remove_handle_ids = []
        new_handle_ids = [
            {'guid': player_uid, 'instance_id': player_gvas['IndividualId']['value']['InstanceId']['value']}
        ]
        for instance_id in loaded_instance:
            new_handle_ids.append({'guid': PalObject.EmptyUUID, 'instance_id': instance_id})
        for instance_id in standbySlots:
            new_handle_ids.append({'guid': PalObject.EmptyUUID, 'instance_id': instance_id})
        start_items = len(new_handle_ids)
        for ind_char in group['individual_character_handle_ids']:
            if ind_char['guid'] == player_uid or ind_char['instance_id'] in loaded_instance or \
                    ind_char['instance_id'] in standbySlots:
                remove_handle_ids.append(ind_char)
            else:
                new_handle_ids.append(ind_char)
        if start_items != len(remove_handle_ids) or replace_anyway:
            anyFix = True
            print(f"{tcl(33)}Error: Guild instance {tcl(36)}{group_id}{tcl(0)} invalid, local items: {start_items}, "
                  f"replace with {len(group['individual_character_handle_ids'])} -> {len(new_handle_ids)}")
            group['individual_character_handle_ids'] = new_handle_ids

    if anyFix:
        print("Reload cache")
        MappingCache.LoadCharacterSaveParameterMap()
        MappingCache.LoadCharacterContainerMaps()
        MappingCache.LoadItemContainerMaps()
        MappingCache.LoadGuildInstanceMapping()


def MigratePlayer(player_uid, new_player_uid):
    load_skipped_decode(wsd, ['MapObjectSaveData', 'GroupSaveDataMap', 'MapObjectSpawnerInStageSaveData',
                              'CharacterContainerSaveData',
                              'ItemContainerSaveData'], False)

    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print(f"{tcl(33)}Warning: Player Sav file Not exists: {player_sav_file}{tcl(0)}")
        return

    # err, new_player_gvas, new_player_sav_file, new_player_gvas_file = GetPlayerGvas(new_player_uid)
    # if not err:
    #     print(f"{tcl(33)}Warning: Player Sav file Not exists: {player_sav_file}{tcl(0)}")
    #     return

    new_player_sav_file = os.path.dirname(
        os.path.abspath(args.filename)) + "/Players/" + new_player_uid.upper().replace("-", "") + ".sav"
    new_player_uid = toUUID(new_player_uid)

    player_uid = player_gvas['PlayerUId']['value']
    player_gvas['PlayerUId']['value'] = new_player_uid
    player_gvas['IndividualId']['value']['PlayerUId']['value'] = player_gvas['PlayerUId']['value']
    player_gvas['IndividualId']['value']['InstanceId']['value'] = toUUID(uuid.uuid4())

    if player_uid not in MappingCache.PlayerIdMapping:
        raise IndexError(f"Migrate player {player_uid} not exists")

    while new_player_uid in MappingCache.PlayerIdMapping:
        DeletePlayer(new_player_uid,
                     InstanceId=MappingCache.PlayerIdMapping[new_player_uid]['key']['InstanceId']['value'])
        MappingCache.LoadCharacterSaveParameterMap()

    backup_file(new_player_sav_file, True)
    with open(new_player_sav_file, "wb") as f:
        print("Saving new player sav %s" % new_player_sav_file)
        if "Pal.PalWorldSaveGame" in player_gvas_file.header.save_game_class_name or "Pal.PalLocalWorldSaveGame" in player_gvas_file.header.save_game_class_name:
            save_type = 0x32
        else:
            save_type = 0x31
        sav_file = compress_gvas_to_sav(player_gvas_file.write(PALWORLD_CUSTOM_PROPERTIES), save_type)
        f.write(sav_file)
    for item in wsd['CharacterSaveParameterMap']['value']:
        player = item['value']['RawData']['value']['object']['SaveParameter']['value']
        if item['key']['PlayerUId']['value'] == player_uid and 'IsPlayer' in player and player['IsPlayer']['value']:
            item['key']['PlayerUId']['value'] = player_gvas['PlayerUId']['value']
            item['key']['InstanceId']['value'] = player_gvas['IndividualId']['value']['InstanceId']['value']
            print(
                f"{tcl(32)}Migrate User{tcl(0)}  UUID: %s  Level: %d  CharacterID: {tcl(93)}%s{tcl(0)}" % (
                    str(item['key']['InstanceId']['value']), player['Level']['value'] if 'Level' in player else -1,
                    player['NickName']['value']))
        elif 'OwnerPlayerUId' in player and player['OwnerPlayerUId']['value'] == player_uid:
            player['OwnerPlayerUId']['value'] = new_player_uid
            player['OldOwnerPlayerUIds']['value']['values'] = [player['OwnerPlayerUId']['value']]
            print(
                f"{tcl(32)}Migrate Pal{tcl(0)}  UUID: %s  Owner: %s  CharacterID: %s" % (
                    str(item['key']['InstanceId']['value']), str(player['OwnerPlayerUId']['value']),
                    player['CharacterID']['value']))
            if 'EquipItemContainerId' in player:
                if player['EquipItemContainerId']['value']['ID']['value'] not in MappingCache.ItemContainerSaveData:
                    print(f"{tcl(31)}Error: Invalid Equal Item Container ID "
                          f"{player['EquipItemContainerId']['value']['ID']['value']}{tcl(0)}")
                    wsd['ItemContainerSaveData']['value'].append(
                        PalObject.ItemContainerSaveData_Array(player['EquipItemContainerId']['value']['ID']['value'],
                                                              2))
        elif 'OldOwnerPlayerUIds' in player and player_uid in player['OldOwnerPlayerUIds']['value']['values']:
            player['OldOwnerPlayerUIds']['value']['values'].remove(player_uid)
            print(
                f"{tcl(31)}Delete Pal OldOwnerPlayerUIds{tcl(0)}  UUID: %s  Owner: %s  CharacterID: %s" % (
                    str(item['key']['InstanceId']['value']), str(player['OwnerPlayerUId']['value']),
                    player['CharacterID']['value']))
        if 'SlotID' in player:
            if player['SlotID']['value']['ContainerId']['value']['ID'][
                'value'] not in MappingCache.CharacterContainerSaveData:
                print(f"{tcl(31)}Error: Invalid Character Container ID "
                      f"{player['SlotID']['value']['ContainerId']['value']['ID']['value']}{tcl(0)}")

    for group_data in wsd['GroupSaveDataMap']['value']:
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            item = group_data['value']['RawData']['value']
            for player in item['players']:
                if player['player_uid'] == player_uid:
                    player['player_uid'] = player_gvas['PlayerUId']['value']
                    print(
                        f"{tcl(32)}Migrate User from Guild{tcl(0)}  {tcl(93)}%s{tcl(0)}   [{tcl(92)}%s{tcl(0)}] Last Online: %d" % (
                            player['player_info']['player_name'], str(player['player_uid']),
                            player['player_info']['last_online_real_time']))
                    remove_handle_ids = []
                    for ind_char in item['individual_character_handle_ids']:
                        if ind_char['guid'] == player_uid:
                            remove_handle_ids.append(ind_char)
                            print(f"{tcl(31)}Delete Guild Character InstanceID %s {tcl(0)}" % str(
                                ind_char['instance_id']))
                    for remove_handle in remove_handle_ids:
                        item['individual_character_handle_ids'].remove(remove_handle)
                    item['individual_character_handle_ids'].append({
                        'guid': player_gvas['PlayerUId']['value'],
                        'instance_id': player_gvas['IndividualId']['value']['InstanceId']['value']
                    })
                    print(f"{tcl(32)}Append Guild Character InstanceID %s {tcl(0)}" % (
                        str(player_gvas['IndividualId']['value']['InstanceId']['value'])))
                    break
            if item['admin_player_uid'] == player_uid:
                item['admin_player_uid'] = player_gvas['PlayerUId']['value']
                print(f"{tcl(32)}Migrate Guild Admin {tcl(0)}")

    MigrateBuilding(player_uid, new_player_uid)

    if new_player_sav_file in delete_files:
        delete_files.remove(new_player_sav_file)
    backup_file(player_sav_file, True)
    delete_files.append(player_sav_file)
    MappingCache.LoadCharacterSaveParameterMap()
    RepairPlayer(new_player_uid)
    print("Finish to migrate player from Save, please delete this file manually: %s" % player_sav_file)


def MigrateBuilding(player_uid, new_player_uid):
    player_uid = toUUID(player_uid)
    new_player_uid = toUUID(new_player_uid)

    for map_data in wsd['MapObjectSaveData']['value']['values']:
        if 'owner_player_uid' in map_data['ConcreteModel']['value']['RawData']['value'] and \
                map_data['ConcreteModel']['value']['RawData']['value']['owner_player_uid'] == player_uid:
            print(
                f"{tcl(32)}Migrate ConcreteModel{tcl(0)}  {tcl(93)}%s{tcl(0)}"
                f" Old Owner: {tcl(93)}{map_data['ConcreteModel']['value']['RawData']['value']['owner_player_uid']}{tcl(0)}" % (
                    str(map_data['MapObjectInstanceId']['value'])))
            map_data['ConcreteModel']['value']['RawData']['value']['owner_player_uid'] = new_player_uid
        for concrete in map_data['ConcreteModel']['value']['ModuleMap']['value']:
            if concrete['key'] == "EPalMapObjectConcreteModelModuleType::PasswordLock":
                for player_info in concrete['value']['RawData']['value']['player_infos']:
                    if player_info['player_uid'] == player_uid:
                        player_info['player_uid'] = new_player_uid
                        print(f"{tcl(32)}Migrate ConcreteModel PasswordLock{tcl(0)}  {tcl(93)}%s{tcl(0)}" % (
                            str(map_data['MapObjectInstanceId']['value'])))
        if map_data['Model']['value']['RawData']['value']['build_player_uid'] == player_uid:
            map_data['Model']['value']['RawData']['value']['build_player_uid'] = new_player_uid
            print(f"{tcl(32)}Migrate Building{tcl(0)}  {tcl(93)}%s{tcl(0)}" % (
                str(map_data['MapObjectInstanceId']['value'])))


def FindReferenceMapObject(mapObjectId, level=0, recursive_mapObjectIds=set(), srcMapping=None):
    if srcMapping is None:
        srcMapping = MappingCache
    mapObjectId = toUUID(mapObjectId)
    if mapObjectId not in srcMapping.MapObjectSaveData:
        print(f"Invalid {mapObjectId}")
        return []
    mapObject = srcMapping.MapObjectSaveData[mapObjectId]
    connector = mapObject['Model']['value']['Connector']['value']['RawData']
    reference_ids = []
    if 'value' in connector:
        # Parent of this object
        if 'connect' in connector['value']:
            if 'any_place' in connector['value']['connect']:
                for connection_item in connector['value']['connect']['any_place']:
                    recursive_mapObjectIds.add(mapObjectId)
                    # reference_ids['sub_id'].append(connection_item['connect_to_model_instance_id'])
                    if connection_item['connect_to_model_instance_id'] in recursive_mapObjectIds:
                        continue
                    # print("%sAny_Place: %s -> %s" % ("  " * level, mapObjectId, connection_item['connect_to_model_instance_id']))
                    reference_ids.append(connection_item['connect_to_model_instance_id'])
                    reference_ids += FindReferenceMapObject(connection_item['connect_to_model_instance_id'], level + 1,
                                                            recursive_mapObjectIds, srcMapping)
        if 'other_connectors' in connector['value']:
            for other_connection_list in connector['value']['other_connectors']:
                for connection_item in other_connection_list['connect']:
                    recursive_mapObjectIds.add(mapObjectId)
                    # reference_ids['sub_id'].append(connection_item['connect_to_model_instance_id'])
                    # print("%sOther: %s -> %s" % ("  " * level, mapObjectId, connection_item['connect_to_model_instance_id']))
                    if connection_item['connect_to_model_instance_id'] in recursive_mapObjectIds:
                        continue
                    # recursive_mapObjectIds.append(connection_item['connect_to_model_instance_id'])
                    reference_ids.append(connection_item['connect_to_model_instance_id'])
                    reference_ids += FindReferenceMapObject(connection_item['connect_to_model_instance_id'], level + 1,
                                                            recursive_mapObjectIds, srcMapping)

    return reference_ids


def PrintReferenceMapObjects():
    for mapObjectId in MappingCache.MapObjectSaveData:
        x = FindReferenceMapObject(mapObjectId, 0, set())
        # print("G -> %d" % len(x.keys()))
        if len(x.keys()) == 0:
            continue
        print(x)


# NON FINISHED
def BatchDeleteMapObject(map_object_ids):
    load_skipped_decode(wsd, ['MapObjectSpawnerInStageSaveData', 'MapObjectSaveData'], False)

    delete_map_object_ids = set()
    delete_item_container_ids = []
    delete_owners = {}

    map_object_ids = set(map_object_ids)
    for map_object_id in list(map_object_ids):
        sub_ids = FindReferenceMapObject(map_object_id)
        for sub_id in sub_ids:
            map_object_ids.add(sub_id)

    for map_object_id in map_object_ids:
        map_object_id = toUUID(map_object_id)
        if map_object_id not in MappingCache.MapObjectSaveData:
            continue
        delete_map_object_ids.add(map_object_id)
        mapObject = MappingCache.MapObjectSaveData[map_object_id]
        for concrete in mapObject['ConcreteModel']['value']['ModuleMap']['value']:
            if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
                delete_item_container_ids.append(concrete['value']['RawData']['value']['target_container_id'])
            if concrete['key'] == "EPalMapObjectConcreteModelModuleType::StatusObserver":
                pass
            if concrete['key'] == "EPalMapObjectConcreteModelModuleType::Workee":
                _DeleteWorkSaveData(concrete['value']['RawData']['value']['target_work_id'])
            # if concrete['RawData']['value']['concrete_model_type'] == "PalMapObjectItemDropOnDamagModel":
        # Connected MapObject
        connected_mapObjects = []

        owner_spawner_level_object_instance_id = mapObject['Model']['value']['RawData']['value'][
            'owner_spawner_level_object_instance_id']
        delete_owners[owner_spawner_level_object_instance_id] = None

        if 'repair_work_id' in mapObject['Model']['value']['RawData']['value'] and \
                mapObject['Model']['value']['RawData']['value'][
                    'repair_work_id'] != PalObject.EmptyUUID:
            _DeleteWorkSaveData(mapObject['Model']['value']['RawData']['value']['repair_work_id'])

        if 'BuildProcess' in mapObject['Model']['value'] and PalObject.EmptyUUID != \
                mapObject['Model']['value']['BuildProcess']['value']['RawData']['value']['id']:
            _DeleteWorkSaveData(mapObject['Model']['value']['BuildProcess']['value']['RawData']['value']['id'])

    new_mapobjects = []
    for mapObject in wsd['MapObjectSaveData']['value']['values']:
        if mapObject['MapObjectInstanceId']['value'] not in delete_map_object_ids:
            new_mapobjects.append(mapObject)
    wsd['MapObjectSaveData']['value']['values'] = new_mapobjects

    new_spawner_objects = []
    spawnInStage = parse_item(wsd['MapObjectSpawnerInStageSaveData']['value'][0]['value'],
                              "MapObjectSpawnerInStageSaveData.Value")
    for mapObj in spawnInStage['SpawnerDataMapByLevelObjectInstanceId']['value']:
        if mapObj['key'] not in delete_owners:
            new_spawner_objects.append(mapObj)

    wsd['MapObjectSpawnerInStageSaveData']['value'][0]['value']['SpawnerDataMapByLevelObjectInstanceId'][
        'value'] = new_spawner_objects
    BatchDeleteItemContainer(delete_item_container_ids)
    print(f"Delete MapObjectSaveData: {len(delete_map_object_ids)} / {len(map_object_ids)}")
    MappingCache.LoadMapObjectMaps()


def CopyMapObject(map_object_id, src_wsd, dry_run=False):
    srcMappingObject = MappingCacheObject.get(src_wsd)
    if toUUID(map_object_id) not in srcMappingObject.MapObjectSaveData:
        print(f"Error: Map Object {map_object_id} not found")
        return False
    mapObject = copy.deepcopy(srcMappingObject.MapObjectSaveData[toUUID(map_object_id)])
    print(f"Clone MapObject {map_object_id}")
    if not dry_run:
        wsd['MapObjectSaveData']['value']['values'].append(mapObject)
    sub_ids = FindReferenceMapObject(map_object_id, srcMapping=srcMappingObject)
    for sub_id in sub_ids:
        if sub_id == map_object_id:
            continue
        CopyMapObject(sub_id, src_wsd, dry_run)
    # MapObjectConcreteModelInstanceId = mapObject['MapObjectConcreteModelInstanceId']['value']
    # concrete_model_instance_id = mapObject['Model']['value']['RawValue']['value']['concrete_model_instance_id']   > = Referer To mapObject['ConcreteModel']
    for concrete in mapObject['ConcreteModel']['value']['ModuleMap']['value']:
        if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
            print(
                f"Clone MapObject {map_object_id} -> ItemContainer {concrete['value']['RawData']['value']['target_container_id']}")
            if not dry_run:
                CopyItemContainers(parse_item(srcMappingObject.ItemContainerSaveData[
                                                  concrete['value']['RawData']['value']['target_container_id']],
                                              "ItemContainerSaveData"),
                                   concrete['value']['RawData']['value']['target_container_id'])
        if concrete['key'] == "EPalMapObjectConcreteModelModuleType::Workee":
            print(
                f"Clone MapObject {map_object_id} -> WorkSaveSata {concrete['value']['RawData']['value']['target_work_id']}")
            if not dry_run:
                _CopyWorkSaveData(concrete['value']['RawData']['value']['target_work_id'], src_wsd)
    if 'repair_work_id' in mapObject['Model']['value']['RawData']['value'] and \
            mapObject['Model']['value']['RawData']['value'][
                'repair_work_id'] != PalObject.EmptyUUID:
        print(
            f"Clone MapObject {map_object_id} -> repair WorkSaveSata {mapObject['Model']['value']['RawData']['value']['repair_work_id']}")
        if not dry_run:
            _CopyWorkSaveData(mapObject['Model']['value']['RawData']['value']['repair_work_id'], src_wsd)
    owner_spawner_level_object_instance_id = mapObject['Model']['value']['RawData']['value'][
        'owner_spawner_level_object_instance_id']
    if owner_spawner_level_object_instance_id in srcMappingObject.MapObjectSpawnerInStageSaveData:
        mapObjSpawner = copy.deepcopy(
            parse_item(srcMappingObject.MapObjectSpawnerInStageSaveData[owner_spawner_level_object_instance_id],
                       "MapObjectSpawnerInStageSaveData.Value"))
        print(
            f"Clone MapObjectSpawnerInStageSaveData {owner_spawner_level_object_instance_id}  Map Object {map_object_id}")
        if not dry_run:
            wsd['MapObjectSpawnerInStageSaveData']['value'][0]['value']['SpawnerDataMapByLevelObjectInstanceId'][
                'value'].append(mapObjSpawner)

    return True


def DeleteMapObject(map_object_id):
    load_skipped_decode(wsd, ['MapObjectSpawnerInStageSaveData'], False)
    if toUUID(map_object_id) not in MappingCache.MapObjectSaveData:
        print(f"Error: Map Object {map_object_id} not found")
        return False
    mapObject = MappingCache.MapObjectSaveData[toUUID(map_object_id)]
    try:
        print(f"Delete MapObjectSaveData {map_object_id}")
        wsd['MapObjectSaveData']['value']['values'].remove(mapObject)
    except ValueError:
        return False
    sub_ids = FindReferenceMapObject(map_object_id)
    for sub_id in sub_ids:
        if sub_id == map_object_id:
            continue
        DeleteMapObject(sub_id)
    # MapObjectConcreteModelInstanceId = mapObject['MapObjectConcreteModelInstanceId']['value']
    # concrete_model_instance_id = mapObject['Model']['value']['RawValue']['value']['concrete_model_instance_id']   > = Referer To mapObject['ConcreteModel']
    for concrete in mapObject['ConcreteModel']['value']['ModuleMap']['value']:
        if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
            DeleteItemContainer(concrete['value']['RawData']['value']['target_container_id'])
        if concrete['key'] == "EPalMapObjectConcreteModelModuleType::Workee":
            _DeleteWorkSaveData(concrete['value']['RawData']['value']['target_work_id'])
    if 'repair_work_id' in mapObject['Model']['value']['RawData']['value'] and \
            mapObject['Model']['value']['RawData']['value'][
                'repair_work_id'] != PalObject.EmptyUUID:
        _DeleteWorkSaveData(mapObject['Model']['value']['RawData']['value']['repair_work_id'])
    owner_spawner_level_object_instance_id = mapObject['Model']['value']['RawData']['value'][
        'owner_spawner_level_object_instance_id']
    if owner_spawner_level_object_instance_id in MappingCache.MapObjectSpawnerInStageSaveData:
        mapObjSpawner = parse_item(MappingCache.MapObjectSpawnerInStageSaveData[owner_spawner_level_object_instance_id],
                                   "MapObjectSpawnerInStageSaveData.Value")
        print(
            f"  Delete MapObjectSpawnerInStageSaveData {owner_spawner_level_object_instance_id}  Map Object {map_object_id}")
        wsd['MapObjectSpawnerInStageSaveData']['value'][0]['value']['SpawnerDataMapByLevelObjectInstanceId'][
            'value'].remove(mapObjSpawner)

    return True


def CopyCharacter(characterId, src_wsd, target_container=None, dry_run=False):
    srcMappingCache = MappingCacheObject.get(src_wsd)
    characterId = toUUID(characterId)
    if characterId not in srcMappingCache.CharacterSaveParameterMap:
        print(f"Error: Character {characterId} not found")
        return False

    if target_container is not None:
        if toUUID(target_container) not in MappingCache.CharacterContainerSaveData:
            print(f"Error: character container {target_container} not found")
            return False
    character = copy.deepcopy(srcMappingCache.CharacterSaveParameterMap[characterId])
    characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']

    origEqualItemContainerId = None
    origItemContainerId = None

    if id(wsd) == id(src_wsd):
        character['key']['InstanceId']['value'] = toUUID(uuid.uuid4())
        print(
            f"Clone Character {tcl(32)}{characterId}{tcl(0)} -> {tcl(32)}{str(character['key']['InstanceId']['value'])}{tcl(0)}")
        if 'EquipItemContainerId' in characterData:
            origEqualItemContainerId = characterData['EquipItemContainerId']['value']['ID']['value']
            characterData['EquipItemContainerId']['value']['ID']['value'] = toUUID(uuid.uuid4())
        if 'ItemContainerId' in characterData:
            origItemContainerId = characterData['ItemContainerId']['value']['ID']['value']
            characterData['ItemContainerId']['value']['ID']['value'] = toUUID(uuid.uuid4())

    if 'EquipItemContainerId' in characterData and not dry_run:
        if origEqualItemContainerId is None:
            origEqualItemContainerId = characterData['EquipItemContainerId']['value']['ID']['value']
        if origEqualItemContainerId in srcMappingCache.ItemContainerSaveData:
            CopyItemContainers(srcMappingCache.ItemContainerSaveData[origEqualItemContainerId],
                               characterData['EquipItemContainerId']['value']['ID']['value'])
    if 'ItemContainerId' in characterData and not dry_run:
        if origItemContainerId is None:
            origItemContainerId = characterData['ItemContainerId']['value']['ID']['value']
        if origItemContainerId in srcMappingCache.ItemContainerSaveData:
            CopyItemContainers(srcMappingCache.ItemContainerSaveData[origItemContainerId],
                               characterData['ItemContainerId']['value']['ID']['value'])

    if 'group_id' in character['value']['RawData']['value']:
        try:
            group = MappingCache.GroupSaveDataMap[character['value']['RawData']['value']['group_id']]
            if not dry_run:
                group['value']['RawData']['value']['individual_character_handle_ids'].append({
                    'guid': PalObject.EmptyUUID,
                    "instance_id": characterId
                })
        except KeyError:
            pass

    if target_container is not None:
        characterContainerId = target_container
    elif 'SlotID' in characterData:
        characterContainerId = characterData['SlotID']['value']['ContainerId']['value']['ID']['value']

    if characterContainerId in MappingCache.CharacterContainerSaveData:
        characterContainer = parse_item(MappingCache.CharacterContainerSaveData[characterContainerId],
                                        "CharacterContainerSaveData")
        isFound = None
        for _slotIndex, slotItem in enumerate(characterContainer['value']['Slots']['value']['values']):
            if slotItem['RawData']['value']['instance_id'] == character['key']['InstanceId']['value']:
                isFound = _slotIndex
                break
        if isFound is None:
            for _slotIndex, slotItem in enumerate(characterContainer['value']['Slots']['value']['values']):
                if slotItem['RawData']['value']['instance_id'] == PalObject.EmptyUUID:
                    slotItem['RawData']['value']['instance_id'] = character['key']['InstanceId']['value']
                    isFound = _slotIndex
                    break
            if isFound is None:
                raise ValueError("No empty slot for the target container")

        slotIndex = isFound
        characterData['SlotID'] = PalObject.PalCharacterSlotId(characterContainerId, slotIndex)
        print(f"Set character {characterId} -> Container {characterContainerId} SlotIndex {slotIndex}")
    try:
        wsd['CharacterSaveParameterMap']['value'].append(character)
        MappingCache.LoadCharacterSaveParameterMap()
    except ValueError:
        return False
    return character['key']['InstanceId']['value']


def DeleteCharacter(characterId, isBatch=False):
    characterId = toUUID(characterId)
    if characterId not in MappingCache.CharacterSaveParameterMap:
        print(f"Error: Character {characterId} not found")
        return False
    character = MappingCache.CharacterSaveParameterMap[characterId]
    characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
    if 'EquipItemContainerId' in characterData:
        DeleteItemContainer(characterData['EquipItemContainerId']['value']['ID']['value'])
    if 'ItemContainerId' in characterData:
        DeleteItemContainer(characterData['ItemContainerId']['value']['ID']['value'])

    if 'group_id' in character['value']['RawData']['value']:
        try:
            group = MappingCache.GroupSaveDataMap[character['value']['RawData']['value']['group_id']]
            for idx, ind in enumerate(group['value']['RawData']['value']['individual_character_handle_ids']):
                if ind['instance_id'] == characterId:
                    print(
                        f"  Delete Chracater {characterId} group {character['value']['RawData']['value']['group_id']} instances")
                    del group['value']['RawData']['value']['individual_character_handle_ids'][idx]
                    break
        except KeyError:
            pass

    if 'SlotID' in characterData:
        try:
            characterContainer = parse_item(MappingCache.CharacterContainerSaveData[
                                                characterData['SlotID']['value']['ContainerId']['value']['ID'][
                                                    'value']], "CharacterContainerSaveData")
            for slotItem in characterContainer['value']['Slots']['value']['values']:
                if slotItem['RawData']['value']['instance_id'] == characterId:
                    slotItem['PermissionTribeID']['value']['value'] = "EPalTribeID::None"
                    slotItem['RawData']['value']['instance_id'] = PalObject.EmptyUUID
                    print(
                        f"  Delete Character {characterId} from CharacterContainer {characterData['SlotID']['value']['ContainerId']['value']['ID']['value']}")
                    break
        except KeyError:
            pass
    try:
        wsd['CharacterSaveParameterMap']['value'].remove(character)
    except ValueError:
        return False
    if not isBatch:
        MappingCache.LoadItemContainerMaps()
        MappingCache.LoadCharacterSaveParameterMap()
    return True


def BatchDeleteCharacter(characterIds):
    deleteItemContainers = []
    characterIds = [toUUID(characterId) for characterId in characterIds]
    for characterId in characterIds:
        if characterId not in MappingCache.CharacterSaveParameterMap:
            print(f"Error: Character {characterId} not found")
            continue

        character = MappingCache.CharacterSaveParameterMap[characterId]
        characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
        if 'EquipItemContainerId' in characterData:
            deleteItemContainers.append(characterData['EquipItemContainerId']['value']['ID']['value'])
        if 'ItemContainerId' in characterData:
            deleteItemContainers.append(characterData['ItemContainerId']['value']['ID']['value'])

        if 'group_id' in character['value']['RawData']['value']:
            try:
                group = MappingCache.GroupSaveDataMap[character['value']['RawData']['value']['group_id']]
                new_individual_character_handle_ids = []
                for idx, ind in enumerate(group['value']['RawData']['value']['individual_character_handle_ids']):
                    if ind['instance_id'] not in characterIds:
                        new_individual_character_handle_ids.append(ind)
                group['value']['RawData']['value'][
                    'individual_character_handle_ids'] = new_individual_character_handle_ids
            except KeyError:
                pass

        if 'SlotID' in characterData:
            try:
                characterContainer = parse_item(MappingCache.CharacterContainerSaveData[
                                                    characterData['SlotID']['value']['ContainerId']['value']['ID'][
                                                        'value']],
                                                "CharacterContainerSaveData")
                for slotItem in characterContainer['value']['Slots']['value']['values']:
                    if slotItem['RawData']['value']['instance_id'] in characterIds:
                        slotItem['PermissionTribeID']['value']['value'] = "EPalTribeID::None"
                        slotItem['RawData']['value']['instance_id'] = PalObject.EmptyUUID
            except KeyError:
                pass
        del MappingCache.CharacterSaveParameterMap[characterId]

    wsd['CharacterSaveParameterMap']['value'] = [MappingCache.CharacterSaveParameterMap[characterId] for characterId in
                                                 MappingCache.CharacterSaveParameterMap]
    print(f"Deleted characters: {len(characterIds)}")
    MappingCache.LoadCharacterSaveParameterMap()
    BatchDeleteItemContainer(deleteItemContainers)
    return True


def GetReferencedCharacterContainerIdsByPlayer(player_uid):
    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print(
            f"{tcl(33)}Warning: Player Sav file for {player_uid} Not exists: %s{tcl(0)}" % player_sav_file)
        return []
    player_container_ids = []
    for key in ['OtomoCharacterContainerId', 'PalStorageContainerId']:
        player_container_ids.append(player_gvas[key]['value']['ID']['value'])
    return player_container_ids


def FindReferenceCharacterContainerIds(with_character=True):
    reference_ids = set()
    for basecamp_id in MappingCache.BaseCampMapping:
        basecamp = MappingCache.BaseCampMapping[basecamp_id]['value']
        if 'WorkerDirector' in basecamp:
            reference_ids.add(basecamp['WorkerDirector']['value']['RawData']['value']['container_id'])

    if with_character:
        for character in wsd['CharacterSaveParameterMap']['value']:
            characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
            if 'SlotID' in characterData:
                reference_ids.add(characterData['SlotID']['value']['ContainerId']['value']['ID']['value'])

    for basecamp in wsd['BaseCampSaveData']['value']:
        for BaseCampModule in basecamp['value']['ModuleMap']['value']:
            if BaseCampModule['key'] == "EPalBaseCampModuleType::TransportItemDirector":
                reference_ids.update(BaseCampModule['value']['RawData']['value']['transport_item_character_infos'])

    for playerUId in MappingCache.PlayerIdMapping:
        reference_ids.update(GetReferencedCharacterContainerIdsByPlayer(playerUId))

    return reference_ids


def FindAllUnreferencedCharacterContainerIds():
    referencedContainerIds = set(FindReferenceCharacterContainerIds())
    allContainerIds = set(MappingCache.CharacterContainerSaveData.keys())
    return list(allContainerIds - referencedContainerIds)


def BatchDeleteUnreferencedCharacterContainers():
    unreferencedContainerIds = FindAllUnreferencedCharacterContainerIds()
    print(f"Delete Non-Referenced Character Containers: {len(unreferencedContainerIds)}")
    BatchDeleteCharacterContainer(unreferencedContainerIds)


def BatchDeleteCharacterContainer(characterContainerIds):
    deleteCharacterContainerIds = []
    for characterContainerId in characterContainerIds:
        characterContainerId = toUUID(characterContainerId)
        if characterContainerId not in MappingCache.CharacterContainerSaveData:
            print(f"Error: Item Container {characterContainerId} not found")
            continue

        deleteCharacterContainerIds.append(characterContainerId)
        if len(deleteCharacterContainerIds) % 10000 == 0:
            print(f"Deleting Character Containers: {len(deleteCharacterContainerIds)} / {len(characterContainerIds)}")
        container = parse_item(MappingCache.CharacterContainerSaveData[characterContainerId],
                               "CharacterContainerSaveData")
        del MappingCache.CharacterContainerSaveData[characterContainerId]

    wsd['CharacterContainerSaveData']['value'] = []
    for container_id in MappingCache.CharacterContainerSaveData:
        wsd['CharacterContainerSaveData']['value'].append(MappingCache.CharacterContainerSaveData[container_id])
    print(f"Delete Character Containers: {len(deleteCharacterContainerIds)} / {len(characterContainerIds)}")
    MappingCache.LoadCharacterContainerMaps()


def FindReferenceItemContainerIds():
    load_skipped_decode(wsd, ['MapObjectSaveData'], False)
    reference_ids = set()

    for mapObject in wsd['MapObjectSaveData']['value']['values']:
        for concrete in mapObject['ConcreteModel']['value']['ModuleMap']['value']:
            if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
                reference_ids.add(concrete['value']['RawData']['value']['target_container_id'])

    for character in wsd['CharacterSaveParameterMap']['value']:
        characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
        if 'EquipItemContainerId' in characterData:
            reference_ids.add(characterData['EquipItemContainerId']['value']['ID']['value'])
        if 'ItemContainerId' in characterData:
            reference_ids.add(characterData['ItemContainerId']['value']['ID']['value'])
    for basecamp in wsd['BaseCampSaveData']['value']:
        for BaseCampModule in basecamp['value']['ModuleMap']['value']:
            if BaseCampModule['key'] == "EPalBaseCampModuleType::ItemStorages":
                pass

    #     reference_ids.append(baseCamp['value']['WorkerDirector']['value']['RawData']['value']['container_id'])
    for uuid in MappingCache.ItemContainerSaveData:
        containers = MappingCache.ItemContainerSaveData[uuid]
        belongInfo = parse_item(containers['value']['BelongInfo'], "ItemContainerSaveData.Value.BelongInfo")
        if 'GroupID' in belongInfo['value'] and belongInfo['value']['GroupID']['value'] != PalObject.EmptyUUID and \
                belongInfo['value']['GroupID']['value'] in MappingCache.GroupSaveDataMap:
            reference_ids.add(uuid)

    for playerId in MappingCache.PlayerIdMapping:
        reference_ids.update(GetReferencedItemContainerIdsByPlayer(playerId))

    return list(reference_ids)


def CharacterDescription(character):
    characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']

    nickname = None
    try:
        if 'NickName' in characterData:
            characterData['NickName']['value'].encode('utf-8')
            nickname = f"{tcl(33)}{characterData['NickName']['value']}{tcl(0)}"
    except UnicodeEncodeError:
        nickname = f"{tcl(31)}***DECODE FAILED***{tcl(0)}"

    if 'IsPlayer' in characterData:
        return f"Player %s%s" % (
            nickname if 'NickName' in characterData else f"{tcl(31)}Invalid{tcl(0)}",
            f" (LV {characterData['Level']['value']})" if 'Level' in characterData else "")
    else:
        return f"Pal %s Own {tcl(32)}%s{tcl(0)}%s" % (
            characterData['CharacterID']['value'] if 'CharacterID' in characterData else "Invalid",
            characterData['OwnerPlayerUId']['value'],
            f" Name: {nickname})" if 'NickName' in characterData else "")


def CleanupCharacterContainer(container_id):
    container_id = toUUID(container_id)
    if container_id not in MappingCache.CharacterContainerSaveData:
        raise IndexError(f"Character Container {container_id} not exists")
    container = parse_item(MappingCache.CharacterContainerSaveData[container_id], "CharacterContainerSaveData")
    new_containerSlots = []
    characterSlotIndexMapping = {}
    containerSlots = container['value']['Slots']['value']['values']
    for slot in containerSlots:
        if slot['IndividualId']['value']['InstanceId']['value'] == PalObject.EmptyUUID and \
                slot['IndividualId']['value']['PlayerUId']['value'] == PalObject.EmptyUUID and \
                slot['PermissionTribeID']['value']['value'] in ["None", "EPalTribeID::None",
                                                                "EPalTribeID::FireKirin"] and \
                slot['RawData']['value']['instance_id'] == PalObject.EmptyUUID:
            continue
        if slot['RawData']['value']['instance_id'] != PalObject.EmptyUUID:
            if slot['RawData']['value']['instance_id'] not in MappingCache.CharacterSaveParameterMap:
                print(
                    f"{tcl(31)}Error: character container {tcl(32)}{container_id}{tcl(31)} -> invalid character {tcl(32)}{slot['RawData']['value']['instance_id']}{tcl(0)}")
                continue
            characterSlotIndexMapping[slot['RawData']['value']['instance_id']] = len(new_containerSlots)
        new_containerSlots.append(slot)
    if len(container['value']['Slots']['value']['values']) != len(new_containerSlots):
        print(
            f"Clenaup Character Container {tcl(32)}{container_id}{tcl(0)}: {len(container['value']['Slots']['value']['values'])} -> {len(new_containerSlots)}")
    for instanceId in characterSlotIndexMapping:
        characterData = \
            MappingCache.CharacterSaveParameterMap[instanceId]['value']['RawData']['value']['object']['SaveParameter'][
                'value']
        characterData['SlotID'] = PalObject.PalCharacterSlotId(container_id,
                                                               characterSlotIndexMapping[instanceId])
    container['value']['Slots']['value']['values'] = new_containerSlots


def CleanupAllCharacterContainer():
    load_skipped_decode(wsd, ['CharacterContainerSaveData'])
    for container_id in MappingCache.CharacterContainerSaveData:
        CleanupCharacterContainer(container_id)


def DeleteFoliageGridItem(map_id):
    foliage = MappingCache.FoliageGridSaveDataMap[map_id]


def FindDamageRefContainer(dry_run=False):
    load_skipped_decode(wsd, ['ItemContainerSaveData', 'CharacterContainerSaveData', 'MapObjectSaveData',
                              'WorkSaveData', 'MapObjectSpawnerInStageSaveData'], False)
    InvalidObjects = {
        "MapObject": set(),
        "BaseCamp": set(),
        "WorkData": set(),
        "MapObjectSpawnerInStage": set(),
        "FoliageGrid": set(),
        'Character': {
            "SaveContainers": [],
            "Owner": [],
            "CharacterContainer": [],
            "EquipItemContainerId": [],
            "ItemContainerId": []
        }
    }

    for playerId in MappingCache.PlayerIdMapping:
        container_ids = GetReferencedItemContainerIdsByPlayer(playerId)
        if container_ids == []:
            print(f"%s {playerId} -> SaveContainers Cannot Get" % CharacterDescription(
                MappingCache.PlayerIdMapping[playerId]))
            InvalidObjects['Character']['SaveContainers'].append(
                MappingCache.PlayerIdMapping[playerId]['key']['PlayerUId']['value'])
        for containerId in container_ids:
            if containerId not in MappingCache.ItemContainerSaveData:
                InvalidObjects['Character']['SaveContainers'].append(
                    MappingCache.PlayerIdMapping[playerId]['key']['PlayerUId']['value'])
                print(f"%s {playerId} -> SaveContainers {containerId} Invalid" % CharacterDescription(
                    MappingCache.PlayerIdMapping[playerId]))
                break

    for basecamp_id in MappingCache.BaseCampMapping:
        baseCamp = MappingCache.BaseCampMapping[basecamp_id]
        group_id = baseCamp['value']['RawData']['value']['group_id_belong_to']
        if group_id not in MappingCache.GuildSaveDataMap:
            print(
                f"BaseCamp {tcl(33)}{basecamp_id}{tcl(0)} {tcl(32)}%s{tcl(0)} -> {tcl(33)}{group_id}{tcl(0)} invalid" %
                baseCamp['value']['RawData']['value']['name'])
            InvalidObjects['BaseCamp'].add(basecamp_id)
        remove_work_ids = set()
        for work_id in baseCamp['value']['WorkCollection']['value']['RawData']['value']['work_ids']:
            if work_id not in MappingCache.WorkSaveData:
                remove_work_ids.add(work_id)
                print(
                    f"BaseCamp {tcl(33)}{basecamp_id}{tcl(0)} {tcl(32)}%s{tcl(0)} -> Work {tcl(33)}{work_id}{tcl(0)} invalid" %
                    baseCamp['value']['RawData']['value']['name'])
        if not dry_run:
            for work_id in remove_work_ids:
                baseCamp['value']['WorkCollection']['value']['RawData']['value']['work_ids'].remove(work_id)

    for work_id in MappingCache.WorkSaveData:
        work = MappingCache.WorkSaveData[work_id]
        basecamp_id = work["RawData"]["value"]["base_camp_id_belong_to"]
        if basecamp_id == PalObject.EmptyUUID:
            continue
        if basecamp_id not in MappingCache.BaseCampMapping:
            print(f"Work {tcl(33)}{work_id}{tcl(0)}  -> Basecamp {tcl(33)}{basecamp_id}{tcl(0)} invalid")
            InvalidObjects['WorkData'].add(work_id)

    # for map_id in MappingCache.FoliageGridSaveDataMap:
    #     if map_id not in MappingCache.MapObjectSaveData:
    #         foliage_item = MappingCache.FoliageGridSaveDataMap[map_id]
    #     InvalidObjects['FoliageGrid'].add(map_id)

    for map_id in MappingCache.MapObjectSaveData:
        mapObject = MappingCache.MapObjectSaveData[map_id]
        basecamp_id = mapObject['Model']['value']['RawData']['value']['base_camp_id_belong_to']
        build_player_uid = mapObject['Model']['value']['RawData']['value']['build_player_uid']
        group_id = mapObject['Model']['value']['RawData']['value']['group_id_belong_to']
        repair_work_id = mapObject['Model']['value']['RawData']['value']['repair_work_id']

        for concrete in mapObject['ConcreteModel']['value']['ModuleMap']['value']:
            if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
                if concrete['value']['RawData']['value']['target_container_id'] \
                        not in MappingCache.ItemContainerSaveData:
                    InvalidObjects['MapObject'].add(mapObject['MapObjectInstanceId']['value'])
                    print(f"MapObject {mapObject['MapObjectInstanceId']['value']} -> ItemContainer "
                          f"{concrete['value']['RawData']['value']['target_container_id']} Invalid")
            if concrete['key'] == "EPalMapObjectConcreteModelModuleType::Workee":
                work_id = concrete['value']['RawData']['value']['target_work_id']
                if work_id != PalObject.EmptyUUID and work_id not in MappingCache.WorkSaveData:
                    print(f"MapObject {tcl(33)}{map_id}{tcl(0)}  -> Workee {tcl(33)}{work_id}{tcl(0)} invalid")
                    InvalidObjects['MapObject'].add(map_id)
        if basecamp_id != PalObject.EmptyUUID and basecamp_id not in MappingCache.BaseCampMapping:
            print(f"MapObject {tcl(33)}{map_id}{tcl(0)}  -> Basecamp {tcl(33)}{basecamp_id}{tcl(0)} invalid")
            InvalidObjects['MapObject'].add(map_id)
        if build_player_uid != PalObject.EmptyUUID and build_player_uid not in MappingCache.PlayerIdMapping:
            print(f"MapObject {tcl(33)}{map_id}{tcl(0)}  -> Build Player {tcl(33)}{build_player_uid}{tcl(0)} invalid")
            InvalidObjects['MapObject'].add(map_id)
        if group_id != PalObject.EmptyUUID and group_id not in MappingCache.GuildSaveDataMap:
            print(f"MapObject {tcl(33)}{map_id}{tcl(0)}  -> Group {tcl(33)}{group_id}{tcl(0)} invalid")
            InvalidObjects['MapObject'].add(map_id)
        if repair_work_id != PalObject.EmptyUUID and repair_work_id not in MappingCache.WorkSaveData:
            print(f"MapObject {tcl(33)}{map_id}{tcl(0)}  -> Repair Work {tcl(33)}{repair_work_id}{tcl(0)} invalid")
            InvalidObjects['MapObject'].add(map_id)

    for spawn_id in MappingCache.MapObjectSpawnerInStageSaveData:
        spawn_obj = MappingCache.MapObjectSpawnerInStageSaveData[spawn_id]
        for spawn_item in spawn_obj['value']['ItemMap']['value']:
            map_id = spawn_item['value']['MapObjectInstanceId']['value']
            if map_id != PalObject.EmptyUUID and map_id not in MappingCache.MapObjectSaveData:
                print(f"MapObjectSpawnerInStage {tcl(33)}{spawn_id}{tcl(0)}  -> Map {tcl(33)}{map_id}{tcl(0)} invalid")
                InvalidObjects['MapObjectSpawnerInStage'].add(spawn_id)

    for character in wsd['CharacterSaveParameterMap']['value']:
        characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
        # Ignored for Boss, Boss will have empty EquipItemContainerId but work
        if 'OwnerPlayerUId' in characterData and characterData['OwnerPlayerUId'][
            'value'] not in MappingCache.PlayerIdMapping:
            print(
                f"{tcl(31)}Invalid item on CharacterSaveParameterMap{tcl(0)}  UUID: %s  Owner: %s  CharacterID: %s" % (
                    str(character['key']['InstanceId']['value']), str(characterData['OwnerPlayerUId']['value']),
                    characterData['CharacterID']['value']))
            InvalidObjects['Character']['Owner'].append(character['key']['InstanceId']['value'])
        if 'SlotID' in characterData and not characterData['SlotID']['value']['ContainerId']['value']['ID'][
                                                 'value'] in MappingCache.CharacterContainerSaveData:
            print(
                f"{tcl(31)}Invalid Character Container{tcl(0)} {characterData['SlotID']['value']['ContainerId']['value']['ID']['value']}  UUID: %s  Owner: %s  CharacterID: %s" % (
                    str(character['key']['InstanceId']['value']), str(characterData['OwnerPlayerUId']['value']),
                    characterData['CharacterID']['value']))
            InvalidObjects['Character']['CharacterContainer'].append(character['key']['InstanceId']['value'])
        if 'EquipItemContainerId' in characterData:
            if characterData['EquipItemContainerId']['value']['ID']['value'] not in MappingCache.ItemContainerSaveData:
                InvalidObjects['Character']['EquipItemContainerId'].append(character['key']['InstanceId']['value'])
                print(
                    f"%-60s {character['key']['InstanceId']['value']} -> EqualItemContainerID {characterData['EquipItemContainerId']['value']['ID']['value']} Invalid" %
                    CharacterDescription(character))
        if 'ItemContainerId' in characterData:
            if characterData['ItemContainerId']['value']['ID']['value'] not in MappingCache.ItemContainerSaveData:
                InvalidObjects['Character']['ItemContainerId'].append(character['key']['InstanceId']['value'])
                print(
                    f"%-60s {character['key']['InstanceId']['value']} -> ItemContainerId {characterData['ItemContainerId']['value']['ID']['value']} Invalid" % CharacterDescription(
                        character))

    return InvalidObjects


def FixBrokenDamageRefContainer(withInvalidEqualItemContainer=False, withInvalidItemContainer=False):
    BrokenObjects = FindDamageRefContainer()
    for basecamp_id in BrokenObjects['BaseCamp']:
        DeleteBaseCamp(basecamp_id)
    _BatchDeleteWorkSaveData(BrokenObjects['WorkData'])
    if withInvalidEqualItemContainer:
        BatchDeleteCharacter(BrokenObjects['Character']['EquipItemContainerId'])
    if withInvalidItemContainer:
        BatchDeleteCharacter(BrokenObjects['Character']['ItemContainerId'])
    for characterId in BrokenObjects['Character']['SaveContainers']:
        DeletePlayer(characterId)
    delete_sets = set(BrokenObjects['Character']['Owner'])
    delete_sets.update(BrokenObjects['Character']['CharacterContainer'])
    BatchDeleteCharacter(delete_sets)

    for objId in BrokenObjects['MapObjectSpawnerInStage']:
        del MappingCache.MapObjectSpawnerInStageSaveData[objId]
    wsd['MapObjectSpawnerInStageSaveData']['value'][0]['value']['SpawnerDataMapByLevelObjectInstanceId']['value'] = \
        [MappingCache.MapObjectSpawnerInStageSaveData[x] for x in MappingCache.MapObjectSpawnerInStageSaveData]

    BatchDeleteMapObject(BrokenObjects['MapObject'])
    MappingCache.LoadItemContainerMaps()
    MappingCache.LoadGroupSaveDataMap()
    MappingCache.LoadCharacterSaveParameterMap()
    MappingCache.LoadCharacterContainerMaps()
    MappingCache.LoadMapObjectMaps()


def FixBrokenObject(dry_run=False):
    load_skipped_decode(wsd, ['MapObjectSaveData'], False)
    delete_map_objects = []
    for mapObjectId in MappingCache.MapObjectSaveData:
        map_data = MappingCache.MapObjectSaveData[mapObjectId]
        if map_data['Model']['value']['RawData']['value']['build_player_uid'] == PalObject.EmptyUUID:
            continue
        if map_data['Model']['value']['RawData']['value']['build_player_uid'] not in MappingCache.PlayerIdMapping:
            delete_map_objects.append(map_data['MapObjectInstanceId']['value'])
            print(f"{tcl(31)}Error: Map Object {tcl(93)}{map_data['MapObjectInstanceId']['value']}{tcl(31)} Owner "
                  f"{tcl(93)}{map_data['Model']['value']['RawData']['value']['build_player_uid']}{tcl(31)} Not Exists"
                  f"{tcl(0)}")
    if len(delete_map_objects) > 0 and not dry_run:
        BatchDeleteMapObject(delete_map_objects)
        MappingCache.LoadMapObjectMaps()
    return delete_map_objects


def GetReferencedItemContainerIdsByPlayer(player_uid):
    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print(
            f"{tcl(33)}Warning: Player Sav file for {player_uid} Not exists: %s{tcl(0)}" % player_sav_file)
        return []
    player_container_ids = []
    # for key in ['OtomoCharacterContainerId', 'PalStorageContainerId']:
    #     player_container_ids.append(player_gvas[key]['value']['ID']['value'])

    for key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
        player_container_ids.append(player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])
    return player_container_ids


def FindAllUnreferencedItemContainerIds():
    referencedContainerIds = set(FindReferenceItemContainerIds())
    allContainerIds = set(MappingCache.ItemContainerSaveData.keys())

    return list(allContainerIds - referencedContainerIds)


def DoubleCheckForUnreferenceItemContainers():
    load_skipped_decode(wsd, ['MapObjectSaveData', 'FoliageGridSaveDataMap', 'MapObjectSpawnerInStageSaveData',
                              'ItemContainerSaveData', 'DynamicItemSaveData', 'CharacterContainerSaveData'])
    unreferencedContainerIds = FindAllUnreferencedItemContainerIds()
    for nRunning, itemContainerId in enumerate(unreferencedContainerIds):
        if nRunning % 1000 == 0:
            print(f"Checking {nRunning} / {len(unreferencedContainerIds)}")
        itemContainerId = toUUID(itemContainerId)
        if itemContainerId not in MappingCache.ItemContainerSaveData:
            print(f"Error: Item Container {itemContainerId} not found")
            continue

        DoubleCheckForDeleteItemContainers(itemContainerId)

    LoadAllUUID()
    for id in unreferencedContainerIds:
        if id in guid_mapping and len(guid_mapping[id]) > 1:
            print("Error: ID %s:" % id)
            gp(guid_mapping[id])
            print()


def DoubleCheckForUnreferenceCharacterContainers():
    load_skipped_decode(wsd, ['MapObjectSaveData', 'FoliageGridSaveDataMap', 'MapObjectSpawnerInStageSaveData',
                              'ItemContainerSaveData', 'DynamicItemSaveData', 'CharacterContainerSaveData'])
    unreferencedContainerIds = FindAllUnreferencedCharacterContainerIds()
    for nRunning, characterContainerId in enumerate(unreferencedContainerIds):
        if nRunning % 1000 == 0:
            print(f"Checking {nRunning} / {len(unreferencedContainerIds)}")
        if characterContainerId not in MappingCache.CharacterContainerSaveData:
            print(f"Error: Item Container {characterContainerId} not found")
            continue

        DoubleCheckForDeleteCharacterContainers(characterContainerId)

    LoadAllUUID()
    for id in unreferencedContainerIds:
        if id in guid_mapping and len(guid_mapping[id]) > 1:
            print("Error: ID %s:" % id)
            gp(guid_mapping[id])
            print()


def BatchDeleteUnreferencedItemContainers():
    unreferencedContainerIds = FindAllUnreferencedItemContainerIds()
    print(f"Delete Non-Referenced Item Containers: {len(unreferencedContainerIds)}")
    BatchDeleteItemContainer(unreferencedContainerIds)


def BatchDeleteItemContainer(itemContainerIds):
    deleteDynamicIds = []
    deleteItemContainerIds = []
    for itemContainerId in itemContainerIds:
        itemContainerId = toUUID(itemContainerId)
        if itemContainerId not in MappingCache.ItemContainerSaveData:
            print(f"Error: Item Container {itemContainerId} not found")
            continue

        deleteItemContainerIds.append(itemContainerId)
        if len(deleteItemContainerIds) % 10000 == 0:
            print(f"Deleting Item Containers: {len(deleteItemContainerIds)} / {len(itemContainerIds)}")
        container = parse_item(MappingCache.ItemContainerSaveData[itemContainerId], "ItemContainerSaveData")
        containerSlots = container['value']['Slots']['value']['values']
        for slotItem in containerSlots:
            dynamicItemId = slotItem['ItemId']['value']['DynamicId']['value']['LocalIdInCreatedWorld']['value']
            if dynamicItemId == PalObject.EmptyUUID:
                continue
            if dynamicItemId not in MappingCache.DynamicItemSaveData:
                print(
                    f"{tcl(31)}  Error missed DynamicItemContainer UUID [{tcl(33)} {str(dynamicItemId)}{tcl(0)}]  Item {tcl(32)} {slotItem['ItemId']['value']['StaticId']['value']} {tcl(0)}")
                continue
            del MappingCache.DynamicItemSaveData[dynamicItemId]
            deleteDynamicIds.append(dynamicItemId)

        del MappingCache.ItemContainerSaveData[itemContainerId]

    wsd['ItemContainerSaveData']['value'] = []
    for container_id in MappingCache.ItemContainerSaveData:
        wsd['ItemContainerSaveData']['value'].append(MappingCache.ItemContainerSaveData[container_id])
    wsd['DynamicItemSaveData']['value']['values'] = []
    for dynamicItemId in MappingCache.DynamicItemSaveData:
        wsd['DynamicItemSaveData']['value']['values'].append(MappingCache.DynamicItemSaveData[dynamicItemId])
    print(f"Delete Dynamic Containers: {len(deleteDynamicIds)}")
    print(f"Delete Item Containers: {len(deleteItemContainerIds)} / {len(itemContainerIds)}")
    MappingCache.LoadItemContainerMaps()


def DeleteItemContainer(itemContainerId, isBatch=False):
    itemContainerId = toUUID(itemContainerId)
    if itemContainerId not in MappingCache.ItemContainerSaveData:
        print(f"Error: Item Container {itemContainerId} not found")
        return False

    container = parse_item(MappingCache.ItemContainerSaveData[itemContainerId], "ItemContainerSaveData")
    containerSlots = container['value']['Slots']['value']['values']
    for slotItem in containerSlots:
        dynamicItemId = slotItem['ItemId']['value']['DynamicId']['value']['LocalIdInCreatedWorld']['value']
        if dynamicItemId == PalObject.EmptyUUID:
            continue
        if dynamicItemId not in MappingCache.DynamicItemSaveData:
            print(
                f"{tcl(31)}  Error missed DynamicItemContainer UUID [{tcl(33)} {str(dynamicItemId)}{tcl(0)}]  Item {tcl(32)} {slotItem['ItemId']['value']['StaticId']['value']} {tcl(0)}")
            continue
        print(f"  Delete DynamicItemId {dynamicItemId}")
        try:
            wsd['DynamicItemSaveData']['value']['values'].remove(MappingCache.DynamicItemSaveData[dynamicItemId])
        except ValueError:
            pass

    try:
        wsd['ItemContainerSaveData']['value'].remove(container)
    except ValueError:
        pass
    if not isBatch:
        MappingCache.LoadItemContainerMaps()


def DeletePlayer(player_uid, InstanceId=None, dry_run=False):
    load_skipped_decode(wsd, ['ItemContainerSaveData', 'CharacterContainerSaveData', 'MapObjectSaveData',
                              'MapObjectSpawnerInStageSaveData', 'DynamicItemSaveData'], False)
    if isinstance(player_uid, int):
        player_uid = str(uuid.UUID("%08x-0000-0000-0000-000000000000" % player_uid))

    player_uid = toUUID(player_uid)
    player_container_ids = []
    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print(f"{tcl(33)}Warning: Player Sav file Not exists: %s{tcl(0)}" % player_sav_file)
    else:
        print(f"{tcl(32)}Batch delete by containers{tcl(0)}")
        if InstanceId is None:
            print("Player Container ID:")
            player_gvas = player_gvas_file.properties['SaveData']['value']
            for key in ['OtomoCharacterContainerId', 'PalStorageContainerId']:
                print("  %s" % player_gvas[key]['value']['ID']['value'])

                print(f"{tcl(31)}Delete Character Container{tcl(0)}  UUID: %s" % (
                    str(player_gvas[key]['value']['ID']['value'])))
                if not dry_run:
                    DeleteCharacterContainer(player_gvas[key]['value']['ID']['value'])
                    print()
                player_container_ids.append(player_gvas[key]['value']['ID']['value'])
            for key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                        'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
                print("  %s" % player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])

                print(f"{tcl(31)}Delete Item Container{tcl(0)}  UUID: %s" % (
                    str(player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])))
                if not dry_run:
                    DeleteItemContainer(player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])
                    print()
                player_container_ids.append(player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])
    # Remove item from CharacterSaveParameterMap
    deleteCharacters = []
    print(f"{tcl(32)}Scan for remain item in CharacterSaveParameterMap{tcl(0)}")
    for item in wsd['CharacterSaveParameterMap']['value']:
        player = item['value']['RawData']['value']['object']['SaveParameter']['value']
        if item['key']['PlayerUId']['value'] == player_uid \
                and 'IsPlayer' in player and player['IsPlayer']['value'] \
                and (InstanceId is None or item['key']['InstanceId']['value'] == toUUID(InstanceId)):
            print(
                f"{tcl(31)}Delete User{tcl(0)}  UUID: %s  %s" % (
                    str(item['key']['InstanceId']['value']),
                    CharacterDescription(item)))
            if not dry_run:
                deleteCharacters.append(item['key']['InstanceId']['value'])
        elif 'OwnerPlayerUId' in player and str(player['OwnerPlayerUId']['value']) == player_uid and InstanceId is None:
            print(
                f"{tcl(31)}Delete Pal{tcl(0)}  UUID: %s  Owner: %s  CharacterID: %s" % (
                    str(item['key']['InstanceId']['value']), str(player['OwnerPlayerUId']['value']),
                    player['CharacterID']['value']))
            if not dry_run:
                deleteCharacters.append(item['key']['InstanceId']['value'])
        elif 'SlotID' in player and player['SlotID']['value']['ContainerId']['value']['ID'][
            'value'] in player_container_ids and InstanceId is None:
            print(
                f"{tcl(31)}Delete Pal{tcl(0)}  UUID: %s  Slot: %s  CharacterID: %s" % (
                    str(item['key']['InstanceId']['value']),
                    str(player['SlotID']['value']['ContainerId']['value']['ID']['value']),
                    player['CharacterID']['value']))
            if not dry_run:
                deleteCharacters.append(item['key']['InstanceId']['value'])
    BatchDeleteCharacter(deleteCharacters)
    print(f"{tcl(32)}Delete from guild{tcl(0)}")
    # Remove Item from GroupSaveDataMap
    remove_guilds = []
    for group_id in MappingCache.GuildSaveDataMap:
        group_data = MappingCache.GuildSaveDataMap[group_id]
        item = group_data['value']['RawData']['value']
        for player in item['players']:
            if player['player_uid'] == player_uid:
                print(
                    f"{tcl(31)}  Delete User {tcl(93)} %s {tcl(0)} from Guild{tcl(0)} {tcl(93)} %s {tcl(0)}   [{tcl(92)}%s{tcl(0)}] Last Online: %d" % (
                        player['player_info']['player_name'],
                        item['guild_name'], str(player['player_uid']),
                        player['player_info']['last_online_real_time']))
                if not dry_run:
                    item['players'].remove(player)
                    if len(item['players']) == 0:
                        remove_guilds.append(item['group_id'])
                break
    if InstanceId is None and len(remove_guilds) > 0:
        print(f"{tcl(32)}Delete guilds{tcl(0)}")
        for guild in remove_guilds:
            DeleteGuild(guild)

    MappingCache.LoadGroupSaveDataMap()
    MappingCache.LoadCharacterSaveParameterMap()
    MappingCache.LoadCharacterContainerMaps()

    delete_map_ids = []
    if InstanceId is None:
        for map_data in wsd['MapObjectSaveData']['value']['values']:
            if map_data['Model']['value']['RawData']['value']['build_player_uid'] == player_uid:
                delete_map_ids.append(map_data['MapObjectInstanceId']['value'])
    if not dry_run:
        BatchDeleteMapObject(delete_map_ids)
    if InstanceId is None:
        backup_file(player_sav_file, True)
        delete_files.append(player_sav_file)
        print("Finish to remove player from Save, please delete this file manually: %s" % player_sav_file)


def search_keys(dicts, key, level=""):
    if isinstance(dicts, dict):
        if key in dicts:
            print("Found at %s['%s']" % (level, key))
        for k in dicts:
            if isinstance(dicts[k], dict) or isinstance(dicts[k], list):
                search_keys(dicts[k], key, level + "['%s']" % k)
    elif isinstance(dicts, list):
        for idx, l in enumerate(dicts):
            if isinstance(l, dict) or isinstance(l, list):
                search_keys(l, key, level + "[%d]" % idx)


def search_guid(dicts, level="", printout=True):
    isFound = {}
    if isinstance(dicts, dict):
        for k in dicts:
            if level == "" and len(list(dicts.keys())) < 100 and printout:
                set_loadingTitle("Searching %s" % k)
            if isinstance(dicts[k], UUID) and dicts[k] != PalObject.EmptyUUID:
                if dicts[k] not in isFound:
                    isFound[dicts[k]] = []
                isFound[dicts[k]].append(f"{level}['{k}']")
                if printout:
                    print("wsd%s['%s'] = '%s'" % (level, k, dicts[k]))
            if isinstance(dicts[k], dict) or isinstance(dicts[k], list):
                rcs = search_guid(dicts[k], level + "['%s']" % k, printout=printout)
                for _uuid in rcs:
                    if _uuid not in isFound:
                        isFound[_uuid] = []
                    isFound[_uuid] += rcs[_uuid]
    elif isinstance(dicts, list):
        for idx, l in enumerate(dicts):
            if level == "" and len(dicts) < 100 and printout:
                set_loadingTitle("Searching %s" % l)
            if isinstance(l, UUID) and l != PalObject.EmptyUUID:
                if l not in isFound:
                    isFound[l] = []
                isFound[l].append(f"{level}[{idx}]")
                if printout:
                    print("wsd%s[%d] = '%s'" % (level, idx, l))
            if isinstance(l, dict) or isinstance(l, list):
                rcs = search_guid(l, level + "[%d]" % idx, printout=printout)
                for _uuid in rcs:
                    if _uuid not in isFound:
                        isFound[_uuid] = []
                    isFound[_uuid] += rcs[_uuid]
    if level == "":
        set_loadingTitle("")
    return isFound


import re


def find_partten(p):
    partten = re.compile(r"\d+")
    return list(set([partten.sub("{NUM}", x) for x in p]))


def search_values(dicts, key, level=""):
    try:
        uuid_match = uuid.UUID(str(key))
    except ValueError:
        uuid_match = None
    isFound = False
    if isinstance(dicts, dict):
        if key in dicts.values():
            print("wsd%s['%s']" % (level, list(dicts.keys())[list(dicts.values()).index(key)]))
            isFound = True
        elif uuid_match is not None and uuid_match in dicts.values():
            print("wsd%s['%s']" % (level, list(dicts.keys())[list(dicts.values()).index(uuid_match)]))
            isFound = True
        for k in dicts:
            if level == "" and len(list(dicts.keys())) < 100:
                set_loadingTitle("Searching %s" % k)
            if isinstance(dicts[k], dict) or isinstance(dicts[k], list):
                isFound |= search_values(dicts[k], key, level + "['%s']" % k)
    elif isinstance(dicts, list):
        if key in dicts:
            print("wsd%s[%d]" % (level, dicts.index(key)))
            isFound = True
        elif uuid_match is not None and uuid_match in dicts:
            print("wsd%s[%d]" % (level, dicts.index(uuid_match)))
            isFound = True
        for idx, l in enumerate(dicts):
            if level == "" and len(dicts) < 100:
                set_loadingTitle("Searching %s" % l)
            if isinstance(l, dict) or isinstance(l, list):
                isFound |= search_values(l, key, level + "[%d]" % idx)
    if level == "":
        set_loadingTitle("")
    return isFound


def dump_enums(dicts, level=""):
    isFound = {}
    if isinstance(dicts, dict):
        if 'type' in dicts and dicts['type'] == "EnumProperty":
            if dicts['value']['type'] not in isFound:
                isFound[dicts['value']['type']] = set()
            isFound[dicts['value']['type']].add(dicts['value']['value'])
        for k in dicts:
            if isinstance(dicts[k], dict) or isinstance(dicts[k], list):
                _dump = dump_enums(dicts[k], level + "['%s']" % k)
                for _type in _dump:
                    if _type in isFound:
                        isFound[_type].update(_dump[_type])
                    else:
                        isFound[_type] = _dump[_type]
    elif isinstance(dicts, list):
        for idx, l in enumerate(dicts):
            if isinstance(l, dict) or isinstance(l, list):
                _dump = dump_enums(l, level + "[%d]" % idx)
                for _type in _dump:
                    if _type in isFound:
                        isFound[_type].update(_dump[_type])
                    else:
                        isFound[_type] = _dump[_type]
    return isFound


def LoadPlayers(data_source=None):
    global wsd, playerMapping
    if data_source is None:
        data_source = wsd

    l_playerMapping = {}
    for item in data_source['CharacterSaveParameterMap']['value']:
        playerStruct = item['value']['RawData']['value']['object']['SaveParameter']
        playerParams = playerStruct['value']
        # if "00000000-0000-0000-0000-000000000000" != str(item['key']['PlayerUId']['value']):
        if 'IsPlayer' in playerParams and playerParams['IsPlayer']['value']:
            if playerStruct['struct_type'] == 'PalIndividualCharacterSaveParameter':
                if 'OwnerPlayerUId' in playerParams:
                    print(
                        f"{tcl(33)}Warning: Corrupted player struct{tcl(0)} UUID {tcl(32)} %s {tcl(0)} Owner {tcl(32)} %s {tcl(0)}" % (
                            str(item['key']['PlayerUId']['value']), str(playerParams['OwnerPlayerUId']['value'])))
                    pp.pprint(playerParams)
                    playerParams['IsPlayer']['value'] = False
                elif 'NickName' in playerParams:
                    try:
                        playerParams['NickName']['value'].encode('utf-8')
                    except UnicodeEncodeError as e:
                        print(
                            f"{tcl(33)}Warning: Corrupted player name{tcl(0)} UUID {tcl(32)} %s {tcl(0)} Player {tcl(32)} %s {tcl(0)}" % (
                                str(item['key']['PlayerUId']['value']), repr(playerParams['NickName']['value'])))
                playerMeta = {}
                for player_k in playerParams:
                    playerMeta[player_k] = playerParams[player_k]['value']
                playerMeta['InstanceId'] = item['key']['InstanceId']['value']
                l_playerMapping[str(item['key']['PlayerUId']['value'])] = playerMeta
    if data_source == wsd:
        playerMapping = l_playerMapping
    return l_playerMapping


def ShowPlayers(data_source=None):
    if data_source is None:
        data_source = wsd
    srcGuildMapping = MappingCacheObject.get(data_source)
    playerMapping = LoadPlayers(data_source)
    for playerUId in playerMapping:
        playerMeta = playerMapping[playerUId]
        try:
            print(
                f"PlayerUId {tcl(32)} %s {tcl(0)} [InstanceID %s %s {tcl(0)}] -> Level %2d  %s" % (
                    playerUId,
                    tcl(33) if toUUID(playerUId) in srcGuildMapping.GuildInstanceMapping and
                               playerMeta['InstanceId'] == srcGuildMapping.GuildInstanceMapping[
                                   toUUID(playerUId)] else tcl(31),
                    playerMeta['InstanceId'],
                    playerMeta['Level'] if 'Level' in playerMeta else -1, playerMeta['NickName']))
        except UnicodeEncodeError as e:
            print(
                f"Corrupted Player Name {tcl(31)} %s {tcl(0)} PlayerUId {tcl(32)} %s {tcl(0)} [InstanceID %s %s {tcl(0)}]" %
                (repr(playerMeta['NickName']), playerUId,
                 tcl(33) if toUUID(playerUId) in srcGuildMapping.GuildInstanceMapping and
                            playerMeta['InstanceId'] ==
                            srcGuildMapping.GuildInstanceMapping[
                                toUUID(playerUId)] else tcl(31),
                 playerMeta['InstanceId']))
        except KeyError:
            print(
                f"PlayerUId {tcl(32)} %s {tcl(0)} [InstanceID %s %s {tcl(0)}] -> Level %2d" % (
                    playerUId,
                    tcl(33) if toUUID(playerUId) in srcGuildMapping.GuildInstanceMapping and
                               playerMeta['InstanceId'] == srcGuildMapping.GuildInstanceMapping[
                                   toUUID(playerUId)] else tcl(31),
                    playerMeta['InstanceId'],
                    playerMeta['Level'] if 'Level' in playerMeta else -1))


def FixDuplicateUser(dry_run=False):
    # Remove Unused in CharacterSaveParameterMap
    removeItems = []
    for item in wsd['CharacterSaveParameterMap']['value']:
        if PalObject.EmptyUUID != item['key']['PlayerUId']['value']:
            player_meta = item['value']['RawData']['value']['object']['SaveParameter']['value']
            if item['key']['PlayerUId']['value'] not in MappingCache.GuildInstanceMapping:
                print(
                    f"{tcl(31)}Invalid player on CharacterSaveParameterMap{tcl(0)}  PlayerUId: %s  InstanceID: %s  %s" % (
                        str(item['key']['PlayerUId']['value']), str(item['key']['InstanceId']['value']),
                        CharacterDescription(item)))
                removeItems.append(item)
            elif item['key']['InstanceId']['value'] != MappingCache.GuildInstanceMapping[
                item['key']['PlayerUId']['value']]:
                print(
                    f"{tcl(31)}Duplicate player on CharacterSaveParameterMap{tcl(0)}  PlayerUId: %s  InstanceID: %s  %s" % (
                        str(item['key']['PlayerUId']['value']), str(item['key']['InstanceId']['value']),
                        CharacterDescription(item)))
                removeItems.append(item)
    if not dry_run:
        for item in removeItems:
            wsd['CharacterSaveParameterMap']['value'].remove(item)
        MappingCache.LoadGuildInstanceMapping()
        MappingCache.LoadCharacterSaveParameterMap()


def TickToHuman(tick):
    seconds = (wsd['GameTimeSaveData']['value']['RealDateTimeTicks']['value'] - tick) / 1e7
    s = ""
    if seconds > 86400:
        s += " %d d" % (seconds // 86400)
        seconds %= 86400
    if seconds > 3600:
        s += " %d h" % (seconds // 3600)
        seconds %= 3600
    if seconds > 60:
        s += " %d m" % (seconds // 60)
        seconds %= 60
    s += " %d s" % seconds
    return s


def TickToLocal(tick):
    ts = filetime + (tick - wsd['GameTimeSaveData']['value']['RealDateTimeTicks']['value']) / 1e7
    t = datetime.datetime.fromtimestamp(ts)
    return t.strftime("%Y-%m-%d %H:%M:%S")


def BindGuildInstanceId(uid, instance_id):
    uid = toUUID(uid)
    instance_id = toUUID(instance_id)
    for group_data in wsd['GroupSaveDataMap']['value']:
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            item = group_data['value']['RawData']['value']
            for ind_char in item['individual_character_handle_ids']:
                if ind_char['guid'] == uid:
                    print("Update Guild %s binding guild UID %s  %s -> %s" % (
                        item['guild_name'], uid, ind_char['instance_id'], instance_id))
                    ind_char['instance_id'] = instance_id
                    MappingCache.GuildInstanceMapping[ind_char['guid']] = ind_char['instance_id']
            print()


def CopyCharacterContainer(containerId, src_wsd, dry_run=False, container_only=False):
    srcMappingCache = MappingCacheObject.get(src_wsd)
    if containerId in srcMappingCache.CharacterContainerSaveData:
        containers = copy.deepcopy(
            parse_item(srcMappingCache.CharacterContainerSaveData[containerId], "CharacterContainerSaveData"))
        if container_only:
            containers['value']['Slots']['value']['values'] = []
        if not dry_run:
            wsd['CharacterContainerSaveData']['value'].append(containers)
    else:
        print(f"Error: Character Container {containerId} not found")
        return []

    try:
        container = parse_item(srcMappingCache.CharacterContainerSaveData[containerId]['value']['Slots'],
                               "CharacterContainerSaveData.Value.Slots")
        containerSlots = container['value']['values']
    except KeyError:
        return
    if not container_only:
        copyItemList = set()
        for slotItem in containerSlots:
            if slotItem['IndividualId']['value']['InstanceId']['value'] != PalObject.EmptyUUID:
                copyItemList.add(slotItem['RawData']['value']['instance_id'])
            if slotItem['RawData']['value']['instance_id'] != PalObject.EmptyUUID:
                copyItemList.add(slotItem['RawData']['value']['instance_id'])
        for characterId in copyItemList:
            CopyCharacter(characterId, src_wsd, dry_run)
    return list(copyItemList)


def DeleteCharacterContainer(containerId, isBatch=False):
    containerId = toUUID(containerId)
    if containerId in MappingCache.CharacterContainerSaveData:
        wsd['CharacterContainerSaveData']['value'].remove(MappingCache.CharacterContainerSaveData[containerId])
    else:
        print(f"Error: Character Container {containerId} not found")
        return []

    try:
        container = parse_item(MappingCache.CharacterContainerSaveData[containerId]['value']['Slots'],
                               "CharacterContainerSaveData.Value.Slots")
        containerSlots = container['value']['values']
    except KeyError:
        return
    removeItemList = set()
    for slotItem in containerSlots:
        if slotItem['IndividualId']['value']['InstanceId']['value'] != PalObject.EmptyUUID:
            removeItemList.add(slotItem['RawData']['value']['instance_id'])
        if slotItem['RawData']['value']['instance_id'] != PalObject.EmptyUUID:
            removeItemList.add(slotItem['RawData']['value']['instance_id'])
    BatchDeleteCharacter(removeItemList)
    if not isBatch:
        MappingCache.LoadCharacterContainerMaps()
    return list(removeItemList)


guid_mapping = None


def LoadAllUUID():
    global guid_mapping
    load_skipped_decode(wsd, ['MapObjectSaveData', 'FoliageGridSaveDataMap', 'MapObjectSpawnerInStageSaveData',
                              'ItemContainerSaveData', 'DynamicItemSaveData', 'CharacterContainerSaveData'])
    if guid_mapping is None:
        print("Loading GUID Mapping")
        guid_mapping = search_guid(wsd, printout=False)
        print("Done")


def DoubleCheckForDeleteItemContainers(itemContainerId, printout=True):
    LoadAllUUID()
    container = parse_item(MappingCache.ItemContainerSaveData[itemContainerId], "ItemContainerSaveData")
    guids = set(search_guid(container, printout=False).keys())
    guids.remove(itemContainerId)
    containerSlots = container['value']['Slots']['value']['values']
    for slotItem in containerSlots:
        dynamicItemId = slotItem['ItemId']['value']['DynamicId']['value']['LocalIdInCreatedWorld']['value']
        if dynamicItemId == PalObject.EmptyUUID:
            continue
        guids.remove(dynamicItemId)
        if dynamicItemId not in MappingCache.DynamicItemSaveData:
            print(
                f"{tcl(31)}  Error missed DynamicItemContainer UUID [{tcl(33)} {str(dynamicItemId)}{tcl(0)}]  Item {tcl(32)} {slotItem['ItemId']['value']['StaticId']['value']} {tcl(0)}")
            continue
        guids.update(search_guid(MappingCache.DynamicItemSaveData[dynamicItemId], printout=False))
        guids.remove(dynamicItemId)
        if dynamicItemId in guid_mapping and len(guid_mapping[dynamicItemId]) > 3:
            print("Error: Dynamic Item ID %s:" % dynamicItemId)
            gp(guid_mapping[dynamicItemId])
    belongInfo = parse_item(container['value']['BelongInfo'], "ItemContainerSaveData.Value.BelongInfo")
    if 'GroupID' in belongInfo['value'] and belongInfo['value']['GroupID']['value'] != PalObject.EmptyUUID:
        guids.remove(belongInfo['value']['GroupID']['value'])
    if len(guids) > 0 and printout:
        print(f"Get Unknow Referer UUID on ItemContainers {itemContainerId}")
        gp(guids)
    return guids


def DoubleCheckForDeleteCharacterContainers(container_ids, printout=True):
    container_guids = set(search_guid(MappingCache.CharacterContainerSaveData[container_ids], printout=False).keys())
    container_guids.remove(container_ids)
    containerSlots = MappingCache.CharacterContainerSaveData[container_ids]['value']['Slots']['value']['values']
    for slotItem in containerSlots:
        if slotItem['IndividualId']['value']['InstanceId']['value'] != PalObject.EmptyUUID:
            container_guids.remove(slotItem['IndividualId']['value']['InstanceId']['value'])
        if slotItem['RawData']['value']['instance_id'] != PalObject.EmptyUUID:
            container_guids.remove(slotItem['RawData']['value']['instance_id'])
    if len(container_guids) > 0 and printout:
        print(f"Get Unknow Referer UUID on CharacterContainer {container_ids}")
        gp(container_guids)
        gp(MappingCache.CharacterContainerSaveData[container_ids])
    return container_guids


def _DoubleCheckForDeleteModel(modelId):
    model = MappingCache.MapObjectSaveData[modelId]
    model_guids = set(search_guid(model, printout=False).keys())
    model_guids.remove(modelId)
    model_guids.remove(model['MapObjectConcreteModelInstanceId']['value'])
    model_guids.remove(model['Model']['value']['RawData']['value']['build_player_uid'])
    model_guids.remove(model['Model']['value']['RawData']['value']['group_id_belong_to'])
    for concrete in model['ConcreteModel']['value']['ModuleMap']['value']:
        if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
            DoubleCheckForDeleteItemContainers(concrete['value']['RawData']['value']['target_container_id'])
            model_guids.remove(concrete['value']['RawData']['value']['target_container_id'])
        if concrete['key'] == "EPalMapObjectConcreteModelModuleType::Workee":
            _DoubleCheckForDeleteWorkSaveData(concrete['value']['RawData']['value']['target_work_id'])
            model_guids.remove(concrete['value']['RawData']['value']['target_work_id'])
    if 'repair_work_id' in model['Model']['value']['RawData']['value'] and \
            model['Model']['value']['RawData']['value'][
                'repair_work_id'] != PalObject.EmptyUUID:
        model_guids.remove(model['Model']['value']['RawData']['value']['repair_work_id'])
    if 'BuildProcess' in model['Model']['value'] and \
            model['Model']['value']['BuildProcess']['value']['RawData']['value'][
                'id'] != PalObject.EmptyUUIDPalObject.EmptyUUID:
        model_guids.remove(model['Model']['value']['BuildProcess']['value']['RawData']['value']['id'])
    return model_guids


# Not call directly
def _DeleteWorkSaveData(wrk_id):
    try:
        if wrk_id in MappingCache.WorkSaveData:
            wsd['WorkSaveData']['value']['values'].remove(MappingCache.WorkSaveData[wrk_id])
    except ValueError:
        print(f"Failed to Delete WorkSave Data {wrk_id}")


def _BatchDeleteWorkSaveData(wrk_ids):
    for wrk_id in wrk_ids:
        try:
            del MappingCache.WorkSaveData[wrk_id]
        except KeyError:
            pass
    wsd['WorkSaveData']['value']['values'] = [MappingCache.WorkSaveData[x] for x in MappingCache.WorkSaveData]
    MappingCache.LoadWorkSaveData()


def _CopyWorkSaveData(wrk_id, old_wsd):
    OldMappingCache = MappingCacheObject.get(old_wsd)
    try:
        if wrk_id in OldMappingCache.WorkSaveData:
            wsd['WorkSaveData']['value']['values'].append(copy.deepcopy(MappingCache.WorkSaveData[wrk_id]))
    except ValueError:
        print(f"Failed to Clone WorkSave Data {wrk_id}")


def _DoubleCheckForDeleteWorkSaveData(wrk_id):
    work = MappingCache.WorkSaveData[wrk_id]
    wsd_guids = set(search_guid(MappingCache.WorkSaveData[wrk_id], printout=False).keys())
    wsd_guids.remove(wrk_id)
    # wsd_guids.remove(work['RawData']['value']['owner_map_object_model_id'])
    # wsd_guids.remove(work['RawData']['value']['owner_map_object_concrete_model_id'])
    # wsd_guids.remove(work['RawData']['value']['base_camp_id_belong_to'])
    return wsd_guids


def CopyBaseCamp(base_id, group_id, old_wsd, dry_run=False):
    load_skipped_decode(old_wsd, ['MapObjectSaveData', 'MapObjectSpawnerInStageSaveData'], False)
    load_skipped_decode(wsd, ['MapObjectSaveData', 'MapObjectSpawnerInStageSaveData'], False)
    srcMappingCache = MappingCacheObject.get(old_wsd)
    base_id = toUUID(base_id)
    group_id = toUUID(group_id)
    if base_id not in srcMappingCache.BaseCampMapping:
        print(f"Error: Base camp {base_id} not found")
        return False
    if base_id in MappingCache.BaseCampMapping:
        print(f"Error: Base camp {base_id} is duplicated on target")
        return False
    if group_id not in MappingCache.GroupSaveDataMap:
        print(f"Error: Target Group {group_id} is not exists")
        return False
    baseCamp = copy.deepcopy(srcMappingCache.BaseCampMapping[base_id]['value'])
    src_group_id = baseCamp['RawData']['value']['group_id_belong_to']
    baseCamp['RawData']['value']['group_id_belong_to'] = group_id
    src_group_data = srcMappingCache.GroupSaveDataMap[src_group_id]['value']['RawData']['value']
    group_data = MappingCache.GroupSaveDataMap[baseCamp['RawData']['value']['group_id_belong_to']]['value']['RawData'][
        'value']
    if base_id in group_data['base_ids']:
        print(f"Error: Base id {base_id} is duplicated on target")
        return False
    if not dry_run:
        group_data['base_ids'].append(base_id)

    if baseCamp['RawData']['value']['owner_map_object_instance_id'] in \
            src_group_data['map_object_instance_ids_base_camp_points']:
        print(
            f"Copy Group UUID {baseCamp['RawData']['value']['group_id_belong_to']}  Map Instance ID {baseCamp['RawData']['value']['owner_map_object_instance_id']}")
        CopyMapObject(baseCamp['RawData']['value']['owner_map_object_instance_id'], old_wsd, dry_run)
        if not dry_run:
            group_data['map_object_instance_ids_base_camp_points'].append(
                baseCamp['RawData']['value']['owner_map_object_instance_id'])
    for wrk_id in baseCamp['WorkCollection']['value']['RawData']['value']['work_ids']:
        if wrk_id in srcMappingCache.WorkSaveData:
            modelId = srcMappingCache.WorkSaveData[wrk_id]['RawData']['value']['owner_map_object_model_id']
            CopyMapObject(modelId, old_wsd, dry_run)
            print(f"Delete Base Camp Work Collection {wrk_id}")
            if not dry_run:
                _CopyWorkSaveData(wrk_id)
        else:
            print(f"Ignore Base Camp Work Collection {wrk_id}")
    workDirectorContainer_id = baseCamp['WorkerDirector']['value']['RawData']['value']['container_id']
    if workDirectorContainer_id in srcMappingCache.ItemContainerSaveData:
        instanceIds = CopyCharacterContainer(workDirectorContainer_id, old_wsd, dry_run)
        instance_lists = list(
            filter(lambda x: x['instance_id'] in instanceIds, src_group_data['individual_character_handle_ids']))
        for instance in instance_lists:
            print(
                f"Clone Character Instance {instance['guid']}  {instance['instance_id']} from Group individual_character_handle_ids")
            if not dry_run:
                group_data['individual_character_handle_ids'].append(copy.deepcopy(instance))

    copy_map_objs = []
    for model in old_wsd['MapObjectSaveData']['value']['values']:
        if model['Model']['value']['RawData']['value']['base_camp_id_belong_to'] == base_id:
            copy_map_objs.append(model['MapObjectInstanceId']['value'])
    for modelId in copy_map_objs:
        if not dry_run:
            CopyMapObject(modelId, old_wsd, dry_run)
    if not dry_run:
        wsd['BaseCampSaveData']['value'].append(srcMappingCache.BaseCampMapping[base_id])
    MappingCache.LoadMapObjectMaps()
    MappingCache.LoadWorkSaveData()
    MappingCache.LoadBaseCampMapping()
    MappingCache.LoadGroupSaveDataMap()
    return True


def DeleteBaseCamp(base_id, group_id=None):
    base_id = toUUID(base_id)
    group_data = None
    if group_id is not None and toUUID(group_id) in MappingCache.GroupSaveDataMap:
        group_data = MappingCache.GroupSaveDataMap[toUUID(group_id)]['value']['RawData']['value']
        print(f"Delete Group UUID {group_id}  Base Camp ID {base_id}")
        if base_id in group_data['base_ids']:
            idx = group_data['base_ids'].index(base_id)
            if len(group_data['base_ids']) == len(group_data['map_object_instance_ids_base_camp_points']):
                group_data['base_ids'].remove(base_id)
                group_data['map_object_instance_ids_base_camp_points'].pop(idx)
            else:
                group_data['base_ids'].remove(base_id)
    if base_id not in MappingCache.BaseCampMapping:
        print(f"Error: Base camp {base_id} not found")
        return False
    baseCamp = MappingCache.BaseCampMapping[base_id]['value']
    if baseCamp['RawData']['value']['group_id_belong_to'] in MappingCache.GroupSaveDataMap:
        group_data = \
            MappingCache.GroupSaveDataMap[baseCamp['RawData']['value']['group_id_belong_to']]['value']['RawData'][
                'value']
        if base_id in group_data['base_ids']:
            print(f"  Delete Group UUID {baseCamp['RawData']['value']['group_id_belong_to']}  Base Camp ID {base_id}")
            group_data['base_ids'].remove(base_id)
        if baseCamp['RawData']['value']['owner_map_object_instance_id'] in group_data[
            'map_object_instance_ids_base_camp_points']:
            print(
                f"  Delete Group UUID {baseCamp['RawData']['value']['group_id_belong_to']}  Map Instance ID {baseCamp['RawData']['value']['owner_map_object_instance_id']}")
            DeleteMapObject(baseCamp['RawData']['value']['owner_map_object_instance_id'])
            group_data['map_object_instance_ids_base_camp_points'].remove(
                baseCamp['RawData']['value']['owner_map_object_instance_id'])
    for wrk_id in baseCamp['WorkCollection']['value']['RawData']['value']['work_ids']:
        if wrk_id in MappingCache.WorkSaveData:
            modelId = MappingCache.WorkSaveData[wrk_id]['RawData']['value']['owner_map_object_model_id']
            DeleteMapObject(modelId)
            print(f"  Delete Base Camp Work Collection {wrk_id}")
    _BatchDeleteWorkSaveData(baseCamp['WorkCollection']['value']['RawData']['value']['work_ids'])
    # _DeleteWorkSaveData(wrk_id)
    # else:
    #     print(f"  Ignore Base Camp Work Collection {wrk_id}")
    instanceIds = DeleteCharacterContainer(baseCamp['WorkerDirector']['value']['RawData']['value']['container_id'])
    if not group_data is None:
        instance_lists = \
            list(filter(lambda x: x['instance_id'] in instanceIds, group_data['individual_character_handle_ids']))
        for instance in instance_lists:
            print(
                f"  Remove Character Instance {instance['guid']}  {instance['instance_id']} from Group individual_character_handle_ids")
            group_data['individual_character_handle_ids'].remove(instance)

    delete_map_objs = []
    for model in wsd['MapObjectSaveData']['value']['values']:
        if model['Model']['value']['RawData']['value']['base_camp_id_belong_to'] == base_id:
            delete_map_objs.append(model['MapObjectInstanceId']['value'])
    BatchDeleteMapObject(delete_map_objs)
    wsd['BaseCampSaveData']['value'].remove(MappingCache.BaseCampMapping[base_id])
    MappingCache.LoadMapObjectMaps()
    MappingCache.LoadWorkSaveData()
    MappingCache.LoadBaseCampMapping()
    MappingCache.LoadGroupSaveDataMap()
    return True


def DoubleCheckForDeleteBaseCamp(base_id):
    LoadAllUUID()
    base_id = toUUID(base_id)
    if base_id not in MappingCache.BaseCampMapping:
        print(f"Error: Base camp {base_id} not found")
        return False
    full_guids = set()
    baseCamp = MappingCache.BaseCampMapping[base_id]['value']
    guids = set(search_guid(baseCamp, printout=False).keys())
    full_guids.update(guids)
    guids.remove(base_id)
    if baseCamp['RawData']['value']['group_id_belong_to'] in MappingCache.GroupSaveDataMap:
        # group_data = MappingCache.GroupSaveDataMap[baseCamp['RawData']['value']['group_id_belong_to']]['value']['RawData']['value']
        # guids.update(set(search_guid(group_data, printout=False).keys()))
        guids.remove(baseCamp['RawData']['value']['group_id_belong_to'])
        full_guids.remove(baseCamp['RawData']['value']['group_id_belong_to'])
        guids.remove(baseCamp['RawData']['value']['owner_map_object_instance_id'])
    for wrk_id in baseCamp['WorkCollection']['value']['RawData']['value']['work_ids']:
        if wrk_id in MappingCache.WorkSaveData:
            work_guids = _DoubleCheckForDeleteWorkSaveData(wrk_id)
            full_guids.update(work_guids)
            work_guids.remove(base_id)
            # Need to check on global
            work_guids.remove(
                MappingCache.WorkSaveData[wrk_id]['RawData']['value']['owner_map_object_concrete_model_id'])
            work_guids.remove(MappingCache.WorkSaveData[wrk_id]['RawData']['value']['owner_map_object_model_id'])
            if len(work_guids) > 0:
                print(f"Get Unknow Referer UUID on WorkSaveData {wrk_id}")
                gp(work_guids)
                gp(MappingCache.WorkSaveData[wrk_id])
            # Remove Map Object
            # *** Model scan on the whole file
            modelId = MappingCache.WorkSaveData[wrk_id]['RawData']['value']['owner_map_object_model_id']
            model_guids = _DoubleCheckForDeleteModel(modelId)
            full_guids.update(model_guids)
            model_guids.remove(base_id)  # base_camp_id_belong_to
            if len(model_guids) > 0:
                print(f"Get Unknow Referer UUID on Model {modelId}")
                gp(model_guids)
                gp(MappingCache.MapObjectSaveData[modelId])
        guids.remove(wrk_id)
    container_ids = baseCamp['WorkerDirector']['value']['RawData']['value']['container_id']
    full_guids.add(container_ids)
    guids.remove(container_ids)
    DoubleCheckForDeleteCharacterContainers(container_ids)
    if len(guids) > 0:
        print(f"Get Unknow Referer UUID on BaseCamp {base_id}")
        gp(guids)
        gp(baseCamp)

    DeleteBaseCamp(base_id)
    global guid_mapping
    guid_mapping = None
    LoadAllUUID()
    for guid in full_guids:
        if guid in guid_mapping:
            print(f"Error after delete uuid {guid}")
            gp(guid_mapping[guid])
    return full_guids


def DeleteGuild(group_id):
    groupMapping = {str(group['key']): group for group in wsd['GroupSaveDataMap']['value']}
    if str(group_id) not in groupMapping:
        return False
    group_info = groupMapping[str(group_id)]['value']['RawData']['value']
    for base_id in group_info['base_ids']:
        DeleteBaseCamp(base_id, group_id)
    print(f"{tcl(31)}Delete Guild{tcl(0)} {tcl(93)} %s {tcl(0)}  UUID: %s" % (
        group_info['guild_name'], str(group_info['group_id'])))
    wsd['GroupSaveDataMap']['value'].remove(groupMapping[str(group_id)])
    return True


def ShowGuild(data_src=None):
    if data_src is None:
        data_src = wsd
    srcMapping = MappingCacheObject.get(data_src)
    # Remove Unused in GroupSaveDataMap
    for group_id in srcMapping.GuildSaveDataMap:
        group_data = srcMapping.GuildSaveDataMap[group_id]
        # pp.pprint(str(group_data['value']['RawData']['value']))
        item = group_data['value']['RawData']['value']
        mapObjectMeta = {}
        for m_k in item:
            mapObjectMeta[m_k] = item[m_k]
        # pp.pprint(mapObjectMeta)
        print(
            f"Guild {tcl(93)}%s{tcl(0)}   Admin {tcl(96)}%s{tcl(0)}  Group ID %s  Base Camp Level: %d Character Count: %d" % (
                mapObjectMeta['guild_name'], str(mapObjectMeta['admin_player_uid']), str(mapObjectMeta['group_id']),
                item['base_camp_level'],
                len(mapObjectMeta['individual_character_handle_ids'])))
        # Referer to ['WorkSaveData']['value']['values'][55]['RawData']['value']['base_camp_id_belong_to']
        # ['BaseCampSaveData']['value'][1]['key']
        # ['BaseCampSaveData']['value'][1]['value']['WorkerDirector']['value']['RawData']['value']['id']
        # ['BaseCampSaveData']['value'][1]['value']['WorkCollection']['value']['RawData']['value']['id']
        # ['BaseCampSaveData']['value'][1]['value']['RawData']['value']['id']
        # ['GroupSaveDataMap']['value'][223]['value']['RawData']['value']['base_ids'][1]
        for base_idx, base_id in enumerate(item['base_ids']):
            basecamp = srcMapping.BaseCampMapping[toUUID(base_id)]
            print(
                f"    Base ID {tcl(32)} {base_id} {tcl(0)} -> {tcl(33)} {basecamp['value']['RawData']['value']['name']} {tcl(0)}    Map ID {tcl(32)} {item['map_object_instance_ids_base_camp_points'][base_idx]} {tcl(0)}")
        print()
        for player in mapObjectMeta['players']:
            try:
                print(
                    f"    Player {tcl(93)} %-30s {tcl(0)}\t[{tcl(92)}%s{tcl(0)}] Last Online: %s - %s" % (
                        player['player_info']['player_name'], str(player['player_uid']),
                        TickToLocal(player['player_info']['last_online_real_time']),
                        TickToHuman(player['player_info']['last_online_real_time'])))
            except UnicodeEncodeError as e:
                print(
                    f"    Player {tcl(93)} %-30s {tcl(0)}\t[{tcl(92)}%s{tcl(0)}] Last Online: %s - %s" % (
                        repr(player['player_info']['player_name']), str(player['player_uid']),
                        TickToLocal(player['player_info']['last_online_real_time']),
                        TickToHuman(player['player_info']['last_online_real_time'])))
        print()
        # elif str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Neutral":
        #     item = group_data['value']['RawData']['value']
        #     print("Neutral Group ID %s  Character Count: %d" % (str(item['group_id']), len(item['individual_character_handle_ids'])))
        #     for ind_char in item['individual_character_handle_ids']:
        #         if ind_char['instance_id'] not in instanceMapping:
        #             print("    \033[31mInvalid Character %s\033[0m" % (str(ind_char['instance_id'])))


def PrettyPrint(data, level=0):
    simpleType = ['DateTime', 'Guid', 'LinearColor', 'Quat', 'Vector', 'PalContainerId']
    if 'struct_type' in data:
        if data['struct_type'] == 'DateTime':
            print("%s<Value Type='DateTime'>%d</Value>" % ("  " * level, data['value']))
        elif data['struct_type'] == 'Guid':
            print(f"{tcl(96)}%s{tcl(0)}" % (data['value']), end="")
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
            print(f"{tcl(96)}%s{tcl(0)}" % (data['value']['ID']['value']), end="")
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
                print(f"%s<%s Type='%s'>{tcl(95)}%d{tcl(0)}</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] == "FloatProperty":
                print(f"%s<%s Type='%s'>{tcl(95)}%f{tcl(0)}</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] in ["StrProperty", "ArrayProperty", "NameProperty"]:
                print(f"%s<%s Type='%s'>{tcl(95)}%s{tcl(0)}</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif isinstance(data[key], list):
                print("%s<%s Type='%s'>%s</%s>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[
                    key] else f"{tcl(31)}unknow struct{tcl(0)}", str(data[key]), key))
            else:
                print("%s<%s Type='%s'>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[
                    key] else f"{tcl(31)}unknow struct{tcl(0)}"))
                PrettyPrint(data[key], level + 1)
                print("%s</%s>" % ("  " * level, key))


def PrettyPrint(data, level=0):
    simpleType = ['DateTime', 'Guid', 'LinearColor', 'Quat', 'Vector', 'PalContainerId']
    if 'struct_type' in data:
        if data['struct_type'] == 'DateTime':
            print("%s<Value Type='DateTime'>%d</Value>" % ("  " * level, data['value']))
        elif data['struct_type'] == 'Guid':
            print(f"{tcl(96)}%s{tcl(0)}" % (data['value']), end="")
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
            print(f"{tcl(96)}%s{tcl(0)}" % (data['value']['ID']['value']), end="")
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
                print(f"%s<%s Type='%s'>{tcl(95)}%d{tcl(0)}</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] == "FloatProperty":
                print(f"%s<%s Type='%s'>{tcl(95)}%f{tcl(0)}</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] in ["StrProperty", "ArrayProperty", "NameProperty"]:
                print(f"%s<%s Type='%s'>{tcl(95)}%s{tcl(0)}</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif isinstance(data[key], list):
                print("%s<%s Type='%s'>%s</%s>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[
                    key] else f"{tcl(31)}unknow struct{tcl(0)}", str(data[key]), key))
            else:
                print("%s<%s Type='%s'>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[
                    key] else f"{tcl(31)}unknow struct{tcl(0)}"))
                PrettyPrint(data[key], level + 1)
                print("%s</%s>" % ("  " * level, key))


def backup_file(file, isPlayerSave=False):
    if not os.path.exists(file):
        return
    if not os.path.exists(os.path.dirname(backup_path)):
        os.mkdir(os.path.dirname(backup_path))
    backup_tar = tarfile.open(f"{backup_path}.tar", mode='a')
    print(
        f"Backup file {tcl(32)}{file}{tcl(0)} to {tcl(32)}backup/{os.path.basename(backup_path)}.tar{tcl(0)}...",
        flush=True, end="")
    with open(file, "rb") as f:
        info = tarfile.TarInfo(("Players/" if isPlayerSave else "") + os.path.basename(file))
        info.size = os.path.getsize(file)
        backup_tar.addfile(info, f)
        backup_tar.close()
    print("Done")


def Save(exit_now=True):
    print("processing GVAS to Sav file...", end="", flush=True)
    if "Pal.PalWorldSaveGame" in gvas_file.header.save_game_class_name or "Pal.PalLocalWorldSaveGame" in gvas_file.header.save_game_class_name:
        save_type = 0x32
    else:
        save_type = 0x31
    sav_file = compress_gvas_to_sav(gvas_file.write(SKP_PALWORLD_CUSTOM_PROPERTIES), save_type)
    print("Done")

    print("Saving Sav file...", end="", flush=True)
    backup_file(output_path, False)
    with open(output_path, "wb") as f:
        f.write(sav_file)
    print("Done")
    print("File saved to %s" % output_path)
    for del_file in delete_files:
        try:
            os.unlink(del_file)
        except FileNotFoundError:
            pass
    if exit_now:
        sys.exit(0)


def dot_itemcontainer(f, container_id, name):
    f.write(f'  "{container_id}" [shape="octagon" fillcolor="lightgreen" style="filled" dir=back label="{name}"]\n')


def dot_charactercontainer(f, container_id, name):
    f.write(f'  "{container_id}" [shape="octagon" fillcolor="lightblue" style="filled" label="{name}"]\n')


def dot_guild(f, group_id):
    guild = MappingCache.GuildSaveDataMap[group_id]
    f.write(
        f'  "{group_id}" [shape="diamond" fillcolor="orange" label="Guild %s" style="filled" weight="60"]\n' %
        guild['value']['RawData']['value']['guild_name'])

    for base_idx, base_id in enumerate(guild['value']['RawData']['value']['base_ids']):
        f.write(f'  "{group_id}" -> "{base_id}"\n')


def dot_mapspawner(f, spawner_id):
    if spawner_id not in MappingCache.MapObjectSpawnerInStageSaveData:
        return
    spawnerObject = MappingCache.MapObjectSpawnerInStageSaveData[spawner_id]
    f.write(
        f'  "{spawner_id}" [shape="invhouse" fillcolor="darkgreen" label="Spawner {str(spawner_id)[:8]}" style="filled" weight="10"]\n')


def dot_mapobject(f, map_id):
    if map_id not in MappingCache.MapObjectSaveData:
        return
    mapObject = MappingCache.MapObjectSaveData[map_id]

    # f.write(f'  "{map_id}" [shape="house" fillcolor="darkgreen" label="Map " style="invis" weight="10"]\n')
    f.write(f'  "{map_id}" [shape="point" fillcolor="darkgreen" label="" style="invis" weight="10"]\n')

    basecamp_id = mapObject['Model']['value']['RawData']['value']['base_camp_id_belong_to']
    # if basecamp_id != PalObject.EmptyUUID:
    #     f.write(f'  "{basecamp_id}" -> "{map_id}"\n')
    build_player_uid = mapObject['Model']['value']['RawData']['value']['build_player_uid']
    # if build_player_uid != PalObject.EmptyUUID:
    #     f.write(f'  "{build_player_uid}" -> "{map_id}"\n')
    group_id = mapObject['Model']['value']['RawData']['value']['group_id_belong_to']
    # if group_id != PalObject.EmptyUUID:
    #     f.write(f'  "{group_id}" -> "{map_id}"\n')
    repair_work_id = mapObject['Model']['value']['RawData']['value']['repair_work_id']
    # if repair_work_id != PalObject.EmptyUUID:
    #     f.write(f'  "{repair_work_id}" -> "{map_id}"\n')

    for concrete in mapObject['ConcreteModel']['value']['ModuleMap']['value']:
        if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
            container_id = concrete['value']['RawData']['value']['target_container_id']
            f.write(f'  "{map_id}" -> "{container_id}"\n')
            dot_itemcontainer(f, container_id, "Map Container")
        if concrete['key'] == "EPalMapObjectConcreteModelModuleType::Workee":
            work_id = concrete['value']['RawData']['value']['target_work_id']
            f.write(f'  "{work_id}" -> "{map_id}"\n')
    owner_spawner_level_object_instance_id = mapObject['Model']['value']['RawData']['value'][
        'owner_spawner_level_object_instance_id']
    if owner_spawner_level_object_instance_id != PalObject.EmptyUUID:
        f.write(f'  "{map_id}" -> "{owner_spawner_level_object_instance_id}"\n')
        dot_mapspawner(f, owner_spawner_level_object_instance_id)


def dot_work(f, work_id):
    if work_id not in MappingCache.WorkSaveData:
        f.write(
            f'  "{work_id}" [shape="parallelogram" fillcolor="red" label="Invalid Work {str(work_id)[:8]}" style="filled" weight="10"]\n')
        return
    work = MappingCache.WorkSaveData[work_id]
    # f.write(
    #     f'  "{work_id}" [shape="parallelogram" fillcolor="lightpink" label="Work %s: %s" style="filled" weight="10"]\n' %
    #     (work['WorkableType']['value']['value'], work['RawData']['value']['assign_define_data_id']))
    f.write(f'  "{work_id}" [shape="point" label="Work" style="filled" weight="10"]\n')
    f.write(f'  "{work_id}" -> "{work["RawData"]["value"]["base_camp_id_belong_to"]}"\n')
    if work["RawData"]["value"]["owner_map_object_model_id"] != PalObject.EmptyUUID:
        dot_mapobject(f, work["RawData"]["value"]["owner_map_object_model_id"])
        f.write(f'  "{work_id}" -> "{work["RawData"]["value"]["owner_map_object_model_id"]}"\n')
    # f.write(f'  "{work_id}" -> "{work["RawData"]["value"]["owner_map_object_concrete_model_id"]}"\n')


def dot_character(f, character_id):
    character = MappingCache.CharacterSaveParameterMap[character_id]
    characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
    if 'IsPlayer' in characterData:
        return
    if 'NickName' in characterData:
        f.write(f'  "%s" [shape="rect" fillcolor="lightyellow" label="Pal %s\n{character_id}" style="filled"]\n' %
                (character['key']['InstanceId']['value'], characterData['NickName']['value']))
    elif 'CharacterID' in characterData:
        f.write(f'  "%s" [shape="rect" fillcolor="lightyellow" label="Pal %s\n{character_id}" style="filled"]\n' %
                (character['key']['InstanceId']['value'], characterData['CharacterID']['value']))
    if 'SlotID' in characterData:
        f.write(f'  "%s" -> "%s"\n' % (characterData['SlotID']['value']['ContainerId']['value']['ID']['value'],
                                       character['key']['InstanceId']['value']))
    elif 'OwnerPlayerUId' in characterData:
        f.write(
            f'  "%s" -> "%s"\n' % (characterData['OwnerPlayerUId']['value'], character['key']['InstanceId']['value']))

    if 'EquipItemContainerId' in characterData:
        container_id = characterData['EquipItemContainerId']['value']['ID']['value']
        f.write(f'  "%s" -> "%s"\n' % (character['key']['InstanceId']['value'], container_id))
        dot_itemcontainer(f, container_id, "EqualItem")
    if 'ItemContainerId' in characterData:
        container_id = characterData['ItemContainerId']['value']['ID']['value']
        f.write(f'  "%s" -> "%s"\n' % (character['key']['InstanceId']['value'], container_id))
        dot_itemcontainer(f, container_id, "Item")


def dot_basecamp(f, basecamp_id):
    basecamp = MappingCache.BaseCampMapping[basecamp_id]
    f.write(
        f'  "{basecamp_id}" [shape="septagon" fillcolor="#ff9900" label="Basecamp %s" style="filled" weight="40"]\n' %
        basecamp['value']['RawData']['value']['name'])
    f.write(f'  "{basecamp_id}" -> "%s"\n' % basecamp['value']['RawData']['value']['group_id_belong_to'])

    f.write(f'  "{basecamp_id}" -> "%s"\n' % basecamp['value']['WorkerDirector']['value']['RawData']['value'][
        'container_id'])
    container_id = basecamp['value']['WorkerDirector']['value']['RawData']['value']['container_id']
    dot_charactercontainer(f, container_id, "WorkerDirector")
    for work_id in basecamp['value']['WorkCollection']['value']['RawData']['value']['work_ids']:
        dot_work(f, work_id)
        f.write(f'  "{basecamp_id}" -> "%s"\n' % work_id)


def buildDotImage():
    load_skipped_decode(wsd, ['ItemContainerSaveData', 'CharacterContainerSaveData', 'MapObjectSaveData',
                              'WorkSaveData', 'MapObjectSpawnerInStageSaveData'], False)

    with open("level.dot", "w") as f:
        f.write("digraph {\n")
        f.write("    rankdir=LR\n")
        # container_ids = FindAllUnreferencedItemContainerIds()
        # for container_id in container_ids:
        #     dot_itemcontainer(f, container_id, f"Unknow {str(container_id)[:8]}")

        for group_id in MappingCache.GuildSaveDataMap:
            dot_guild(f, group_id)
        for player_id in MappingCache.PlayerIdMapping:
            character = MappingCache.PlayerIdMapping[player_id]
            f.write(f'  "{character["value"]["RawData"]["value"]["group_id"]}" -> "{str(player_id)}"\n')
            characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
            f.write(
                f'  "{str(player_id)}" [shape="rect" fillcolor="orange" label="Player %s" style="filled" weight="20"]\n' %
                characterData['NickName']['value'])
            err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_id)
            if err:
                continue
            for idx_key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                            'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
                container_id = player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value']
                if container_id in MappingCache.ItemContainerSaveData:
                    dot_itemcontainer(f, container_id, idx_key[:-11])
                    f.write(f'  "{str(player_id)}" -> "{container_id}"\n')
                else:
                    dot_itemcontainer(f, container_id, "Player %s" % characterData['NickName']['value'])

            for idx_key in ['OtomoCharacterContainerId', 'PalStorageContainerId']:
                container_id = player_gvas[idx_key]['value']['ID']['value']
                if container_id in MappingCache.CharacterContainerSaveData:
                    dot_charactercontainer(f, container_id, idx_key[:-11])
                    f.write(f'  "{str(player_id)}" -> "{container_id}"\n')
                else:
                    dot_charactercontainer(f, container_id, "Player %s" % characterData['NickName']['value'])
        for character_id in MappingCache.CharacterSaveParameterMap:
            dot_character(f, character_id)

        for basecamp_id in MappingCache.BaseCampMapping:
            dot_basecamp(f, basecamp_id)

        # for map_id in MappingCache.MapObjectSaveData:
        #     dot_mapobject(f, map_id)

        f.write("}\n")


if __name__ == "__main__":
    main()
