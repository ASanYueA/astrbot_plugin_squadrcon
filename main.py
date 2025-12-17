import json
import os

from astrbot.api.event import AstrMessageEvent, filter
from gamercon_async import GameRCON

# 全局插件实例
_plugin_instance = None


class SquadRconPlugin:

    def __init__(self, context=None, config=None):
        self.context = context
        self.config = config or {}

        self.data_file = os.path.join(
            os.path.dirname(__file__), "servers.json"
        )
        self.servers = self._load_servers()
        
        # 设置全局实例
        global _plugin_instance
        _plugin_instance = self

    # ---------- 存储 ----------

    def _load_servers(self):
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_servers(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.servers, f, indent=2, ensure_ascii=False)

    def _session_key(self, event: AstrMessageEvent):
        if event.group_id:
            return f"group_{event.group_id}"
        return f"private_{event.user_id}"

    def _has_permission(self, user_id):
        return user_id in self.config.get("allowed_qq_ids", [])


# 命令处理函数（独立函数，不是类方法）
@filter.command("rcon")
async def rcon(event: AstrMessageEvent, *, text: str = ""):
    """RCON 命令处理器"""
    
    global _plugin_instance
    if not _plugin_instance:
        await event.reply("❌ 插件未初始化")
        return
    
    plugin = _plugin_instance
    
    if not plugin._has_permission(event.user_id):
        await event.reply("❌ 你没有权限使用 RCON")
        return

    args = text.split()
    if not args:
        args = ["help"]

    action = args[0]
    key = plugin._session_key(event)
    plugin.servers.setdefault(key, {})

    # ---- help ----
    if action == "help":
        await event.reply(
            "🎮 Squad RCON 使用说明\n"
            "/rcon add <名> <IP> <端口> <密码>\n"
            "/rcon use <名>\n"
            "/rcon del <名>\n"
            "/rcon list\n"
            "/rcon <RCON命令>"
        )
        return

    # ---- add ----
    if action == "add" and len(args) == 5:
        name, host, port, password = args[1:]
        plugin.servers[key][name] = {
            "host": host,
            "port": int(port),
            "password": password
        }
        plugin.servers[key]["_current"] = name
        plugin._save_servers()
        await event.reply(f"✅ 已添加并切换到服务器 `{name}`")
        return
    
    # ---- use ----
    if action == "use" and len(args) == 2:
        name = args[1]
        if name in plugin.servers[key]:
            plugin.servers[key]["_current"] = name
            plugin._save_servers()
            await event.reply(f"✅ 已切换到服务器 `{name}`")
        else:
            await event.reply(f"❌ 未找到服务器 `{name}`")
        return
    
    # ---- del ----
    if action == "del" and len(args) == 2:
        name = args[1]
        if name in plugin.servers[key]:
            del plugin.servers[key][name]
            # 如果删除的是当前服务器，清除当前选择
            if plugin.servers[key].get("_current") == name:
                del plugin.servers[key]["_current"]
            plugin._save_servers()
            await event.reply(f"✅ 已删除服务器 `{name}`")
        else:
            await event.reply(f"❌ 未找到服务器 `{name}`")
        return

    # ---- list ----
    if action == "list":
        current = plugin.servers[key].get("_current")
        names = [
            ("⭐ " if n == current else "") + n
            for n in plugin.servers[key]
            if n != "_current"
        ]
        await event.reply(
            "📡 服务器列表：\n" + ("\n".join(names) if names else "（空）")
        )
        return

    # ---- RCON 命令 ----
    current = plugin.servers[key].get("_current")
    if not current:
        await event.reply("❌ 未选择服务器，请先 /rcon add")
        return

    if current not in plugin.servers[key]:
        await event.reply(f"❌ 服务器 `{current}` 不存在")
        return

    server = plugin.servers[key][current]

    try:
        async with GameRCON(
            server["host"],
            server["port"],
            server["password"],
            timeout=10
        ) as rcon:
            # 如果是 help、add、use、del、list 之外的命令，直接发送给服务器
            result = await rcon.send(text)
    except Exception as e:
        await event.reply(f"⚠️ RCON 执行失败：{e}")
        return

    await event.reply(f"🎮【{current}】\n{result}")
