#!/usr/bin/env python3
# Author: MagicBear
# License: MIT License
import json
import os, datetime, time
import sys
import threading
import pprint
import uuid
import argparse
import copy
import importlib.metadata
import traceback

module_dir = os.path.dirname(os.path.abspath(__file__))
# sys.path.insert(0, module_dir)
sys.path.insert(0, os.path.join(module_dir, "../save_tools"))

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

class GvasPrettyPrint(pprint.PrettyPrinter):
    _dispatch = pprint.PrettyPrinter._dispatch.copy()

    def _pprint_dict(self, object, stream, indent, allowance, context, level):
        write = stream.write
        write('{')
        if self._indent_per_level > 1:
            write((self._indent_per_level - 1) * ' ')
        length = len(object)
        if length:
            if self._sort_dicts:
                items = sorted(object.items(), key=pprint._safe_tuple)
            else:
                items = object.items()
            fmtValue = False
            rep = ""
            dict_type = set(object.keys())
            if {'id', 'type', 'value'}.issubset(dict_type) and object['id'] is None:
                dict_type -= {'id', 'type', 'value', 'custom_type'}
                if dict_type == set() and object['type'] in ["Int64Property", "NameProperty", "EnumProperty",
                                                             "IntProperty", "BoolProperty",
                                                             "FloatProperty", "StrProperty"]:
                    fmtValue = True
                    rep = object['type']
                elif dict_type == {'struct_id', 'struct_type'} and object['type'] == "StructProperty" and str(
                        object['struct_id']) == '00000000-0000-0000-0000-000000000000':
                    rep = f"Struct:{object['struct_type']}"
                    fmtValue = True
                elif dict_type == {'array_type'} and object['type'] == "ArrayProperty":
                    rep = f"ArrayProperty:{object['array_type']}"
                    fmtValue = True
                # elif dict_type == {'key_type', 'key_struct_type', 'value_type', 'value_struct_type'} and object['type'] == "MapProperty":
                #     rep = f"Map:{object['key_type']}{{{object['key_struct_type']}}}={object['value_type']}{{{object['value_struct_type']}}}"
                #     fmtValue = True
            if fmtValue:
                repr = self._repr('value', context, level)
                write(f"\033[36m{rep}\033[0m=")
                if rep == "Struct:Guid":
                    write(
                        "\033[43;31m" if str(object['value']) == "00000000-0000-0000-0000-000000000000" else "\033[93m")
                    self._format(str(object['value']), stream, indent + len(repr) + 1, allowance,
                                 context, level)
                    write("\033[0m")
                else:
                    self._format(object['value'], stream, indent + len(repr) + 1, allowance,
                                 context, level)
            else:
                self._format_dict_items(items, stream, indent, allowance + 1,
                                        context, level)
        write('}')

    def _pprint_UUID(self, object, stream, indent, allowance, context, level):
        stream.write(
            "\033[36mUUID:\033[0m\033[43;31m" if str(object) == "00000000-0000-0000-0000-000000000000" else "\033[93m")
        self._format(str(object), stream, indent, allowance,
                     context, level)
        stream.write("\033[0m")

    _dispatch[dict.__repr__] = _pprint_dict
    _dispatch[UUID.__repr__] = _pprint_UUID


pp = pprint.PrettyPrinter(width=80, compact=True, depth=6)
gvas_pp = GvasPrettyPrint(width=1, compact=True, depth=6)
gp = gvas_pp.pprint

wsd = None
output_file = None
gvas_file = None
backup_gvas_file = None
backup_wsd = None
playerMapping = None
guildInstanceMapping = None
output_path = None
args = None
player = None
filetime = -1
gui = None


def skip_decode(
        reader: FArchiveReader, type_name: str, size: int, path: str
) -> dict[str, Any]:
    if type_name == "ArrayProperty":
        array_type = reader.fstring()
        value = {
            "skip_type": type_name,
            "array_type": array_type,
            "id": reader.optional_guid(),
            "value": reader.read(size),
            "size": size
        }
    elif type_name == "MapProperty":
        key_type = reader.fstring()
        value_type = reader.fstring()
        _id = reader.optional_guid()
        value = {
            "skip_type": type_name,
            "key_type": key_type,
            "value_type": value_type,
            "id": _id,
            "value": reader.read(size),
        }
    elif type_name == "StructProperty":
        value = {
            "skip_type": type_name,
            "struct_type": reader.fstring(),
            "struct_id": reader.guid(),
            "id": reader.optional_guid(),
            "value": reader.read(size),
        }
    else:
        raise Exception(
            f"Expected ArrayProperty or MapProperty or StructProperty, got {type_name} in {path}"
        )
    return value


def skip_encode(
        writer: FArchiveWriter, property_type: str, properties: dict[str, Any]
) -> int:
    if "skip_type" not in properties:
        if properties['custom_type'] in PALWORLD_CUSTOM_PROPERTIES is not None:
            # print("process parent encoder -> ", properties['custom_type'])
            return PALWORLD_CUSTOM_PROPERTIES[properties["custom_type"]][1](
                writer, property_type, properties
            )
        else:
            # Never be run to here
            return writer.property_inner(writer, property_type, properties)
    if property_type == "ArrayProperty":
        del properties["custom_type"]
        del properties["skip_type"]
        writer.fstring(properties["array_type"])
        writer.optional_guid(properties.get("id", None))
        writer.write(properties["value"])
        return len(properties["value"])
    elif property_type == "MapProperty":
        del properties["custom_type"]
        del properties["skip_type"]
        writer.fstring(properties["key_type"])
        writer.fstring(properties["value_type"])
        writer.optional_guid(properties.get("id", None))
        writer.write(properties["value"])
        return len(properties["value"])
    elif property_type == "StructProperty":
        del properties["custom_type"]
        del properties["skip_type"]
        writer.fstring(properties["struct_type"])
        writer.guid(properties["struct_id"])
        writer.optional_guid(properties.get("id", None))
        writer.write(properties["value"])
        return len(properties["value"])
    else:
        raise Exception(
            f"Expected ArrayProperty or MapProperty or StructProperty, got {property_type}"
        )


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
                if gui is not None:
                    gui.progressbar['value'] = 100 * self.reader.data.tell() / self.size
                time.sleep(0.02)
        except ValueError:
            pass


class FProgressArchiveReader(FArchiveReader):
    sub_progress = None

    def progress(self, lv=0):
        ext_prog = 0
        if self.sub_progress is not None:
            proc, total_len = self.sub_progress
            ext_prog = proc.progress(lv + 1)
            if ext_prog >= total_len:
                self.sub_progress = None
        return self.data.tell() + ext_prog

    def internal_copy(self, data, debug: bool) -> "FArchiveReader":
        inst = FProgressArchiveReader(
            data,
            self.type_hints,
            self.custom_properties,
            debug=debug,
            allow_nan=self.allow_nan,
        )
        self.sub_progress = (inst, len(data))
        return inst


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
        for key in properties:
            call_skip_path = skip_path + "." + key[0].upper() + key[1:]
            if isinstance(properties[key], dict) and \
                    'type' in properties[key] and \
                    properties[key]['type'] in ['StructProperty', 'ArrayProperty', 'MapProperty']:
                if 'skip_type' in properties[key]:
                    # print("Parsing worldSaveData.%s..." % call_skip_path, end="", flush=True)
                    properties[key] = parse_skiped_item(properties[key], call_skip_path, False, True)
                    # print("Done")
                else:
                    properties[key]['value'] = parse_item(properties[key]['value'], call_skip_path)
            else:
                properties[key] = parse_item(properties[key], call_skip_path)
    elif isinstance(properties, list):
        top_skip_path = ".".join(skip_path.split(".")[:-1])
        for idx, item in enumerate(properties):
            properties[idx] = parse_item(item, top_skip_path)
    return properties


def parse_skiped_item(properties, skip_path, progress=True, recursive=True):
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
            localProperties
    ) as reader:
        if progress:
            skip_loading_progress(reader, len(properties['value'])).start()
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

def load_skiped_decode(wsd, skip_paths, recursive=True):
    if isinstance(skip_paths, str):
        skip_paths = [skip_paths]
    for skip_path in skip_paths:
        properties = wsd[skip_path]

        if "skip_type" not in properties:
            continue
        print("Parsing worldSaveData.%s..." % skip_path, end="", flush=True)
        t1 = time.time()
        parse_skiped_item(properties, skip_path, True, recursive)
        print("Done in %.2fs" % (time.time() - t1))
        # t1 = time.time()
        # a=json.dumps(wsd[skip_path], cls=CustomEncoder)
        # print("str %.2f" % (time.time()-t1))


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


def gui_thread():
    GUI()
    if gui is None:
        return
    gui.mainloop()


