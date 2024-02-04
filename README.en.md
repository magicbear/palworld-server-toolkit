# palworld-server-toolkit

### Tools for Palworld servers

<p align="center">
   <a href="/README.md">简体中文</a> | <strong>English</strong>
</p>


<p align='center'>
<img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/magicbear/palworld-server-toolkit?style=for-the-badge">&nbsp;&nbsp;
<img alt="Python" src="https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue">&nbsp;&nbsp;
</p>


### GUI

![](./docs/img/GUI.png)


### Prerequisites

1. Python 3.9 or newer.
    - Windows users: You can install [Python 3.12 from the Microsoft Store](https://apps.microsoft.com/detail/9NCVDN91XZQP) or from [python.org](https://www.python.org/)

2. Use `pip install palworld-save-tools` or `git submodule update --init --recursive` or Download [https://github.com/cheahjs/palworld-save-tools](https://github.com/cheahjs/palworld-save-tools) and put `palworld-save-tools` contents to `save_tools` directory

3. Windows User present use `Windows Terminal` instance of `cmd` for color

---

## list.py
Tool for list player's nickname, steam id on server

- List player - `python3 list.py` in working directory `/PalSaved/SaveGames/0/<server id>/Players`
- Check player detail - `python3 list.py <PLAYER HEX UID>`


---

## palworld-cleanup-tools.py

This tools is for cleanup the unreference item, rename the player name, migrate player and delete the player.

> [!CAUTION]
> 
> :warning: This tool is experimental. Be careful of data loss and *always* make a backup.


> [!NOTE]
> 
> Without -o params, default save file is `Level_fixed.sav`

- For cleaning the capture log in guild, use the follow command `python palworld-cleanup-tools.py --fix-missing --fix-capture Level.sav`

- For GUI to modify `Level.sav` file - `python -i palworld-cleanup-tools.py -g -o Level.sav Level.sav`

- For modifiy the `Level.sav` file, use the follow command
`python -i palworld-cleanup-tools.py -o Level.sav Level.sav`

	- `ShowPlayers()` - List the Players
	- `FixMissing()` - Remove missing player instance
	- `FixCaptureLog()` - Remove invalid caputre log in guild
	- `FixDuplicateUser()` - Remove duplicated user data
	- `ShowGuild()` - List the Guild and members
	- `BindGuildInstanceId(uid,instance_id)` - Update Guild binding instance for user
	- `RenamePlayer(uid,new_name)` - Rename player to new_name
	- `DeletePlayer(uid,InstanceId=None, dry_run=False)` - Wipe player data from save InstanceId: delete specified InstanceId
	- `EditPlayer(uid)` - Allocate player base meta data to variable `player`
	- `MoveToGuild(uid,guild_id)` - Move player to guild `guild_id`
	- `OpenBackup(filename)` - Open Backup Level.sav file and assign to `backup_wsd`
	- `MigratePlayer(old_uid,new_uid)` - Migrate the player from old PlayerUId to new PlayerUId
	- `CopyPlayer(old_uid,new_uid, backup_wsd)` - Copy the player from old PlayerUId to new PlayerUId `backup_wsd` is the OpenBackup file, `wsd` is current file
	- `Save()` - Save the file and exit


### Function screenshot

![](./docs/img/ShowPlayer.png)
![](./docs/img/ShowGuild.png)

### Operate Sample

> [!IMPORTANT]
> 
> ALL OPERATE REQUIRE to STOP SERVER
> 
> Finally is replace `Level_fixed.sav` to `Level.sav` and start Palworld Server.


- Migrate difference server to single server sample:

	1. Copy old server `Level.sav` to `SaveGames/0/<Server ID>/Old-Level.sav`
	2. Copy old server `Players/xxxxxxxx000000000000000000000000.sav` to `SaveGames/0/<Server ID>/Players/xxxxxxxx000000000000000000000000.sav`
	3. Use interactive mode `python -i palworld-cleanup-tools.py Level.sav`
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
	1. Use interactive mode `python -i palworld-cleanup-tools.py Level.sav`
	1. Execute following command 
		```
		OpenBackup("Old-Level.sav")
		CopyPlayer("00000000-0000-0000-0000-000000000001", "xxxxxxxx-0000-0000-0000-000000000000", backup_wsd)
		Save()
		```
	5. remove `00000000000000000000000000000001.sav` and `Old-Level.sav`

- Migrate User

	1. Use interactive mode `python -i palworld-cleanup-tools.py Level.sav`
	1. Execute following command 
		```
		MigratePlayer("xxxxxxxx-0000-0000-0000-000000000000","yyyyyyyy-0000-0000-0000-000000000000")
		Save()
		```


---

## taskset.py
Tools for set cpu affinity to CPU performance core (Linux only)

