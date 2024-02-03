# palworld-server-toolkit
<p align="center">
   <strong>简体中文</strong> | <a href="/README.en.md">English</a>
</p>
<p align="center">
幻兽帕鲁服务端工具包
</p>

<p align='center'>
<img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/magicbear/palworld-server-toolkit?style=for-the-badge">&nbsp;&nbsp;
<img alt="Python" src="https://img.shields.io/badge/Python-FFD43B?style=for-the-badge&logo=python&logoColor=blue">&nbsp;&nbsp;
</p>



### 前置安装需求

1. Python 3.9或以上版本.
    - Windows用户: 可从 [Microsoft Store下载Python 3.12](https://apps.microsoft.com/detail/9NCVDN91XZQP) or [python.org](https://www.python.org/)

2. 使用 `git submodule update --init --recursive` 或 下载 [https://github.com/cheahjs/palworld-save-tools](https://github.com/cheahjs/palworld-save-tools) 并放置 `palworld-save-tools` 在本工具目录下

---
## list.py
用于列出服务器中的玩家名字，PlayerUId，Steam ID

- 列出玩家 - 在工作目录 `/PalSaved/SaveGames/0/<server id>/Players` 中运行 `python3 list.py`
- 玩家详细 - `python3 list.py <PLAYER HEX UID>`

---
## palworld-cleanup-tools.py

清理捕捉日志，改名，合并不同服务器玩家，删除玩家，迁移坏档等工具包

> ### :warning: 此工具是实验性的。 小心数据丢失并 ***务必*** 进行备份。
> 未加-o参数默认保存文件为`Level_fixed.sav`
	
- 清理捕捉日志及不存在玩家数据 - `python palworld-cleanup-tools.py --fix-missing --fix-capture Level.sav`

- 修改 `Level.sav` 文件 - `python -i palworld-cleanup-tools.py -o Level.sav Level.sav`

	- `ShowPlayers()` - 列出玩家
	- `FixMissing()` - 删除未引用玩家数据
	- `FixCaptureLog()` - 删除多余捕捉日志
	- `FixDuplicateUser()` - 删除多余用户数据
	- `ShowGuild()` - 列出公会及成员列表
	- `BindGuildInstanceId(uid,instance_id)` - 修改公会成员绑定ID
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



### 功能截图

![](./docs/img/ShowPlayer.png)
![](./docs/img/ShowGuild.png)

---

## taskset.py

把服务端绑定至CPU性能核