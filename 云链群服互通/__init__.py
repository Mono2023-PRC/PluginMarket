import json
import websocket
import time
import re
import threading
from tooldelta import Plugin, plugins, Config, Utils, Print


def remove_cq_code(content):
    cq_start = content.find("[CQ:")
    while cq_start != -1:
        cq_end = content.find("]", cq_start) + 1
        content = content[:cq_start] + content[cq_end:]
        cq_start = content.find("[CQ:")
    return content


def create_result_cb():
    ret = [None]
    lock = threading.Lock()
    lock.acquire()

    def getter(timeout=60):
        lock.acquire(timeout=timeout)
        return ret[0]

    def setter(s):
        ret[0] = s
        lock.release()

    return getter, setter


CQ_IMAGE_RULE = re.compile(r"\[CQ:image,([^\]])*\]")
CQ_VIDEO_RULE = re.compile(r"\[CQ:video,[^\]]*\]")
CQ_FILE_RULE = re.compile(r"\[CQ:file,[^\]]*\]")
CQ_AT_RULE = re.compile(r"\[CQ:at,[^\]]*\]")
CQ_REPLY_RULE = re.compile(r"\[CQ:reply,[^\]]*\]")
CQ_FACE_RULE = re.compile(r"\[CQ:face,[^\]]*\]")


def replace_cq(content: str):
    for i, j in (
        (CQ_IMAGE_RULE, "[图片]"),
        (CQ_FILE_RULE, "[文件]"),
        (CQ_VIDEO_RULE, "[视频]"),
        (CQ_AT_RULE, "[@]"),
        (CQ_REPLY_RULE, "[回复]"),
        (CQ_FACE_RULE, "[表情]"),
    ):
        content = i.sub(j, content)
    return content