def main():
    global output_file, output_path, args, gui, playerMapping

    parser = argparse.ArgumentParser(
        prog="palworld-save-editor",
        description="Editor for the Level.sav",
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
        help="Fix the too many capture logs (not need after 1.4.0)",
    )
    parser.add_argument(
        "--fix-duplicate",
        action="store_true",
        help="Fix duplicate user data",
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

    if len(sys.argv) == 1:
        bk_f = filedialog.askopenfilename(filetypes=[("Level.sav file", "*.sav")], title="Open Level.sav")
        if bk_f:
            args = type('', (), {})()
            args.filename = bk_f
            args.gui = True
            args.statistics = False
            args.fix_missing = False
            args.fix_capture = False
            args.fix_duplicate = False
            args.output = None
        else:
            args = parser.parse_args()
    else:
        args = parser.parse_args()

    if not os.path.exists(args.filename):
        print(f"{args.filename} does not exist")
        exit(1)

    if not os.path.isfile(args.filename):
        print(f"{args.filename} is not a file")
        exit(1)

    LoadFile(args.filename)

    if args.statistics:
        Statistics()

    if args.output is None:
        output_path = args.filename.replace(".sav", "_fixed.sav")
    else:
        output_path = args.output

    ShowGuild()
    playerMapping = LoadPlayers(data_source=wsd)
    ShowPlayers()

    if args.fix_missing:
        FixMissing()
    if args.fix_capture:
        FixCaptureLog()
    if args.fix_duplicate:
        FixDuplicateUser()

    if args.gui and sys.flags.interactive:
        threading.Thread(target=gui_thread).start()

    if sys.flags.interactive:
        print("Go To Interactive Mode (no auto save), we have follow command:")
        print("  ShowPlayers()                              - List the Players")
        print("  FixMissing(dry_run=False)                  - Remove missing player instance")
        print("  FixCaptureLog(dry_run=False)               - Remove unused capture log")
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
        print("                                               Note: be sure you have already use the new playerUId to ")
        print("                                               login the game.")
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
        return

    if args.fix_missing or args.fix_capture:
        Save()

try:
    class EntryPopup(tk.Entry):
        def __init__(self, parent, iid, column, **kw):
            ''' If relwidth is set, then width is ignored '''
            super().__init__(parent, **kw)
            self._textvariable = kw['textvariable']
            self.tv = parent
            self.iid = iid
            self.column = column
            global cc
            cc = self
            # self['state'] = 'readonly'
            # self['readonlybackground'] = 'white'
            # self['selectbackground'] = '#1BA1E2'
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
            self.font = tk.font.Font(family="Courier New")
            ttk.Style().configure("custom.TButton",
                              font=(self.font, 12))
        
        def build_subgui(self, g_frame, attribute_key, attrib_var, attrib):
            sub_frame = ttk.Frame(master=g_frame, borderwidth=1, relief=tk.constants.GROOVE, padding=2)
            sub_frame.pack(side="right")
            sub_frame_c = ttk.Frame(master=sub_frame)
    
            sub_frame_item = ttk.Frame(master=sub_frame)
            tk.Label(master=sub_frame_item, font=self.font, text=attrib['array_type']).pack(side="left")
            cmbx = ttk.Combobox(master=sub_frame_item, font=self.font, width=20, state="readonly",
                                values=["Item %d" % i for i in range(len(attrib['value']['values']))])
            cmbx.bind("<<ComboboxSelected>>",
                      lambda evt: self.cmb_array_selected(evt, sub_frame_c, attribute_key, attrib_var, attrib))
            cmbx.pack(side="right")
            sub_frame_item.pack(side="top")
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
                                index = list(self.var_options[attribute_key].values()).index(attrib_var[attribute_key].get())
                                attrib_var[attribute_key].set(list(self.var_options[attribute_key].keys())[index])
                                print("Assign Attrib ", list(self.var_options[attribute_key].keys())[index])
                            except ValueError:
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
                        tk.Label(master=g_frame, text=attribute_key, font=self.font).pack(side="left")
                    else:
                        g_frame = parent
    
                    attrib_var[attribute_key] = self.make_attrib_var(master=parent, attrib=attrib)
                    if attrib['type'] == "BoolProperty":
                        tk.Checkbutton(master=g_frame, text="Enabled", variable=attrib_var[attribute_key]).pack(
                            side="left")
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "EnumProperty" and attrib['value']['type'] == "EPalWorkSuitability":
                        enum_options = ['EPalWorkSuitability::EmitFlame', 'EPalWorkSuitability::Watering',
                                        'EPalWorkSuitability::Seeding',
                                        'EPalWorkSuitability::GenerateElectricity', 'EPalWorkSuitability::Handcraft',
                                        'EPalWorkSuitability::Collection', 'EPalWorkSuitability::Deforest',
                                        'EPalWorkSuitability::Mining',
                                        'EPalWorkSuitability::OilExtraction', 'EPalWorkSuitability::ProductMedicine',
                                        'EPalWorkSuitability::Cool', 'EPalWorkSuitability::Transport',
                                        'EPalWorkSuitability::MonsterFarm']
                        if attrib['value']['value'] not in enum_options:
                            enum_options.append(attrib['value']['value'])
                        ttk.Combobox(master=g_frame, font=self.font, state="readonly", width=40,
                                     textvariable=attrib_var[attribute_key],
                                     values=enum_options).pack(side="right")
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "ArrayProperty" and attrib['array_type'] in ["StructProperty", "NameProperty"]:
                        self.build_subgui(g_frame, attribute_key, attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] in ["Guid", "PalContainerId"]:
                        tk.Entry(font=self.font, master=g_frame, width=50,
                                 textvariable=attrib_var[attribute_key]).pack(
                            side="right", fill=tk.constants.X)
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] == "Vector":
                        valid_cmd = (self.register(self.valid_float), '%P')
                        tk.Entry(font=self.font, master=g_frame, width=16,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][2]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.font, master=g_frame, width=16,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][1]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.font, master=g_frame, width=16,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][0]).pack(side="right", fill=tk.constants.X)
                        self.assign_attrib_var(attrib_var[attribute_key], attrib)
                    elif attrib['type'] == "StructProperty" and attrib['struct_type'] in ["Quat", "LinearColor"]:
                        valid_cmd = (self.register(self.valid_float), '%P')
                        tk.Entry(font=self.font, master=g_frame, width=12,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][3]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.font, master=g_frame, width=12,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][2]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.font, master=g_frame, width=12,
                                 validate='all', validatecommand=valid_cmd,
                                 textvariable=attrib_var[attribute_key][1]).pack(side="right", fill=tk.constants.X)
                        tk.Entry(font=self.font, master=g_frame, width=12,
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
    
                        tk.Entry(font=self.font, master=g_frame,
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
                            ".%s" % attrib['struct_type'] if attrib['type'] == "StructProperty" else ""), attrib['value'])
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
        def on_table_gui_dblclk(event, popup_set, columns, attrib_var):
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
            popup_set.entryPopup = EntryPopup(event.widget, rowid, column, textvariable=attrib_var[int(rowid)][col_name])
            popup_set.entryPopup.place(x=x, y=y + pady, anchor=tk.constants.W, width=width)
    
        def build_array_gui_item(self, tables, idx, attrib_var, attrib_list):
            values = []
            for key in attrib_list:
                attrib = attrib_list[key]
                attrib_var[key] = self.make_attrib_var(tables, attrib)
                if attrib_var[key] is not None:
                    self.assign_attrib_var(attrib_var[key], attrib)
                    if self.var_options is not None and key in self.var_options\
                            and attrib_var[key].get() in self.var_options[key]:
                        values.append(self.var_options[key][attrib_var[key].get()])
                    else:
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
            tables.bind("<Double-1>", lambda event: self.on_table_gui_dblclk(event, popup_set, columns, attrib_var))
            return tables
    
    
    def GetPlayerGvas(player_uid):
        player_sav_file = os.path.dirname(os.path.abspath(args.filename)) + "/Players/" + player_uid.upper().replace(
            "-",
            "") + ".sav"
        if not os.path.exists(player_sav_file):
            return player_sav_file, None, None, None
    
        with open(player_sav_file, "rb") as f:
            raw_gvas, _ = decompress_sav_to_gvas(f.read())
            player_gvas_file = GvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
        player_gvas = player_gvas_file.properties['SaveData']['value']
    
        return None, player_gvas, player_sav_file, player_gvas_file
    
    
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
            if MappingCache.PlayerIdMapping is None:
                LoadCharacterSaveParameterMap()
            self.player_uid = player_uid
            self.player = MappingCache.PlayerIdMapping[toUUID(player_uid)]['value']['RawData']['value']['object'][
                'SaveParameter']['value']
            self.gui.title("Player Item Edit - %s" % player_uid)
            tabs = ttk.Notebook(master=self)
            tabs.pack(anchor=tk.constants.N, fill=tk.constants.BOTH, expand=True)
            ttk.Button(master=self.gui, style="custom.TButton", text="Save", command=self.savedata).pack(fill=tk.constants.X,
                                                                                                anchor=tk.constants.S,
                                                                                                expand=False)
            threading.Thread(target=self.load, args=[tabs, player_gvas]).start()
    
        def load(self, tabs, player_gvas):
            with open(module_dir+"/resources/item_%s.json" % self.i18n, "r", encoding='utf-8') as f:
                item_list = json.load(f)
            if MappingCache.ItemContainerSaveData is None:
                LoadItemContainerMaps()
    
            for idx_key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                            'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
                if player_gvas['inventoryInfo']['value'][idx_key]['value']['ID'][
                    'value'] in MappingCache.ItemContainerSaveData:
                    tab = tk.Frame(tabs)
                    tabs.add(tab, text=idx_key[:-11])
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
            self.build_variable_gui(self.gui, self.gui_attribute, self.player)
            ttk.Button(master=self.gui, style="custom.TButton", text="Save", command=self.savedata).pack(fill=tk.constants.X)
    
        def savedata(self):
            self.save(self.player, self.gui_attribute)
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
            if MappingCache.CharacterSaveParameterMap is None:
                LoadCharacterSaveParameterMap()
            self.player = MappingCache.CharacterSaveParameterMap[
                playerMapping[player_uid]['InstanceId'] if instanceId is None else toUUID(instanceId)]['value']['RawData'][
                'value']['object']['SaveParameter']['value']
            gp(self.player)
            self.gui.title(
                "Player Edit - %s" % player_uid if player_uid is not None else "Character Edit - %s" % instanceId)
            self.gui_attribute = {}
            self.build_variable_gui(self.gui, self.gui_attribute, self.player)
            ttk.Button(master=self.gui, style="custom.TButton", text="Save", command=self.savedata).pack(fill=tk.constants.X)
    
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
            print(self.group_data)
            self.gui.title("Guild Edit - %s" % group_id)
            self.gui_attribute = {}
            self.build_variable_gui(self.gui, self.gui_attribute, self.group_data)
            ttk.Button(master=self.gui, style="custom.TButton", text="Save", command=self.savedata).pack(fill=tk.constants.X)
    
        def savedata(self):
            self.save(self.group_data, self.gui_attribute)
            self.destroy()
    
    
    # g = GuildEditGUI("5cbf2999-92db-40e7-be6d-f96faf810453")
    
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
            self._completion_list = sorted(completion_list, key=str.lower)  # Work with a sorted list
            self._hits = []
            self._hit_index = 0
            self.position = 0
            self.bind('<KeyRelease>', self.handle_keyrelease)
            # self['values'] = self._completion_list  # Setup our popup menu
    
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
            if len(event.keysym) == 1 and event.keysym in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c',
                                                           'd', 'e', 'f']:
                self.autocomplete()
            # No need for up/down, we'll jump to the popup
            # list at the position of the autocompletion
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
        self.language = None
        self.pal_i18n = None
        self.g_move_guild_owner = None
        global gui
        try:
            if tk is None:
                pass
        except NameError:
            print("ERROR: Without Tkinter Environment, GUI not work")
            return
        if gui is not None:
            gui.gui.destroy()
        gui = self
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
            uuid.UUID(target_guild_uuid)
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
            messagebox.showerror("Copy Error", str(e))

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

        self.target_player['value'] = target_value_lists

        if MappingCache.CharacterSaveParameterMap is None:
            LoadCharacterSaveParameterMap()
        self.target_instance['value'] = sorted([
            "%s - %s" % (str(k), self.characterInstanceName(MappingCache.CharacterSaveParameterMap[k]))
            for k in MappingCache.CharacterSaveParameterMap.keys()
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
            self.btn_migrate["state"] = "normal"
        else:
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
        if new_player_name:
            try:
                RenamePlayer(target_uuid, new_player_name)
                messagebox.showinfo("Result", "Rename success")
                self.load_players()
            except Exception as e:
                messagebox.showerror("Rename Error", str(e))

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
        if MappingCache.CharacterSaveParameterMap is None:
            LoadCharacterSaveParameterMap()
        if toUUID(target_uuid) not in MappingCache.CharacterSaveParameterMap:
            messagebox.showerror("Edit Instance Error", "Instance Not Found")
            return
        PlayerEditGUI(instanceId=target_uuid)

    def edit_player_item(self):
        target_uuid = self.parse_target_uuid()
        if target_uuid is None:
            return
        PlayerItemEdit(target_uuid, self.language)

    def edit_player_save(self):
        target_uuid = self.parse_target_uuid()
        if target_uuid is None:
            return
        PlayerSaveEdit(target_uuid)

    def pal_edit(self):
        PalEditConfig.font = self.font
        pal = PalEditGUI()
        pal.load(None)
        pal.mainloop()

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
            if MappingCache.PlayerIdMapping is None:
                LoadCharacterSaveParameterMap()
            gid = MappingCache.PlayerIdMapping[toUUID(target_uuid)]['value']['RawData']['value']['group_id']
            for idx, grp_msg in enumerate(self.target_guild['values']):
                if str(gid) == grp_msg[0:36]:
                    self.target_guild.current(idx)
                    self.select_guild(evt)
                    break

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

    def getPalTranslatedName(self, saveParameter):
        internal_name = saveParameter['CharacterID']['value']
        name = ''
        if 'NickName' in saveParameter:
            name = " - %s" % saveParameter['NickName']['value']
        try_split = internal_name.split("BOSS_",1)
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
        else:
            try:
                return 'Pal:%s' % self.getPalTranslatedName(saveParameter)
            except UnicodeEncodeError:
                return 'Pal:%s' % repr(saveParameter['CharacterID']['value'])

    def build_gui(self):
        #
        self.gui = tk.Tk()
        self.gui.parent = self
        try:
            __version__ = importlib.metadata.version('palworld-server-toolkit')
        except importlib.metadata.PackageNotFoundError:
            __version__ = "0.0.1"
        self.gui.title(f'PalWorld Save Editor v{__version__} - Author by MagicBear')
        # self.gui.geometry('640x200')
        #
        self.font = tk.font.Font(family="Courier New")
        self.mono_font = tk.font.Font(family="Courier New")
        mono_font_list = ('Dejavu Sans', 'Courier New')
        font_list = ('Apple LiGothic', 'PangMenZhengDao', 'Droid Sans Fallback', '微软雅黑', 'Courier New', 'Arial')
        for font in font_list:
            if font in tkinter.font.families():
                self.font = tk.font.Font(family=font)
                ttk.Style().configure("custom.TButton",
                              font=(font, 12))
                break
        for font in mono_font_list:
            if font in tkinter.font.families():
                self.mono_font = tk.font.Font(family=font)
                break
                
        self.gui.option_add('*TCombobox*Listbox.font', self.mono_font)
        # window.resizable(False, False)
        with open(module_dir+"/resources/gui.json", "r", encoding='utf-8') as f:
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
        self.i18n['delete_base'] = g_delete_base = ttk.Button(master=f_target_guildbase, text="Delete Base Camp", style="custom.TButton",
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

        g_multi_button_frame = tk.Frame()
        self.btn_migrate = ttk.Button(master=g_multi_button_frame, text="⬆️ Migrate Player ⬇️", style="custom.TButton",
                                     command=self.migrate)
        self.i18n['migrate_player'] = self.btn_migrate
        self.btn_migrate.pack(side="left")
        g_copy = ttk.Button(master=g_multi_button_frame, text="⬆️ Copy Player ⬇️", style="custom.TButton",
                           command=self.copy_player)
        self.i18n['copy_player'] = g_copy
        g_copy.pack(side="left")

        #
        # g_target_player_frame = tk.Frame(borderwidth=1, relief=tk.constants.GROOVE, pady=5)
        g_button_frame = tk.Frame(borderwidth=1, relief=tk.constants.GROOVE, pady=5)
        self.i18n['op_for_target'] = tk.Label(master=g_button_frame, text="Operate for Target Player", font=self.font)
        self.i18n['op_for_target'].pack(fill="x", side="top")
        g_move = ttk.Button(master=g_button_frame, text="Move To Guild", style="custom.TButton", command=self.move_guild)
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
        g_edit_item = ttk.Button(master=g_button_frame, text="Edit Item", style="custom.TButton", command=self.edit_player_item)
        self.i18n['edit_item'] = g_edit_item
        g_edit_item.pack(side="left")
        g_edit_save = ttk.Button(master=g_button_frame, text="Edit Save", style="custom.TButton", command=self.edit_player_save)
        self.i18n['edit_save'] = g_edit_save
        g_edit_save.pack(side="left")

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
        g_del_unref_item = ttk.Button(master=g_wholefile, text="Delete Unref Item", style="custom.TButton",
                            command=lambda: BatchDeleteUnreferencedItemContainers())
        self.i18n['del_unreference_item'] = g_del_unref_item
        g_del_unref_item.pack(side="left")

        g_pal = ttk.Button(master=g_wholefile, text="Pal Edit", style="custom.TButton", command=self.pal_edit)
        self.i18n['edit_pal'] = g_pal
        g_pal.pack(side="left")
        g_wholefile.pack(fill=tk.X)


        g_save = ttk.Button(text="Save & Exit", style="custom.TButton", command=self.save)
        self.i18n['save'] = g_save
        g_save.pack()

        self.progressbar = ttk.Progressbar()
        self.progressbar.pack(fill=tk.constants.X)

        self.set_i18n(list(i18n_list.keys())[0])
        self.load_players()
        self.load_guilds()
    
    def set_i18n(self, lang):
        self.language = lang
        with open("%s/resources/gui_%s.json" % (module_dir, lang), encoding='utf-8') as f:
            lang_data = json.load(f)
        with open("%s/resources/pal_%s.json" % (module_dir, lang), encoding='utf-8') as f:
            self.pal_i18n = json.load(f)

        for item in self.i18n:
            if item in lang_data:
                if isinstance(self.i18n[item], ttk.Combobox):
                    index = self.i18n[item].current()
                    self.i18n[item]['values'] = lang_data[item]
                    self.i18n[item].current(index)
                else:
                    self.i18n[item].config(text=lang_data[item])

        if self.target_instance['value'] != '':
            self.load_players()


def DumpSavDecompressData(filename):
    with open(filename, "rb") as f:
        data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)

    with open(filename + ".raw", "wb") as f:
        f.write(raw_gvas)


def LoadFile(filename):
    global filetime, gvas_file, wsd
    print(f"Loading {filename}...")
    filetime = os.stat(filename).st_mtime
    with open(filename, "rb") as f:
        # Read the file
        data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)

        print(f"Parsing {filename}...", end="", flush=True)
        start_time = time.time()
        gvas_file = ProgressGvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, SKP_PALWORLD_CUSTOM_PROPERTIES)
        print("Done in %.2fs." % (time.time() - start_time))

    wsd = gvas_file.properties['worldSaveData']['value']


