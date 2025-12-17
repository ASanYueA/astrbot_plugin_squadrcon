import json
import os
import traceback

from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from gamercon_async import GameRCON

@register("squadrcon", "YourName", "战术小队 RCON 管理插件", "0.1.0")
class SquadRconPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        self.data_file = os.path.join(os.path.dirname(__file__), "servers.json")
        self.servers = self._load_servers()

    # ----------------- 服务器存储 -----------------
    def _load_servers(self):
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except Exception as e:
            print(f"[ERROR] 读取 servers.json 失败: {e}")
            return {}

    def _save_servers(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.servers, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] 保存 servers.json 失败: {e}")

    def _session_key(self, event: AstrMessageEvent):
        group_id = getattr(event, "group_id", None)
        user_id = getattr(event, "user_id", None)
        if group_id:
            return f"group_{group_id}"
        return f"private_{user_id}"

    def _has_permission(self, user_id: int):
        return user_id in self.config.get("allowed_qq_ids", [])

    # ----------------- /rcon 指令 -----------------
    @filter.command("rcon")
    async def rcon(self, event: AstrMessageEvent):
        try:
            user_id = getattr(event, "user_id", None) or getattr(event, "sender", {}).get("user_id", None)
            if not self._has_permission(user_id):
                yield event.plain_result("❌ 你没有权限使用 RCON")
                return

            text = event.message_str.strip()
            parts = text.split()[1:]  # 去掉 /rcon

            if not parts or parts[0].lower() == "help":
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

            # ---- add ----
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

            # ---- use ----
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

            # ---- del ----
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

            # ---- list ----
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

            # ---- RCON 命令 ----
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

            # --- 调试输出 ---
            print(f"[DEBUG] RCON -> {host}:{port}, 命令: {cmd}")

            try:
                async with GameRCON(host, port, pwd, timeout=10) as client:
                    resp = await client.send(cmd)
                    resp_text = resp.strip() if resp else "(空响应)"
                    print(f"[DEBUG] RCON 响应: {resp_text}")
                    yield event.plain_result(f"🎮【{current}】\n{resp_text}")
            except Exception as e:
                print(f"[ERROR] RCON 执行异常: {e}")
                traceback.print_exc()
                yield event.plain_result(f"⚠️ RCON 执行失败：{e}")

        except Exception as e:
            print(f"[ERROR] /rcon 命令处理异常: {e}")
            traceback.print_exc()
            yield event.plain_result(f"❌ 处理命令时发生错误：{e}")