@plugins.add_plugin_as_api("群服互通")
class QQLinker(Plugin):
    version = (0, 0, 4)
    name = "云链群服互通"
    author = "大庆油田"
    description = "提供简单的群服互通"

    def __init__(self, f):
        super().__init__(f)
        self.ws = None
        self.reloaded = False
        CFG_DEFAULT = {
            "云链地址": "ws://127.0.0.1:5556",
            "消息转发设置": {
                "链接的群聊": 194838530,
                "游戏到群": {
                    "是否启用": False,
                    "转发格式": "<[玩家名]> [消息]",
                    "仅转发以下符号开头的消息(为空则全部转发)": ["#"],
                },
                "群到游戏": {
                    "是否启用": True,
                    "转发格式": "群 <[昵称]> [消息]",
                    "屏蔽的QQ号": [2398282073],
                },
            },
            "指令设置": {
                "可以对游戏执行指令的QQ号名单": [2528622340, 2483724640],
                "是否允许查看玩家列表": True,
            },
        }
        cfg_std = Config.auto_to_std(CFG_DEFAULT)
        self.cfg, _ = Config.get_plugin_config_and_version(
            self.name, cfg_std, CFG_DEFAULT, self.version
        )
        self.enable_game_2_group = self.cfg["消息转发设置"]["游戏到群"]["是否启用"]
        self.enable_group_2_game = self.cfg["消息转发设置"]["群到游戏"]["是否启用"]
        self.enable_playerlist = self.cfg["指令设置"]["是否允许查看玩家列表"]
        self.linked_group = self.cfg["消息转发设置"]["链接的群聊"]
        self.block_qqids = self.cfg["消息转发设置"]["游戏到群"]
        self.game2qq_trans_chars = self.cfg["消息转发设置"]["游戏到群"][
            "仅转发以下符号开头的消息(为空则全部转发)"
        ]
        self.waitmsg_cbs = {}

    def on_def(self):
        self.tps_calc = plugins.get_plugin_api("tps计算器", (0, 0, 1), False)

    def on_inject(self):
        self.connect_to_websocket()
        self.frame.add_console_cmd_trigger(
            ["QQ", "发群"], "[消息]", "在群内发消息测试", self.sendmsg_test
        )

    @Utils.thread_func("云链群服连接进程")
    def connect_to_websocket(self):
        self.ws = websocket.WebSocketApp(  # type: ignore
            self.cfg["云链地址"],
            on_message=self.on_ws_message,
            on_error=self.on_ws_error,
            on_close=self.on_ws_close,
        )
        self.ws.on_open = self.on_ws_open
        self.ws.run_forever()

    def on_ws_open(self, ws):
        Print.print_suc("已成功连接到群服互通")

    def on_ws_message(self, ws, message):
        data = json.loads(message)
        bc_recv = plugins.broadcastEvt("群服互通/数据json", data)
        if any(bc_recv):
            return
        if data.get("post_type") == "message" and data["message_type"] == "group":
            msg: str = data["message"]
            if data["group_id"] == self.linked_group:
                if self.enable_group_2_game:
                    user_id = data["sender"]["user_id"]
                    nickname = data["sender"]["nickname"]
                    if user_id in self.waitmsg_cbs.keys():
                        self.waitmsg_cbs[user_id](msg)
                        return
                    bc_recv = plugins.broadcastEvt(
                        "群服互通/链接群消息",
                        {"QQ号": user_id, "昵称": nickname, "消息": msg},
                    )
                    if any(bc_recv):
                        return
                    if msg.startswith("/"):
                        if (
                            user_id
                            in self.cfg["指令设置"]["可以对游戏执行指令的QQ号名单"]
                        ):
                            self.sb_execute_cmd(msg)
                        else:
                            self.sendmsg(self.linked_group, "你是管理吗你还发指令 🤓👆")
                        return
                    elif msg in ["玩家列表", "list"] and self.enable_playerlist:
                        self.send_player_list()
                    self.game_ctrl.say_to(
                        "@a",
                        Utils.simple_fmt(
                            {
                                "[昵称]": nickname,
                                "[消息]": replace_cq(msg),
                            },
                            self.cfg["消息转发设置"]["群到游戏"]["转发格式"],
                        ),
                    )

    def waitMsg(self, qqid: int, timeout=60) -> str | None:
        g, s = create_result_cb()
        self.waitmsg_cbs[qqid] = s
        r = g(timeout)
        del self.waitmsg_cbs[qqid]
        return r

    def on_ws_error(self, ws, error):
        if not isinstance(error, Exception):
            Print.print_inf(f"群服互通发生错误: {error}, 可能为系统退出, 已关闭")
            self.reloaded = True
            return
        Print.print_err(f"群服互通发生错误: {error}, 15s后尝试重连")
        time.sleep(15)

    @Utils.thread_func("群服执行指令并获取返回")
    def sb_execute_cmd(self, cmd: str):
        res = self.execute_cmd_and_get_zhcn_cb(cmd)
        self.sendmsg(self.linked_group, res)

    def on_ws_close(self, ws, _, _2):
        if self.reloaded:
            return
        Print.print_err("群服互通被关闭, 10s后尝试重连")
        time.sleep(10)
        self.connect_to_websocket()

    def on_player_join(self, player: str):
        if self.ws and self.enable_game_2_group:
            self.sendmsg(self.linked_group, f"{player} 加入了游戏")

    def on_player_leave(self, player: str):
        if self.ws and self.enable_game_2_group:
            self.sendmsg(self.linked_group, f"{player} 退出了游戏")

    def on_player_message(self, player: str, msg: str):
        if self.ws and self.enable_game_2_group:
            if self.game2qq_trans_chars != []:
                can_send = False
                for prefix in self.game2qq_trans_chars:
                    if msg.startswith(prefix):
                        can_send = True
                        msg = msg[1:]
                        break
            else:
                can_send = True
            if not can_send:
                return
            self.sendmsg(
                self.linked_group,
                Utils.simple_fmt(
                    {"[玩家名]": player, "[消息]": remove_cq_code(msg)},
                    self.cfg["消息转发设置"]["游戏到群"]["转发格式"],
                ),
            )

    def sendmsg(self, group: int, msg: str):
        assert self.ws
        jsondat = json.dumps(
            {
                "action": "send_group_msg",
                "params": {"group_id": group, "message": remove_cq_code(msg)},
            }
        )
        self.ws.send(jsondat)

    def execute_cmd_and_get_zhcn_cb(self, cmd: str):
        try:
            result = self.game_ctrl.sendcmd_with_resp(cmd, 10)
            if len(result.OutputMessages) == 0:
                return ["😅 指令执行失败", "😄 指令执行成功"][bool(result.SuccessCount)]
            if (result.OutputMessages[0].Message == "commands.generic.syntax") | (
                result.OutputMessages[0].Message == "commands.generic.unknown"
            ):
                return f'😅 未知的 MC 指令, 可能是指令格式有误: "{cmd}"'
            else:
                if game_text_handler := self.game_ctrl.game_data_handler:
                    mjon = json.loads(
                        " ".join(
                            self.game_ctrl.game_data_handler.Handle_Text_Class1(
                                result.as_dict["OutputMessages"]
                            )
                        )
                    )
                if result.SuccessCount:
                    if game_text_handler:
                        return "😄 指令执行成功， 执行结果：\n " + mjon
                    else:
                        return (
                            "😄 指令执行成功， 执行结果：\n"
                            + result.OutputMessages[0].Message
                        )
                else:
                    if game_text_handler:
                        return "😭 指令执行失败， 原因：\n" + mjon
                    else:
                        return (
                            "😭 指令执行失败， 原因：\n"
                            + result.OutputMessages[0].Message
                        )

        except IndexError as exec_err:
            import traceback

            traceback.print_exc()
            return f"执行出现问题: {exec_err}"
        except TimeoutError:
            return "😭超时： 指令获取结果返回超时"

    def send_player_list(self):
        players = [f"{i+1}.{j}" for i, j in enumerate(self.game_ctrl.allplayers)]
        fmt_msg = (
            f"在线玩家有 {len(players)} 人：\n "
            + "\n ".join(players)
            + (
                f"\n当前 TPS： {round(self.tps_calc.get_tps(), 1)}/20"
                if self.tps_calc
                else ""
            )
        )
        self.sendmsg(self.linked_group, fmt_msg)

    def sendmsg_test(self, args: list[str]):
        if self.ws:
            self.sendmsg(self.linked_group, " ".join(args))
        else:
            Print.print_err("还没有连接到群服互通")