def Statistics():
    for key in wsd:
        print("%40s\t%.3f MB\tKey: %d" % (key, len(str(wsd[key])) / 1048576, len(wsd[key]['value'])))


def EditPlayer(player_uid):
    global player
    for item in wsd['CharacterSaveParameterMap']['value']:
        if str(item['key']['PlayerUId']['value']) == player_uid:
            player = item['value']['RawData']['value']['object']['SaveParameter']['value']
            print("Player has allocated to 'player' variable, you can use player['Property']['value'] = xxx to modify")
            pp.pprint(player)


def RenamePlayer(player_uid, new_name):
    for item in wsd['CharacterSaveParameterMap']['value']:
        if str(item['key']['PlayerUId']['value']) == player_uid:
            player = item['value']['RawData']['value']['object']['SaveParameter']['value']
            print(
                "\033[32mRename User\033[0m  UUID: %s  Level: %d  CharacterID: \033[93m%s\033[0m -> %s" % (
                    str(item['key']['InstanceId']['value']), player['Level']['value'],
                    repr(player['NickName']['value']), new_name))
            player['NickName']['value'] = new_name
    for group_data in wsd['GroupSaveDataMap']['value']:
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            item = group_data['value']['RawData']['value']
            for g_player in item['players']:
                if str(g_player['player_uid']) == player_uid:
                    print(
                        "\033[32mRename Guild User\033[0m  \033[93m%s\033[0m  -> %s" % (
                            repr(g_player['player_info']['player_name']), new_name))
                    g_player['player_info']['player_name'] = new_name
                    break


