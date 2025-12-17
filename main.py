import json
import os
import traceback

from astrbot.api.event import filter
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
        
        print("插件初始化完成")
        if context:
            print(f"Context 类型: {type(context)}")
            print(f"Context 属性: {dir(context)}")

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

    def _session_key(self, event):
        """从事件中获取会话key"""
        # 尝试多种方式获取群ID和用户ID
        group_id = None
        user_id = None
        
        # 尝试获取群ID
        if hasattr(event, 'group_id'):
            group_id = event.group_id
        elif hasattr(event, 'group'):
            group_id = event.group
        
        # 尝试获取用户ID
        if hasattr(event, 'user_id'):
            user_id = event.user_id
        elif hasattr(event, 'sender'):
            sender = event.sender
            if hasattr(sender, 'user_id'):
                user_id = sender.user_id
            elif isinstance(sender, dict) and 'user_id' in sender:
                user_id = sender['user_id']
        
        if group_id:
            return f"group_{group_id}"
        elif user_id:
            return f"private_{user_id}"
        else:
            return "default"

    def _has_permission(self, user_id):
        return user_id in self.config.get("allowed_qq_ids", [])


# 命令处理函数
@filter.command("rcon")
async def rcon(event, *, text: str = ""):
    """RCON 命令处理器"""
    print("收到 /rcon 命令")
    print(f"事件类型: {type(event)}")
    print(f"事件属性: {dir(event)}")
    
    global _plugin_instance
    if not _plugin_instance:
        # 尝试直接发送消息
        try:
            await event.reply("❌ 插件未初始化")
        except:
            print("无法发送回复消息")
        return
    
    plugin = _plugin_instance
    
    try:
        # 获取用户ID
        user_id = None
        if hasattr(event, 'user_id'):
            user_id = event.user_id
            print(f"从 event.user_id 获取用户ID: {user_id}")
        elif hasattr(event, 'sender'):
            sender = event.sender
            print(f"Sender 类型: {type(sender)}")
            if hasattr(sender, 'user_id'):
                user_id = sender.user_id
                print(f"从 sender.user_id 获取用户ID: {user_id}")
            elif isinstance(sender, dict):
                print(f"Sender 字典内容: {sender}")
                if 'user_id' in sender:
                    user_id = sender['user_id']
                    print(f"从 sender['user_id'] 获取用户ID: {user_id}")
        
        # 检查权限
        if user_id and not plugin._has_permission(user_id):
            try:
                await event.reply("❌ 你没有权限使用 RCON")
            except Exception as e:
                print(f"发送权限错误消息失败: {e}")
                print(f"尝试使用其他方式发送消息...")
                # 尝试使用上下文中的bot
                if plugin.context and hasattr(plugin.context, 'bot'):
                    bot = plugin.context.bot
                    if hasattr(bot, 'send'):
                        # 尝试发送消息
                        await bot.send(event, "❌ 你没有权限使用 RCON")
            return

        args = text.split()
        if not args:
            args = ["help"]

        action = args[0]
        key = plugin._session_key(event)
        plugin.servers.setdefault(key, {})

        # ---- help ----
        if action == "help":
            try:
                await event.reply(
                    "🎮 Squad RCON 使用说明\n"
                    "/rcon add <名> <IP> <端口> <密码>\n"
                    "/rcon use <名>\n"
                    "/rcon del <名>\n"
                    "/rcon list\n"
                    "/rcon <RCON命令>"
                )
            except:
                print("发送 help 消息失败")
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
            try:
                await event.reply(f"✅ 已添加并切换到服务器 `{name}`")
            except:
                print("发送 add 成功消息失败")
            return
        
        # ---- use ----
        if action == "use" and len(args) == 2:
            name = args[1]
            if name in plugin.servers[key]:
                plugin.servers[key]["_current"] = name
                plugin._save_servers()
                try:
                    await event.reply(f"✅ 已切换到服务器 `{name}`")
                except:
                    print("发送 use 成功消息失败")
            else:
                try:
                    await event.reply(f"❌ 未找到服务器 `{name}`")
                except:
                    print("发送 use 失败消息失败")
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
                try:
                    await event.reply(f"✅ 已删除服务器 `{name}`")
                except:
                    print("发送 del 成功消息失败")
            else:
                try:
                    await event.reply(f"❌ 未找到服务器 `{name}`")
                except:
                    print("发送 del 失败消息失败")
            return

        # ---- list ----
        if action == "list":
            current = plugin.servers[key].get("_current")
            names = [
                ("⭐ " if n == current else "") + n
                for n in plugin.servers[key]
                if n != "_current"
            ]
            try:
                await event.reply(
                    "📡 服务器列表：\n" + ("\n".join(names) if names else "（空）")
                )
            except:
                print("发送 list 消息失败")
            return

        # ---- RCON 命令 ----
        current = plugin.servers[key].get("_current")
        if not current:
            try:
                await event.reply("❌ 未选择服务器，请先 /rcon add")
            except:
                print("发送未选择服务器消息失败")
            return

        if current not in plugin.servers[key]:
            try:
                await event.reply(f"❌ 服务器 `{current}` 不存在")
            except:
                print("发送服务器不存在消息失败")
            return

        server = plugin.servers[key][current]

        try:
            async with GameRCON(
                server["host"],
                server["port"],
                server["password"],
                timeout=10
            ) as rcon_conn:
                # 如果是 help、add、use、del、list 之外的命令，直接发送给服务器
                result = await rcon_conn.send(text)
        except Exception as e:
            try:
                await event.reply(f"⚠️ RCON 执行失败：{e}")
            except:
                print(f"发送RCON执行失败消息失败: {e}")
            return

        try:
            await event.reply(f"🎮【{current}】\n{result}")
        except:
            print("发送RCON结果消息失败")
            
    except Exception as e:
        print(f"处理命令时发生异常: {e}")
        traceback.print_exc()
        try:
            await event.reply(f"❌ 处理命令时发生错误: {e}")
        except:
            print("发送错误消息失败")
