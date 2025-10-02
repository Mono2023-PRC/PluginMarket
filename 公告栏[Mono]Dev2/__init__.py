import datetime
import difflib
import time
from tooldelta import utils, cfg, Plugin, fmts, plugin_entry
from tooldelta.constants import PacketIDS,TOOLDELTA_PLUGIN_CFG_DIR


packets = PacketIDS
from rich import print as rp
from rich.prompt import Prompt

class BetterAnnounce(Plugin):
    name = "公告栏Dev"
    author = "Mono"
    version = (1, 1, 0)

    def __init__(self, frame):
        super().__init__(frame)
        self.ListenPreload(self.on_def)
        self.ListenActive(self.on_inject)
        self.ListenPacket([packets.IDSetScore], self.on_setscore)
        # self.ListenActive(self.on_cfg_changed)

    def on_def(self):
        """
        公告修改手册:
        1.直接修改下面的列表,排列顺序(上->下),提供的可供更换的文本有:
            {num_players} : 在线人数
            {week_day}    : 周几
            {tps}         : tps
            {year}        : 年
            {month}       : 月
            {day}         : 日
            {time_cn}     : 时间中文
            {time_color}  : 时间颜色
            {hour}        : 小时
            {minute}      : 分钟
            {second}      : 秒
            {run_time}    : 运行时间
        2.修改title 修改标题,默认为"公告栏"
        3.修改刷新时间 修改刷新时间,默认为1秒
        4.最好别乱改,运行不了删了重新从插件市场下载
        5.已自动同步北京时间(UTC+8),一般面板时间不会影响到显示时间
        注:因为写个配置太麻烦了,所以就没有设置,直接修改本文件即可

        修改下面的self.ads_texts_bak 修改公告栏内容
        """
        self.ads_texts_bak_1 = [
            "§7***************",
            "§7| §7{year}/{month}/{day} {week_day}",
            "§b| §7已运行{run_time}",
            "§b| §7{time_cn} §{time_color}{hour}:{minute}:{second}",
            "§b",
            "§b| §f延迟 : {tps}§r",
            "§b| §f在线 §r§7: §e{num_players}",
            "§r§7",
            "§r§7***************",
        ]
        self.刷新时间 = 1
        self.title = "公告栏"
        self.tpscalc = self.GetPluginAPI("tps计算器", (0, 0, 1), True)
        self.another_ad_plugin = self.GetPluginAPI("更好的公告栏", (0, 0, 1), False)
        if self.another_ad_plugin is not None:
            fmts.print_war("检测到<更好的公告栏插件>,请勿同时使用两个公告栏插件,否则可能出现冲突")
            # if Prompt.ask(f"是否继续使用<§e{self.name}§r>插件?继续使用请按回车",default="",show_default=False)=="":
            #     pass
            # else:
            #     fmts.print_war(f"已取消使用<§e{self.name}§r>插件,请勿同时使用两个公告栏插件,否则可能出现冲突")

        self.on_first_run = True
        self.start_time = time.time()
        self.record_del_and_create = {"create": {}}

        pip = self.GetPluginAPI("pip")
        pip.require({"tomlkit": "tomlkit"})
        pip.require({"watchdog": "watchdog"})
        pip.require({"pytz": "pytz"})
        self.read_cfg()
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        import pytz
        self.Observer = Observer
        self.FileSystemEventHandler = FileSystemEventHandler
        self.pytz = pytz
        self.on_cfg_changed()
        
    
    def read_cfg(self):
        import tomlkit
        self.cfg_path = TOOLDELTA_PLUGIN_CFG_DIR / "BetterAnnounce配置.toml"
        if not self.cfg_path.is_file():
            fmts.print_inf("生成配置文件,您可能需要一些操作")
            other_plugin_path = TOOLDELTA_PLUGIN_CFG_DIR / "更好的公告栏.json"
            if other_plugin_path.is_file():
                with other_plugin_path.open("r", encoding="utf-8") as f:
                    other_plugin_cfg = utils.tempjson.read(other_plugin_path)
                ads_texts_bak = other_plugin_cfg.get("公告内容(公告内容:计分板数字)", {
                r"§7%m/%d/20%y 星期[星期]": 0,
                r"§a%H§f : §a%M": -1,
                r"§f在线人数: §a[在线人数]": -2,
                r"§6TPS: [TPS带颜色]§7/20": -3,
                r"§d欢迎大家游玩": -4,
            })
                title = other_plugin_cfg.get("公告标题栏名(请注意长度)", "公告")
                刷新时间 = other_plugin_cfg.get("刷新频率(秒)", 20)
                fmts.print_inf(f"已从<§e更好的公告栏§r>插件配置中读取配置,并生成<§e{self.name}§r>配置文件,可前往<§e{self.cfg_path}§r>修改配置文件,并重新启动插件")
                ads_texts=[]
                basic_args = {
                "[在线人数]": "{num_players}",
                "[星期]": "{week_day}",
                "[TPS]": "{tps}",
                "[TPS带颜色]": "{tps}",
                "%m": "{month}",
                "%d": "{day}",
                "20%y": "{year}",
                "%H": "{hour}",
                "%M": "{minute}",
                "%S": "{second}"
            }
                for text ,_ in ads_texts_bak.items():
                    ads_texts.append(fmts.simple_fmt(basic_args, text))
            cfg_content = tomlkit.document()
            cfg_content.add(tomlkit.comment("公告栏Dev配置文件"))
            cfg_content.add(tomlkit.comment("修改后请重启插件生效"))
            cfg_content.add(tomlkit.comment("公告栏内容,支持的变量有:"))
            cfg_content.add(tomlkit.comment("{num_players} : 在线人数"))
            cfg_content.add(tomlkit.comment("{week_day}    : 周几"))
            cfg_content.add(tomlkit.comment("{tps}         : tps"))
            cfg_content.add(tomlkit.comment("{year}        : 年"))
            cfg_content.add(tomlkit.comment("{month}       : 月"))
            cfg_content.add(tomlkit.comment("{day}         : 日"))
            cfg_content.add(tomlkit.comment("{time_cn}     : 时间中文"))
            cfg_content.add(tomlkit.comment("{time_color}  : 时间颜色"))
            cfg_content.add(tomlkit.comment("{hour}        : 小时"))
            cfg_content.add(tomlkit.comment("{minute}      : 分钟"))
            cfg_content.add(tomlkit.comment("{second}      : 秒"))
            cfg_content.add(tomlkit.comment("{run_time}    : 运行时间"))
            cfg_content.add(tomlkit.comment("排列顺序(上->下),每行前后空格会被忽略,如果需要空行请直接添加一个空行"))
            cfg_content.add(tomlkit.comment("如果需要在文本中使用{}请使用{{}}转义,例如{{num_players}}将被显示为{num_players}"))
            cfg_content.add(tomlkit.nl())
            arr = tomlkit.array()
            arr.multiline(True)
            fmts.print_inf("默认公告栏如下:")
            for line in self.ads_texts_bak_1:
                fmts.clean_print(line+"§r")
                arr.append(line)
            cfg_content["ads_texts"] = arr
            cfg_content.add(tomlkit.nl())
            cfg_content.add(tomlkit.comment("公告栏标题"))
            cfg_content["title"] = Prompt.ask("请输入公告栏标题:",default="公告栏")
            cfg_content.add(tomlkit.nl())
            cfg_content.add(tomlkit.comment("刷新时间(秒)"))
            get_time = Prompt.ask("请输入公告栏刷新时间:",default="1")
            cfg_content["refresh_interval"] = int(get_time) if get_time.isdigit() else 1
            with self.cfg_path.open("w", encoding="utf-8") as f:
                f.write(tomlkit.dumps(cfg_content))
            fmts.print_suc(f"已生成<§e{self.name}§r>配置文件,可前往<§e{self.cfg_path}§r>修改配置文件,并重新启动插件")
        try:
            with self.cfg_path.open("r", encoding="utf-8") as f:
                cfg_content = tomlkit.loads(f.read())
            self.ads_texts_bak = cfg_content.get("ads_texts", self.ads_texts_bak_1)
            self.title = cfg_content.get("title", "公告栏")
            self.刷新时间 = cfg_content.get("refresh_interval", 1)
        except Exception as e:
            fmts.print_err(f"读取配置文件<§e{self.cfg_path}§r>失败,请检查配置文件格式是否正确,错误信息:{e}")
            fmts.print_err("将使用默认配置继续运行,请修复配置文件后重启插件")
            cfg_content = {}
            self.ads_texts_bak = self.ads_texts_bak_1
            self.title = "公告栏"
            self.刷新时间 = 1
        
        fmts.print_suc(f"已加载<§e{self.name}§r>配置文件.")
    def on_inject(self):
        time.sleep(1)
        self.flush_gg()
        time.sleep(1)
        self.flush_scoreboard_text()

    @utils.thread_func("配置文件监控")
    def on_cfg_changed(self):
        num = 0
        for thead in utils.tooldelta_thread.get_threads_list():
            if thead.usage == "配置文件监控":
                num += 1
                if num > 1:
                    return
                thead.stop()
        times = 0
        while True:
            if not self.cfg_path.is_file():
                times += 1
                if times > 5:
                    fmts.print_war(f"配置文件<§e{self.cfg_path}§r>可能丢失,请检查")
                    return
                continue
            break
        cfg_path = self.cfg_path
        
        class ConfigReloadHandler(self.FileSystemEventHandler):
            def __init__(self,outer_self):
                self.outer_self = outer_self
                self.last_modified = 0
                with open(cfg_path, "r", encoding="utf-8") as f:
                    self.cfg_content = f.read()
            def on_modified(self, event):
                current_time = time.time()
                if current_time - self.last_modified < 1:
                    return
                if not event.is_directory and isinstance(event.src_path,str) and event.src_path.endswith(cfg_path.name):
                    fmts.print("检测到§e配置文件已修改,正在重新加载配置文件")
                    
                    try:
                        if self.outer_self is not None:
                            self.last_modified = current_time
                            self.outer_self.read_cfg()
                            fmts.print_suc("配置文件重新加载成功")
                            new_content = cfg_path.read_text(encoding="utf-8")
                            old_lines = self.cfg_content.splitlines(keepends=True)
                            new_lines = new_content.splitlines(keepends=True)
                            diff = difflib.unified_diff(
                            old_lines, new_lines,
                            fromfile=f'{cfg_path.name} (旧)',
                            tofile=f'{cfg_path.name} (新)',
                            lineterm=''
                        )
                            rp("".join(diff))
                            self.cfg_content = new_content
                        else:
                            fmts.print_war("外部类已被销毁,无法重新加载配置文件")
                    except Exception as e:
                        fmts.print_err(f"配置文件重新加载失败:{e}")
        observer = self.Observer()
        observer.schedule(ConfigReloadHandler(self), path=str(self.cfg_path.parent.resolve()), recursive=False)
        observer.start()
        observer.join()


    def flush_gg(self):
        repeat_times = 0
        have_scoreboard = False
        res = self.game_ctrl.sendwscmd(
            "/scoreboard objectives list", waitForResp=True, timeout=5
        )
        if res:
            if len(res.OutputMessages) > 0:
                for i in res.OutputMessages:
                    if i.Success and i.Parameters[0] == "公告":
                        have_scoreboard = True
                        break
            if not have_scoreboard:
                self.print("§e公告栏不存在,尝试创建公告栏")
                self.game_ctrl.sendwocmd(
                    f"/scoreboard objectives add 公告 dummy {self.title}"
                )
        else:
            raise KeyError("获取计分板列表失败")
        while True:
            if repeat_times > 5:
                self.print(
                    "重试次数过多,可能无法正常显示公告栏,请确认租赁服是否流畅,这可能导致命令发送失败"
                )
                raise TimeoutError("公告栏重试失败次数过多.")
            self.print("§e尝试删除重建公告栏[1/3]")
            res = self.game_ctrl.sendwscmd(
                "/scoreboard objectives remove 公告", waitForResp=True, timeout=3
            )
            if res:
                if res.SuccessCount == 0:
                    repeat_times += 1
                    self.print(f"§c删除公告栏失败§f,将在§e{repeat_times * 3}s§f后重试")
                    time.sleep(repeat_times * 3)
                    continue
                else:
                    self.print("§a删除公告栏成功")
            else:
                repeat_times += 1
                self.print(f"§c删除公告栏失败§f,将在§e{repeat_times * 3}s§f后重试")
                time.sleep(repeat_times * 3)
                continue
            time.sleep(0.3)
            self.print("§e尝试创建公告栏[2/3]")
            res = self.game_ctrl.sendwscmd(
                f"/scoreboard objectives add 公告 dummy {self.title}",
                timeout=3,
                waitForResp=True,
            )
            if res:
                if res.SuccessCount == 0:
                    repeat_times += 1
                    self.print(f"§c创建公告栏失败§f,将在§e{repeat_times * 3}s§f后重试")
                    time.sleep(repeat_times * 3)
                    continue
                else:
                    self.print("§a创建公告栏成功")
            else:
                repeat_times += 1
                self.print(f"§c创建公告栏失败§f,将在§e{repeat_times * 3}s§f后重试")
                time.sleep(repeat_times * 3)
                continue
            time.sleep(0.3)
            self.print("§e尝试创建公告栏[3/3]")
            res = self.game_ctrl.sendwscmd(
                "/scoreboard objectives setdisplay sidebar 公告",
                timeout=3,
                waitForResp=True,
            )
            if res:
                if res.SuccessCount == 0:
                    repeat_times += 1
                    self.print(f"§c显示公告栏失败§f,将在§e{repeat_times * 3}s§f后重试")
                    time.sleep(repeat_times * 3)
                    continue
                else:
                    self.print("§a显示公告栏成功")
            else:
                repeat_times += 1
                self.print(f"§c显示公告栏失败§f,将在§e{repeat_times * 3}s§f后重试")
                time.sleep(repeat_times * 3)
                continue
            break

    def get_tps_str(self, color=False):
        if self.tpscalc is None:
            return "§c无前置tps计算器"
        elif color:
            return self.get_tps_color() + str(round(self.tpscalc.get_tps(), 1))
        else:
            return str(round(self.tpscalc.get_tps(), 1))

    def get_tps_color(self):
        tps = self.tpscalc.get_tps()
        if tps > 14:
            return "§a"
        elif tps > 10:
            return "§6"
        else:
            return "§c"

    def get_time_color(self, nowTime):
        hour = int(nowTime.strftime("%H"))
        if 4 <= hour < 7:
            return_value = ("清晨", "9")
        elif 7 <= hour < 11:
            return_value = ("早晨", "a")
        elif 11 <= hour < 13:
            return_value = ("午时", "c")
        elif 13 <= hour < 17:
            return_value = ("下午", "g")
        elif 17 <= hour < 22:
            return_value = ("夜晚", "b")
        elif (22 <= hour <= 23) or (0 <= hour < 4):
            return_value = ("深夜", "3")
        else:
            return_value = ("未知", "f")
        return return_value

    @utils.thread_func("计分板公告文字刷新")
    def flush_scoreboard_text(self):
        self.lastest_texts = []
        beijing_tz = self.pytz.timezone("Asia/Shanghai")
        while True:
            if hasattr(self, "ads_texts_bak") is False:
                time.sleep(0.1)
                continue
            nowTime = datetime.datetime.now(beijing_tz)
            return_value = self.get_time_color(nowTime)
            (self.time_cn, self.time_color) = return_value
            scb_score = len(self.ads_texts_bak)
            self.lastest_texts_bak = self.lastest_texts.copy()
            self.lastest_texts_bak.reverse()
            self.lastest_texts = []
            endime = time.time()
            difference = endime - self.start_time
            for text in self.ads_texts_bak:
                text = utils.simple_fmt(
                    {
                        "{num_players}": len(self.game_ctrl.allplayers),
                        "{week_day}": "周" + "一二三四五六日"[time.localtime().tm_wday],
                        "{tps}": self.get_tps_str(True),
                        "{year}": nowTime.strftime("%Y"),
                        "{month}": nowTime.strftime("%m"),
                        "{day}": nowTime.strftime("%d"),
                        "{time_cn}": self.time_cn,
                        "{time_color}": self.time_color,
                        "{hour}": nowTime.strftime("%H"),
                        "{minute}": nowTime.strftime("%M"),
                        "{second}": nowTime.strftime("%S"),
                        "{run_time}": str(int(difference // 86400))
                        + "天"
                        + str(int((difference % 86400) // 3600))
                        + "小时"
                        + str(int((difference % 3600) // 60))
                        + "分",
                    },
                    text,
                )
                scb_score -= 1
                if self.on_first_run:
                    repeat_times = 0
                    while True:
                        repeat_times += 1
                        if repeat_times > 5:
                            self.print(f"§c多次尝试设置公告栏内容['{text}']失败§f")
                            raise TimeoutError(f"多次尝试设置公告栏内容['{text}']失败")
                        res = self.game_ctrl.sendwscmd(
                            f'/scoreboard players set "{text}" 公告 {scb_score}',
                            waitForResp=True,
                            timeout=3,
                        )
                        if res:
                            if res.SuccessCount == 0:
                                self.print(
                                    f"§c设置公告栏内容['{text}']失败§f,将在§e{repeat_times * 3}s§f后重试"
                                )
                                time.sleep(repeat_times * 3)
                                continue
                        else:
                            self.print(
                                f"§c设置公告栏内容['{text}']失败§f,将在§e{repeat_times * 3}s§f后重试"
                            )
                            continue
                        break
                else:
                    if self.lastest_texts_bak[scb_score] == text:
                        self.lastest_texts.append(text)
                        continue
                    self.game_ctrl.sendwocmd(
                        f'/scoreboard players reset "{self.lastest_texts_bak[scb_score]}" 公告'
                    )
                    self.game_ctrl.sendwocmd(
                        f'/scoreboard players set "{text}" 公告 {scb_score}'
                    )
                self.lastest_texts.append(text)
            self.on_first_run = False
            time.sleep(self.刷新时间)

    def on_setscore(self, packet: dict):
        try:
            if isinstance(packet, dict):
                if packet.get("ActionType", None) is not None:
                    if packet["ActionType"] == 1:
                        for i in packet["Entries"]:
                            if i["ObjectiveName"] == "公告":
                                self.record_del_and_create["create"][i["EntryID"]] = i[
                                    "DisplayName"
                                ]
                    else:
                        for i in packet["Entries"]:
                            if i["EntryID"] in self.record_del_and_create["create"]:
                                del self.record_del_and_create["create"][i["EntryID"]]
                    if len(self.record_del_and_create["create"]) > 3:
                        for i, v in list(self.record_del_and_create["create"].items()):
                            self.game_ctrl.sendwocmd(f'/scoreboard players reset "{v}" 公告')
                        self.record_del_and_create["create"] = {}
            return False
        except Exception as err:
            self.print(f"处理公告栏数据包错误: {err}")
            return False


entry = plugin_entry(BetterAnnounce)