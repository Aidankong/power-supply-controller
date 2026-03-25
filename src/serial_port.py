"""
串口通信管理
"""
import serial
import serial.tools.list_ports
from typing import Optional, List, Callable
from protocol import FrameParser


class SerialManager:
    """串口管理器"""

    # 默认串口配置
    DEFAULT_BAUDRATE = 9600
    DEFAULT_TIMEOUT = 1.0

    def __init__(self):
        self.serial: Optional[serial.Serial] = None
        self._is_connected = False

    @staticmethod
    def list_ports() -> List[str]:
        """列出所有可用串口"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self.serial is not None and self.serial.is_open

    def connect(self, port: str, baudrate: int = DEFAULT_BAUDRATE) -> bool:
        """
        连接串口
        Args:
            port: 串口设备路径 (如 /dev/ttyUSB0 或 COM3)
            baudrate: 波特率，默认9600
        Returns:
            bool: 连接是否成功
        """
        try:
            if self.is_connected:
                self.disconnect()

            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.DEFAULT_TIMEOUT
            )
            self._is_connected = True
            return True
        except serial.SerialException as e:
            print(f"串口连接失败: {e}")
            self._is_connected = False
            return False

    def disconnect(self):
        """断开串口连接"""
        if self.serial is not None:
            try:
                if self.serial.is_open:
                    self.serial.close()
            except Exception:
                pass
            finally:
                self.serial = None
                self._is_connected = False

    def send(self, data: bytes) -> bool:
        """
        发送数据
        Args:
            data: 要发送的字节数据
        Returns:
            bool: 发送是否成功
        """
        if not self.is_connected:
            return False

        try:
            self.serial.write(data)
            self.serial.flush()
            return True
        except serial.SerialException as e:
            print(f"发送数据失败: {e}")
            return False

    def receive(self, length: int = 64, timeout: float = None) -> Optional[bytes]:
        """
        接收数据
        Args:
            length: 最大读取长度
            timeout: 超时时间（秒），None使用默认超时
        Returns:
            接收到的数据，失败返回None
        """
        if not self.is_connected:
            return None

        try:
            if timeout is not None:
                old_timeout = self.serial.timeout
                self.serial.timeout = timeout

            data = self.serial.read(length)

            if timeout is not None:
                self.serial.timeout = old_timeout

            return data if data else None
        except serial.SerialException as e:
            print(f"接收数据失败: {e}")
            return None

    def send_and_receive(self, data: bytes, response_length: int = 64) -> Optional[bytes]:
        """
        发送数据并等待响应
        Args:
            data: 要发送的数据
            response_length: 期望的响应长度
        Returns:
            响应数据，失败返回None
        """
        if self.send(data):
            return self.receive(response_length)
        return None


class PowerSupplyController:
    """电源控制器 - 高层封装"""

    def __init__(self):
        self.serial_manager = SerialManager()

    @property
    def is_connected(self) -> bool:
        return self.serial_manager.is_connected

    def connect(self, port: str) -> bool:
        """连接电源"""
        return self.serial_manager.connect(port)

    def disconnect(self):
        """断开连接"""
        self.serial_manager.disconnect()

    def output_on(self) -> bool:
        """打开输出"""
        from protocol import FrameBuilder
        return self.serial_manager.send(FrameBuilder.output_on())

    def output_off(self) -> bool:
        """关闭输出"""
        from protocol import FrameBuilder
        return self.serial_manager.send(FrameBuilder.output_off())

    def set_voltage(self, voltage: float) -> bool:
        """
        设置电压
        Args:
            voltage: 电压值（伏特），如 5.0 表示5V
        """
        from protocol import FrameBuilder
        voltage_mv = int(voltage * 1000)
        return self.serial_manager.send(FrameBuilder.set_voltage(voltage_mv))

    def set_current(self, current: float) -> bool:
        """
        设置电流
        Args:
            current: 电流值（安培），如 1.0 表示1A
        """
        from protocol import FrameBuilder
        current_ma = int(current * 1000)
        return self.serial_manager.send(FrameBuilder.set_current(current_ma))

    def read_voltage(self) -> float:
        """读取当前电压"""
        from protocol import FrameBuilder, FrameParser
        response = self.serial_manager.send_and_receive(FrameBuilder.read_voltage())
        if response:
            return FrameParser.parse_voltage(response)
        return -1.0

    def read_current(self) -> float:
        """读取当前电流"""
        from protocol import FrameBuilder, FrameParser
        response = self.serial_manager.send_and_receive(FrameBuilder.read_current())
        if response:
            return FrameParser.parse_current(response)
        return -1.0
