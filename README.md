# palworld-server-toolkit
Tools for Palworld servers


### Prerequisites

1. Python 3.9 or newer.
    - Windows users: You can install [Python 3.12 from the Microsoft Store](https://apps.microsoft.com/detail/9NCVDN91XZQP) or from [python.org](https://www.python.org/)

2. Download [https://github.com/cheahjs/palworld-save-tools.git](url) and put `lib` on the same directory

## list.py
Tool for list player's nickname, steam id on server

Usage:

- List player - `python3 list.py` in working directory `/PalSaved/SaveGames/0/<server id>/Players`
- Check player detail - `python3 list.py <PLAYER HEX UID>`


## palworld-cleanup-tools.py

This tools is for cleanup the unreference item, rename the player name, migrate player and delete the player.

- For cleaning the capture log in guild, use the follow command `python palworld-cleanup-tools.py --fix-missing --fix-capture Level.sav`

- For modifiy the `Level.sav` file, use the follow command
`python -i palworld-cleanup-tools.py Level.sav`

	- `ShowPlayers()` - List the Players
	- `FixMissing()` - Remove missing player instance
	- `ShowGuild(fix_capture=False)` - List the Guild and members
	- `RenamePlayer(uid,new_name)` - Rename player to new_name
	- `DeletePlayer(uid,InstanceId=None, dry_run=False)` - Wipe player data from save InstanceId: delete specified InstanceId
	- `EditPlayer(uid)` - Allocate player base meta data to variable `player`
	- `OpenBackup(filename)` - Open Backup Level.sav file and assign to backup_wsd
	- `MigratePlayer(old_uid,new_uid)` - Migrate the player from old PlayerUId to new PlayerUId
	- `CopyPlayer(old_uid,new_uid, backup_wsd)` - Copy the player from old PlayerUId to new PlayerUId `backup_wsd is the OpenBackup file, wsd is current file`
	- `Save()` - Save the file and exit

Migrate difference server to single server sample:

1. The player login to the new server to create player instance for new server, and then stop the server
1. Copy old server `Level.sav` to `SaveGames/0/<Server ID>/Old-Level.sav`
1. Copy old server `Players/xxxxxxxx-0000-0000-0000-000000000000.sav` to `SaveGames/0/<Server ID>/Players/xxxxxxxx-0000-0000-0000-000000000001.sav`
1. Use interactive mode `python -i palworld-cleanup-tools.py Level.sav`
1. Use following command `OpenBackup("Old-Level.sav")`
1. Next step `CopyPlayer("xxxxxxxx-0000-0000-0000-000000000001", "xxxxxxxx-0000-0000-0000-000000000000", backup_wsd)` for every require to migrate player
1. Next step `Save()`
1. And remove all the old `-000000000001.sav`, rename `Level_fixed.sav` to `Level.sav` and start the Palworld Server.


## taskset.py
Tools for set cpu affinity to CPU performance core

---

# palworld-server-toolkit
幻兽帕鲁服务端工具包


### 前置安装需求

1. Python 3.9或以上版本.
    - Windows用户: 可从 [Microsoft Store下载Python 3.12](https://apps.microsoft.com/detail/9NCVDN91XZQP) or [python.org](https://www.python.org/)

2. 下载 [https://github.com/cheahjs/palworld-save-tools.git](url) 并放置 `lib` 在目录下

## list.py
用于列出服务器中的玩家名字，PlayerUId，Steam ID

用法:

- 列出玩家 - 在工作目录 `/PalSaved/SaveGames/0/<server id>/Players` 中运行 `python3 list.py`
- 玩家详细 - `python3 list.py <PLAYER HEX UID>`


## palworld-cleanup-tools.py

清理捕捉日志，改名，合并不同服务器玩家，删除玩家，迁移坏档等工具包

- 清理捕捉日志及不存在玩家数据 - `python palworld-cleanup-tools.py --fix-missing --fix-capture Level.sav`

- 修改 `Level.sav` 文件 - `python -i palworld-cleanup-tools.py Level.sav`

	- `ShowPlayers()` - 列出玩家
	- `FixMissing()` - 删除未引用玩家数据
	- `ShowGuild(fix_capture=False)` - 列出公会及成员列表 `fix_capture=True`为删除多余捕捉日志
	- `RenamePlayer(uid,new_name)` - 修改玩家名字为 `new_name`
	- `DeletePlayer(uid,InstanceId=None, dry_run=False)` - 删除玩家数据 `InstanceId: 删除指定InstanceId`
	- `EditPlayer(uid)` - 快速指定玩家数据至变量`player`
	- `OpenBackup(filename)` - 打开备份`Level.sav`文件并指向变量`backup_wsd`
	- `MigratePlayer(old_uid,new_uid)` - 从`old_uid`向`new_uid`迁移玩家数据
	- `CopyPlayer(old_uid,new_uid, backup_wsd)` - 复制玩家数据 `backup_wsd 为OpenBackup备份文件 wsd为当前主文件`
	- `Save()` - 保存修改并退出


- 跨服务器迁移玩家数据示例

	1. 需迁移的所有玩家登录新服务器创建新用户，然后退出服务端
	1. 复制旧服务器 `Level.sav` 至 `SaveGames/0/<Server ID>/Old-Level.sav`
	1. 复制旧服务器所有需迁移玩家 `Players/xxxxxxxx-0000-0000-0000-000000000000.sav` 至 `SaveGames/0/<Server ID>/Players/xxxxxxxx-0000-0000-0000-000000000001.sav`
	1. 使用编辑模式运行 `python -i palworld-cleanup-tools.py Level.sav`
	1. 使用以下命令 `OpenBackup("Old-Level.sav")`
	1. 下一步对所有需迁移玩家执行 `CopyPlayer("xxxxxxxx-0000-0000-0000-000000000001", "xxxxxxxx-0000-0000-0000-000000000000", backup_wsd)`
	1. 然后保存 `Save()`
	1. 最后删除旧 `-000000000001.sav`, 把 `Level_fixed.sav` 替换至 `Level.sav` 并启动服务端


## taskset.py

把服务端绑定至CPU性能核