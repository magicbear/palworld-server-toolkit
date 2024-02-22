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

0.8.2
-------

Feature:

- Edit GUI for MapProperty

Fix:

- CopyMapObject failed
- Adjust Slots cancel with msg
- _CopyWorkSaveData failed
- Progress stucked on Repair player
- Edit GUI error on Quat Struct

0.8.1
-------

Feature:

- Startup Inteactive Mode in GUI

Fix:

- Edit GUI for ArrayProperty can not multiple edit now
- CopyPlayer error


0.8.0
-------

Feature:

- Status on GUI
- Change Pal Storage Slot Count
- AdjustCharacterContainerSlots
- Change Guild Worker Slot Count

0.7.9
-------

Fix:

- Bug on Edit GUI

v0.7.8
-------

Fix:

- Bug on RepairPlayer
- Copy Instance will replace the item in containers, on the game will be the copied pals replace the old one
- Delete Damange Object delete the MapObject on invalid Workee attribute

Feature:

- Show error msg on corrupted save file
- Have login to steam save convert to no login to steam save (have app_id to no app_id)
- Migrate player to specified Steam ID
- MP loading progress
- Delete Damange Object will delete no CharacterId object

v0.7.7
-------

Fix:

- KeyError on DeleteBaseCamp

v0.7.6
-------

Feature:

- Edit EquipWaza for Pals
- Edit MasteredWaza for Pals
- Edit Guild Info
- PalEdit: Moveset on pals.json  Name -> CodeName
- PalEdit: Pal skill show only available skills on Equipped Skills
- Add no select src/target player prompt
- Logging system, save the log to backup file

Fix:

- Bug for DeleteMapObject
- Attrib transport_item_character_infos for BaseCamp will cause delete character container not work
- FindReferenceMapObject will be raise RecursionError on very deep MapObject
- RepairPlayer will be fail on unavailable Character Container
- PalEdit: Pal skills EPalWazaID::None, None will be failed on loading
- PalEdit: change skills from Name -> CodeName save to skills for i18n
- RepairPlayer make Guild individual_character_handle_ids invalid

Major:

- Improve performance for DeleteMapObject
- implementation for CopyMapObject
- Progress bar for Cleanup Item
- Progress bar for Cleanup Character
- Repair All Player will be throw Exception when can not repair a player
- Copy Player: Ignore the Pals that on the guild, only copy for the teams Pals and the Pal Storage's Pals, ignore
  the Pals that working on the base

v0.7.5
-------

Fix:

- CopyPlayer not change OldOwnerPlayerUIds
- CopyPlayer will be repair the player after copy
- BatchDeleteCharacter will be failed to build structure
- BatchDeleteItemContainer will be failed to build structure
- BatchDeleteCharacterContainer will be failed to build structure

Feature:

- Repair Player would be move duplicated pal storage container with same uid to new pal storage container

v0.7.4
-------

Feature:

- Delete Damange Object will be delete broken BaseCamp, WorkData
- Export Graphviz dot feature
- Delete Damange Object will be delete no character container's character
- Delete Damange Object will be delete broken map spawner
- Edit Instance to Pals only
- Copy Player can be load the Player's save file from the backup Level.sav folder

Fix:

- CopyPlayer on the same save file will be lost the working / base state, and put to PalStorage
- CopyPlayer multiple times on same target UUID will be no pals on character
- Copy Instance will be check for empty slots

v0.7.3
-------

Feature:

- i18n support half translate of language

v0.7.2
-------

Fix:

- OpenBackup cause error on Linux platform
- Migrate Player / Repair Player move Pals that working on base to user Pal Container

v0.7.1
-------

Major:

- Performance upgrade for DeletePlayer
- Remove unused Fix Capture Log
- Merge fix missing to Delete Invalid Object
- Auto backup as a tar file with structure
- Merge PalEdit to 0.6.1

Feature:

- Delete Inactive Player on GUI
- Batch repair all player on GUI
- One key migrate to local feature
- Delete damage object will be also delete invalid map object

v0.6.9
-------

Fix:

- Sub edit feature not working
- Copy player have add error

v0.6.8
-------

Fix:

- Gui Open error
- Memory leak for shared memory

v0.6.7
-------

Feature:

- Repair User Feature
- Delete Damage Object will delete damage container player

Fix:

- Bug for Delete Player
- Bug for Migrate Player: not delete the old player
- Bug for Copy Player: not change the UUID for not exists player

v0.6.6
-------

Major:

- Improve loading speed
- Multi processing loading to increase performance for loading

v0.6.5
-------

Fix:

- Check for Players folder process with wrong

v0.6.4
-------

Feature:

- Add FindInactivePlayer function for cli

Major:

- Auto backup feature, change default save file to the open file
- Auto delete old players file

Fix:

- CopyPlayer on exists player will be share the object before save and open again

v0.6.2
-------

Major:

- Add warning message

v0.6.1
-------

Feature:

- CleanupAllCharacterContainer feature, remove all empty item on character containers

v0.6.0
-------

Feature:

- Copy Instance feature

v0.5.9
-------

Feature:

- Open GUI for drag file to the exe
- Add icons for release

Fix:

- Rename player cannot edit the local save file

v0.5.8
-------

Major:

- Merge palworld_save_tools from upstream
- Merge PalEdit from upstream

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


