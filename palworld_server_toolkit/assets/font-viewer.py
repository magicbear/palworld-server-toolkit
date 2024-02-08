import tkinter as tk
import tkinter.font
import time
import matplotlib.font_manager
from fontTools import ttLib
from PIL import ImageFont
from fontTools.ttLib.ttFont import TTFont

from enum import IntEnum
from fontTools.ttLib.tables._n_a_m_e import NameRecord
from fontTools.ttLib.ttFont import TTFont
from fontTools.unicode import Unicode

class NameID(IntEnum):
    COPYRIGHT = 0
    FAMILY_NAME = 1
    SUBFAMILY_NAME = 2
    UNIQUE_ID = 3
    FULL_NAME = 4
    VERSION_STRING = 5
    POSTSCRIPT_NAME = 6
    TRADEMARK = 7
    MANUFACTURER = 8
    DESIGNER = 9
    DESCRIPTION = 10
    VENDOR_URL = 11
    DESIGNER_URL = 12
    LICENSE_DESCRIPTION = 13
    LICENSE_URL = 14
    TYPOGRAPHIC_FAMILY_NAME = 16
    TYPOGRAPHIC_SUBFAMILY_NAME = 17
    MAC_FULL_NAME = 18
    SAMPLE_TEXT = 19
    POSTSCRIPT_CID_FINDFONT_NAME = 20
    WWS_FAMILY_NAME = 21
    WWS_SUBFAMILY_NAME = 22
    LIGHT_BACKGROUND = 23
    DARK_BACKGROUND = 24
    VARIATIONS_PREFIX_NAME = 25


def sort_naming_table(names: list[NameRecord]) -> list[NameRecord]:
    """
    Parameters:
        names (List[NameRecord]): Naming table
    Returns:
        The sorted naming table
    """

    def is_english(name: NameRecord) -> bool:
        return (name.platformID, name.langID) in ((1, 0), (3, 0x409))

    PLATFORM_ID_APPLE_UNICODE = 0
    PLATFORM_ID_MACINTOSH = 1
    PLATFORM_ID_ISO = 2
    PLATFORM_ID_MICROSOFT = 3
    PLATFORM_ID_ORDER = [
        PLATFORM_ID_MICROSOFT,
        PLATFORM_ID_APPLE_UNICODE,
        PLATFORM_ID_MACINTOSH,
        PLATFORM_ID_ISO,
    ]

    return sorted(
        names,
        key=lambda name: (
            PLATFORM_ID_ORDER.index(name.platformID),
            name.nameID,
            name.platEncID,
            -is_english(name),
            name.langID,
        ),
    )


def get_name_by_id(names: list[NameRecord], nameID: int, ) -> str:
    """
    Parameters:
        names (List[NameRecord]): Naming table
        nameID (int): ID of the name you search
    Returns:
        The decoded name
    """

    names = list(filter(lambda name: name.nameID == nameID, names))
    names = sort_naming_table(names)

    for name in names:
        try:
            name_str = name.toUnicode()
        except UnicodeDecodeError:
            continue

        return name_str

root = tk.Tk()
root.title('Font Families')
fonts = list(tk.font.families())
fonts.sort()

font_lists = []
def assign_font():
    t1 = time.time()
    for item, label in font_lists:
        if item in ['Noto Color Emoji']:
            continue
        # if time.time() - t1 > 1:
        # root.update()
            # t1 = time.time()
        # time.sleep(0.1)

def populate(frame):
    '''Put in the fonts'''
    listnumber = 1
    for filename in matplotlib.font_manager.findSystemFonts():
        try:
            font = TTFont(filename, fontNumber=0)
            isChinese = False
            for tbl in font['cmap'].tables:
                isChinese |= 'uni4E2D' in tbl.cmap.values()  # '中'
            # if not isChinese:
            #     continue
            print(f"File: {filename}, family name: {get_name_by_id(font['name'].names, NameID.FAMILY_NAME)} - {get_name_by_id(font['name'].names, NameID.TYPOGRAPHIC_FAMILY_NAME)}")
    
            # Handle TTC font
            if hasattr(font.reader, "numFonts") and font.reader.numFonts > 1:
                for index in range(1, font.reader.numFonts):
                    font = TTFont(filename, fontNumber=index)
                    print(f"File: {filename}, family name: {get_name_by_id(font['name'].names, NameID.FAMILY_NAME)}")

            font = ImageFont.FreeTypeFont(filename)
            name, weight = font.getname()
            label = tk.Label(frame, text=f"{name} - {weight}%s - Test Width" % (" - 中文字体" if isChinese else ""))
            label.pack(anchor=tk.W)
            label.config(font=(name, 12))
            font_lists.append((name, label))
            listnumber += 1
        except OSError:
            print("Invalid font %s" % filename)

def onFrameConfigure(canvas):
    '''Reset the scroll region to encompass the inner frame'''
    canvas.configure(scrollregion=canvas.bbox("all"))
    
canvas = tk.Canvas(root, borderwidth=0, background="#ffffff")
frame = tk.Frame(canvas, background="#ffffff")
vsb = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=vsb.set)

vsb.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)
canvas.create_window((4,4), window=frame, anchor="nw")

frame.bind("<Configure>", lambda event, canvas=canvas: onFrameConfigure(canvas))

populate(frame)

root.update()
assign_font()
root.mainloop()