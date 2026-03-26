"""
主界面 - PyQt6
"""
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QSpinBox, QDoubleSpinBox,
    QGroupBox, QGridLayout, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from serial_port import PowerSupplyController, SerialManager


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.controller = PowerSupplyController()
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_readings)

        self.init_ui()
        self.refresh_ports()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("数控直流电源控制器")
        self.setMinimumSize(500, 400)

        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'icon.ico')
        if os.path.exists(icon_path):
            from PyQt6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 串口连接区域
        connection_group = self.create_connection_group()
        main_layout.addWidget(connection_group)

        # 控制区域
        control_group = self.create_control_group()
        main_layout.addWidget(control_group)

        # 状态显示区域
        status_group = self.create_status_group()
        main_layout.addWidget(status_group)

        # 添加弹性空间
        main_layout.addStretch()

    def create_connection_group(self) -> QGroupBox:
        """创建串口连接区域"""
        group = QGroupBox("串口连接")
        layout = QHBoxLayout(group)

        # 串口选择
        layout.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        layout.addWidget(self.port_combo)

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_ports)
        layout.addWidget(self.refresh_btn)

        # 连接/断开按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setStyleSheet("background-color: #27ae60; color: white;")
        self.connect_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_btn)

        layout.addStretch()
        return group

    def create_control_group(self) -> QGroupBox:
        """创建控制区域"""
        group = QGroupBox("电源控制")
        layout = QGridLayout(group)
        layout.setSpacing(15)

        # 电压设置
        layout.addWidget(QLabel("电压 (V):"), 0, 0)
        self.voltage_spin = QDoubleSpinBox()
        self.voltage_spin.setRange(0, 30)
        self.voltage_spin.setValue(5.0)
        self.voltage_spin.setSingleStep(0.1)
        self.voltage_spin.setDecimals(2)
        layout.addWidget(self.voltage_spin, 0, 1)

        self.set_voltage_btn = QPushButton("设置电压")
        self.set_voltage_btn.setEnabled(False)
        self.set_voltage_btn.clicked.connect(self.set_voltage)
        layout.addWidget(self.set_voltage_btn, 0, 2)

        # 电流设置
        layout.addWidget(QLabel("电流 (A):"), 1, 0)
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0, 5)
        self.current_spin.setValue(1.0)
        self.current_spin.setSingleStep(0.1)
        self.current_spin.setDecimals(2)
        layout.addWidget(self.current_spin, 1, 1)

        self.set_current_btn = QPushButton("设置电流")
        self.set_current_btn.setEnabled(False)
        self.set_current_btn.clicked.connect(self.set_current)
        layout.addWidget(self.set_current_btn, 1, 2)

        # 输出开关
        layout.addWidget(QLabel("输出控制:"), 2, 0)

        output_layout = QHBoxLayout()

        self.output_on_btn = QPushButton("打开输出")
        self.output_on_btn.setEnabled(False)
        self.output_on_btn.setStyleSheet("background-color: #27ae60; color: white;")
        self.output_on_btn.clicked.connect(self.output_on)
        output_layout.addWidget(self.output_on_btn)

        self.output_off_btn = QPushButton("关闭输出")
        self.output_off_btn.setEnabled(False)
        self.output_off_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        self.output_off_btn.clicked.connect(self.output_off)
        output_layout.addWidget(self.output_off_btn)

        layout.addLayout(output_layout, 2, 1, 1, 2)

        return group

    def create_status_group(self) -> QGroupBox:
        """创建状态显示区域"""
        group = QGroupBox("实时状态")
        layout = QGridLayout(group)

        # 电压显示
        layout.addWidget(QLabel("当前电压:"), 0, 0)
        self.voltage_label = QLabel("-- V")
        self.voltage_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.voltage_label.setStyleSheet("color: #2980b9;")
        layout.addWidget(self.voltage_label, 0, 1)

        # 电流显示
        layout.addWidget(QLabel("当前电流:"), 1, 0)
        self.current_label = QLabel("-- A")
        self.current_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.current_label.setStyleSheet("color: #c0392b;")
        layout.addWidget(self.current_label, 1, 1)

        # 连接状态
        layout.addWidget(QLabel("连接状态:"), 2, 0)
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(self.status_label, 2, 1)

        # 自动刷新开关
        self.auto_refresh_btn = QPushButton("自动刷新: 关")
        self.auto_refresh_btn.setCheckable(True)
        self.auto_refresh_btn.clicked.connect(self.toggle_auto_refresh)
        layout.addWidget(self.auto_refresh_btn, 2, 2)

        return group

    def refresh_ports(self):
        """刷新串口列表"""
        ports = SerialManager.list_ports()
        self.port_combo.clear()
        self.port_combo.addItems(ports)

        if not ports:
            self.port_combo.addItem("未检测到串口")

    def toggle_connection(self):
        """切换连接状态"""
        if self.controller.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """连接串口"""
        port = self.port_combo.currentText()
        if not port or port == "未检测到串口":
            QMessageBox.warning(self, "警告", "请选择有效的串口")
            return

        if self.controller.connect(port):
            self.status_label.setText("已连接")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.connect_btn.setText("断开")
            self.connect_btn.setStyleSheet("background-color: #e74c3c; color: white;")
            self.set_controls_enabled(True)
        else:
            QMessageBox.critical(self, "错误", f"无法连接到 {port}")

    def disconnect(self):
        """断开连接"""
        self.controller.disconnect()
        self.refresh_timer.stop()
        self.status_label.setText("未连接")
        self.status_label.setStyleSheet("color: #7f8c8d;")
        self.connect_btn.setText("连接")
        self.connect_btn.setStyleSheet("background-color: #27ae60; color: white;")
        self.set_controls_enabled(False)
        self.voltage_label.setText("-- V")
        self.current_label.setText("-- A")
        self.auto_refresh_btn.setChecked(False)
        self.auto_refresh_btn.setText("自动刷新: 关")

    def set_controls_enabled(self, enabled: bool):
        """设置控制按钮的启用状态"""
        self.set_voltage_btn.setEnabled(enabled)
        self.set_current_btn.setEnabled(enabled)
        self.output_on_btn.setEnabled(enabled)
        self.output_off_btn.setEnabled(enabled)
        self.auto_refresh_btn.setEnabled(enabled)

    def set_voltage(self):
        """设置电压"""
        voltage = self.voltage_spin.value()
        if self.controller.set_voltage(voltage):
            self.refresh_readings()
        else:
            QMessageBox.warning(self, "警告", "设置电压失败")

    def set_current(self):
        """设置电流"""
        current = self.current_spin.value()
        if self.controller.set_current(current):
            self.refresh_readings()
        else:
            QMessageBox.warning(self, "警告", "设置电流失败")

    def output_on(self):
        """打开输出"""
        if not self.controller.output_on():
            QMessageBox.warning(self, "警告", "打开输出失败")

    def output_off(self):
        """关闭输出"""
        if not self.controller.output_off():
            QMessageBox.warning(self, "警告", "关闭输出失败")

    def refresh_readings(self):
        """刷新电压和电流读数"""
        if not self.controller.is_connected:
            return

        voltage = self.controller.read_voltage()
        current = self.controller.read_current()

        if voltage >= 0:
            self.voltage_label.setText(f"{voltage:.2f} V")
        if current >= 0:
            self.current_label.setText(f"{current:.3f} A")

    def toggle_auto_refresh(self, checked: bool):
        """切换自动刷新"""
        if checked:
            self.refresh_timer.start(500)  # 每500ms刷新一次
            self.auto_refresh_btn.setText("自动刷新: 开")
        else:
            self.refresh_timer.stop()
            self.auto_refresh_btn.setText("自动刷新: 关")

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.refresh_timer.stop()
        if self.controller.is_connected:
            self.controller.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
