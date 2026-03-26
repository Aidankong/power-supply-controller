"""
Main UI for the production-line power supply controller.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import List, Optional

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_logging import configure_logging, get_log_path
from protocol import DeviceSnapshot
from serial_port import CommunicationError, PowerSupplyController
from version import APP_VERSION


ENGINEER_PASSWORD = "123456"
REFRESH_INTERVAL_MS = 1000
logger = logging.getLogger(__name__)


class EngineerPasswordDialog(QDialog):
    """Password dialog for entering engineer mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("工程师验证")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("请输入工程师密码"))

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def password(self) -> str:
        return self.password_edit.text().strip()


class EngineerSettingsDialog(QDialog):
    """Engineer settings dialog."""

    def __init__(
        self,
        ports: List[str],
        current_port: str,
        voltage: float,
        current: float,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("工程师设置")
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.port_combo = QComboBox()
        self.port_combo.addItems(ports)
        if current_port and current_port in ports:
            self.port_combo.setCurrentText(current_port)
        form.addRow("串口", self.port_combo)

        self.voltage_spin = QDoubleSpinBox()
        self.voltage_spin.setRange(0.001, 9999.999)
        self.voltage_spin.setDecimals(3)
        self.voltage_spin.setSingleStep(0.100)
        self.voltage_spin.setValue(max(voltage, 0.001))
        form.addRow("电压 (V)", self.voltage_spin)

        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0.001, 9999.999)
        self.current_spin.setDecimals(3)
        self.current_spin.setSingleStep(0.100)
        self.current_spin.setValue(max(current, 0.001))
        form.addRow("电流 (A)", self.current_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("应用并保存到设备")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_port(self) -> str:
        return self.port_combo.currentText().strip()

    def values(self) -> tuple[str, float, float]:
        return (
            self.selected_port(),
            self.voltage_spin.value(),
            self.current_spin.value(),
        )


class DeviceWorker(QObject):
    """Background worker for serial communication."""

    snapshot_ready = pyqtSignal(object)
    ports_ready = pyqtSignal(list)
    status_message = pyqtSignal(str)
    error_message = pyqtSignal(str)
    connection_state = pyqtSignal(bool, str)
    operation_finished = pyqtSignal(str, object)

    def __init__(self):
        super().__init__()
        self.controller = PowerSupplyController()
        self._busy = False

    def _run_exclusive(self, fn):
        if self._busy:
            return
        self._busy = True
        try:
            fn()
        finally:
            self._busy = False

    @pyqtSlot()
    def refresh_ports(self):
        ports = self.controller.list_ports()
        logger.info("UI refreshed serial ports: %s", ports or "none")
        self.ports_ready.emit(ports)

    @pyqtSlot()
    def auto_connect(self):
        def action():
            self.status_message.emit("正在自动扫描并连接电源...")
            port = self.controller.auto_connect()
            if not port:
                self.connection_state.emit(False, "")
                message = self.controller.last_error or "未找到可用电源"
                logger.warning("Auto-connect failed: %s", message)
                self.status_message.emit(message)
                return
            snapshot = self.controller.read_snapshot()
            self.connection_state.emit(True, port)
            self.snapshot_ready.emit(snapshot)
            self.status_message.emit(f"已自动连接到 {port}")
            logger.info("Auto-connect succeeded on %s", port)

        try:
            self._run_exclusive(action)
        except CommunicationError as exc:
            self.controller.disconnect()
            self.connection_state.emit(False, "")
            logger.exception("Auto-connect raised a communication error")
            self.error_message.emit(str(exc))

    @pyqtSlot()
    def refresh_snapshot(self):
        def action():
            if not self.controller.is_connected:
                return
            snapshot = self.controller.read_snapshot()
            self.snapshot_ready.emit(snapshot)

        try:
            self._run_exclusive(action)
        except CommunicationError as exc:
            self.controller.disconnect()
            self.connection_state.emit(False, "")
            logger.warning("Snapshot refresh failed: %s", exc)
            self.error_message.emit(f"刷新失败: {exc}")

    @pyqtSlot(bool)
    def set_output(self, enabled: bool):
        def action():
            if not self.controller.is_connected:
                raise CommunicationError("设备未连接")
            snapshot = self.controller.output_on() if enabled else self.controller.output_off()
            self.snapshot_ready.emit(snapshot)
            text = "输出已打开" if enabled else "输出已关闭"
            self.status_message.emit(text)
            self.operation_finished.emit("output", snapshot)
            logger.info("Output state changed: %s", "ON" if enabled else "OFF")

        try:
            self._run_exclusive(action)
        except CommunicationError as exc:
            logger.warning("Failed to change output state: %s", exc)
            self.error_message.emit(str(exc))

    @pyqtSlot(str, float, float)
    def apply_settings(self, port: str, voltage: float, current: float):
        def action():
            if not port:
                raise CommunicationError("请选择有效串口")
            if self.controller.port_name != port or not self.controller.is_connected:
                self.controller.disconnect()
                if not self.controller.connect(port):
                    message = self.controller.last_error or f"无法连接到 {port}"
                    raise CommunicationError(message)
                self.connection_state.emit(True, port)
                logger.info("Engineer settings connected to %s", port)

            snapshot = self.controller.set_voltage_current(voltage, current)
            self.snapshot_ready.emit(snapshot)
            self.status_message.emit("参数已写入并保存到设备")
            self.operation_finished.emit("settings", snapshot)
            logger.info(
                "Engineer settings applied on %s: voltage=%.3fV current=%.3fA",
                port,
                voltage,
                current,
            )

        try:
            self._run_exclusive(action)
        except CommunicationError as exc:
            logger.warning("Applying settings failed on %s: %s", port, exc)
            self.error_message.emit(str(exc))

    def shutdown(self):
        logger.info("Worker shutdown requested")
        self.controller.disconnect()


class MainWindow(QMainWindow):
    """Production operator UI."""

    request_refresh_ports = pyqtSignal()
    request_auto_connect = pyqtSignal()
    request_refresh_snapshot = pyqtSignal()
    request_set_output = pyqtSignal(bool)
    request_apply_settings = pyqtSignal(str, float, float)
    request_shutdown = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.available_ports: List[str] = []
        self.current_snapshot: Optional[DeviceSnapshot] = None
        self.current_port = ""
        self.log_path = configure_logging()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(REFRESH_INTERVAL_MS)
        self.refresh_timer.timeout.connect(self.request_refresh_snapshot.emit)

        self._init_worker()
        self.init_ui()

        self.request_refresh_ports.emit()
        QTimer.singleShot(0, self.request_auto_connect.emit)
        logger.info("Main window initialized, log file: %s", self.log_path)

    def _init_worker(self):
        self.worker_thread = QThread(self)
        self.worker = DeviceWorker()
        self.worker.moveToThread(self.worker_thread)

        self.request_refresh_ports.connect(self.worker.refresh_ports)
        self.request_auto_connect.connect(self.worker.auto_connect)
        self.request_refresh_snapshot.connect(self.worker.refresh_snapshot)
        self.request_set_output.connect(self.worker.set_output)
        self.request_apply_settings.connect(self.worker.apply_settings)
        self.request_shutdown.connect(self.worker.shutdown)

        self.worker.ports_ready.connect(self.on_ports_ready)
        self.worker.snapshot_ready.connect(self.on_snapshot_ready)
        self.worker.status_message.connect(self.show_status_message)
        self.worker.error_message.connect(self.on_error_message)
        self.worker.connection_state.connect(self.on_connection_state)
        self.worker.operation_finished.connect(self.on_operation_finished)

        self.worker_thread.start()

    def init_ui(self):
        self.setWindowTitle(f"产线电源控制器 v{APP_VERSION}")
        self.setMinimumSize(680, 420)

        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f4f6f8;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #1f4f7a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QPushButton {
                min-height: 36px;
                padding: 6px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #d2d7dc;
                color: #6c757d;
            }
            QLabel[value="true"] {
                font-weight: bold;
            }
            """
        )

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        header_layout = QHBoxLayout()
        self.title_label = QLabel("产线电源控制")
        self.title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.engineer_btn = QPushButton("工程师设置")
        self.engineer_btn.clicked.connect(self.open_engineer_settings)
        header_layout.addWidget(self.engineer_btn)
        root_layout.addLayout(header_layout)

        root_layout.addWidget(self.create_connection_group())
        root_layout.addWidget(self.create_values_group())
        root_layout.addWidget(self.create_output_group())

        self.statusBar().showMessage("启动中")

    def create_connection_group(self) -> QGroupBox:
        group = QGroupBox("连接信息")
        layout = QGridLayout(group)

        layout.addWidget(QLabel("连接状态"), 0, 0)
        self.connection_label = QLabel("未连接")
        self.connection_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(self.connection_label, 0, 1)

        layout.addWidget(QLabel("当前串口"), 0, 2)
        self.port_label = QLabel("--")
        self.port_label.setFont(QFont("Consolas", 12))
        layout.addWidget(self.port_label, 0, 3)

        self.scan_btn = QPushButton("重新扫描并连接")
        self.scan_btn.clicked.connect(self.request_auto_connect.emit)
        layout.addWidget(self.scan_btn, 0, 4)
        return group

    def create_values_group(self) -> QGroupBox:
        group = QGroupBox("参数与状态")
        layout = QGridLayout(group)
        layout.setSpacing(12)

        self.set_voltage_label = self._create_value_label("-- V")
        self.set_current_label = self._create_value_label("-- A")
        self.actual_voltage_label = self._create_value_label("-- V")
        self.actual_current_label = self._create_value_label("-- A")
        self.output_state_label = self._create_value_label("未知")

        layout.addWidget(QLabel("设定电压"), 0, 0)
        layout.addWidget(self.set_voltage_label, 0, 1)
        layout.addWidget(QLabel("设定电流"), 0, 2)
        layout.addWidget(self.set_current_label, 0, 3)

        layout.addWidget(QLabel("实际电压"), 1, 0)
        layout.addWidget(self.actual_voltage_label, 1, 1)
        layout.addWidget(QLabel("实际电流"), 1, 2)
        layout.addWidget(self.actual_current_label, 1, 3)

        layout.addWidget(QLabel("输出状态"), 2, 0)
        layout.addWidget(self.output_state_label, 2, 1)
        return group

    def create_output_group(self) -> QGroupBox:
        group = QGroupBox("输出控制")
        layout = QHBoxLayout(group)

        self.output_on_btn = QPushButton("打开输出")
        self.output_on_btn.setStyleSheet("background-color: #2c8a46; color: white;")
        self.output_on_btn.setEnabled(False)
        self.output_on_btn.clicked.connect(lambda: self.request_set_output.emit(True))
        layout.addWidget(self.output_on_btn)

        self.output_off_btn = QPushButton("关闭输出")
        self.output_off_btn.setStyleSheet("background-color: #b54134; color: white;")
        self.output_off_btn.setEnabled(False)
        self.output_off_btn.clicked.connect(lambda: self.request_set_output.emit(False))
        layout.addWidget(self.output_off_btn)

        layout.addStretch()
        return group

    def _create_value_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        label.setProperty("value", True)
        return label

    @pyqtSlot(list)
    def on_ports_ready(self, ports: List[str]):
        self.available_ports = ports
        logger.info("Available ports updated: %s", ports or "none")

    @pyqtSlot(bool, str)
    def on_connection_state(self, connected: bool, port: str):
        self.current_port = port
        logger.info("Connection state updated: connected=%s port=%s", connected, port or "")
        self.connection_label.setText("已连接" if connected else "未连接")
        self.connection_label.setStyleSheet(
            "color: #2c8a46;" if connected else "color: #7b8794;"
        )
        self.port_label.setText(port or "--")
        self.output_on_btn.setEnabled(connected)
        self.output_off_btn.setEnabled(connected)

        if connected:
            self.refresh_timer.start()
        else:
            self.refresh_timer.stop()
            self._clear_snapshot_labels()

    @pyqtSlot(object)
    def on_snapshot_ready(self, snapshot: DeviceSnapshot):
        self.current_snapshot = snapshot
        logger.info(
            "Snapshot updated: port=%s set=%.3f/%.3f actual=%.3f/%.3f output=%s",
            snapshot.port,
            snapshot.set_voltage,
            snapshot.set_current,
            snapshot.actual_voltage,
            snapshot.actual_current,
            snapshot.output_on,
        )
        self.set_voltage_label.setText(f"{snapshot.set_voltage:.3f} V")
        self.set_current_label.setText(f"{snapshot.set_current:.3f} A")
        self.actual_voltage_label.setText(f"{snapshot.actual_voltage:.3f} V")
        self.actual_current_label.setText(f"{snapshot.actual_current:.3f} A")
        self.output_state_label.setText("开启" if snapshot.output_on else "关闭")
        self.output_state_label.setStyleSheet(
            "color: #2c8a46;" if snapshot.output_on else "color: #b54134;"
        )
        self.port_label.setText(snapshot.port or self.current_port or "--")

    @pyqtSlot(str)
    def show_status_message(self, message: str):
        logger.info("Status message: %s", message)
        self.statusBar().showMessage(message, 5000)

    @pyqtSlot(str)
    def on_error_message(self, message: str):
        logger.warning("UI error message: %s", message)
        self.statusBar().showMessage(message, 7000)
        QMessageBox.warning(self, "通讯异常", message)

    @pyqtSlot(str, object)
    def on_operation_finished(self, operation: str, snapshot: DeviceSnapshot):
        self.current_snapshot = snapshot
        logger.info("Operation finished: %s", operation)
        if operation == "settings":
            QMessageBox.information(self, "完成", "参数已成功写入设备并保存")

    def _clear_snapshot_labels(self):
        self.current_snapshot = None
        self.set_voltage_label.setText("-- V")
        self.set_current_label.setText("-- A")
        self.actual_voltage_label.setText("-- V")
        self.actual_current_label.setText("-- A")
        self.output_state_label.setText("未知")
        self.output_state_label.setStyleSheet("")

    def open_engineer_settings(self):
        logger.info("Engineer settings dialog requested")
        password_dialog = EngineerPasswordDialog(self)
        if password_dialog.exec() != QDialog.DialogCode.Accepted:
            logger.info("Engineer password dialog canceled")
            return

        if password_dialog.password() != ENGINEER_PASSWORD:
            logger.warning("Engineer password verification failed")
            QMessageBox.warning(self, "验证失败", "工程师密码错误")
            return

        default_voltage = self.current_snapshot.set_voltage if self.current_snapshot else 5.000
        default_current = self.current_snapshot.set_current if self.current_snapshot else 1.000
        ports = list(self.available_ports)
        if self.current_port and self.current_port not in ports:
            ports.insert(0, self.current_port)
        if not ports:
            logger.warning("Engineer settings blocked because no serial ports were detected")
            QMessageBox.warning(self, "无串口", "当前未检测到串口，无法打开工程师设置")
            return

        dialog = EngineerSettingsDialog(
            ports=ports,
            current_port=self.current_port,
            voltage=default_voltage,
            current=default_current,
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            logger.info("Engineer settings dialog canceled")
            return

        port, voltage, current = dialog.values()
        logger.info(
            "Engineer settings submitted: port=%s voltage=%.3fV current=%.3fA",
            port,
            voltage,
            current,
        )
        self.request_apply_settings.emit(port, voltage, current)

    def closeEvent(self, event):
        logger.info("Main window closing")
        self.refresh_timer.stop()
        self.request_shutdown.emit()
        self.worker_thread.quit()
        self.worker_thread.wait(2000)
        super().closeEvent(event)


def main():
    log_path = configure_logging()
    logger.info("Application startup v%s, log file: %s", APP_VERSION, log_path)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
