import unittest

from src.protocol import (
    FunctionCode,
    ProtocolType,
    Register,
    append_crc,
    build_read_request,
    build_write_multiple_request,
    build_write_single_request,
)
from src.serial_port import CommunicationError, PowerSupplyController


class FakeTransport:
    def __init__(self):
        self._ports = ["COM5"]
        self._connected = False
        self._port_name = ""
        self.registers = {
            Register.PROTOCOL_TYPE: ProtocolType.RTU,
            Register.SET_VOLTAGE: 5000,
            Register.SET_CURRENT: 1000,
            Register.SAVE_VOLTAGE: 5000,
            Register.SAVE_CURRENT: 1000,
            Register.ACTUAL_VOLTAGE: 4998,
            Register.ACTUAL_CURRENT: 950,
            Register.DEVICE_STATUS: 0,
            Register.OUTPUT_CONTROL: 0,
        }

    def list_ports(self):
        return list(self._ports)

    @property
    def is_connected(self):
        return self._connected

    @property
    def port_name(self):
        return self._port_name

    def connect(self, port: str, baudrate: int = 9600):
        if port not in self._ports:
            return False
        self._connected = True
        self._port_name = port
        return True

    def disconnect(self):
        self._connected = False
        self._port_name = ""

    def request(self, payload: bytes) -> bytes:
        function_code = payload[1]
        if function_code in (FunctionCode.READ_HOLDING_REGISTERS, FunctionCode.READ_INPUT_REGISTERS):
            start = int.from_bytes(payload[2:4], byteorder="big")
            quantity = int.from_bytes(payload[4:6], byteorder="big")
            values = [self.registers[start + offset] for offset in range(quantity)]
            data = bytearray([payload[0], function_code, quantity * 2])
            for value in values:
                data.extend(value.to_bytes(2, byteorder="big"))
            return append_crc(bytes(data))

        if function_code == FunctionCode.WRITE_SINGLE_REGISTER:
            register = int.from_bytes(payload[2:4], byteorder="big")
            value = int.from_bytes(payload[4:6], byteorder="big")
            self.registers[register] = value
            if register == Register.OUTPUT_CONTROL:
                self.registers[Register.DEVICE_STATUS] = 1 if value else 0
            return append_crc(payload[:-2])

        if function_code == FunctionCode.WRITE_MULTIPLE_REGISTERS:
            start = int.from_bytes(payload[2:4], byteorder="big")
            quantity = int.from_bytes(payload[4:6], byteorder="big")
            data = payload[7:-2]
            for index in range(quantity):
                value = int.from_bytes(data[index * 2:index * 2 + 2], byteorder="big")
                self.registers[start + index] = value
            return append_crc(bytes([payload[0], function_code, payload[2], payload[3], payload[4], payload[5]]))

        raise AssertionError("Unsupported request")


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.controller = PowerSupplyController(transport=self.transport)

    def test_auto_connect_and_read_snapshot(self):
        self.assertEqual(self.controller.auto_connect(), "COM5")
        snapshot = self.controller.read_snapshot()
        self.assertEqual(snapshot.port, "COM5")
        self.assertEqual(snapshot.set_voltage, 5.0)
        self.assertEqual(snapshot.set_current, 1.0)
        self.assertAlmostEqual(snapshot.actual_voltage, 4.998, places=3)
        self.assertAlmostEqual(snapshot.actual_current, 0.95, places=3)
        self.assertFalse(snapshot.output_on)

    def test_set_voltage_current_writes_and_confirms(self):
        self.controller.connect("COM5")
        snapshot = self.controller.set_voltage_current(12.345, 2.5)
        self.assertEqual(self.transport.registers[Register.SET_VOLTAGE], 12345)
        self.assertEqual(self.transport.registers[Register.SET_CURRENT], 2500)
        self.assertEqual(self.transport.registers[Register.SAVE_VOLTAGE], 12345)
        self.assertEqual(self.transport.registers[Register.SAVE_CURRENT], 2500)
        self.assertEqual(snapshot.set_voltage, 12.345)
        self.assertEqual(snapshot.set_current, 2.5)

    def test_output_on_and_off_confirm_status(self):
        self.controller.connect("COM5")
        snapshot = self.controller.output_on()
        self.assertTrue(snapshot.output_on)
        snapshot = self.controller.output_off()
        self.assertFalse(snapshot.output_on)

    def test_reject_zero_settings(self):
        self.controller.connect("COM5")
        with self.assertRaises(CommunicationError):
            self.controller.set_voltage_current(0.0, 1.0)


if __name__ == "__main__":
    unittest.main()
