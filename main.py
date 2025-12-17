import json
import os
import traceback
import asyncio

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from gamercon_async import GameRCON

@register("squadrcon", "YourName", "战术小队 RCON 管理插件", "0.1.0")
class SquadRconPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        
        self.data_file = os.path.join(os.path.dirname(__file__), "servers.json")
        self.servers = self._load_servers()

    def _load_servers(self):
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except:
            return {}

    def _save_servers(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.servers, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print("保存 servers.json 失败:", e)

    def _session_key(self, event: AstrMessageEvent):
        group_id = event.get_group_id() if hasattr(event, "get_group_id") else None
        user_id = event.get_sender_id()
        if group_id:
            return f"group_{group_id}"
        return f"private_{user_id}"

    def _has_permission(self, user_id: int):
        # 从插件配置读取 allowed_qq_ids 白名单（配置界面可设）
        return user_id in self.config.get("allowed_qq_ids", [])

    @filter.command("rcon")
    async def rcon(self, event: AstrMessageEvent):
        """处理 /rcon 指令"""
        try:
            user_id = event.get_sender_id()
        except Exception:
            yield event.plain_result("❌ 无法获取用户 ID")
            return

        if not self._has_permission(user_id):
            yield event.plain_result("❌ 你没有权限使用 RCON")
            return

        text = event.message_str.strip()
        parts = text.split()[1:]

        # 帮助
        if not parts or parts[0] == "help":
            yield event.plain_result(
                "🎮 RCON 使用说明\n"
                "/rcon add <name> <ip> <port> <pwd>\n"
                "/rcon use <name>\n"
                "/rcon del <name>\n"
                "/rcon list\n"
                "/rcon <任意 RCON 命令>"
            )
            return

        action = parts[0].lower()
        key = self._session_key(event)
        self.servers.setdefault(key, {})

        # add
        if action == "add":
            if len(parts) != 5:
                yield event.plain_result("❌ 参数错误: /rcon add <name> <ip> <port> <pwd>")
                return
            name, host, port_str, pwd = parts[1:]
            try:
                port = int(port_str)
            except ValueError:
                yield event.plain_result("❌ 端口必须是数字")
                return
            self.servers[key][name] = {"host": host, "port": port, "password": pwd}
            self.servers[key]["_current"] = name
            self._save_servers()
            yield event.plain_result(f"✅ 添加并切换到服务器 {name}")
            return

        # use
        if action == "use":
            if len(parts) != 2:
                yield event.plain_result("❌ 参数错误: /rcon use <name>")
                return
            name = parts[1]
            if name in self.servers[key]:
                self.servers[key]["_current"] = name
                self._save_servers()
                yield event.plain_result(f"✅ 切换到服务器 {name}")
            else:
                yield event.plain_result(f"❌ 未找到服务器 {name}")
            return

        # del
        if action == "del":
            if len(parts) != 2:
                yield event.plain_result("❌ 参数错误: /rcon del <name>")
                return
            name = parts[1]
            if name in self.servers[key]:
                del self.servers[key][name]
                if self.servers[key].get("_current") == name:
                    self.servers[key].pop("_current", None)
                self._save_servers()
                yield event.plain_result(f"✅ 删除服务器 {name}")
            else:
                yield event.plain_result(f"❌ 未找到服务器 {name}")
            return

        # list
        if action == "list":
            current = self.servers[key].get("_current")
            lines = []
            for nm, cfg in self.servers[key].items():
                if nm == "_current":
                    continue
                prefix = "⭐ " if nm == current else ""
                lines.append(f"{prefix}{nm}: {cfg.get('host')}:{cfg.get('port')}")
            text = "📡 服务器列表：\n" + ("\n".join(lines) if lines else "(空)")
            yield event.plain_result(text)
            return

        # RCON 执行
        current = self.servers[key].get("_current")
        if not current:
            yield event.plain_result("❌ 尚未选择服务器，请先 /rcon add 或 /rcon use")
            return

        server = self.servers[key].get(current)
        if not server:
            yield event.plain_result(f"❌ 当前服务器 `{current}` 不存在")
            return

        host = server.get("host")
        port = server.get("port")
        pwd = server.get("password")
        if not host or not port or not pwd:
            yield event.plain_result(f"❌ 当前服务器 `{current}` 配置不完整")
            return

        cmd = " ".join(parts)
        
        # 显示正在执行的命令
        yield event.plain_result(f"⏳ 正在执行命令: `{cmd}`")
        
        try:
            # 调试信息
            print(f"[RCON] 连接到 {host}:{port}")
            print(f"[RCON] 发送命令: {cmd}")
            
            # 使用 asyncio 的 timeout 来控制超时
            async with GameRCON(host, port, pwd, timeout=15) as client:
                # 发送命令并获取响应
                resp = await client.send(cmd)
                
                # 调试信息
                print(f"[RCON] 收到响应: {repr(resp)}")
                print(f"[RCON] 响应类型: {type(resp)}")
                
                # 处理空响应
                if resp is None:
                    yield event.plain_result("✅ 命令已执行（无返回内容）")
                elif isinstance(resp, str):
                    resp = resp.strip()
                    if resp:
                        # 限制回复长度，避免消息过长
                        if len(resp) > 1000:
                            resp = resp[:1000] + "\n... (响应过长，已截断)"
                        yield event.plain_result(f"🎮 命令执行结果:\n```\n{resp}\n```")
                    else:
                        yield event.plain_result("✅ 命令已执行（空响应）")
                else:
                    # 处理非字符串响应
                    resp_str = str(resp).strip()
                    if resp_str:
                        yield event.plain_result(f"🎮 命令执行结果:\n```\n{resp_str}\n```")
                    else:
                        yield event.plain_result("✅ 命令已执行")
                    
        except asyncio.TimeoutError:
            yield event.plain_result("⏰ RCON 连接超时，请检查服务器状态和网络连接")
        except ConnectionRefusedError:
            yield event.plain_result("🔌 连接被拒绝，请检查服务器IP、端口和RCON是否开启")
        except Exception as e:
            error_msg = f"⚠️ RCON 执行失败：{str(e)}"
            print(f"[RCON] 错误详情: {traceback.format_exc()}")
            yield event.plain_result(error_msg)
