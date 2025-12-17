from astrbot.api.plugin import Plugin
from astrbot.api import Context, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from gamercon_async import GameRCON

class SquadRconPlugin(Plugin):
    """
    战术小队服务器 RCON 管理插件
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    @filter.command("rcon")
    async def rcon_command(self, event: AstrMessageEvent, *, command: str):
        user_id = event.user_id
        allowed_ids = self.config.get("allowed_qq_ids", [])

        if user_id not in allowed_ids:
            await event.reply("❌ 你没有权限使用 RCON 命令。")
            return

        host = self.config.get("rcon_host", "127.0.0.1")
        port = self.config.get("rcon_port", 25575)
        passwd = self.config.get("rcon_password", "")

        if not passwd:
            await event.reply("❌ RCON 密码未配置，无法执行命令。")
            return

        try:
            async with GameRCON(host, port, passwd, timeout=10) as client:
                response = await client.send(command)
        except Exception as e:
            await event.reply(f"⚠️ RCON 命令执行失败: {e}")
            return

        await event.reply(f"📡 执行命令: `{command}`\n📥 响应:\n```\n{response}\n```")
