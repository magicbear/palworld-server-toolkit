import sys, os
from cx_Freeze import setup, Executable

build_options = {
    "includes": ["pyperclip"],
    "excludes": [],
    "packages": ["palworld_save_tools"],
    "zip_include_packages": ["zip_includes"],
    "replace_paths": [("save_tools/palworld_save_tools", "palworld_save_tools"), ("palworld_server_toolkit/resources", "resources")],
    "include_files": ["palworld_server_toolkit/PalEdit", "save_tools/palworld_save_tools", "palworld_server_toolkit/resources"],
    "zip_includes": [],
}

base = "Win32GUI" if sys.platform == "win32" else None

ver = ""
with open("setup.cfg", "r") as f:
    for line in f:
        line = line.split(" = ")
        if line[0] == "version":
            ver = line[1].strip()

setup(
    name = f"Palworld-Save-Editor {ver}",
    version = ver,
    description = "A simple tool for editing PalWorld saves",
    options={"build_exe": build_options},
    executables=[Executable("palworld_server_toolkit/editor.py", base=base, icon="palworld_server_toolkit/resources/palworld-save-editor.ico")],
)
