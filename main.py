import json
import os
from astrbot.api.event import filter
from gamercon_async import GameRCON

# 白名单 QQ
ALLOWED_QQ_IDS = [12345678, 87654321]

SERVERS_FILE = os.path.join(os.path.dirname(__file__), "servers.json")

def load_servers():
    """安全加载服务器数据，返回字典，每个 chat_id 对应列表"""
    if not os.path.exists(SERVERS_FILE):
        return {}
    try:
        with open(SERVERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
        for k, v in data.items():
            if not isinstance(v, list):
                data[k] = []
        return data
    except:
        # 文件损坏或空文件，返回空字典
        return {}

def save_servers(servers):
    """保存服务器数据"""
    with open(SERVERS_FILE, "w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2, ensure_ascii=False)

@filter.command("rcon")
async def rcon(event, *, args=""):
    user_id = getattr(event, "user_id", None)
    if user_id not in ALLOWED_QQ_IDS:
        await event.reply("❌ 你没有权限使用 RCON 命令。")
        return

    args = (args or "").strip()
    if not args or args.lower() == "help":
        await event.reply(
            "📌 RCON 命令列表:\n"
            "/rcon help - 显示帮助\n"
            "/rcon add <chat_id> <host> <port> <password>\n"
            "/rcon list <chat_id>\n"
            "/rcon send <chat_id> <server_index> <命令>"
        )
        return

    parts = args.split()
    command = parts[0].lower()
    servers = load_servers()

    # 添加服务器
    if command == "add":
        if len(parts) != 5:
            await event.reply("❌ 参数错误: /rcon add <chat_id> <host> <port> <password>")
            return
        chat_id, host, port_str, passwd = parts[1], parts[2], parts[3], parts[4]
        try:
            port = int(port_str)
        except ValueError:
            await event.reply("❌ 端口必须是数字")
            return
        servers.setdefault(str(chat_id), []).append({
            "host": host,
            "port": port,
            "password": passwd
        })
        save_servers(servers)
        await event.reply(f"✅ 已为 {chat_id} 添加服务器 {host}:{port}")
        return

    # 列出服务器
    elif command == "list":
        if len(parts) != 2:
            await event.reply("❌ 参数错误: /rcon list <chat_id>")
            return
        chat_id = parts[1]
        chat_servers = servers.get(str(chat_id))
        if not isinstance(chat_servers, list) or len(chat_servers) == 0:
            await event.reply(f"❌ {chat_id} 没有配置服务器")
            return
        msg = f"📌 {chat_id} 服务器列表:\n"
        for i, s in enumerate(chat_servers):
            msg += f"{i}. {s.get('host','未知')}:{s.get('port','未知')}\n"
        await event.reply(msg)
        return

    # 发送 RCON 命令
    elif command == "send":
        if len(parts) < 4:
            await event.reply("❌ 参数错误: /rcon send <chat_id> <server_index> <命令>")
            return
        chat_id = parts[1]
        try:
            idx = int(parts[2])
        except ValueError:
            await event.reply("❌ 服务器索引必须是数字")
            return
        user_command = " ".join(parts[3:])
        chat_servers = servers.get(str(chat_id))

        if not isinstance(chat_servers, list) or len(chat_servers) == 0:
            await event.reply(f"❌ {chat_id} 没有配置服务器")
            return
        if idx < 0 or idx >= len(chat_servers):
            await event.reply(f"❌ 服务器索引错误，有效范围：0-{len(chat_servers)-1}")
            return

        s = chat_servers[idx]
        host = s.get("host")
        port = s.get("port")
        password = s.get("password")
        if not host or not port or not password:
            await event.reply("❌ 服务器配置不完整")
            return

        try:
            async with GameRCON(host, port, password, timeout=10) as client:
                response = await client.send(user_command)
        except Exception as e:
            await event.reply(f"⚠️ 执行失败: {e}")
            return

        await event.reply(f"📡 执行命令: {user_command}\n📥 响应:\n```\n{response}\n```")
        return

    else:
        await event.reply("❌ 未知命令，请使用 /rcon help 查看命令。")
