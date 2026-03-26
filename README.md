# 产线电源控制器

面向离线产线电脑部署的 PyQt6 上位机程序，用于通过 `Modbus RTU` 控制程控电源输出开关，并在工程师授权后修改串口、电压、电流参数。

## 产品定位

- 操作员界面只允许查看状态并执行 `打开输出`、`关闭输出`
- 工程师界面输入密码 `123456` 后才可修改串口、电压、电流
- 程序启动后自动扫描串口并尝试连接设备
- 参数修改后会同时写入运行寄存器和掉电保存寄存器
- 所有关键操作都执行 `写入 + 应答校验 + 回读确认`

## 通讯协议

- 协议类型：`Modbus RTU`
- 默认串口参数：`9600 8N1`
- 小数位规则：统一按 `00.000`
- 关键寄存器：
  - `1000` 实际输出电压
  - `1001` 实际输出电流
  - `1007` 设备状态
  - `2001` 基准电压
  - `2002` 基准电流
  - `2016` 输出控制
  - `2021` 掉电保存电压
  - `2022` 掉电保存电流

## 开发运行

```bash
python3 -m pip install -r requirements.txt
python3 src/main.py
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## Windows 打包

```bash
python3 -m pip install pyinstaller
pyinstaller PowerSupplyController.spec
```

打包产物位于 `dist/PowerSupplyController`。
