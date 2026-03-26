"""
Serial communication and high-level power supply control.
"""
from __future__ import annotations

import time
from typing import List, Optional, Protocol

import serial
import serial.tools.list_ports

try:
    from .protocol import (
        DeviceSnapshot,
        FunctionCode,
        ModbusError,
        ModbusResponseError,
        ProtocolType,
        Register,
        build_read_request,
        build_write_multiple_request,
        build_write_single_request,
        expected_response_length,
        parse_read_response,
        parse_write_response,
        scale_from_register,
        scale_to_register,
        status_bits_to_dict,
    )
except ImportError:
    from protocol import (
        DeviceSnapshot,
        FunctionCode,
        ModbusError,
        ModbusResponseError,
        ProtocolType,
        Register,
        build_read_request,
        build_write_multiple_request,
        build_write_single_request,
        expected_response_length,
        parse_read_response,
        parse_write_response,
        scale_from_register,
        scale_to_register,
        status_bits_to_dict,
    )


class CommunicationError(Exception):
    """Raised for transport or protocol failures."""


class SerialTransport(Protocol):
    """Transport interface for device communication."""

    def list_ports(self) -> List[str]:
        ...

    @property
    def is_connected(self) -> bool:
        ...

    @property
    def port_name(self) -> str:
        ...

    def connect(self, port: str, baudrate: int = 9600) -> bool:
        ...

    def disconnect(self):
        ...

    def request(self, payload: bytes) -> bytes:
        ...


class SerialManager:
    """Low-level serial transport."""

    DEFAULT_BAUDRATE = 9600
    DEFAULT_TIMEOUT = 0.5

    def __init__(self):
        self.serial: Optional[serial.Serial] = None
        self._port_name = ""

    def list_ports(self) -> List[str]:
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    @property
    def port_name(self) -> str:
        return self._port_name

    @property
    def is_connected(self) -> bool:
        return self.serial is not None and self.serial.is_open

    def connect(self, port: str, baudrate: int = DEFAULT_BAUDRATE) -> bool:
        try:
            if self.is_connected:
                self.disconnect()

            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.DEFAULT_TIMEOUT,
                write_timeout=self.DEFAULT_TIMEOUT,
            )
            self._port_name = port
            return True
        except serial.SerialException:
            self.serial = None
            self._port_name = ""
            return False

    def disconnect(self):
        if self.serial is not None:
            try:
                if self.serial.is_open:
                    self.serial.close()
            finally:
                self.serial = None
                self._port_name = ""

    def request(self, payload: bytes) -> bytes:
        if not self.is_connected or self.serial is None:
            raise CommunicationError("Serial port is not connected")

        try:
            self.serial.reset_input_buffer()
            self.serial.write(payload)
            self.serial.flush()
            response = self._read_response(payload[1])
            return response
        except serial.SerialException as exc:
            raise CommunicationError(f"Serial request failed: {exc}") from exc

    def _read_response(self, request_function: int) -> bytes:
        header = self._read_exactly(2)
        function_code = header[1]

        if function_code & 0x80:
            return header + self._read_exactly(3)

        if request_function in (FunctionCode.READ_HOLDING_REGISTERS, FunctionCode.READ_INPUT_REGISTERS):
            byte_count = self._read_exactly(1)[0]
            return header + bytes([byte_count]) + self._read_exactly(byte_count + 2)

        if request_function in (FunctionCode.WRITE_SINGLE_REGISTER, FunctionCode.WRITE_MULTIPLE_REGISTERS):
            return header + self._read_exactly(6)

        expected_length = expected_response_length(bytes([0, request_function, 0, 0, 0, 0]))
        return header + self._read_exactly(expected_length - 2)

    def _read_exactly(self, expected_length: int) -> bytes:
        assert self.serial is not None
        deadline = time.monotonic() + self.DEFAULT_TIMEOUT
        chunks = bytearray()
        while len(chunks) < expected_length and time.monotonic() < deadline:
            remaining = expected_length - len(chunks)
            chunk = self.serial.read(remaining)
            if chunk:
                chunks.extend(chunk)
                continue
            time.sleep(0.01)

        if len(chunks) != expected_length:
            raise CommunicationError("Timed out waiting for device response")
        return bytes(chunks)


