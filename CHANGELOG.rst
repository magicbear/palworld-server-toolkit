Changelog
=========

..
    Please try to update this file in the commits that make the changes.

    To make merging/rebasing easier, we don't manually break lines in here
    when they are too long, so any particular change is just one line.

    To make tracking easier, please add either ``closes #123`` or ``fixes #123``
    to the first line of the commit message. There are more syntaxes at:
    <https://blog.github.com/2013-01-22-closing-issues-via-commit-messages/>.

    Note that they these tags will not actually close the issue/PR until they
    are merged into the "default" branch.

v0.5.8
-------

Feature:

- Copy Bamp Camp feature (beta)

v0.5.7
-------

Feature:

- Item edit with code name #33
- CleanupWorkerSick() on cli
- Delete Attrib for Player

Fix:

- Move Guild feature not work on some case.

v0.5.6
-------

Fix:

- Bug from merge #29

v0.5.4
-------

Feature:

- Editor with scroll
- Editor array with add / del
- Merge from #29 export "Delete Unref Item" and "Delete Damage Object" for cli

v0.5.3
-------

Update:

- For PalEdit
- EnumProperty add

v0.5.2
-------

Change:

- FixBrokenDamageRefItemContainer will not automate delete invalid on EquipItemContainerId and ItemContainerId

v0.5.1
-------

Major

- Performance improvement for copy player
- Performance improvement for delete player

Fix:

- Copy player for boss pals not copy the item containers

v0.5.0
-------

Major

- Performance Improvement

Fix:

- Multiple function loading error

v0.4.9
-------

Major:

- Performance Improvement (upstream palworld-save-tools)

Fix:

- MigratePlayer failed on v0.4.8

v0.4.8
-------

Major:

- MappingCache to be autoloaded, prevent bugs for feature.
- Performance Improvement

Fix:

- Corrupted save file after delete base

v0.4.7
-------

Fix:

- Delete Unreference item containers damage the save file (didn't chk BelongInfo->GroupID reference for ItemContainerSaveData)
- Migrate User will not delete the target user Pals

TODO:

- Check Damage save after delete base

v0.4.6
-------

Fix:

- Not load corrently for Del damange instance

Feature:

- Instance relative to target player

v0.4.5
-------

Fix:

- Cheaters will damange the loading for GUI
- font chagne for open sub editor
- broken flags on the PalEdit
- broken game save when BatchDeleteUnreferencedItemContainers didn't check for ItemContainerId on CharacterSaveParameterMap
- delete Damange Instance feature


v0.4.3
-------

Fix:

- Invalid character for opening cheated file

v0.4.2
-------

Fix:

- Bug for i18n for PalEdit

v0.4.1
-------

Feature:

- i18n For PalEdit

Fix:

- process for invalid player that use cheats

v0.4.0
-------

Feature:

- Item Editor with Autocomplete Combobox 

v0.3.10
-------

Fix:

- Fix BatchDeleteUnreferencedItemContainers failed befure running another feature.

v0.3.9
-------

Merge:
- i18n for Pals (Edit Instance dropdown menu) Pull Request #9 by KrisCris
- BatchDeleteUnreferencedItemContainers by Kakoen

Fix:

- Copy Player group instances bug

v0.3.8
-------

Fix:

- Install packaage fail to install PalEdit for pip

v0.3.7
-------

Major:

- I18n Multiple language support
- Fix bug for packing pip package for PalEdit

v0.3.6
-------

Feature:

- Move Guild Owner Feature 

v0.3.4
-------

Major:

- DeleteMapObject will delete item containers now
- Performance Upgrade for Multiple Functions
- Mapping Cache System

Feature:

- BatchDeleteItemContainers

Fix:

- Loading Cache cause Save Failed
- Edit Player if didn't change Array Value, can not save

v0.3.3
-------

Major:

- GUI Modified for more clearly

Feature:

- Auto complete Combobox for Editory
- Delete Player To Clean More Data
- Delete Item Containers Feature
- Delete Character Containers Feature
- Delete MapSaveData Feature

v0.3.2
-------

Feature:

- Edit Character Instance Feature
- Reconstruct edit player item loading
- Reconstruct editor
- Add interactive function gp to print the Gvas Object cleanly

v0.3.1
-------

Fix:

- Delete Base Camp on GUI with selected Guide will force delete Base Camp
- CopyPlayer Without copy base camp relative variable

v0.3.0
-------

Feature:

- Delete Guild Base Camp Feature
- GUI Select Player auto locate the Guild
- DeleteGuild

v0.2.9
-------

Major:

- Player Save Editor: Add support for inventoryInfo
- CopyPlayer: Add convert for the DynamicItemSaveData

v0.2.8
-------

Major:

- Copy Player: Target allow custom enter UUID

Fixes:

- GUI Copy Player from Local (UUID 00000000-0000-0000-0000-000000000001 will not work)

v0.2.7
-------

Major:

- Update PalEdit for using GvasFile manage

Features:

- Performance improve for loading edit player item and CopyPlayer and DeletePlayer

Fixes:

- Fix Save Error on Fast load feature
- Fix pip dependenices

v0.2.5
-------

Major:

- PalEdit feature
- Player Sav file edti feature
- Reconstruction for Tk usage

Fixed:

- Non UTF-8 encode error catch

v0.2.0
-------

Major:

- Player Item Editor

v0.1.9
-------

Major:
- Player Editor


