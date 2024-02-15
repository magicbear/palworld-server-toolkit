import sys, os
from cx_Freeze import setup, Executable
import shutil

module_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(module_dir, "palworld_server_toolkit"))
sys.path.insert(0, os.path.join(module_dir, "save_tools"))
sys.path.insert(0, os.path.join(module_dir, "palworld_server_toolkit/PalEdit"))
build_options = {
    "build_exe": f"build/exe.{sys.platform}",
    "optimize": 2,
    "silent": 1,
    "silent_level": 2,
    "includes": [],
    "excludes": ["test", "unittest", "html", "pydoc_data"],
    # "zip_include_packages": ["zip_includes", "palworld_save_tools"],
    "zip_exclude_packages": ["*"],
    "replace_paths": [("palworld_server_toolkit/resources", "resources")],
    "include_files": ["palworld_server_toolkit/PalEdit/resources", "palworld_server_toolkit/resources"],
    "zip_includes": [],
}

base = "Win32GUI" if sys.platform == "win32" else None
base = "console"

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

shutil.rmtree(f"build/exe.{sys.platform}/lib/palworld_server_toolkit/PalEdit")