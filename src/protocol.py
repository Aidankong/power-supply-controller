"""
数控直流电源通信协议
型号: 3402206271 数控型直流电源
"""
from dataclasses import dataclass
from typing import List


@dataclass
class Command:
    """命令定义"""
    READ_VOLTAGE: int = 0x01      # 读取电压
    SET_VOLTAGE: int = 0x02       # 设置电压
    READ_CURRENT: int = 0x03      # 读取电流
    SET_CURRENT: int = 0x04       # 设置电流
    OUTPUT_CONTROL: int = 0x05    # 输出开关控制
    READ_STATUS: int = 0x06       # 读取状态


class FrameBuilder:
    """通信帧构建器"""

    HEADER = bytes([0xAA, 0x55])
    DEFAULT_ADDRESS = 0x01

    @classmethod
    def calculate_checksum(cls, data: bytes) -> int:
        """计算校验和：所有字节累加取低8位"""
        return sum(data) & 0xFF

    @classmethod
    def build_frame(cls, command: int, data: bytes = b'') -> bytes:
        """
        构建通信帧

        帧格式: 帧头(2B) + 设备地址(1B) + 命令码(1B) + 数据长度(1B) + 数据(NB) + 校验和(1B)
        """
        frame = bytearray()
        frame.extend(cls.HEADER)
        frame.append(cls.DEFAULT_ADDRESS)
        frame.append(command)
        frame.append(len(data))
        frame.extend(data)

        # 添加校验和
        checksum = cls.calculate_checksum(bytes(frame))
        frame.append(checksum)

        return bytes(frame)

    @classmethod
    def set_voltage(cls, voltage_mv: int) -> bytes:
        """
        设置电压
        Args:
            voltage_mv: 电压值，单位毫伏 (如 5000 = 5.0V)
        """
        # 电压值用2字节表示，小端序
        data = voltage_mv.to_bytes(2, byteorder='little')
        return cls.build_frame(Command.SET_VOLTAGE, data)

    @classmethod
    def set_current(cls, current_ma: int) -> bytes:
        """
        设置电流
        Args:
            current_ma: 电流值，单位毫安 (如 1000 = 1.0A)
        """
        # 电流值用2字节表示，小端序
        data = current_ma.to_bytes(2, byteorder='little')
        return cls.build_frame(Command.SET_CURRENT, data)

    @classmethod
    def output_on(cls) -> bytes:
        """打开输出"""
        return cls.build_frame(Command.OUTPUT_CONTROL, bytes([0x01]))

    @classmethod
    def output_off(cls) -> bytes:
        """关闭输出"""
        return cls.build_frame(Command.OUTPUT_CONTROL, bytes([0x00]))

    @classmethod
    def read_voltage(cls) -> bytes:
        """读取电压"""
        return cls.build_frame(Command.READ_VOLTAGE)

    @classmethod
    def read_current(cls) -> bytes:
        """读取电流"""
        return cls.build_frame(Command.READ_CURRENT)

    @classmethod
    def read_status(cls) -> bytes:
        """读取状态"""
        return cls.build_frame(Command.READ_STATUS)


class FrameParser:
    """响应帧解析器"""

    @classmethod
    def verify_checksum(cls, frame: bytes) -> bool:
        """验证校验和"""
        if len(frame) < 7:
            return False

        data = frame[:-1]
        checksum = frame[-1]
        return FrameBuilder.calculate_checksum(data) == checksum

    @classmethod
    def parse_response(cls, frame: bytes) -> dict:
        """
        解析响应帧
        Returns:
            dict: {
                'address': int,
                'command': int,
                'data': bytes,
                'valid': bool
            }
        """
        if len(frame) < 7:
            return {'valid': False, 'error': 'Frame too short'}

        if frame[:2] != FrameBuilder.HEADER:
            return {'valid': False, 'error': 'Invalid header'}

        address = frame[2]
        command = frame[3]
        data_length = frame[4]
        data = frame[5:5 + data_length]

        result = {
            'address': address,
            'command': command,
            'data': data,
            'valid': cls.verify_checksum(frame)
        }

        return result

    @classmethod
    def parse_voltage(cls, frame: bytes) -> float:
        """解析电压响应，返回伏特值"""
        result = cls.parse_response(frame)
        if result['valid'] and len(result['data']) >= 2:
            voltage_mv = int.from_bytes(result['data'][:2], byteorder='little')
            return voltage_mv / 1000.0
        return -1.0

    @classmethod
    def parse_current(cls, frame: bytes) -> float:
        """解析电流响应，返回安培值"""
        result = cls.parse_response(frame)
        if result['valid'] and len(result['data']) >= 2:
            current_ma = int.from_bytes(result['data'][:2], byteorder='little')
            return current_ma / 1000.0
        return -1.0