def GetPlayerItems(player_uid):
    load_skiped_decode(wsd, ["ItemContainerSaveData"])
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
        print("\033[33mWarning: Player Sav file Not exists: %s\033[0m" % player_sav_file)
        return
    for idx_key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                    'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
        print("  %s" % player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value'])
        pp.pprint(item_containers[str(player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value'])])
        print()


def OpenBackup(filename):
    global backup_gvas_file, backup_wsd
    print(f"Loading {filename}...")
    with open(filename, "rb") as f:
        # Read the file
        data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)

        print(f"Parsing {filename}...", end="", flush=True)
        start_time = time.time()
        backup_gvas_file = ProgressGvasFile.read(raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES)
        print("Done in %.2fs." % (time.time() - start_time))
    backup_wsd = backup_gvas_file.properties['worldSaveData']['value']
    ShowPlayers(backup_wsd)


def toUUID(uuid_str):
    if isinstance(uuid_str, UUID):
        return uuid_str
    return UUID.from_str(str(uuid_str))


def SetGuildOwner(group_id, new_player_uid):
    new_player_uid = toUUID(new_player_uid)
    if MappingCache.PlayerIdMapping is None:
        LoadCharacterSaveParameterMap()
    if new_player_uid not in MappingCache.PlayerIdMapping:
        raise Exception("Error: target player not exists")
    if MappingCache.GroupSaveDataMap is None:
        LoadGroupSaveDataMap()
    if toUUID(group_id) not in MappingCache.GroupSaveDataMap:
        raise Exception("Error: Guild not exists")
    MoveToGuild(new_player_uid, group_id)
    MappingCache.GroupSaveDataMap[toUUID(group_id)]['value']['RawData']['value']['admin_player_uid'] = new_player_uid
    return True


def CopyPlayer(player_uid, new_player_uid, old_wsd, dry_run=False):
    if MappingCache.ItemContainerSaveData is None or MappingCache.DynamicItemSaveData:
        LoadItemContainerMaps()

    if MappingCache.CharacterContainerSaveData is None:
        LoadCharacterContainerMaps()

    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print("\033[33mWarning: Player Sav file Not exists: %s\033[0m" % player_sav_file)
        return
    new_player_sav_file = os.path.dirname(
        os.path.abspath(args.filename)) + "/Players/" + new_player_uid.upper().replace("-", "") + ".sav"
    instances = []
    container_mapping = {}
    new_player_uid = toUUID(new_player_uid)
    player_uid = player_gvas['PlayerUId']['value']
    player_gvas['PlayerUId']['value'] = new_player_uid
    player_gvas['IndividualId']['value']['PlayerUId']['value'] = player_gvas['PlayerUId']['value']
    player_gvas['IndividualId']['value']['InstanceId']['value'] = toUUID(uuid.uuid4())
    # Clone Item from CharacterContainerSaveData
    for idx_key in ['OtomoCharacterContainerId', 'PalStorageContainerId']:
        for container in parse_item(old_wsd['CharacterContainerSaveData']['value'], "CharacterContainerSaveData"):
            if container['key']['ID']['value'] == player_gvas[idx_key]['value']['ID']['value']:
                new_item = copy.deepcopy(container)
                IsFound = False
                if MappingCache.CharacterContainerSaveData is None:
                    LoadCharacterContainerMaps()
                if player_gvas[idx_key]['value']['ID']['value'] in MappingCache.CharacterContainerSaveData:
                    player_gvas[idx_key]['value']['ID']['value'] = toUUID(uuid.uuid4())
                    new_item['key']['ID']['value'] = player_gvas[idx_key]['value']['ID']['value']
                    IsFound = True
                container_mapping[idx_key] = new_item
                if not dry_run:
                    wsd['CharacterContainerSaveData']['value'].append(new_item)
                if IsFound:
                    print(
                        "\033[32mCopy Character Container\033[0m %s UUID: %s -> %s" % (idx_key,
                                                                                       str(container['key']['ID'][
                                                                                               'value']), str(
                            new_item['key']['ID']['value'])))
                else:
                    print(
                        "\033[32mCopy Character Container\033[0m %s UUID: %s" % (idx_key,
                                                                                 str(container['key']['ID']['value'])))
                break

    srcDynamicItemContainer = {dyn_item_data['ID']['value']['LocalIdInCreatedWorld']['value']: dyn_item_data for
                               dyn_item_data in old_wsd['DynamicItemSaveData']['value']['values']}
    srcItemContainers = {container['key']['ID']['value']: container for container in
                         old_wsd['ItemContainerSaveData']['value']}
    cloneDynamicItemIds = []
    for idx_key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                    'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
        container_id = player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value']
        if container_id in srcItemContainers:
            container = parse_item(srcItemContainers[container_id], "ItemContainerSaveData")
            new_item = copy.deepcopy(container)
            if container_id in MappingCache.ItemContainerSaveData:
                player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value'] = toUUID(uuid.uuid4())
                new_item['key']['ID']['value'] = player_gvas['inventoryInfo']['value'][idx_key]['value']['ID']['value']
                print("\033[32mCreate Item Container\033[0m %s UUID: %s -> %s" % (idx_key,
                                                                                  str(container['key']['ID']['value']),
                                                                                  str(new_item['key']['ID']['value'])))
            else:
                print("\033[32mCopy Item Container\033[0m %s UUID: %s" % (idx_key,
                                                                          str(container['key']['ID']['value'])))
            containerSlots = container['value']['Slots']['value']['values']
            for slotItem in containerSlots:
                dynamicItemId = slotItem['ItemId']['value']['DynamicId']['value']['LocalIdInCreatedWorld']['value']
                if str(dynamicItemId) == '00000000-0000-0000-0000-000000000000':
                    continue
                if dynamicItemId not in srcDynamicItemContainer:
                    print(
                        f"\033[31m  Error missed DynamicItemContainer UUID [\033[33m {str(dynamicItemId)}\033[0m]  Item \033[32m {slotItem['ItemId']['value']['StaticId']['value']} \033[0m")
                    continue
                if dynamicItemId not in MappingCache.ItemContainerSaveData:
                    print(
                        f"\033[32m  Copy DynamicItemContainer  \033[33m {str(dynamicItemId)}\033[0m  Item \033[32m {slotItem['ItemId']['value']['StaticId']['value']} \033[0m")
                    if not dry_run:
                        wsd['DynamicItemSaveData']['value']['values'].append(srcDynamicItemContainer[dynamicItemId])
            dynamicItemIds = list(filter(lambda x: str(x) != '00000000-0000-0000-0000-000000000000',
                                         [x['ItemId']['value']['DynamicId']['value']['LocalIdInCreatedWorld'][
                                              'value'] for x in
                                          containerSlots]))
            if len(dynamicItemIds) > 0:
                print("  \033[33mDynamic IDS: \033[0m %s" % ",".join([str(x) for x in dynamicItemIds]))
            if not dry_run:
                wsd['ItemContainerSaveData']['value'].append(new_item)

    if MappingCache.PlayerIdMapping is None:
        LoadCharacterSaveParameterMap()

    srcPlayerMapping = {character['key']['PlayerUId']['value']: character for character in
                        filter(
                            lambda x: 'IsPlayer' in x['value']['RawData']['value']['object']['SaveParameter']['value'],
                            old_wsd['CharacterSaveParameterMap']['value'])}

    if player_uid not in srcPlayerMapping:
        print(f"\033[31mError, player \033[32m {str(player_uid)} %s \033[31m not exists \033[0m")
    if new_player_uid in MappingCache.PlayerIdMapping:
        print(f"\033[36mPlayer \033[32m {str(new_player_uid)} \033[31m exists, update new player information \033[0m")
        userInstance = MappingCache.PlayerIdMapping[new_player_uid]
    else:
        print(
            f"\033[36mCopy Player \033[32m {str(new_player_uid)} %s \033[31m \033[0m")
        userInstance = copy.deepcopy(srcPlayerMapping[player_uid])
        if not dry_run:
            wsd['CharacterSaveParameterMap']['value'].append(userInstance)
    
    instances.append({'guid': new_player_uid, 'instance_id': player_gvas['IndividualId']['value']['InstanceId']['value']})
    
    if not dry_run:
        userInstance['key']['PlayerUId']['value'] = new_player_uid
        userInstance['key']['InstanceId']['value'] = player_gvas['IndividualId']['value']['InstanceId']['value']
        userInstance['value'] = srcPlayerMapping[player_uid]['value']

    _playerMapping = LoadPlayers(wsd)
    for item in old_wsd['CharacterSaveParameterMap']['value']:
        player = item['value']['RawData']['value']['object']['SaveParameter']['value']
        if 'IsPlayer' not in player and 'OwnerPlayerUId' in player and player['OwnerPlayerUId']['value'] == player_uid:
            isFound = item['key']['InstanceId']['value'] in MappingCache.CharacterSaveParameterMap
            new_item = copy.deepcopy(item)
            new_item['value']['RawData']['value']['object']['SaveParameter']['value']['OwnerPlayerUId']['value'] = \
                player_gvas['PlayerUId']['value']
            new_item['value']['RawData']['value']['object']['SaveParameter']['value']['SlotID']['value']['ContainerId'][
                'value']['ID'][
                'value'] = player_gvas['PalStorageContainerId']['value']['ID']['value']
            if isFound:
                new_item['key']['InstanceId']['value'] = toUUID(uuid.uuid4())
                print(
                    "\033[32mCopy Pal\033[0m  UUID: %s -> %s  Owner: %s  CharacterID: %s" % (
                        str(item['key']['InstanceId']['value']), str(new_item['key']['InstanceId']['value']),
                        str(player['OwnerPlayerUId']['value']),
                        player['CharacterID']['value']))
            else:
                print(
                    "\033[32mCopy Pal\033[0m  UUID: %s  Owner: %s  CharacterID: %s" % (
                        str(item['key']['InstanceId']['value']), str(player['OwnerPlayerUId']['value']),
                        player['CharacterID']['value']))
            if not dry_run:
                wsd['CharacterSaveParameterMap']['value'].append(new_item)
            instances.append(
                {'guid': toUUID("00000000-0000-0000-0000-000000000000"), 'instance_id': new_item['key']['InstanceId']['value']})
    # Copy Item from GroupSaveDataMap
    if MappingCache.GroupSaveDataMap is None:
        LoadGroupSaveDataMap()
    player_group = None
    for group_data in wsd['GroupSaveDataMap']['value']:
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            item = group_data['value']['RawData']['value']
            for g_player in item['players']:
                if g_player['player_uid'] == new_player_uid:
                    # Target Player is already in the server, update the player data
                    player_group = group_data
                    if not dry_run:
                        item['individual_character_handle_ids'] += instances
                        userInstance['value']['RawData']['value']['group_id'] = group_data['value']['RawData']['value'][
                            'group_id']
                        g_player['player_info'] = {
                            'last_online_real_time': 0,
                            'player_name':
                                userInstance['value']['RawData']['value']['object']['SaveParameter'][
                                    'value']['NickName']['value']
                        }
                    print(
                        "\033[32mCopy User \033[93m %s \033[0m -> \033[93m %s \033[32m to Guild\033[0m \033[32m %s \033[0m  UUID %s" % (
                            g_player['player_info']['player_name'],
                            userInstance['value']['RawData']['value']['object']['SaveParameter']['value']['NickName'][
                                'value'],
                            item['guild_name'], item['group_id']))
                    break
    if player_group is None:
        for group_data in old_wsd['GroupSaveDataMap']['value']:
            if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
                item = group_data['value']['RawData']['value']
                for old_gplayer in item['players']:
                    if old_gplayer['player_uid'] == player_uid:
                        # Check group is exists
                        player_group = MappingCache.GroupSaveDataMap.get(group_data['key'], None)
                        # Same Guild is not exists in target save
                        if player_group is None:
                            player_group = copy.deepcopy(group_data)
                            player_group['value']['RawData']['value']['base_ids'] = []
                            player_group['value']['RawData']['value']['map_object_instance_ids_base_camp_points'] = []
                            player_group['value']['RawData']['value']['admin_player_uid'] = \
                            userInstance['key']['PlayerUId']['value']
                            print(
                                "\033[32mCopy Guild\033[0m Group ID [\033[92m%s\033[0m]" % (
                                    str(player_group['key'])))
                            if not dry_run:
                                wsd['GroupSaveDataMap']['value'].append(player_group)
                        else:
                            print(
                                f"\033[32mGuild \033[93m {item['guild_name']} \033[0m exists\033[0m  Group ID \033[92m {item['group_id']} \033[0m   ")
                        if not dry_run:
                            userInstance['value']['RawData']['value']['group_id'] = player_group['key']
                            bIsUpdateItem = False
                            n_item = player_group['value']['RawData']['value']
                            for n_player_info in n_item['players']:
                                if n_player_info['player_uid'] == new_player_uid:
                                    n_item['players'].remove(n_player_info)
                                    break
                            n_item['players'].append({
                                'player_uid': new_player_uid,
                                'player_info': {
                                    'last_online_real_time': 0,
                                    'player_name':
                                        userInstance['value']['RawData']['value']['object']['SaveParameter'][
                                            'value']['NickName']['value']
                                }
                            })
                            n_item['individual_character_handle_ids'] += instances
                        break
    LoadItemContainerMaps()
    LoadCharacterSaveParameterMap()
    LoadCharacterContainerMaps()
    LoadGroupSaveDataMap()
    if not dry_run:
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
    target_group = None
    for group_data in wsd['GroupSaveDataMap']['value']:
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            group_info = group_data['value']['RawData']['value']
            if group_info['group_id'] == toUUID(group_id):
                target_group = group_info
    if target_group is None:
        print("\033[31mError: cannot found target guild")
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
                'guid': toUUID(uuid.UUID("00000000-0000-0000-0000-000000000000")),
                'instance_id': item['key']['InstanceId']['value']
            })
            remove_instance_ids.append(item['key']['InstanceId']['value'])

    remove_guilds = []
    for group_data in wsd['GroupSaveDataMap']['value']:
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            group_info = group_data['value']['RawData']['value']
            delete_g_players = []
            for g_player in group_info['players']:
                if g_player['player_uid'] == player_uid:
                    delete_g_players.append(g_player)
                    print(
                        "\033[31mDelete player \033[93m %s \033[31m on guild \033[93m %s \033[0m [\033[92m %s \033[0m] " % (
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
                        "\033[31mDelete guild [\033[92m %s \033[31m] character handle GUID \033[92m %s \033[0m [InstanceID \033[92m %s \033[0m] " % (
                            group_info['group_id'], ind_id['guid'], ind_id['instance_id']))
            for item in remove_items:
                group_info['individual_character_handle_ids'].remove(item)

    print("\033[32mAppend character and players to guild\033[0m")
    target_group['players'].append({
        'player_uid': player_uid,
        'player_info': {
            'last_online_real_time': 0,
            'player_name':
                playerInstance['NickName']['value']
        }
    })
    target_group['individual_character_handle_ids'] += instances


def MigratePlayer(player_uid, new_player_uid):
    load_skiped_decode(wsd, ['MapObjectSaveData'], False)

    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print("\033[33mWarning: Player Sav file Not exists: %s\033[0m" % player_sav_file)
        return
    new_player_sav_file = os.path.dirname(
        os.path.abspath(args.filename)) + "/Players/" + new_player_uid.upper().replace("-", "") + ".sav"
    DeletePlayer(new_player_uid)

    player_uid = player_gvas['PlayerUId']['value']
    player_gvas['PlayerUId']['value'] = toUUID(uuid.UUID(new_player_uid))
    player_gvas['IndividualId']['value']['PlayerUId']['value'] = player_gvas['PlayerUId']['value']
    player_gvas['IndividualId']['value']['InstanceId']['value'] = toUUID(uuid.uuid4())
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
        if str(item['key']['PlayerUId']['value']) == str(player_uid) and \
                'IsPlayer' in player and player['IsPlayer']['value']:
            item['key']['PlayerUId']['value'] = player_gvas['PlayerUId']['value']
            item['key']['InstanceId']['value'] = player_gvas['IndividualId']['value']['InstanceId']['value']
            print(
                "\033[32mMigrate User\033[0m  UUID: %s  Level: %d  CharacterID: \033[93m%s\033[0m" % (
                    str(item['key']['InstanceId']['value']), player['Level']['value'] if 'Level' in player else -1,
                    player['NickName']['value']))
        elif 'OwnerPlayerUId' in player and str(player['OwnerPlayerUId']['value']) == str(player_uid):
            player['OwnerPlayerUId']['value'] = toUUID(uuid.UUID(new_player_uid))
            player['OldOwnerPlayerUIds']['value']['values'] = [player['OwnerPlayerUId']['value']]
            print(
                "\033[32mMigrate Pal\033[0m  UUID: %s  Owner: %s  CharacterID: %s" % (
                    str(item['key']['InstanceId']['value']), str(player['OwnerPlayerUId']['value']),
                    player['CharacterID']['value']))
    for group_data in wsd['GroupSaveDataMap']['value']:
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            item = group_data['value']['RawData']['value']
            for player in item['players']:
                if str(player['player_uid']) == str(player_uid):
                    player['player_uid'] = player_gvas['PlayerUId']['value']
                    print(
                        "\033[32mMigrate User from Guild\033[0m  \033[93m%s\033[0m   [\033[92m%s\033[0m] Last Online: %d" % (
                            player['player_info']['player_name'], str(player['player_uid']),
                            player['player_info']['last_online_real_time']))
                    remove_handle_ids = []
                    for ind_char in item['individual_character_handle_ids']:
                        if str(ind_char['guid']) == str(player_uid):
                            remove_handle_ids.append(ind_char)
                            print("\033[31mDelete Guild Character InstanceID %s \033[0m" % str(ind_char['instance_id']))
                    for remove_handle in remove_handle_ids:
                        item['individual_character_handle_ids'].remove(remove_handle)
                    item['individual_character_handle_ids'].append({
                        'guid': player_gvas['PlayerUId']['value'],
                        'instance_id': player_gvas['IndividualId']['value']['InstanceId']['value']
                    })
                    print("\033[32mAppend Guild Character InstanceID %s \033[0m" % (
                        str(player_gvas['IndividualId']['value']['InstanceId']['value'])))
                    break
            if str(item['admin_player_uid']) == str(player_uid):
                item['admin_player_uid'] = player_gvas['PlayerUId']['value']
                print("\033[32mMigrate Guild Admin \033[0m")
    for map_data in wsd['MapObjectSaveData']['value']['values']:
        if str(map_data['Model']['value']['RawData']['value']['build_player_uid']) == str(player_uid):
            map_data['Model']['value']['RawData']['value']['build_player_uid'] = player_gvas['PlayerUId']['value']
            print(
                "\033[32mMigrate Building\033[0m  \033[93m%s\033[0m" % (
                    str(map_data['MapObjectInstanceId']['value'])))
    print("Finish to migrate player from Save, please delete this file manually: %s" % player_sav_file)


class MappingCache:
    PlayerIdMapping = None
    CharacterSaveParameterMap = None
    MapObjectSaveData = None
    MapObjectSpawnerInStageSaveData = None
    ItemContainerSaveData = None
    DynamicItemSaveData = None
    CharacterContainerSaveData = None
    GroupSaveDataMap = None


def LoadMapObjectMaps():
    load_skiped_decode(wsd, ['MapObjectSaveData', 'MapObjectSpawnerInStageSaveData'], False)
    MappingCache.MapObjectSaveData = {
        mapobj['MapObjectInstanceId']['value']: mapobj for mapobj in
        wsd['MapObjectSaveData']['value']['values']}
    MappingCache.MapObjectSaveDataIndex = {
        mapobj['MapObjectInstanceId']['value']: idx for idx, mapobj in
        enumerate(wsd['MapObjectSaveData']['value']['values'])
    }
    MappingCache.MapObjectSpawnerInStageSaveData = {
        mapObj['key']: mapObj
        for mapObj in
        wsd['MapObjectSpawnerInStageSaveData']['value'][0]['value']['SpawnerDataMapByLevelObjectInstanceId']['value']
    }
    MappingCache.MapObjectSpawnerInStageSaveDataIndex = {
        mapObj['key']: idx
        for idx, mapObj in
        enumerate(wsd['MapObjectSpawnerInStageSaveData']['value'][0]['value']['SpawnerDataMapByLevelObjectInstanceId'][
                      'value'])
    }


def LoadCharacterSaveParameterMap():
    MappingCache.CharacterSaveParameterMap = {character['key']['InstanceId']['value']: character for character in
                                              wsd['CharacterSaveParameterMap']['value']}
    MappingCache.PlayerIdMapping = {character['key']['PlayerUId']['value']: character for character in
                                    filter(lambda x: 'IsPlayer' in
                                                     x['value']['RawData']['value']['object']['SaveParameter']['value'],
                                           wsd['CharacterSaveParameterMap']['value'])}


def LoadItemContainerMaps():
    load_skiped_decode(wsd, ['ItemContainerSaveData', 'DynamicItemSaveData'], False)
    MappingCache.ItemContainerSaveData = {container['key']['ID']['value']: container for container in
                                          wsd['ItemContainerSaveData']['value']}
    MappingCache.DynamicItemSaveData = {dyn_item_data['ID']['value']['LocalIdInCreatedWorld']['value']: dyn_item_data
                                        for
                                        dyn_item_data in wsd['DynamicItemSaveData']['value']['values']}


def LoadCharacterContainerMaps():
    load_skiped_decode(wsd, ['CharacterContainerSaveData'], False)
    MappingCache.CharacterContainerSaveData = {container['key']['ID']['value']: container for container in
                                               wsd['CharacterContainerSaveData']['value']}


def LoadGroupSaveDataMap():
    MappingCache.GroupSaveDataMap = {group['key']: group for group in wsd['GroupSaveDataMap']['value']}


def BatchDeleteMapObject(map_object_ids):
    load_skiped_decode(wsd, ['MapObjectSpawnerInStageSaveData'], False)
    if MappingCache.MapObjectSaveData is None:
        LoadMapObjectMaps()

    delete_map_object_ids = {}
    delete_item_container_ids = []
    delete_owners = {}
    for map_object_id in map_object_ids:
        map_object_id = toUUID(map_object_id)
        if map_object_id not in MappingCache.MapObjectSaveData:
            continue
        delete_map_object_ids[map_object_id] = None
        mapObject = MappingCache.MapObjectSaveData[map_object_id]
        for concrete in mapObject['ConcreteModel']['value']['ModuleMap']['value']:
            if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
                delete_item_container_ids.append(concrete['value']['RawData']['value']['target_container_id'])
        owner_spawner_level_object_instance_id = mapObject['Model']['value']['RawData']['value'][
            'owner_spawner_level_object_instance_id']
        delete_owners[owner_spawner_level_object_instance_id] = None

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
    print(f"Delete MapObjectSaveData: {len(delete_map_object_ids.keys())} / {len(map_object_ids)}")
    LoadMapObjectMaps()


def DeleteMapObject(map_object_id):
    load_skiped_decode(wsd, ['MapObjectSpawnerInStageSaveData'], False)
    if MappingCache.MapObjectSaveData is None:
        LoadMapObjectMaps()
    if toUUID(map_object_id) not in MappingCache.MapObjectSaveData:
        print(f"Error: Map Object {map_object_id} not found")
        return False
    mapObject = MappingCache.MapObjectSaveData[toUUID(map_object_id)]
    try:
        print(f"Delete MapObjectSaveData {map_object_id}")
        wsd['MapObjectSaveData']['value']['values'].remove(mapObject)
    except ValueError:
        return False
    # MapObjectConcreteModelInstanceId = mapObject['MapObjectConcreteModelInstanceId']['value']
    # concrete_model_instance_id = mapObject['Model']['value']['RawValue']['value']['concrete_model_instance_id']   > = Referer To mapObject['ConcreteModel']
    for concrete in mapObject['ConcreteModel']['value']['ModuleMap']['value']:
        if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
            DeleteItemContainer(concrete['value']['RawData']['value']['target_container_id'])
    owner_spawner_level_object_instance_id = mapObject['Model']['value']['RawData']['value'][
        'owner_spawner_level_object_instance_id']
    if owner_spawner_level_object_instance_id in MappingCache.MapObjectSpawnerInStageSaveData:
        mapObjSpawner = parse_item(MappingCache.MapObjectSpawnerInStageSaveData[owner_spawner_level_object_instance_id],
                                   "MapObjectSpawnerInStageSaveData.Value")
        print(
            f"Delete MapObjectSpawnerInStageSaveData {owner_spawner_level_object_instance_id}  Map Object {map_object_id}")
        wsd['MapObjectSpawnerInStageSaveData']['value'][0]['value']['SpawnerDataMapByLevelObjectInstanceId'][
            'value'].remove(mapObjSpawner)

    return True


def DeleteCharacterContainer(characterContainerId):
    if MappingCache.CharacterContainerSaveData is None:
        LoadCharacterContainerMaps()

    characterContainerId = toUUID(characterContainerId)
    if characterContainerId not in MappingCache.CharacterContainerSaveData:
        print(f"Error: Character Container {characterContainerId} not found")
        return False

    container = parse_item(MappingCache.CharacterContainerSaveData[characterContainerId], "CharacterContainerSaveData")
    containerSlots = container['value']['Slots']['value']['values']
    deleteCharacterIds = []
    for slotItem in containerSlots:
        if slotItem['IndividualId']['value']['InstanceId']['value'] != "00000000-0000-0000-0000-000000000000":
            deleteCharacterIds.append(slotItem['IndividualId']['value']['InstanceId']['value'])

    for character_id in deleteCharacterIds:
        DeleteCharacter(character_id)

    print(f"Delete Characher Container {characterContainerId}")
    wsd['CharacterContainerSaveData']['value'].remove(container)
    LoadCharacterContainerMaps()


def DeleteCharacter(characterId):
    if MappingCache.CharacterSaveParameterMap is None:
        LoadCharacterSaveParameterMap()

    characterId = toUUID(characterId)
    if characterId not in MappingCache.CharacterSaveParameterMap:
        print(f"Error: Character {characterId} not found")
        return False
    character = MappingCache.CharacterSaveParameterMap[characterId]
    characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
    if 'EquipItemContainerId' in characterData:
        DeleteItemContainer(characterData['EquipItemContainerId']['value']['ID']['value'])

    if 'group_id' in character['value']['RawData']['value']:
        if MappingCache.GroupSaveDataMap is None:
            LoadGroupSaveDataMap()
        try:
            group = MappingCache.GroupSaveDataMap[character['value']['RawData']['value']['group_id']]
            for idx, ind in enumerate(group['value']['RawData']['value']['individual_character_handle_ids']):
                if ind['instance_id'] == characterId:
                    print(
                        f"Delete Chracater {characterId} group {character['value']['RawData']['value']['group_id']} instances")
                    del group['value']['RawData']['value']['individual_character_handle_ids'][idx]
                    break
        except KeyError:
            pass

    if 'SlotID' in characterData:
        if MappingCache.CharacterContainerSaveData is None:
            LoadCharacterContainerMaps()
        try:
            characterContainer = parse_item(MappingCache.CharacterContainerSaveData[
                                                characterData['SlotID']['value']['ContainerId']['value']['ID'][
                                                    'value']], "CharacterContainerSaveData")
            for slotItem in characterContainer['value']['Slots']['value']['values']:
                if slotItem['RawData']['value']['instance_id'] == characterId:
                    characterContainer['value']['Slots']['value']['values'].remove(slotItem)
                    print(
                        f"Delete Character {characterId} from CharacterContainer {characterData['SlotID']['value']['ContainerId']['value']['ID']['value']}")
                    break
        except KeyError:
            pass
    try:
        wsd['CharacterSaveParameterMap']['value'].remove(character)
    except ValueError:
        return False
    LoadCharacterSaveParameterMap()
    return True


def FindReferenceItemContainerIds():
    load_skiped_decode(wsd, ['MapObjectSaveData'], False)
    reference_ids = []

    for mapObject in wsd['MapObjectSaveData']['value']['values']:
        for concrete in mapObject['ConcreteModel']['value']['ModuleMap']['value']:
            if concrete['key'] == "EPalMapObjectConcreteModelModuleType::ItemContainer":
                reference_ids.append(concrete['value']['RawData']['value']['target_container_id'])

    for character in wsd['CharacterSaveParameterMap']['value']:
        characterData = character['value']['RawData']['value']['object']['SaveParameter']['value']
        if 'EquipItemContainerId' in characterData:
            reference_ids.append(characterData['EquipItemContainerId']['value']['ID']['value'])
            
    for baseCamp in wsd['BaseCampSaveData']['value']:
        reference_ids.append(baseCamp['value']['WorkerDirector']['value']['RawData']['value']['container_id'])
    
    return reference_ids

def GetReferencedItemContainerIdsByPlayer(player_uid):
    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print(f"\033[33mWarning: Player Sav file for {player_uid} Not exists: %s\033[0m" % player_sav_file)
        return []
    player_container_ids = []
    for key in ['OtomoCharacterContainerId', 'PalStorageContainerId']:
        player_container_ids.append(player_gvas[key]['value']['ID']['value'])

    for key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
        player_container_ids.append(player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])
    return player_container_ids


def FindAllUnreferencedItemContainerIds():
    LoadCharacterSaveParameterMap()
    LoadItemContainerMaps()
    referencedContainerIds = set(FindReferenceItemContainerIds())
    allContainerIds = set(MappingCache.ItemContainerSaveData.keys())
    for playerId in playerMapping:
        referencedContainerIds.update(GetReferencedItemContainerIdsByPlayer(playerId))

    return list(allContainerIds - referencedContainerIds)


def BatchDeleteUnreferencedItemContainers():
    unreferencedContainerIds = FindAllUnreferencedItemContainerIds()
    print(f"Delete Non-Referenced Item Containers: {len(unreferencedContainerIds)}")
    BatchDeleteItemContainer(unreferencedContainerIds)

def BatchDeleteItemContainer(itemContainerIds):
    LoadItemContainerMaps()

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
            if dynamicItemId == '00000000-0000-0000-0000-000000000000':
                continue
            if dynamicItemId not in MappingCache.DynamicItemSaveData:
                print(
                    f"\033[31m  Error missed DynamicItemContainer UUID [\033[33m {str(dynamicItemId)}\033[0m]  Item \033[32m {slotItem['ItemId']['value']['StaticId']['value']} \033[0m")
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
    LoadItemContainerMaps()


def DeleteItemContainer(itemContainerId):
    if MappingCache.ItemContainerSaveData is None:
        LoadItemContainerMaps()

    itemContainerId = toUUID(itemContainerId)
    if itemContainerId not in MappingCache.ItemContainerSaveData:
        print(f"Error: Item Container {itemContainerId} not found")
        return False

    container = parse_item(MappingCache.ItemContainerSaveData[itemContainerId], "ItemContainerSaveData")
    containerSlots = container['value']['Slots']['value']['values']
    for slotItem in containerSlots:
        dynamicItemId = slotItem['ItemId']['value']['DynamicId']['value']['LocalIdInCreatedWorld']['value']
        if dynamicItemId == '00000000-0000-0000-0000-000000000000':
            continue
        if dynamicItemId not in MappingCache.DynamicItemSaveData:
            print(
                f"\033[31m  Error missed DynamicItemContainer UUID [\033[33m {str(dynamicItemId)}\033[0m]  Item \033[32m {slotItem['ItemId']['value']['StaticId']['value']} \033[0m")
            continue
        print(f"Delete DynamicItemId {dynamicItemId}")
        wsd['DynamicItemSaveData']['value']['values'].remove(MappingCache.DynamicItemSaveData[dynamicItemId])

    print(f"Delete Item Container {itemContainerId}")
    wsd['ItemContainerSaveData']['value'].remove(container)
    LoadItemContainerMaps()


# DeleteMapObject("6137354f-422d-73af-5791-2faf850bdaed")

def DeletePlayer(player_uid, InstanceId=None, dry_run=False):
    if MappingCache.ItemContainerSaveData is None:
        LoadItemContainerMaps()
    load_skiped_decode(wsd, ['ItemContainerSaveData', 'CharacterContainerSaveData', 'MapObjectSaveData'], False)
    if isinstance(player_uid, int):
        player_uid = str(uuid.UUID("%08x-0000-0000-0000-000000000000" % player_uid))

    err, player_gvas, player_sav_file, player_gvas_file = GetPlayerGvas(player_uid)
    if err:
        print("\033[33mWarning: Player Sav file Not exists: %s\033[0m" % player_sav_file)
        return
    player_container_ids = []
    playerInstanceId = None
    if InstanceId is None:
        print("Player Container ID:")
        player_gvas = player_gvas_file.properties['SaveData']['value']
        playerInstanceId = player_gvas['IndividualId']['value']['InstanceId']['value']
        for key in ['OtomoCharacterContainerId', 'PalStorageContainerId']:
            print("  %s" % player_gvas[key]['value']['ID']['value'])

            print("\033[31mDelete Character Container\033[0m  UUID: %s" % (
                str(player_gvas[key]['value']['ID']['value'])))
            if not dry_run:
                DeleteCharacterContainer(player_gvas[key]['value']['ID']['value'])
            player_container_ids.append(player_gvas[key]['value']['ID']['value'])
        for key in ['CommonContainerId', 'DropSlotContainerId', 'EssentialContainerId', 'FoodEquipContainerId',
                    'PlayerEquipArmorContainerId', 'WeaponLoadOutContainerId']:
            print("  %s" % player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])

            print("\033[31mDelete Item Container\033[0m  UUID: %s" % (
                str(player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])))
            if not dry_run:
                DeleteItemContainer(player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])
            player_container_ids.append(player_gvas['inventoryInfo']['value'][key]['value']['ID']['value'])
    else:
        playerInstanceId = InstanceId
    # Remove item from CharacterSaveParameterMap
    for item in wsd['CharacterSaveParameterMap']['value']:
        player = item['value']['RawData']['value']['object']['SaveParameter']['value']
        if str(item['key']['PlayerUId']['value']) == player_uid \
                and 'IsPlayer' in player and player['IsPlayer']['value'] \
                and (InstanceId is None or str(item['key']['InstanceId']['value']) == InstanceId):
            print(
                "\033[31mDelete User\033[0m  UUID: %s  Level: %d  CharacterID: \033[93m%s\033[0m" % (
                    str(item['key']['InstanceId']['value']), player['Level']['value'] if 'Level' in player else -1,
                    player['NickName']['value']))
            if not dry_run:
                DeleteCharacter(item['key']['InstanceId']['value'])
        elif 'OwnerPlayerUId' in player and str(player['OwnerPlayerUId']['value']) == player_uid and InstanceId is None:
            print(
                "\033[31mDelete Pal\033[0m  UUID: %s  Owner: %s  CharacterID: %s" % (
                    str(item['key']['InstanceId']['value']), str(player['OwnerPlayerUId']['value']),
                    player['CharacterID']['value']))
            if not dry_run:
                DeleteCharacter(item['key']['InstanceId']['value'])
        elif 'SlotID' in player and player['SlotID']['value']['ContainerId']['value']['ID'][
            'value'] in player_container_ids and InstanceId is None:
            print(
                "\033[31mDelete Pal\033[0m  UUID: %s  Slot: %s  CharacterID: %s" % (
                    str(item['key']['InstanceId']['value']),
                    str(player['SlotID']['value']['ContainerId']['value']['ID']['value']),
                    player['CharacterID']['value']))
            if not dry_run:
                DeleteCharacter(item['key']['InstanceId']['value'])
    # Remove Item from GroupSaveDataMap
    remove_guilds = []
    for group_data in wsd['GroupSaveDataMap']['value']:
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            item = group_data['value']['RawData']['value']
            for player in item['players']:
                if str(player['player_uid']) == player_uid and InstanceId is None:
                    print(
                        "\033[31mDelete User \033[93m %s \033[0m from Guild\033[0m \033[93m %s \033[0m   [\033[92m%s\033[0m] Last Online: %d" % (
                            player['player_info']['player_name'],
                            item['guild_name'], str(player['player_uid']),
                            player['player_info']['last_online_real_time']))
                    if not dry_run:
                        item['players'].remove(player)
                        if len(item['players']) == 0:
                            DeleteGuild(item['group_id'])
                    break
    for guild in remove_guilds:
        wsd['GroupSaveDataMap']['value'].remove(guild)

    delete_map_ids = []
    for map_data in wsd['MapObjectSaveData']['value']['values']:
        if str(map_data['Model']['value']['RawData']['value']['build_player_uid']) == str(player_uid):
            delete_map_ids.append(map_data['MapObjectInstanceId']['value'])
    if not dry_run:
        BatchDeleteMapObject(delete_map_ids)
    if InstanceId is None:
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


