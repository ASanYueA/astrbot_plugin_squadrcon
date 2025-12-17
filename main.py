from astrbot.api.event import AstrMessageEvent, filter
from gamercon_async import GameRCON


class SquadRconPlugin:
    """
    战术小队服务器 RCON 管理插件
    """

    def __init__(self, context=None, config=None):
        # 老 / 新 AstrBot 都能兼容
        self.context = context
        self.config = config or {}

    @filter.command("rcon")
    async def rcon(self, event: AstrMessageEvent, *, command: str):
        user_id = event.user_id

        # 权限检查
        allowed_ids = self.config.get("allowed_qq_ids", [])
        if user_id not in allowed_ids:
            await event.reply("❌ 你没有权限使用该 RCON 命令")
            return

        # RCON 配置
        host = self.config.get("rcon_host", "127.0.0.1")
        port = self.config.get("rcon_port", 21114)
        password = self.config.get("rcon_password")

        if not password:
            await event.reply("❌ RCON 密码未配置")
            return

        try:
            async with GameRCON(host, port, password, timeout=10) as rcon:
                result = await rcon.send(command)
        except Exception as e:
            await event.reply(f"⚠️ RCON 执行失败：{e}")
            return

        await event.reply(
            f"🎮【Squad RCON】\n"
            f"📤 命令：{command}\n"
            f"📥 返回：\n{result}"
        )
