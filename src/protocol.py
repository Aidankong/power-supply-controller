"""
Modbus RTU protocol helpers for the programmable power supply.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


class ModbusError(Exception):
    """Base Modbus protocol error."""


class ModbusResponseError(ModbusError):
    """Raised when a device returns an invalid or exceptional response."""


class Register:
    """Device register map."""

    ACTUAL_VOLTAGE = 1000
    ACTUAL_CURRENT = 1001
    DEVICE_STATUS = 1007
    DEVICE_ADDRESS = 2000
    SET_VOLTAGE = 2001
    SET_CURRENT = 2002
    BAUDRATE = 2007
    WORK_MODE = 2014
    OUTPUT_CONTROL = 2016
    PROTOCOL_TYPE = 2020
    SAVE_VOLTAGE = 2021
    SAVE_CURRENT = 2022


class FunctionCode:
    """Modbus function codes used by the device."""

    READ_HOLDING_REGISTERS = 0x03
    READ_INPUT_REGISTERS = 0x04
    WRITE_SINGLE_REGISTER = 0x06
    WRITE_MULTIPLE_REGISTERS = 0x10


class ProtocolType:
    """Protocol type register values."""

    RTU = 0
    SCPI = 65


def crc16(data: bytes) -> int:
    """Calculate Modbus RTU CRC16."""
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def append_crc(data: bytes) -> bytes:
    """Append little-endian CRC16 to a Modbus frame."""
    checksum = crc16(data)
    return data + checksum.to_bytes(2, byteorder="little")


def verify_crc(frame: bytes) -> bool:
    """Verify frame CRC16."""
    if len(frame) < 4:
        return False
    body = frame[:-2]
    received_crc = int.from_bytes(frame[-2:], byteorder="little")
    return crc16(body) == received_crc


def build_read_request(device_address: int, function_code: int, start_register: int, quantity: int) -> bytes:
    """Build a read register request."""
    payload = bytes(
        [
            device_address,
            function_code,
            (start_register >> 8) & 0xFF,
            start_register & 0xFF,
            (quantity >> 8) & 0xFF,
            quantity & 0xFF,
        ]
    )
    return append_crc(payload)


def build_write_single_request(device_address: int, register: int, value: int) -> bytes:
    """Build a write single register request."""
    payload = bytes(
        [
            device_address,
            FunctionCode.WRITE_SINGLE_REGISTER,
            (register >> 8) & 0xFF,
            register & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
        ]
    )
    return append_crc(payload)


def build_write_multiple_request(device_address: int, start_register: int, values: List[int]) -> bytes:
    """Build a write multiple registers request."""
    quantity = len(values)
    register_bytes = bytearray()
    for value in values:
        register_bytes.extend([(value >> 8) & 0xFF, value & 0xFF])

    payload = bytearray(
        [
            device_address,
            FunctionCode.WRITE_MULTIPLE_REGISTERS,
            (start_register >> 8) & 0xFF,
            start_register & 0xFF,
            (quantity >> 8) & 0xFF,
            quantity & 0xFF,
            len(register_bytes),
        ]
    )
    payload.extend(register_bytes)
    return append_crc(bytes(payload))


def expected_response_length(request: bytes) -> int:
    """Infer the expected response length from a request."""
    function_code = request[1]
    if function_code in (FunctionCode.READ_HOLDING_REGISTERS, FunctionCode.READ_INPUT_REGISTERS):
        quantity = int.from_bytes(request[4:6], byteorder="big")
        return 5 + quantity * 2
    if function_code in (FunctionCode.WRITE_SINGLE_REGISTER, FunctionCode.WRITE_MULTIPLE_REGISTERS):
        return 8
    raise ModbusError(f"Unsupported function code: 0x{function_code:02X}")


def _raise_if_exception(function_code: int, data: bytes):
    if function_code & 0x80:
        exception_code = data[0] if data else None
        raise ModbusResponseError(f"Device returned exception code: {exception_code}")


def parse_read_response(frame: bytes, expected_address: int, expected_function: int, expected_quantity: int) -> List[int]:
    """Parse a read registers response."""
    if len(frame) == 5:
        if not verify_crc(frame):
            raise ModbusResponseError("Invalid CRC in exception response")
        if frame[0] != expected_address:
            raise ModbusResponseError("Unexpected device address in response")
        _raise_if_exception(frame[1], frame[2:-2])
    if len(frame) != 5 + expected_quantity * 2:
        raise ModbusResponseError("Unexpected read response length")
    if not verify_crc(frame):
        raise ModbusResponseError("Invalid CRC in read response")
    if frame[0] != expected_address:
        raise ModbusResponseError("Unexpected device address in response")

    function_code = frame[1]
    _raise_if_exception(function_code, frame[2:-2])
    if function_code != expected_function:
        raise ModbusResponseError("Unexpected function code in response")

    byte_count = frame[2]
    expected_byte_count = expected_quantity * 2
    if byte_count != expected_byte_count:
        raise ModbusResponseError("Unexpected byte count in response")

    payload = frame[3:-2]
    values = []
    for index in range(0, len(payload), 2):
        values.append(int.from_bytes(payload[index:index + 2], byteorder="big"))
    return values


def parse_write_response(
    frame: bytes,
    expected_address: int,
    expected_function: int,
    expected_start_register: int,
    expected_quantity_or_value: int,
):
    """Parse a write single/multiple registers response."""
    if len(frame) == 5:
        if not verify_crc(frame):
            raise ModbusResponseError("Invalid CRC in exception response")
        if frame[0] != expected_address:
            raise ModbusResponseError("Unexpected device address in response")
        _raise_if_exception(frame[1], frame[2:-2])
    if len(frame) != 8:
        raise ModbusResponseError("Unexpected write response length")
    if not verify_crc(frame):
        raise ModbusResponseError("Invalid CRC in write response")
    if frame[0] != expected_address:
        raise ModbusResponseError("Unexpected device address in response")

    function_code = frame[1]
    _raise_if_exception(function_code, frame[2:-2])
    if function_code != expected_function:
        raise ModbusResponseError("Unexpected function code in response")

    echoed_register = int.from_bytes(frame[2:4], byteorder="big")
    echoed_value = int.from_bytes(frame[4:6], byteorder="big")
    if echoed_register != expected_start_register or echoed_value != expected_quantity_or_value:
        raise ModbusResponseError("Unexpected write echo from device")


def status_bits_to_dict(status_word: int) -> Dict[str, bool]:
    """Decode the device status word."""
    return {
        "output_on": bool(status_word & (1 << 0)),
        "constant_current": bool(status_word & (1 << 1)),
        "constant_voltage": bool(status_word & (1 << 2)),
        "external_control": bool(status_word & (1 << 3)),
        "over_temperature": bool(status_word & (1 << 4)),
        "over_current": bool(status_word & (1 << 5)),
        "over_voltage": bool(status_word & (1 << 6)),
        "fault": bool(status_word & (1 << 15)),
    }


def scale_to_register(value: float) -> int:
    """Convert engineering units to the device register format (00.000)."""
    return int(round(value * 1000))


def scale_from_register(value: int) -> float:
    """Convert register value to engineering units (00.000)."""
    return value / 1000.0


@dataclass
class DeviceSnapshot:
    """Current device values shown on the operator UI."""

    port: str
    connected: bool
    set_voltage: float
    set_current: float
    actual_voltage: float
    actual_current: float
    output_on: bool
    status_word: int
