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


