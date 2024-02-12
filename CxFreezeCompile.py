import sys, os
from cx_Freeze import setup, Executable

build_options = {
    "includes": ["pyperclip"],
    "excludes": [],
    "zip_include_packages": [],
    "include_files": ["save_tools", "palworld_server_toolkit/PalEdit"],
    "zip_includes": ["palworld_server_toolkit/resources/", "palworld_server_toolkit/PalEdit"],
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
