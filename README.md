# Palworld Server Toolkit

### 幻兽帕鲁服务端工具包

<p align="center">
   <strong>简体中文</strong> | <a href="/README.en.md">English</a>
</p>

<p align='center'>
<img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/magicbear/palworld-server-toolkit?style=for-the-badge">&nbsp;&nbsp;
<img alt="Python" src="https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue">&nbsp;&nbsp;
</p>

世界上最高速的帕鲁服务器存档编辑器, 1.9秒 打开对应转换时间 4分54秒 的约 5.1GB 的JSON。

- 这个工具包可用于在 Palworld 世界间转移角色，允许朋友们将他们的角色转移到彼此的服务器上，而不会失去任何进度。

- 亦可以用于编辑玩家所持有的帕鲁、参数、持有物品、金钱等等数据。

- 亦可以移动玩家的公会、删除营地、删除玩家


---

- [Palworld Server Toolkit](#palworld-server-toolkit)
  - [如何安装](#直接运行)
  - [找到存档文件](#faq)
  - [操作示例](#操作示例)
  - [跨服务器迁移玩家数据](#跨服务器迁移玩家数据)
  - [服务器存档转本地](#服务器存档转本地)
  - [感谢](#感谢)
  - [视频操作教程 - 哔哩哔哩](https://www.bilibili.com/video/BV1s2421A7jX/)


## GUI

![](./docs/img/GUI.png)

## 直接运行

访问 [Release Pages](https://github.com/magicbear/palworld-server-toolkit/releases) 下载运行即可。

## 手动安装

1. Python 3.9或以上版本.
    - Windows用户: 可从 [Microsoft Store下载Python 3.12](https://apps.microsoft.com/detail/9NCVDN91XZQP) or [python.org](https://www.python.org/)

2. 安装 `pip` 包管理器
	- For Linux users: `python -m ensurepip --upgrade`
	- For Windows users: `py -m ensurepip --upgrade`

3. 安装包

	```
	pip3 install palworld-server-toolkit
	```

4. 运行

	```
	python3 -m palworld_server_toolkit.editor [options] <Level.sav>
	```

## 使用源码前置安装需求

1. Python 3.9或以上版本.
    - Windows用户: 可从 [Microsoft Store下载Python 3.12](https://apps.microsoft.com/detail/9NCVDN91XZQP) or [python.org](https://www.python.org/)

2. 通过 `git clone https://github.com/magicbear/palworld-server-toolkit.git` 下载源码

3. 执行 `git submodule update --init --recursive`

## 问题交流

QQ群 139107098

---
## palworld-save-editor

清理捕捉日志，改名，合并不同服务器玩家，删除玩家，迁移坏档等工具包

> [!CAUTION]
> 
> :warning: 此工具是实验性的。 小心数据丢失并 ***务必*** 进行备份。
> 
> 选择的 `Level.sav` 需要在游戏原存档目录下、或者连同 `Players` 一起复制的完整存档、程序会对 `Players` 下的存档文件同时进行操作，否则可能损坏存档。

> [!WARNING]
>
> 删除用户、删除营地、清理未引用的物品库均为测试功能，有导致服务端闪退可能性，请 ***务必*** 进行备份，如碰到问题请提交您的存档到Issues。

> [!NOTE]
> 
> 未加-o参数默认保存文件为`Level_fixed.sav`
>
> 使用源码版本 以下命令 ` -m palworld_server_toolkit.editor` 部份 修改为 `palworld_server_toolkit/editor.py` 运行即可


- 清理捕捉日志及不存在玩家数据 - `python -m palworld_server_toolkit.editor --fix-missing --fix-capture Level.sav`

- 使用GUI修改 `Level.sav` 文件 - `python -i -m palworld_server_toolkit.editor -g -o Level.sav Level.sav`

- 修改 `Level.sav` 文件 - `python -m palworld_server_toolkit.editor -i -o Level.sav Level.sav`

	- `ShowPlayers()` - 列出玩家
	- `FixDuplicateUser()` - 删除多余用户数据
	- `ShowGuild()` - 列出公会及成员列表
	- `BindGuildInstanceId(uid,instance_id)` - 修改公会成员绑定ID
	- `RenamePlayer(uid,new_name)` - 修改玩家名字为 `new_name`
	- `DeletePlayer(uid,InstanceId=None, dry_run=False)` - 删除玩家数据 `InstanceId: 删除指定InstanceId`
	- `DeleteGuild(group_id)` - 删除公会
	- `DeleteBaseCamp(base_id)` - 删除基地
	- `EditPlayer(uid)` - 快速指定玩家数据至变量`player`
	- `MoveToGuild(uid,guild_id)` - 移动玩家至公会`guild_id`
	- `OpenBackup(filename)` - 打开备份`Level.sav`文件并指向变量`backup_wsd`
	- `MigratePlayer(old_uid,new_uid)` - 从`old_uid`向`new_uid`迁移玩家数据
	- `CopyPlayer(old_uid,new_uid, backup_wsd)` - 复制玩家数据 `backup_wsd` 为OpenBackup备份文件 `wsd`为当前主文件
	- `BatchDeleteUnreferencedItemContainers()` - 删除未引用的物品库
	- `FixBrokenDamageRefItemContainer()` - 删除损坏对象
	- `FindInactivePlayer(day)` - 找出<day>天未上线的玩家
	- `Save()` - 保存修改并退出

### 操作示例
> [!IMPORTANT]
> 
> 以下操作均需先退出服务端
> 
> 最后均为把 `Level_fixed.sav` 替换至 `Level.sav` 并启动服务端

#### 跨服务器迁移玩家数据

- 提前工作

	1. 复制旧服务器 `Level.sav` 至 `SaveGames/0/<Server ID>/Old-Level.sav`
	1. 复制旧服务器所有需迁移玩家 `Players/xxxxxxxx000000000000000000000000.sav` 至 `SaveGames/0/<Server ID>/Players/xxxxxxxx000000000000000000000000.sav`

- GUI模式操作

	1. `Source Player Data Source` 选择 `Backup File`
	2. 点击 `Open File` 选择旧服务器存档 `Old-Level.sav`
	3. `Source Player` 选择要迁移的旧玩家
	4. `Target Player` 选择要被替换的玩家（如果目标玩家ID不变，可从`Source Player`拷贝UUID)
	5. 点击 `Copy Player`
	6. 点击 `Save & Exit`
	7. 替换文件 `Level_fixed.sav` 到 `Level.sav`

- 命令模式操作
	1. 使用编辑模式运行 `python -i -m palworld_server_toolkit.editor Level.sav`
	1. 使用以下命令 并所有需迁移玩家执行`CopyPlayer`
		> :warning: UUID 可相同，数据自`backup_wsd`拷贝
		```
		OpenBackup("Old-Level.sav")
		CopyPlayer("xxxxxxxx-0000-0000-0000-000000000000", "xxxxxxxx-0000-0000-0000-000000000000", backup_wsd)
		Save()
		```
	5. \(Optional) 最后删除旧 `xxxxxxxx000000000000000000000001.sav`, 

### 服务器存档转本地

- GUI模式操作

	1. `Source Player` 选择要迁移的旧玩家
	2. `Target Player` 输入 `00000000-0000-0000-0000-000000000001`
	3. 点击 `Migrate Player`
	4. 点击 `Save & Exit`
	5. 替换文件 `Level_fixed.sav` 到 `Level.sav`

### 其他迁移示例

- 本地存档迁移至服务器示例

	1. 复制本地 `Level.sav` 至 `SaveGames/0/<Server ID>/Old-Level.sav`
	> 本地存档通常在
	`C:\Users\<username>\AppData\Local\Pal\Saved\SaveGames\<SteamID>\<World Folder>`

	2. 复制本地 `Players/00000000000000000000000000000001.sav` 至 `SaveGames/0/<Server ID>/Players/00000000000000000000000000000001.sav`
	3. 使用编辑模式运行 `python -i -m palworld_server_toolkit.editor Level.sav`
	4. 使用以下命令
		```
		OpenBackup("Old-Level.sav")
		CopyPlayer("00000000-0000-0000-0000-000000000001", "xxxxxxxx-0000-0000-0000-000000000000", backup_wsd)
		Save()
		```
	5. \(Optional) 最后删除旧 `00000000000000000000000000000001.sav` 和 `Old-Level.sav`

- 迁移用户示例

	1. 使用编辑模式运行 `python -i -m palworld_server_toolkit.editor Level.sav`
	2. 使用以下命令 
		```
		MigratePlayer("xxxxxxxx-0000-0000-0000-000000000000","yyyyyyyy-0000-0000-0000-000000000000")
		Save()
		```

- 清理7天未上线玩家

	1. 使用编辑模式运行 `python -i -m palworld_server_toolkit.editor Level.sav`
	2. 使用以下命令 
		```
		for player_uid in FindInactivePlayer(7): DeletePlayer(player_uid)
		Save()
		```


---
## palworld-player-list
```
usage: palworld-playey-list [-h] [--host HOST] [--port PORT] [--password PASSWORD] [filename]

用于列出服务器Players目录中的玩家名字，PlayerUId，Steam ID

positional arguments:
  filename              Filename of the player sav

options:
  -h, --help            show this help message and exit
  --host HOST, -H HOST  Host for PalWorld Server RCON
  --port PORT, -P PORT  PalWorld Server RCON Port
  --password PASSWORD, -p PASSWORD  RCON密码
```


- 列出玩家 - 在工作目录 `/PalSaved/SaveGames/0/<server id>/Players` 中运行 `python3 list.py`
- 玩家详细 - `python3 list.py <PLAYER HEX UID>`


---

## palworld-server-taskset

把服务端绑定至CPU性能核 (Linux only)

---

# FAQ

- 复制玩家为将角色及其所有队伍和终端中的伙伴、角色身上的物品以及进度转移，但不会转移任何地图对象、原世界中箱子里的物品以及基地中工作的伙伴。（如果你想将它们一起转移，请将它们移动到身上/终端中）
- 对于合作模式的存档，存档文件通常位于 `%LocalAppData%\Pal\Saved\SaveGames<SteamID><世界文件夹>`
- 对于Xbox Game Pass玩家的存档，存档文件通常位于 `C:\Users\<用户名>\AppData\Packages\ PocketpairInc.Palworld_ad4psfrxyesvt\SystemAppData\wgs`
- 对于服务器存档，请通过 Steam 进入服务器的文件位置。
- 你需要至少 3 个文件来完成转移：源玩家角色存档文件（在 Players/中），源世界的 level.sav 文件，以及目标世界的 Level.sav 文件
- 对于本地合作模式的存档，如果你是主机，角色文件始终是 `000000...001.sav`
- 对于其他玩家的存档，只需知道他们的 `ID` 在不同世界间不会改变，因此他们在你的合作世界和服务器世界的角色文件名是相同的。
- Windows 用户建议使用 `Windows Terminal` 取代 `cmd`，否则不显示色彩

- 存档结构如下
	- 源世界
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
	- 目标世界
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

## **TODO**
	
- [ ] Cleanup the data on `FoliageGridSaveDataMap`

---

# 感谢

- [palworld-save-tools](https://github.com/cheahjs/palworld-save-tools) 提供了存档解析工具实现
- [PalEdit](https://github.com/EternalWraith/PalEdit) - 提供了帕鲁编辑器
- [PalworldCharacterTransfer](https://github.com/jmkl009/PalworldCharacterTransfer) - 参考了其中的动态物品数据迁移引用概念
- [Palworld Host Save Fix](https://github.com/xNul/palworld-host-save-fix) - 提供了最早期迁移玩家数据的概念

- [https://afdian.net/a/magicbear](https://afdian.net/a/magicbear?tab=home) - 赞助我