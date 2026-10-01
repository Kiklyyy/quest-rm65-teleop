"""Contract of the onsite RealMan tool-RS485 wrapper, without a robot."""

import importlib.util
from pathlib import Path
import sys
import types

import pytest

SDK_TRANSPORT = Path(
    "/home/lh/quest2ros2_ws/linkerhand/linker_hand_python_sdk/"
    "LinkerHand/core/rs485/realman_modbus.py"
)


def load_transport():
    if not SDK_TRANSPORT.is_file():
        pytest.skip("onsite RealMan-adapted LinkerHand SDK unavailable")
    name = "realman_modbus_contract_test"
    spec = importlib.util.spec_from_file_location(name, SDK_TRANSPORT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_init_only_connects_and_configures_tool_bus(monkeypatch):
    events = []

    class FakeRealmanArmClient:
        def __init__(self, **kwargs):
            events.append(("create", kwargs))

        def set_tool_voltage(self, voltage):
            events.append(("tool_voltage", voltage))

        def set_modbus_mode(self, **kwargs):
            events.append(("modbus_mode", kwargs))

        def disconnect(self):
            events.append(("disconnect",))

    monkeypatch.setitem(sys.modules, "realman_arm_api_api2",
                        types.SimpleNamespace(RealmanArmClient=FakeRealmanArmClient))
    transport = load_transport()
    client = transport.RealmanModbusClient(
        "realman://169.254.128.19:8080?modbus_port=1&baudrate=115200"
        "&timeout=3&tool_voltage=3", slave=0x27)
    assert events == [
        ("create", {"ip": "169.254.128.19", "port": 8080, "auto_connect": True}),
        ("tool_voltage", 3),
        ("modbus_mode", {"port": 1, "baudrate": 115200, "timeout": 3}),
    ]
    client.close()
    assert events[-1] == ("disconnect",)


def test_register_io_uses_only_modbus_calls(monkeypatch):
    events = []

    class FakeRealmanArmClient:
        def __init__(self, **_):
            pass

        def set_tool_voltage(self, *_):
            pass

        def set_modbus_mode(self, **_):
            pass

        def read_multiple_input_registers(self, port, address, count, *, device):
            events.append(("read", port, address, count, device))
            return [0, 73, 0, 0]

        def write_registers(self, port, address, values, *, device):
            events.append(("write", port, address, values, device))

        def disconnect(self):
            pass

    monkeypatch.setitem(sys.modules, "realman_arm_api_api2",
                        types.SimpleNamespace(RealmanArmClient=FakeRealmanArmClient))
    transport = load_transport()
    client = transport.RealmanModbusClient(
        "realman://169.254.128.19:8080?modbus_port=1&tool_voltage=3", slave=0x27)
    response = client.read_input_registers(address=0, count=2, slave=0x27)
    assert response.registers == [73, 0]
    client.write_registers(address=0, values=[73, 0], slave=0x27)
    assert events == [
        ("read", 1, 0, 2, 0x27),
        ("write", 1, 0, [73, 0], 0x27),
    ]
    client.close()


def test_full_l7_sdk_constructor_reads_version_without_arm_motion(monkeypatch):
    events = []

    class FakeRealmanArmClient:
        def __init__(self, **kwargs):
            events.append(("create", kwargs))

        def set_tool_voltage(self, voltage):
            events.append(("tool_voltage", voltage))

        def set_modbus_mode(self, **kwargs):
            events.append(("modbus_mode", kwargs))

        def read_multiple_input_registers(self, port, address, count, *, device):
            events.append(("read", port, address, count, device))
            return [0, 1] * count

        def write_registers(self, port, address, values, *, device):
            events.append(("write", port, address, list(values), device))

        def disconnect(self):
            events.append(("disconnect",))

    monkeypatch.setitem(sys.modules, "realman_arm_api_api2",
                        types.SimpleNamespace(RealmanArmClient=FakeRealmanArmClient))
    sdk_root = SDK_TRANSPORT.parents[3]
    monkeypatch.syspath_prepend(str(sdk_root))
    from LinkerHand.linker_hand_api import LinkerHandApi

    hand = LinkerHandApi(hand_type="right", hand_joint="L7", modbus="RML")
    assert events == [
        ("create", {"ip": "169.254.128.19", "port": 8080, "auto_connect": True}),
        ("tool_voltage", 3),
        ("modbus_mode", {"port": 1, "baudrate": 115200, "timeout": 3}),
        ("read", 1, 153, 6, 0x27),
    ]
    assert hand.get_state() == [1] * 7
    assert hand.get_fault() == [1] * 7
    assert events[-2:] == [
        ("read", 1, 0, 7, 0x27),
        ("read", 1, 28, 7, 0x27),
    ]
    hand.finger_move([73, 0, 0, 0, 0, 0, 156])
    assert events[-1] == ("write", 1, 0, [73, 0, 0, 0, 0, 0, 156], 0x27)
    hand.hand.close()
    assert events[-1] == ("disconnect",)
