import json
import os

from astrbot.api.event import AstrMessageEvent, filter
from gamercon_async import GameRCON


class SquadRconPlugin:

    def __init__(self, context=None, config=None):
        self.context = context
        self.config = config or {}

        self.data_file = os.path.join(
            os.path.dirname(__file__), "servers.json"
        )
        self.servers = self._load_servers()

    # ---------- 数据存储 ----------

    def _load_servers(self):
        if not os.path.exists(self.data_file):
            return {}
        with open(self.data_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_servers(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.servers, f, indent=2, ensure_ascii=False)

    def _session_key(self, event: AstrMessageEvent):
        if event.group_id:
            return f"group_{event.group_id}"
        return f"private_{event.user_id}"

    # ---------- 权限 ----------

    def _check_permission(self, user_id):
        allowed = self.config.get("allowed_qq_ids", [])
        return user_id in allowed

    # ---------- 主命令 ----------

    @filter.command("rcon")
    async def rcon(self, event: AstrMessageEvent, *args):
        user_id = event.user_id
        if not self._check_permission(user_id):
            await event.reply("❌ 你没有权限使用 RCON")
            return

        if not args:
            await event.reply("❌ 用法错误，输入 /rcon help 查看帮助")
            return

        action = args[0]
        key = self._session_key(event)
        self.servers.setdefault(key, {})

        # ----- 帮助 -----
        if action == "help":
            await event.reply(
                "🎮 Squad RCON\n"
                "/rcon add <名> <IP> <端口> <密码>\n"
                "/rcon use <名>\n"
                "/rcon del <名>\n"
                "/rcon list\n"
                "/rcon <RCON命令>"
            )
            return

        # ----- 添加服务器 -----
        if action == "add" and len(args) == 5:
            name, host, port, password = args[1:]
            self.servers[key][name] = {
                "host": host,
                "port": int(port),
                "password": password
            }
            self.servers[key]["_current"] = name
            self._save_servers()
            await event.reply(f"✅ 已添加并切换到服务器 `{name}`")
            return

        # ----- 切换服务器 -----
        if action == "use" and len(args) == 2:
            name = args[1]
            if name not in self.servers[key]:
                await event.reply("❌ 服务器不存在")
                return
            self.servers[key]["_current"] = name
            self._save_servers()
            await event.reply(f"✅ 已切换到服务器 `{name}`")
            return

        # ----- 删除服务器 -----
        if action == "del" and len(args) == 2:
            name = args[1]
            if name not in self.servers[key]:
                await event.reply("❌ 服务器不存在")
                return
            del self.servers[key][name]
            self._save_servers()
            await event.reply(f"🗑 已删除服务器 `{name}`")
            return

        # ----- 列表 -----
        if action == "list":
            items = []
            current = self.servers[key].get("_current")
            for name in self.servers[key]:
                if name == "_current":
                    continue
                flag = "⭐" if name == current else ""
                items.append(f"{flag}{name}")
            if not items:
                await event.reply("📭 当前没有服务器")
            else:
                await event.reply("📡 服务器列表：\n" + "\n".join(items))
            return

        # ----- 执行 RCON -----
        current = self.servers[key].get("_current")
        if not current or current not in self.servers[key]:
            await event.reply("❌ 未选择服务器，请先 /rcon add 或 /rcon use")
            return

        server = self.servers[key][current]
        command = " ".join(args)

        try:
            async with GameRCON(
                server["host"],
                server["port"],
                server["password"],
                timeout=10
            ) as rcon:
                result = await rcon.send(command)
        except Exception as e:
            await event.reply(f"⚠️ RCON 执行失败：{e}")
            return

        await event.reply(
            f"🎮【{current}】\n"
            f"📤 {command}\n"
            f"📥 {result}"
        )
