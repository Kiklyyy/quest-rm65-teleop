"""Pure startup checks; operator confirmations are never inferred from telemetry."""
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Confirmation:
    workspace_clear: bool = False
    estop_reachable: bool = False
    operator_ready: bool = False
    linkerhand_risk_accepted: bool = False

    @property
    def complete(self):
        return self.workspace_clear and self.estop_reachable and self.operator_ready


@dataclass(frozen=True)
class PreflightFacts:
    domain: str = '0'
    environment_ok: bool = False
    hardware_packages: bool = False
    graph_ok: bool = False
    process_scan_ok: bool = False
    tcp_port_free: bool = False
    duplicate_driver: bool = False
    duplicate_control: bool = False
    stack_running: bool = False
    hand_running: bool = False
    hand_sdk_ok: bool = False
    quest_available: bool = False
    detail: str = ''


@dataclass(frozen=True)
class Check:
    key: str
    title: str
    level: str
    detail: str


@dataclass(frozen=True)
class PreflightResult:
    mode: str
    checks: Tuple[Check, ...]
    component: str = 'system'

    @property
    def allowed(self):
        return all(c.level != 'blocking' for c in self.checks)

    def can_start(self, confirmation=Confirmation()):
        return self.allowed and (self.mode == 'dry_run' or (confirmation.complete and
            (self.component != 'hand' or confirmation.linkerhand_risk_accepted)))


def evaluate_preflight(facts, mode, component='system'):
    if mode not in ('dry_run', 'hardware'):
        raise ValueError(mode)
    valid_domain = facts.domain.isascii() and facts.domain.isdecimal() and 0 <= int(facts.domain) <= 232
    checks = []

    def check(key, title, ok, detail):
        checks.append(Check(key, title, 'pass' if ok else 'blocking', detail))

    check('environment', 'ROS 2 环境', facts.environment_ok,
          facts.detail or ('系统 Python · Humble' if facts.environment_ok else '等待环境检测'))
    check('domain', 'ROS Domain', valid_domain, f'Domain {facts.domain} · 与监控共用环境')
    check('graph', 'ROS graph / 本机进程检查', facts.graph_ok and facts.process_scan_ok,
          '只读发现；检查结果会在启动时重新获取')
    if component == 'hand':
        check('hand', '无重复灵巧手进程', not facts.hand_running, '仅启动独立右手节点')
        if mode == 'hardware':
            check('sdk', '现场 RealMan 适配 SDK', facts.hand_sdk_ok, '只检查文件；此检查不连接 SDK')
            checks.append(Check('coexistence', '第二 API 连接共存风险', 'warning',
                                '风险尚未关闭；须单独确认，不随双臂系统启动'))
        return PreflightResult(mode, tuple(checks), component)
    check('driver', '无重复 RM Driver', not facts.duplicate_driver, '已发现' if facts.duplicate_driver else '未发现')
    check('control', '无重复 rm_control', not facts.duplicate_control, '已发现' if facts.duplicate_control else '未发现')
    check('tcp', 'TCP 10000', facts.tcp_port_free, '空闲' if facts.tcp_port_free else '占用或不可用')
    check('stack', '控制栈未运行', not facts.stack_running, '已发现' if facts.stack_running else '未发现')
    if mode == 'hardware':
        check('packages', '硬件软件包', facts.hardware_packages, '需要已安装 RM Driver / rm_control')
        check('hand', '无灵巧手共存连接', not facts.hand_running, '第二 API 连接共存风险尚未关闭')
    checks.append(Check('quest', 'Quest 输入', 'pass' if facts.quest_available else 'warning',
                        '左右输入新鲜' if facts.quest_available else '尚未收到；TCP 启动后继续等待输入'))
    return PreflightResult(mode, tuple(checks), component)
