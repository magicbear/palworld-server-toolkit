# Palworld Server Toolkit

### Tools for Palworld servers

<p align="center">
   <a href="/README.md">简体中文</a> | <strong>English</strong>
</p>


<p align='center'>
<img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/magicbear/palworld-server-toolkit?style=for-the-badge">&nbsp;&nbsp;
<img alt="Python" src="https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue">&nbsp;&nbsp;
</p>

The world fastest PalWorld server save editor, parse 45MB Level.sav in 1.9s for JSON about 5.1GB, and for convert.py time spent in 4m54s.

- This toolkit transfers character between worlds in Palworld, which allows friends to transfer their characters to each other's server without losing one's progress.

- Also can be edit the Player's Item, Pals, Guilds, Money, etc...

---

- [Palworld Server Toolkit](#palworld-server-toolkit)
  - [Releases](https://github.com/TronickDev/palworld-server-toolkit-auto-update)
  - [How to use install](#Binaries)
  - [Where to find the save-files](#faq)
  - [An example](#operate-sample)
  - [Migrate Data Between Server](#migrate-difference-server-to-single-server)
  - [Migrate server to local](#migrate-server-to-local)
  - [Credits](#acknowledgements)
  - [Video Operate - Chinese on bilibili](https://www.bilibili.com/video/BV1s2421A7jX/)


## GUI

![](./docs/img/GUI.png)	

## Binaries

Visit [Release Pages](https://github.com/magicbear/palworld-server-toolkit/releases) to download and run.


## Manual Install

1. Python 3.9 or newer.
    - Windows users: You can install [Python 3.12 from the Microsoft Store](https://apps.microsoft.com/detail/9NCVDN91XZQP) or from [python.org](https://www.python.org/)

2. Install `pip` Package manager
	- For Linux users: `python -m ensurepip --upgrade`
	- For Windows users: `py -m ensurepip --upgrade`


3. Install by `pip`

	```
	pip3 install palworld-server-toolkit
	```

4. Execute

	```
	python3 -m palworld_server_toolkit.editor [options] <Level.sav>
	```

## Source Code Prerequisites

1. Python 3.9 or newer.
    - Windows users: You can install [Python 3.12 from the Microsoft Store](https://apps.microsoft.com/detail/9NCVDN91XZQP) or from [python.org](https://www.python.org/)
    - Ubuntu users:
      - for 20.04/22.04 `add-apt-repository ppa:deadsnakes/ppa -y; apt update; apt install python3.11-full`

2. Download source code by `git clone https://github.com/magicbear/palworld-server-toolkit.git`

3. Execute `git submodule update --init --recursive`

4. Execute by `python3.11 -i <SRCDIR>/palworld_save_tools/editor.py <Level.sav>`

## Question?

[Discord](https://discord.gg/EQcMD5VQ2q)


---

## palworld-save-editor

This tools is for cleanup the unreference item, rename the player name, migrate player and delete the player.

> [!CAUTION]
> 
> :warning: This tool is experimental. Be careful of data loss and *always* make a backup.
>
> Open `Level.sav` need to be on the SaveGames directory, or copied with `Players`, the editor will also reference to `Players` 's file for working, if you didn't may be corrupted the save file.


> [!WARNING]
>
> Delete user, delete base camp, delete unreference item containers are beta feature, may be cause the server error. Please *always* backup the file, if have any issue, please provide your `Level.sav` file to issues.


> [!NOTE]
> 
> Without -o params, default save file is `Level_fixed.sav`
> 
> Use source code version just replace below command ` -m palworld_server_toolkit.editor` to `palworld_server_toolkit/editor.py`

- For GUI to modify `Level.sav` file - `python -i -m palworld_server_toolkit.editor -g -o Level.sav Level.sav`

- For modify the `Level.sav` file, use the follow command
`python -i -m palworld_server_toolkit.editor -o Level.sav Level.sav`

	- `ShowPlayers()` - List the Players
	- `FixDuplicateUser()` - Remove duplicated user data
	- `ShowGuild()` - List the Guild and members
	- `BindGuildInstanceId(uid,instance_id)` - Update Guild binding instance for user
	- `RenamePlayer(uid,new_name)` - Rename player to new_name
	- `DeletePlayer(uid,InstanceId=None, dry_run=False)` - Wipe player data from save InstanceId: delete specified InstanceId
	- `DeleteGuild(group_id)` - Delete Guild
	- `DeleteBaseCamp(base_id)` - Delete Base Camp
	- `EditPlayer(uid)` - Allocate player base meta data to variable `player`
	- `MoveToGuild(uid,guild_id)` - Move player to guild `guild_id`
	- `OpenBackup(filename)` - Open Backup Level.sav file and assign to `backup_wsd`
	- `MigratePlayer(old_uid,new_uid)` - Migrate the player from old PlayerUId to new PlayerUId
	- `CopyPlayer(old_uid,new_uid, backup_wsd)` - Copy the player from old PlayerUId to new PlayerUId `backup_wsd` is the OpenBackup file, `wsd` is current file
	- `BatchDeleteUnreferencedItemContainers()` - Delete Unreference Item Containers
	- `FixBrokenDamageRefItemContainer()` - Delete Damage Instance
	- `FindInactivePlayer(day)` - Find player that <days> not active
	- `Save()` - Save the file and exit


### Operate Sample

> [!IMPORTANT]
> 
> ALL OPERATE REQUIRE to STOP SERVER
> 
> Finally is replace `Level_fixed.sav` to `Level.sav` and start Palworld Server.


#### Migrate difference server to single server

- Preparing

	1. Copy old server `Level.sav` to `SaveGames/0/<Server ID>/Old-Level.sav`
	2. Copy old server `Players/xxxxxxxx000000000000000000000000.sav` to `SaveGames/0/<Server ID>/Players/xxxxxxxx000000000000000000000000.sav`

- Operate By GUI

	1. Item `Source Player Data Source` Select `Backup File`
	2. Click `Open File` to load old server `Old-Level.sav`
	3. Item `Source Player` to select player that you want to migrate
	4. Item `Target Player` to select player that will be replaced. (if target player ID is the same, can copy the UUID from `Source Player`)
	5. Click `Copy Player`
	6. Click `Save & Exit`
	7. Replace `Level_fixed.sav` to `Level.sav`, enjoy it.

#### Migrate server to local

- Operate By GUI

	1. Item `Source Player` to select player that you want to migrate
	2. Item `Target Player` paste `00000000-0000-0000-0000-000000000001`
	3. Click `Migrate Player`
	4. Click `Save & Exit`
	5. Replace `Level_fixed.sav` to `Level.sav`, enjoy it.


#### Other Migrate

- Operate By Command Line

	3. Use interactive mode `python -i -m palworld_server_toolkit.editor Level.sav`
	4. Execute following command and run `CopyPlayer` for each migrate player
		> :warning: UUID can be the same, the user data will be copy from `backup_wsd`
		```
		OpenBackup("Old-Level.sav")
		CopyPlayer("xxxxxxxx-0000-0000-0000-000000000000", "xxxxxxxx-0000-0000-0000-000000000000", backup_wsd)
		Save()
		```
	5. \(Optional) remove all the old `xxxxxxxx000000000000000000000000.sav` and `Old-Level.sav`

- Migrate Local save to server:

	1. Copy local save `Level.sav` to `SaveGames/0/<Server ID>/Old-Level.sav`
	> For co-op saves, they are usually at
	`C:\Users\<username>\AppData\Local\Pal\Saved\SaveGames\<SteamID>\<World Folder>`

	1. Copy local `Players/00000000000000000000000000000001.sav` to `SaveGames/0/<Server ID>/Players/00000000000000000000000000000001.sav`
	1. Use interactive mode `python -i -m palworld_server_toolkit.editor Level.sav`
	1. Execute following command 
		```
		OpenBackup("Old-Level.sav")
		CopyPlayer("00000000-0000-0000-0000-000000000001", "xxxxxxxx-0000-0000-0000-000000000000", backup_wsd)
		Save()
		```
	5. remove `00000000000000000000000000000001.sav` and `Old-Level.sav`

- Migrate User

	1. Use interactive mode `python -i -m palworld_server_toolkit.editor Level.sav`
	1. Execute following command 
		```
		MigratePlayer("xxxxxxxx-0000-0000-0000-000000000000","yyyyyyyy-0000-0000-0000-000000000000")
		Save()
		```

- Clean the player that 7 days not online

	1. Use interactive mode `python -i -m palworld_server_toolkit.editor Level.sav`
	1. Execute following command 
		```
		for player_uid in FindInactivePlayer(7): DeletePlayer(player_uid)
		Save()
		```



---

## palworld-player-list
```
usage: palworld-playey-list [-h] [--host HOST] [--port PORT] [--password PASSWORD] [filename]

List player on the Players Folder

positional arguments:
  filename              Filename of the player sav

options:
  -h, --help            show this help message and exit
  --host HOST, -H HOST  Host for PalWorld Server RCON
  --port PORT, -P PORT  PalWorld Server RCON Port
  --password PASSWORD, -p PASSWORD
                        RCON Password
```

- List player - `python3 list.py` in working directory `/PalSaved/SaveGames/0/<server id>/Players`
- Check player detail - `python3 list.py <PLAYER HEX UID>`


---

## palworld-server-taskset
Tools for set cpu affinity to CPU performance core (Linux only)

---

## FAQ

- Copy Player will transfers the character and all its pals on your team and in your inventory, items on the character, and progress. It does not transfer map objects, items in chests and pals working at your base. Move items into your inventory / pals into your team if you want to transfer them.
- The save files are usually located at C:\Users<username>\AppData\Local\Pal\Saved\SaveGames<SteamID><Original Server Folder> for co-op saves.
- For `Xbox Game Pass` Player, save files are usually located at `C:\Users\<User>\AppData\Packages\ PocketpairInc.Palworld_ad4psfrxyesvt\SystemAppData\wgs`
- For server saves, go to the dedicated server's file location through steam.
- u need at least 3 files to complete the transfer:
	- The source player character save file in Players folder
	- The source world's `Level.sav` file
	- The target world's `Level.sav` file
- For co-op saves, the player character save file is always `000000...001.sav`
- For another server saves, their `ID` will not change between worlds, so that have the same name in target server, you only need the source world's `000000...000.sav`
- Windows User present use `Windows Terminal` instance of `cmd` for color

- Data Struct
	- Source World
	```
	SaveGames
	└── <steam-id>
	    └── <source-world-id>
	        ├── backup
	        ├── Level.sav  ----------  <- The source world save-file
	        ├── LevelMeta.sav
	        ├── Players
	        │   ├── 00000...0001.sav
	        │   └── 12345...6789.sav   <- character save-file we want to transfer
	        └── WorldOption.sav
	```
	- Target World
	```
	SaveGames
	└── <steam-id>
	    └── <destination-world-id>
	        ├── backup
	        ├── Level.sav  ----------  <- The target world save-file
	        ├── LevelMeta.sav
	        ├── Players
	        │   ├── 00000...0001.sav   <- the target player-placeholder save-file
	        │   └── 98765...4321.sav
	        └── WorldOption.sav
	```

---

## Acknowledgements

Thanks to

- [palworld-save-tools](https://github.com/cheahjs/palworld-save-tools) for providing save file parsing tool implementation
- [PalEdit](https://github.com/EternalWraith/PalEdit) - GUI for editing Pals
- [PalworldCharacterTransfer](https://github.com/jmkl009/PalworldCharacterTransfer) - Idea for the Dynamic Item Data transfer
- [Palworld Host Save Fix](https://github.com/xNul/palworld-host-save-fix) - Idea for the first to transfer between server
- [palworld-steam-id-to-player-uid](https://github.com/cheahjs/palworld-steam-id-to-player-uid)
- [Buy me a coffee](https://www.buymeacoffee.com/magicbear)