import sys, os
from cx_Freeze import setup, Executable

build_options = {
    "includes": ["pyperclip", "palworld_save_tools"],
    "excludes": [],
    "zip_include_packages": ["zip_includes", "palworld_save_tools"],
    "replace_paths": [("palworld_server_toolkit/resources", "resources")],
    "include_files": ["palworld_server_toolkit/PalEdit", "palworld_server_toolkit/resources"],
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
