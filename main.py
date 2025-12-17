import json
import os
from astrbot.api.event import filter, AiocqhttpMessageEvent
from gamercon_async import GameRCON

# 可修改为你的 QQ 白名单
ALLOWED_QQ_IDS = [12345678, 87654321]

SERVERS_FILE = os.path.join(os.path.dirname(__file__), "servers.json")

def load_servers():
    if not os.path.exists(SERVERS_FILE):
        return {}
    try:
        with open(SERVERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_servers(servers):
    with open(SERVERS_FILE, "w", encoding="utf-8") as f:
        json.dump(servers, f, indent=2, ensure_ascii=False)

@filter.command("rcon")
async def rcon(event: AiocqhttpMessageEvent, *, args: str = ""):
    user_id = event.user_id

    # 权限检查
    if user_id not in ALLOWED_QQ_IDS:
        await event.reply("❌ 你没有权限使用 RCON 命令。")
        return

    # 帮助命令
    if not args or args.strip().lower() == "help":
        help_text = (
            "📌 RCON 插件命令列表:\n"
            "/rcon help - 显示此帮助\n"
            "/rcon add <chat_id> <host> <port> <password> - 添加服务器\n"
            "/rcon list <chat_id> - 列出服务器\n"
            "/rcon send <chat_id> <server_index> <命令> - 发送 RCON 命令\n"
        )
        await event.reply(help_text)
        return

    parts = args.strip().split()
    if not parts:
        await event.reply("❌ 参数错误，请使用 /rcon help 查看命令。")
        return

    command = parts[0].lower()
    servers = load_servers()

    # 添加服务器
    if command == "add":
        if len(parts) != 5:
            await event.reply("❌ 参数错误: /rcon add <chat_id> <host> <port> <password>")
            return
        chat_id, host, port, passwd = parts[1], parts[2], int(parts[3]), parts[4]
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
        chat_servers = servers.get(str(chat_id), [])
        if not chat_servers:
            await event.reply(f"❌ {chat_id} 没有配置服务器")
            return
        msg = f"📌 {chat_id} 服务器列表:\n"
        for i, s in enumerate(chat_servers):
            msg += f"{i}. {s['host']}:{s['port']}\n"
        await event.reply(msg)
        return

    # 发送 RCON 命令
    elif command == "send":
        if len(parts) < 4:
            await event.reply("❌ 参数错误: /rcon send <chat_id> <server_index> <命令>")
            return
        chat_id, idx = parts[1], int(parts[2])
        user_command = " ".join(parts[3:])
        chat_servers = servers.get(str(chat_id), [])
        if idx >= len(chat_servers) or idx < 0:
            await event.reply("❌ 服务器索引错误")
            return
        s = chat_servers[idx]
        try:
            async with GameRCON(s["host"], s["port"], s["password"], timeout=10) as client:
                response = await client.send(user_command)
        except Exception as e:
            await event.reply(f"⚠️ 执行失败: {e}")
            return
        await event.reply(f"📡 执行命令: {user_command}\n📥 响应:\n```\n{response}\n```")
        return

    else:
        await event.reply("❌ 未知命令，请使用 /rcon help 查看命令。")
