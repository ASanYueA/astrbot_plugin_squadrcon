import json
import os
import traceback

from astrbot.api.event import filter
from gamercon_async import GameRCON

_plugin_instance = None

class SquadRconPlugin:
    def __init__(self, context=None, config=None):
        self.context = context
        self.config = config or {}
        self.data_file = os.path.join(os.path.dirname(__file__), "servers.json")
        self.servers = self._load_servers()

        global _plugin_instance
        _plugin_instance = self

        print("插件初始化完成")

    def _load_servers(self):
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            return data
        except:
            return {}

    def _save_servers(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.servers, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存 servers.json 失败: {e}")

    def _session_key(self, event):
        group_id = getattr(event, "group_id", None)
        user_id = getattr(event, "user_id", None)
        if group_id:
            return f"group_{group_id}"
        elif user_id:
            return f"private_{user_id}"
        else:
            return "default"

    def _has_permission(self, user_id):
        return user_id in self.config.get("allowed_qq_ids", [])


@filter.command("rcon")
async def rcon(event, *, text: str = ""):
    global _plugin_instance
    plugin = _plugin_instance
    if not plugin:
        await event.reply("❌ 插件未初始化")
        return

    print("触发 /rcon 命令:", text)
    try:
        user_id = getattr(event, "user_id", None)
        if user_id is None and hasattr(event, "sender"):
            sender = event.sender
            if hasattr(sender, "user_id"):
                user_id = sender.user_id
            elif isinstance(sender, dict):
                user_id = sender.get("user_id")

        if user_id and not plugin._has_permission(user_id):
            await event.reply("❌ 你没有权限使用 RCON")
            return

        args = (text or "").strip().split()
        if not args:
            args = ["help"]

        action = args[0].lower()
        key = plugin._session_key(event)
        if key not in plugin.servers or not isinstance(plugin.servers[key], dict):
            plugin.servers[key] = {}
            plugin._save_servers()

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
            name, host, port_str, password = args[1:]
            try:
                port = int(port_str)
            except ValueError:
                await event.reply("❌ 端口必须是数字")
                return
            plugin.servers[key][name] = {"host": host, "port": port, "password": password}
            plugin.servers[key]["_current"] = name
            plugin._save_servers()
            await event.reply(f"✅ 已添加并切换到服务器 `{name}`")
            return

        # ---- list ----
        if action == "list":
            current = plugin.servers[key].get("_current")
            names = [("⭐ " if n == current else "") + n
                     for n in plugin.servers[key] if n != "_current"]
            await event.reply("📡 服务器列表：\n" + ("\n".join(names) if names else "（空）"))
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
                if plugin.servers[key].get("_current") == name:
                    plugin.servers[key].pop("_current", None)
                plugin._save_servers()
                await event.reply(f"✅ 已删除服务器 `{name}`")
            else:
                await event.reply(f"❌ 未找到服务器 `{name}`")
            return

        # ---- RCON 命令 ----
        current = plugin.servers[key].get("_current")
        if not current:
            await event.reply("❌ 未选择服务器，请先 /rcon add 或 /rcon use")
            return

        server = plugin.servers[key].get(current)
        if not server or not all(k in server for k in ("host", "port", "password")):
            await event.reply(f"❌ 当前服务器 `{current}` 配置不完整")
            return

        host, port, password = server["host"], server["port"], server["password"]
        try:
            async with GameRCON(host, port, password, timeout=10) as rcon_conn:
                result = await rcon_conn.send(text)
        except Exception as e:
            await event.reply(f"⚠️ RCON 执行失败：{e}")
            return

        await event.reply(f"🎮【{current}】\n{result}")

    except Exception as e:
        print("RCON 命令处理异常:", e)
        traceback.print_exc()
        try:
            await event.reply(f"❌ 处理命令时发生错误: {e}")
        except:
            print("发送错误消息失败")