class PowerSupplyController:
    """High-level device controller."""

    def __init__(self, transport: Optional[SerialTransport] = None, device_address: int = 0x01):
        self.transport = transport or SerialManager()
        self.device_address = device_address
        self.connected_port = ""

    @property
    def is_connected(self) -> bool:
        return self.transport.is_connected

    @property
    def port_name(self) -> str:
        return self.transport.port_name or self.connected_port

    def list_ports(self) -> List[str]:
        return self.transport.list_ports()

    def connect(self, port: str) -> bool:
        if not self.transport.connect(port):
            return False

        try:
            self._probe_device()
        except CommunicationError:
            self.transport.disconnect()
            return False

        self.connected_port = port
        return True

    def auto_connect(self) -> Optional[str]:
        for port in self.list_ports():
            if self.connect(port):
                return port
        return None

    def disconnect(self):
        self.transport.disconnect()
        self.connected_port = ""

    def _probe_device(self):
        protocol_type = self.read_holding_register(Register.PROTOCOL_TYPE)
        if protocol_type not in (ProtocolType.RTU, ProtocolType.SCPI):
            raise CommunicationError("Unexpected protocol register value")

        if protocol_type != ProtocolType.RTU:
            raise CommunicationError("Device is not configured for Modbus RTU")

        self.read_input_register(Register.DEVICE_STATUS)

    def _request_read(self, function_code: int, start_register: int, quantity: int) -> List[int]:
        request = build_read_request(self.device_address, function_code, start_register, quantity)
        try:
            response = self.transport.request(request)
            return parse_read_response(response, self.device_address, function_code, quantity)
        except (CommunicationError, ModbusError, ModbusResponseError) as exc:
            raise CommunicationError(str(exc)) from exc

    def _request_write_single(self, register: int, value: int):
        request = build_write_single_request(self.device_address, register, value)
        try:
            response = self.transport.request(request)
            parse_write_response(
                response,
                self.device_address,
                FunctionCode.WRITE_SINGLE_REGISTER,
                register,
                value,
            )
        except (CommunicationError, ModbusError, ModbusResponseError) as exc:
            raise CommunicationError(str(exc)) from exc

    def _request_write_multiple(self, start_register: int, values: List[int]):
        request = build_write_multiple_request(self.device_address, start_register, values)
        try:
            response = self.transport.request(request)
            parse_write_response(
                response,
                self.device_address,
                FunctionCode.WRITE_MULTIPLE_REGISTERS,
                start_register,
                len(values),
            )
        except (CommunicationError, ModbusError, ModbusResponseError) as exc:
            raise CommunicationError(str(exc)) from exc

    def read_input_register(self, register: int) -> int:
        return self._request_read(FunctionCode.READ_INPUT_REGISTERS, register, 1)[0]

    def read_input_registers(self, start_register: int, quantity: int) -> List[int]:
        return self._request_read(FunctionCode.READ_INPUT_REGISTERS, start_register, quantity)

    def read_holding_register(self, register: int) -> int:
        return self._request_read(FunctionCode.READ_HOLDING_REGISTERS, register, 1)[0]

    def read_holding_registers(self, start_register: int, quantity: int) -> List[int]:
        return self._request_read(FunctionCode.READ_HOLDING_REGISTERS, start_register, quantity)

    def read_snapshot(self) -> DeviceSnapshot:
        set_voltage, set_current = self.read_holding_registers(Register.SET_VOLTAGE, 2)
        actual_voltage, actual_current = self.read_input_registers(Register.ACTUAL_VOLTAGE, 2)
        status_word = self.read_input_register(Register.DEVICE_STATUS)
        status = status_bits_to_dict(status_word)

        return DeviceSnapshot(
            port=self.port_name,
            connected=self.is_connected,
            set_voltage=scale_from_register(set_voltage),
            set_current=scale_from_register(set_current),
            actual_voltage=scale_from_register(actual_voltage),
            actual_current=scale_from_register(actual_current),
            output_on=status["output_on"],
            status_word=status_word,
        )

    def set_voltage_current(self, voltage: float, current: float) -> DeviceSnapshot:
        voltage_value = scale_to_register(voltage)
        current_value = scale_to_register(current)

        if voltage_value <= 0 or current_value <= 0:
            raise CommunicationError("电压和电流都必须大于 0，设备才允许启动输出")

        self._request_write_multiple(Register.SET_VOLTAGE, [voltage_value, current_value])
        self._request_write_multiple(Register.SAVE_VOLTAGE, [voltage_value, current_value])

        confirmed_voltage, confirmed_current = self.read_holding_registers(Register.SET_VOLTAGE, 2)
        if confirmed_voltage != voltage_value or confirmed_current != current_value:
            raise CommunicationError("参数写入后回读校验失败")

        return self.read_snapshot()

    def output_on(self) -> DeviceSnapshot:
        self._request_write_single(Register.OUTPUT_CONTROL, 0xFFFF)
        snapshot = self.read_snapshot()
        if not snapshot.output_on:
            raise CommunicationError("设备未确认输出已开启")
        return snapshot

    def output_off(self) -> DeviceSnapshot:
        self._request_write_single(Register.OUTPUT_CONTROL, 0)
        snapshot = self.read_snapshot()
        if snapshot.output_on:
            raise CommunicationError("设备未确认输出已关闭")
        return snapshot
