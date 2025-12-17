import json
import os

from astrbot.api.event import filter
from gamercon_async import GameRCON

# 全局插件实例
_plugin_instance = None
_bot_instance = None


class SquadRconPlugin:

    def __init__(self, context=None, config=None):
        self.context = context
        self.config = config or {}

        self.data_file = os.path.join(
            os.path.dirname(__file__), "servers.json"
        )
        self.servers = self._load_servers()
        
        # 设置全局实例
        global _plugin_instance, _bot_instance
        _plugin_instance = self
        
        # 保存 bot 实例
        if context and hasattr(context, 'bot'):
            _bot_instance = context.bot

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
        elif hasattr(event, '_group_id'):
            group_id = event._group_id
        elif hasattr(event, 'message_type') and event.message_type == 'group':
            # 从原始数据中获取
            raw_data = getattr(event, 'raw_message', {})
            if isinstance(raw_data, dict) and 'group_id' in raw_data:
                group_id = raw_data['group_id']
        
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
            # 如果都无法获取，使用默认值
            return "default"

    def _has_permission(self, user_id):
        return user_id in self.config.get("allowed_qq_ids", [])


async def send_reply(event, message):
    """发送回复消息的辅助函数"""
    global _bot_instance
    
    if _bot_instance and hasattr(_bot_instance, 'send'):
        try:
            # 获取消息ID和消息类型
            message_id = getattr(event, 'message_id', None)
            
            # 判断是群消息还是私聊
            if hasattr(event, 'group_id') and event.group_id:
                # 群聊消息
                await _bot_instance.send(event, message, at_sender=True)
            else:
                # 私聊消息
                await _bot_instance.send(event, message)
        except Exception as e:
            print(f"发送消息失败: {e}")
    else:
        print(f"无法发送消息: bot实例不存在")


# 命令处理函数（独立函数，不是类方法）
@filter.command("rcon")
async def rcon(event, *, text: str = ""):
    """RCON 命令处理器"""
    
    global _plugin_instance
    if not _plugin_instance:
        await send_reply(event, "❌ 插件未初始化")
        return
    
    plugin = _plugin_instance
    
    # 获取用户ID
    user_id = None
    if hasattr(event, 'user_id'):
        user_id = event.user_id
    elif hasattr(event, 'sender'):
        sender = event.sender
        if hasattr(sender, 'user_id'):
            user_id = sender.user_id
        elif isinstance(sender, dict) and 'user_id' in sender:
            user_id = sender['user_id']
    elif hasattr(event, 'raw_message'):
        raw = event.raw_message
        if isinstance(raw, dict) and 'user_id' in raw:
            user_id = raw['user_id']
    
    if user_id and not plugin._has_permission(user_id):
        await send_reply(event, "❌ 你没有权限使用 RCON")
        return

    args = text.split()
    if not args:
        args = ["help"]

    action = args[0]
    key = plugin._session_key(event)
    plugin.servers.setdefault(key, {})

    # ---- help ----
    if action == "help":
        await send_reply(event,
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
        await send_reply(event, f"✅ 已添加并切换到服务器 `{name}`")
        return
    
    # ---- use ----
    if action == "use" and len(args) == 2:
        name = args[1]
        if name in plugin.servers[key]:
            plugin.servers[key]["_current"] = name
            plugin._save_servers()
            await send_reply(event, f"✅ 已切换到服务器 `{name}`")
        else:
            await send_reply(event, f"❌ 未找到服务器 `{name}`")
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
            await send_reply(event, f"✅ 已删除服务器 `{name}`")
        else:
            await send_reply(event, f"❌ 未找到服务器 `{name}`")
        return

    # ---- list ----
    if action == "list":
        current = plugin.servers[key].get("_current")
        names = [
            ("⭐ " if n == current else "") + n
            for n in plugin.servers[key]
            if n != "_current"
        ]
        await send_reply(event,
            "📡 服务器列表：\n" + ("\n".join(names) if names else "（空）")
        )
        return

    # ---- RCON 命令 ----
    current = plugin.servers[key].get("_current")
    if not current:
        await send_reply(event, "❌ 未选择服务器，请先 /rcon add")
        return

    if current not in plugin.servers[key]:
        await send_reply(event, f"❌ 服务器 `{current}` 不存在")
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
        await send_reply(event, f"⚠️ RCON 执行失败：{e}")
        return

    await send_reply(event, f"🎮【{current}】\n{result}")
