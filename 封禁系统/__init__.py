import os
import time
from datetime import datetime
from typing import ClassVar

from tooldelta import Utils, Config, Plugin, Print, game_utils, plugins, TYPE_CHECKING


@plugins.add_plugin_as_api("封禁系统")
class BanSystem(Plugin):
    name = "封禁系统"
    author = "SuperScript"
    version = (0, 0, 7)
    description = "便捷美观地封禁玩家, 同时也是一个前置插件"
    BAN_DATA_DEFAULT: ClassVar[dict[str, str | float]] = {"BanTo": 0, "Reason": ""}

    def __init__(self, frame):
        super().__init__(frame)
        self.tmpjson = Utils.TMPJson
        STD_BAN_CFG = {"踢出玩家提示格式": str, "玩家被封禁的广播提示": str}
        DEFAULT_BAN_CFG = {
            "踢出玩家提示格式": "§c你因为 [ban原因]\n被系统封禁至 §6[日期时间]",
            "玩家被封禁的广播提示": "§6WARNING: §c[玩家名] 因为[ban原因] 被系统封禁至 §6[日期时间]",
        }
        self.cfg, _ = Config.getPluginConfigAndVersion(
            self.name, STD_BAN_CFG, DEFAULT_BAN_CFG, self.version
        )

    def on_def(self):
        self.chatbar = plugins.get_plugin_api("聊天栏菜单", (0, 0, 1))
        self.xuidm = plugins.get_plugin_api("XUID获取")
        self.qqlink = plugins.get_plugin_api("群服互通", force=False)
        if TYPE_CHECKING:
            from 前置_聊天栏菜单 import ChatbarMenu
            from 前置_玩家XUID获取 import XUIDGetter
            from 群服互通云链版 import QQLinker

            self.chatbar = plugins.instant_plugin_api(ChatbarMenu)
            self.xuidm = plugins.instant_plugin_api(XUIDGetter)
            self.qqlink = plugins.instant_plugin_api(QQLinker)

    def on_inject(self):
        self.chatbar.add_trigger(
            ["ban", "封禁"],
            None,
            "封禁玩家",
            self.on_chatbar_ban,
            lambda x: x in (0, 1),
            True,
        )
        for i in self.game_ctrl.allplayers:
            self.test_ban(i)
        self.frame.add_console_cmd_trigger(
            ["ban", "封禁"], None, "封禁玩家", self.on_console_ban
        )
        self.frame.add_console_cmd_trigger(
            ["unban", "解封"], None, "解封玩家", self.on_console_unban
        )
        if self.qqlink:
            self.qqlink.add_trigger(
                ["ban", "封禁"],
                "[玩家名] [封禁时间(秒数)] [原因]",
                "封禁玩家",
                self.on_qq_ban,
                lambda x: x in (1, 2, 3),
                True,
            )
            self.qqlink.add_trigger(
                ["unban", "解封"],
                None,
                "解封玩家",
                self.on_qq_unban,
                op_only=True,
            )

    # -------------- API --------------
    def ban(self, player: str, ban_time: float, reason: str = ""):
        """
        封禁玩家.
            player: 需要ban的玩家
            ban_to_time_ticks: 将其封禁直到(时间戳, 和time.time()一样)
            reason: 原因
        """
        ban_datas = self.BAN_DATA_DEFAULT.copy()
        ban_datas["BanTo"] = time.time() + ban_time
        ban_datas["Reason"] = reason
        self.rec_ban_data(player, ban_datas)
        if player in self.game_ctrl.allplayers:
            self.test_ban(player)

    def unban(self, player: str):
        """
        解封玩家.
            player: 玩家名
        """
        self.del_ban_data(player)

    # ----------------------------------

    @Utils.thread_func("封禁系统测试 ban")
    def on_player_join(self, player: str):
        self.test_ban(player)

    def on_console_ban(self, _):
        allplayers = self.game_ctrl.allplayers.copy()
        Print.print_inf("选择一个玩家进行封禁：")
        for i, j in enumerate(allplayers):
            Print.print_inf(f"{i + 1}: {j}")
        resp = Utils.try_int(input(Print.fmt_info("请输入序号：")))
        if resp and resp in range(1, len(allplayers) + 1):
            ban_player = allplayers[resp - 1]
            reason = input(Print.fmt_info("请输入封禁理由：")) or "未知"
            self.ban(ban_player, -1, reason)
            Print.print_suc(f"封禁成功: 已封禁 {ban_player}")
        else:
            Print.print_err("输入有误")

    def on_console_unban(self, _):
        all_ban_player_xuids = os.listdir(self.data_path)
        all_ban_playernames: list[tuple[str, str]] = []
        for i in all_ban_player_xuids:
            xuid = i.replace(".json", "")
            try:
                all_ban_playernames.append(
                    (self.xuidm.get_name_by_xuid(xuid, allow_offline=True), xuid)
                )
            except ValueError:
                continue
        if all_ban_playernames == []:
            Print.print_inf("没有封禁的玩家")
            return
        Print.print_inf("选择一个玩家进行解封：")
        for i, (name, xuid) in enumerate(all_ban_playernames):
            Print.print_inf(f"{i + 1}: {name}")
        resp = Utils.try_int(input(Print.fmt_info("请输入序号：")))
        if resp and resp in range(1, len(all_ban_playernames) + 1):
            unban_player = all_ban_playernames[resp - 1][0]
            self.del_ban_data(all_ban_playernames[resp - 1][0])
            Print.print_suc(f"解封成功: 已解封 {unban_player}")
        else:
            Print.print_err("输入有误")

    def on_qq_ban(self, qqid: int, args: list[str]):
        Utils.fill_list_index(args, ["", "永久", "未知"])
        ban_who, ban_time, reason = args
        if ban_who not in self.game_ctrl.allplayers:
            self.qqlink.sendmsg(self.qqlink.linked_group, "此玩家不在线..")
            return
        if ban_time == "永久":
            ban_time = -1
        elif (ban_time := Utils.try_int(ban_time)) is None or ban_time <= 0:
            self.qqlink.sendmsg(self.qqlink.linked_group, "封禁时间不正确..")
            return
        self.ban(ban_who, ban_time, reason)
        if ban_time > 0:
            self.qqlink.sendmsg(
                self.qqlink.linked_group,
                f"[CQ:at,qq={qqid}] 封禁 {ban_who} 成功， 封禁了 {self.format_date_zhcn(ban_time)}",
            )
        else:
            self.qqlink.sendmsg(
                self.qqlink.linked_group,
                f"[CQ:at,qq={qqid}] 封禁 {ban_who} 成功， 封禁至永久",
            )

    def on_qq_unban(self, qqid: int, _):
        all_ban_player_xuids = os.listdir(self.data_path)
        all_ban_playernames: list[tuple[str, str]] = []
        for i in all_ban_player_xuids:
            xuid = i.replace(".json", "")
            try:
                all_ban_playernames.append(
                    (self.xuidm.get_name_by_xuid(xuid, allow_offline=True), xuid)
                )
            except ValueError:
                continue
        if all_ban_playernames == []:
            self.qqlink.sendmsg(self.qqlink.linked_group, "没有封禁的玩家")
            return
        output_msg = "选择一个玩家进行解封："
        for i, (name, xuid) in enumerate(all_ban_playernames):
            output_msg += f"\n  {i + 1}: {name}"
        self.qqlink.sendmsg(self.qqlink.linked_group, output_msg + "\n请输入序号：")
        resp = Utils.try_int(self.qqlink.waitMsg(qqid))
        if resp and resp in range(1, len(all_ban_playernames) + 1):
            unban_player = all_ban_playernames[resp - 1][0]
            self.del_ban_data(all_ban_playernames[resp - 1][0])
            self.qqlink.sendmsg(
                self.qqlink.linked_group, f"解封成功: 已解封 {unban_player}"
            )
        else:
            self.qqlink.sendmsg(self.qqlink.linked_group, "输入有误")

    def on_chatbar_ban(self, caller: str, _):
        allplayers = self.game_ctrl.allplayers.copy()
        self.game_ctrl.say_to(caller, "§6选择一个玩家进行封禁：")
        for i, j in enumerate(allplayers):
            self.game_ctrl.say_to(caller, f"{i + 1}: {j}")
        self.game_ctrl.say_to(caller, "§6请输入序号：")
        resp = Utils.try_int(game_utils.waitMsg(caller))
        if resp and resp in range(1, len(allplayers) + 1):
            ban_player = allplayers[resp - 1]
            if caller == ban_player:
                self.game_ctrl.say_to(caller, "§6看起来你不能封禁自己..")
                return
            self.ban(allplayers[resp - 1], -1)
            Print.print_suc(f"封禁成功: 已封禁 {ban_player}")
        else:
            Print.print_err("输入有误")

    def test_ban(self, player):
        ban_data = self.get_ban_data(player)
        ban_to, reason = ban_data["BanTo"], ban_data["Reason"]
        if ban_to == -1 or ban_to > time.time():
            Print.print_inf(
                f"封禁系统: {player} 被封禁至 {datetime.fromtimestamp(ban_to) if ban_to > 0 else '永久'}"
            )
            self.game_ctrl.sendwocmd(
                f"/kick {player} {self.format_msg(player, ban_to, reason, '踢出玩家提示格式')}"
            )
            self.game_ctrl.say_to(
                "@a", self.format_msg(player, ban_to, reason, "玩家被封禁的广播提示")
            )
            # 防止出现敏感词封禁原因的指令
            self.game_ctrl.sendwocmd(f"/kick {player}")

    def format_bantime(self, banto_time: int):
        if banto_time == -1:
            return "永久"
        else:
            struct_time = time.localtime(banto_time)
            date_show = time.strftime("%Y年 %m月 %d日", struct_time)
            time_show = time.strftime("%H : %M : %S", struct_time)
        return date_show + "  " + time_show

    def format_msg(self, player: str, ban_to_sec: int, ban_reason: str, cfg_key: str):
        fmt_time = self.format_bantime(ban_to_sec)
        return Utils.SimpleFmt(
            {
                "[日期时间]": fmt_time,
                "[玩家名]": player,
                "[ban原因]": ban_reason or "未知",
            },
            self.cfg[cfg_key],
        )

    def rec_ban_data(self, player: str, data):
        Utils.TMPJson.write_as_tmp(
            path := self.format_data_path(
                self.xuidm.get_xuid_by_name(player, allow_offline=True) + ".json"
            ),
            data,
            needFileExists=False,
        )
        Utils.TMPJson.flush(path)

    def del_ban_data(self, player: str):
        p = self.format_data_path(
            self.xuidm.get_xuid_by_name(player, allow_offline=True) + ".json"
        )
        if os.path.isfile(p):
            os.remove(p)

    def get_ban_data(self, player: str) -> dict:
        if os.path.isfile(
            self.format_data_path(
                fname := self.xuidm.get_xuid_by_name(player, allow_offline=True)
                + ".json"
            )
        ):
            return Utils.JsonIO.readFileFrom(
                self.name,
                fname,
                default=self.BAN_DATA_DEFAULT,
            )
        else:
            return self.BAN_DATA_DEFAULT

    @staticmethod
    def format_date_zhcn(seconds: int):
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分钟{seconds % 60}秒"
        elif seconds < 86400:
            return f"{seconds // 3600}小时{seconds % 3600 // 60}分钟{seconds % 60}秒"
        else:
            return f"{seconds // 86400}天{seconds % 86400 // 3600}小时{seconds % 3600 // 60}分钟{seconds % 60}秒"