def search_gpid(dicts, level=""):
    isFound = False
    empty_uuid = toUUID("00000000-0000-0000-0000-000000000000")
    if isinstance(dicts, dict):
        for k in dicts:
            if level == "":
                set_loadingTitle("Searching %s" % k)
            if isinstance(dicts[k], UUID) and dicts[k] != empty_uuid:
                isFound = True
                print("wsd%s['%s'] = '%s'" % (level, k, dicts[k]))
            if isinstance(dicts[k], dict) or isinstance(dicts[k], list):
                isFound |= search_gpid(dicts[k], level + "['%s']" % k)
    elif isinstance(dicts, list):
        for idx, l in enumerate(dicts):
            if level == "":
                set_loadingTitle("Searching %s" % l)
            if isinstance(l, UUID) and l != empty_uuid:
                isFound = True
                print("wsd%s[%d] = '%s'" % (level, idx, l))
            if isinstance(l, dict) or isinstance(l, list):
                isFound |= search_gpid(l, level + "[%d]" % idx)
    if level == "":
        set_loadingTitle("")
    return isFound


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
            if level == "":
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
            if level == "":
                set_loadingTitle("Searching %s" % l)
            if isinstance(l, dict) or isinstance(l, list):
                isFound |= search_values(l, key, level + "[%d]" % idx)
    if level == "":
        set_loadingTitle("")
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
                        "\033[33mWarning: Corrupted player struct\033[0m UUID \033[32m %s \033[0m Owner \033[32m %s \033[0m" % (
                            str(item['key']['PlayerUId']['value']), str(playerParams['OwnerPlayerUId']['value'])))
                    pp.pprint(playerParams)
                    playerParams['IsPlayer']['value'] = False
                elif 'NickName' in playerParams:
                    try:
                        playerParams['NickName']['value'].encode('utf-8')
                    except UnicodeEncodeError as e:
                        print(
                            "\033[33mWarning: Corrupted player name\033[0m UUID \033[32m %s \033[0m Player \033[32m %s \033[0m" % (
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
    global guildInstanceMapping
    playerMapping = LoadPlayers(data_source)
    for playerUId in playerMapping:
        playerMeta = playerMapping[playerUId]
        try:
            print("PlayerUId \033[32m %s \033[0m [InstanceID %s %s \033[0m] -> Level %2d  %s" % (
                playerUId,
                "\033[33m" if toUUID(playerUId) in guildInstanceMapping and
                              playerMeta['InstanceId'] == guildInstanceMapping[toUUID(playerUId)] else "\033[31m", playerMeta['InstanceId'],
                playerMeta['Level'] if 'Level' in playerMeta else -1, playerMeta['NickName']))
        except UnicodeEncodeError as e:
            print("Corrupted Player Name \033[31m %s \033[0m PlayerUId \033[32m %s \033[0m [InstanceID %s %s \033[0m]" %
                  (repr(playerMeta['NickName']), playerUId, "\033[33m" if toUUID(playerUId) in guildInstanceMapping and
                                        playerMeta['InstanceId'] == guildInstanceMapping[toUUID(playerUId)] else "\033[31m",
                                        playerMeta['InstanceId']))
        except KeyError:
            print("PlayerUId \033[32m %s \033[0m [InstanceID %s %s \033[0m] -> Level %2d" % (
                playerUId,
                "\033[33m" if toUUID(playerUId) in guildInstanceMapping and
                              playerMeta['InstanceId'] == guildInstanceMapping[toUUID(playerUId)] else "\033[31m", playerMeta['InstanceId'],
                playerMeta['Level'] if 'Level' in playerMeta else -1))


def FixMissing(dry_run=False):
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
                removeItems.append(item)
    if not dry_run:
        for item in removeItems:
            wsd['CharacterSaveParameterMap']['value'].remove(item)


def FixCaptureLog(dry_run=False):
    if MappingCache.CharacterSaveParameterMap is None:
        LoadCharacterSaveParameterMap()

    for group_data in wsd['GroupSaveDataMap']['value']:
        if str(group_data['value']['GroupType']['value']['value']) == "EPalGroupType::Guild":
            item = group_data['value']['RawData']['value']
            removeItems = []
            for ind_char in item['individual_character_handle_ids']:
                if ind_char['instance_id'] not in MappingCache.CharacterSaveParameterMap:
                    print("    \033[31mInvalid Character %s\033[0m" % (str(ind_char['instance_id'])))
                    removeItems.append(ind_char)
            print("After remove character count: %d" % (len(
                group_data['value']['RawData']['value']['individual_character_handle_ids']) - len(removeItems)))
            if dry_run:
                for rm_item in removeItems:
                    item['individual_character_handle_ids'].remove(rm_item)


def FixDuplicateUser(dry_run=False):
    # Remove Unused in CharacterSaveParameterMap
    removeItems = []
    for item in wsd['CharacterSaveParameterMap']['value']:
        if "00000000-0000-0000-0000-000000000000" != str(item['key']['PlayerUId']['value']):
            player_meta = item['value']['RawData']['value']['object']['SaveParameter']['value']
            if item['key']['PlayerUId']['value'] not in guildInstanceMapping:
                print(
                    "\033[31mInvalid player on CharacterSaveParameterMap\033[0m  PlayerUId: %s  InstanceID: %s  Nick: %s" % (
                        str(item['key']['PlayerUId']['value']), str(item['key']['InstanceId']['value']),
                        str(player_meta['NickName']['value'])))
                removeItems.append(item)
            elif item['key']['InstanceId']['value'] != guildInstanceMapping[item['key']['PlayerUId']['value']]:
                print(
                    "\033[31mDuplicate player on CharacterSaveParameterMap\033[0m  PlayerUId: %s  InstanceID: %s  Nick: %s" % (
                        str(item['key']['PlayerUId']['value']), str(item['key']['InstanceId']['value']),
                        str(player_meta['NickName']['value'])))
                removeItems.append(item)
    if not dry_run:
        for item in removeItems:
            wsd['CharacterSaveParameterMap']['value'].remove(item)


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
                    guildInstanceMapping[ind_char['guid']] = ind_char['instance_id']
            print()


def DeleteCharacterByContainerId(containerId):
    removeItemList = list(
        filter(lambda x: "SlotID" in x['value']['RawData']['value']['object']['SaveParameter']['value'] and
                         str(x['value']['RawData']['value']['object']['SaveParameter']['value']['SlotID']['value'][
                                 'ContainerId']['value']['ID']['value']) == str(containerId),
               wsd['CharacterSaveParameterMap']['value']))
    for item in removeItemList:
        print(
            f"Delete Character UUID {item['key']['PlayerUId']['value']}  InstanceID {item['key']['InstanceId']['value']}")
        wsd['CharacterSaveParameterMap']['value'].remove(item)
    return [x['key']['InstanceId']['value'] for x in removeItemList]


def DeleteBaseCamp(base_id, group_id=None):
    baseCampMapping = {str(base['key']): base for base in wsd['BaseCampSaveData']['value']}
    groupMapping = {str(group['key']): group for group in wsd['GroupSaveDataMap']['value']}
    workDataMapping = {str(wrk['RawData']['value']['id']): wrk for wrk in wsd['WorkSaveData']['value']['values']}
    if group_id is not None and str(group_id) in groupMapping:
        group_data = groupMapping[str(group_id)]['value']['RawData']['value']
        print(f"Delete Group UUID {group_id}  Base Camp ID {base_id}")
        if base_id in group_data['base_ids']:
            idx = group_data['base_ids'].index(base_id)
            if len(group_data['base_ids']) == len(group_data['map_object_instance_ids_base_camp_points']):
                group_data['base_ids'].remove(base_id)
                group_data['map_object_instance_ids_base_camp_points'].pop(idx)
            else:
                group_data['base_ids'].remove(base_id)
    if str(base_id) not in baseCampMapping:
        print(f"Error: Base camp {base_id} not found")
        return False
    baseCamp = baseCampMapping[str(base_id)]['value']
    group_data = None
    if str(baseCamp['RawData']['value']['group_id_belong_to']) in groupMapping:
        group_data = groupMapping[str(baseCamp['RawData']['value']['group_id_belong_to'])]['value']['RawData']['value']
        if base_id in group_data['base_ids']:
            print(f"Delete Group UUID {baseCamp['RawData']['value']['group_id_belong_to']}  Base Camp ID {base_id}")
            group_data['base_ids'].remove(base_id)
        if str(baseCamp['RawData']['value']['owner_map_object_instance_id']) in group_data[
            'map_object_instance_ids_base_camp_points']:
            print(
                f"Delete Group UUID {baseCamp['RawData']['value']['group_id_belong_to']}  Map Instance ID {baseCamp['RawData']['value']['owner_map_object_instance_id']}")
            group_data['map_object_instance_ids_base_camp_points'].remove(
                baseCamp['RawData']['value']['owner_map_object_instance_id'])
    for wrk_id in baseCamp['WorkCollection']['value']['RawData']['value']['work_ids']:
        if str(wrk_id) in workDataMapping:
            print(f"Delete Base Camp Work Collection {wrk_id}")
            wsd['WorkSaveData']['value']['values'].remove(workDataMapping[(str(wrk_id))])
        else:
            print(f"Ignore Base Camp Work Collection {wrk_id}")
    instanceIds = DeleteCharacterByContainerId(baseCamp['WorkerDirector']['value']['RawData']['value']['container_id'])
    if group_data is not None:
        for instance in list(
                filter(lambda x: x['instance_id'] in instanceIds, group_data['individual_character_handle_ids'])):
            print(
                f"Remove Character Instance {instance['guid']}  {instance['instance_id']} from Group individual_character_handle_ids")
            group_data['individual_character_handle_ids'].remove(instance)
    wsd['BaseCampSaveData']['value'].remove(baseCampMapping[str(base_id)])
    return True


def DeleteGuild(group_id):
    groupMapping = {str(group['key']): group for group in wsd['GroupSaveDataMap']['value']}
    if str(group_id) not in groupMapping:
        return False
    group_info = groupMapping[str(group_id)]['value']['RawData']['value']
    for base_id in group_info['base_ids']:
        DeleteBaseCamp(base_id, group_id)
    print("\033[31mDelete Guild\033[0m \033[93m %s \033[0m  UUID: %s" % (
        group_info['guild_name'], str(group_info['group_id'])))
    wsd['GroupSaveDataMap']['value'].remove(groupMapping[str(group_id)])
    return True


def ShowGuild():
    global guildInstanceMapping
    guildInstanceMapping = {}
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
            print(
                "Guild \033[93m%s\033[0m   Admin \033[96m%s\033[0m  Group ID %s  Base Camp Level: %d Character Count: %d" % (
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
                print(
                    f"    Base ID \033[32m {base_id} \033[0m    Map ID \033[32m {item['map_object_instance_ids_base_camp_points'][base_idx]} \033[0m")
            print()
            for player in mapObjectMeta['players']:
                try:
                    print("    Player \033[93m %-30s \033[0m\t[\033[92m%s\033[0m] Last Online: %s - %s" % (
                        player['player_info']['player_name'], str(player['player_uid']),
                        TickToLocal(player['player_info']['last_online_real_time']),
                        TickToHuman(player['player_info']['last_online_real_time'])))
                except UnicodeEncodeError as e:
                    print("    Player \033[93m %-30s \033[0m\t[\033[92m%s\033[0m] Last Online: %s - %s" % (
                        repr(player['player_info']['player_name']), str(player['player_uid']),
                        TickToLocal(player['player_info']['last_online_real_time']),
                        TickToHuman(player['player_info']['last_online_real_time'])))
            for ind_char in mapObjectMeta['individual_character_handle_ids']:
                guildInstanceMapping[ind_char['guid']] = ind_char['instance_id']
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
                print("%s<%s Type='%s'>\033[95m%d\033[0m</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] == "FloatProperty":
                print("%s<%s Type='%s'>\033[95m%f\033[0m</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] in ["StrProperty", "ArrayProperty", "NameProperty"]:
                print("%s<%s Type='%s'>\033[95m%s\033[0m</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif isinstance(data[key], list):
                print("%s<%s Type='%s'>%s</%s>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[
                    key] else "\033[31munknow struct\033[0m", str(data[key]), key))
            else:
                print("%s<%s Type='%s'>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[
                    key] else "\033[31munknow struct\033[0m"))
                PrettyPrint(data[key], level + 1)
                print("%s</%s>" % ("  " * level, key))


def PrettyPrint(data, level=0):
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
                print("%s<%s Type='%s'>\033[95m%d\033[0m</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] == "FloatProperty":
                print("%s<%s Type='%s'>\033[95m%f\033[0m</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif 'type' in data[key] and data[key]['type'] in ["StrProperty", "ArrayProperty", "NameProperty"]:
                print("%s<%s Type='%s'>\033[95m%s\033[0m</%s>" % (
                    "  " * level, key, data[key]['type'], data[key]['value'], key))
            elif isinstance(data[key], list):
                print("%s<%s Type='%s'>%s</%s>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[
                    key] else "\033[31munknow struct\033[0m", str(data[key]), key))
            else:
                print("%s<%s Type='%s'>" % ("  " * level, key, data[key]['struct_type'] if 'struct_type' in data[
                    key] else "\033[31munknow struct\033[0m"))
                PrettyPrint(data[key], level + 1)
                print("%s</%s>" % ("  " * level, key))


def Save(exit_now=True):
    print("processing GVAS to Sav file...", end="", flush=True)
    if "Pal.PalWorldSaveGame" in gvas_file.header.save_game_class_name or "Pal.PalLocalWorldSaveGame" in gvas_file.header.save_game_class_name:
        save_type = 0x32
    else:
        save_type = 0x31
    sav_file = compress_gvas_to_sav(gvas_file.write(SKP_PALWORLD_CUSTOM_PROPERTIES), save_type)
    print("Done")

    print("Saving Sav file...", end="", flush=True)
    with open(output_path, "wb") as f:
        f.write(sav_file)
    print("Done")
    print("File saved to %s" % output_path)
    if exit_now:
        sys.exit(0)


if __name__ == "__main__":
    main()
