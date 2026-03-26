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
- 默认设备地址：`0x01`
- 小数位规则：统一按 `00.000`
- 缩放规则：`寄存器值 = 实际值 × 1000`

### 关键寄存器

- `1000` 实际输出电压
- `1001` 实际输出电流
- `1007` 设备状态
- `2001` 基准电压
- `2002` 基准电流
- `2016` 输出控制
- `2021` 掉电保存电压
- `2022` 掉电保存电流

### 常用命令与应答

#### 读取实际电压和电流

发送：

```text
01 04 03 E8 00 02 F1 BB
```

应答格式：

```text
01 04 04 VV VV II II CRC CRC
```

示例应答：

```text
01 04 04 13 86 03 B6 DB 04
```

表示：

- `0x1386 = 4998 -> 4.998V`
- `0x03B6 = 950 -> 0.950A`

#### 读取设备状态

发送：

```text
01 04 03 EF 00 01 00 7B
```

应答格式：

```text
01 04 02 SS SS CRC CRC
```

示例：

- 输出关闭：`01 04 02 00 00 B8 F0`
- 输出开启：`01 04 02 00 01 79 30`

状态字 `1007` 主要位定义：

- bit0：输出开关
- bit1：恒流状态
- bit2：恒压状态
- bit4：过热
- bit5：过流
- bit6：过压
- bit15：故障

#### 读取设定电压和电流

发送：

```text
01 03 07 D1 00 02 95 46
```

应答格式：

```text
01 03 04 VV VV II II CRC CRC
```

示例应答，表示设定 `5.000V / 1.000A`：

```text
01 03 04 13 88 03 E8 7A BE
```

#### 打开输出

发送：

```text
01 06 07 E0 FF FF 88 F8
```

应答：

```text
01 06 07 E0 FF FF 88 F8
```

程序随后会再读一次 `1007` 做状态确认。

#### 关闭输出

发送：

```text
01 06 07 E0 00 00 89 48
```

应答：

```text
01 06 07 E0 00 00 89 48
```

程序随后会再读一次 `1007` 做状态确认。

#### 设置 5.000V / 1.000A

运行寄存器：

```text
01 10 07 D1 00 02 04 13 88 03 E8 9D 1F
```

掉电保存寄存器：

```text
01 10 07 E5 00 02 04 13 88 03 E8 9F F8
```

两条命令的应答格式相同：

```text
01 10 START_H START_L 00 02 CRC CRC
```

对应应答：

- `01 10 07 D1 00 02 10 85`
- `01 10 07 E5 00 02 51 45`

#### 设置 12.345V / 2.500A

运行寄存器：

```text
01 10 07 D1 00 02 04 30 39 09 C4 C1 C1
```

掉电保存寄存器：

```text
01 10 07 E5 00 02 04 30 39 09 C4 C3 26
```

### Modbus 异常应答

异常应答格式：

```text
01 8X EC CRC CRC
```

例如：

```text
01 84 02 C2 C1
```

表示 `0x04` 读输入寄存器时返回异常码 `0x02`。

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

### 本地打包

```bash
python3 -m pip install pyinstaller
pyinstaller PowerSupplyController.spec
```

打包产物位于 `dist/PowerSupplyController`。

### GitHub Actions 自动打包

工作流文件：

```text
.github/workflows/build.yml
```

触发方式：

1. 在 GitHub `Actions` 页面手动执行 `Build Releases`
2. 推送版本标签，例如：

```bash
git tag v2.0.1
git push origin v2.0.1
```

构建完成后可在 GitHub Actions 的 artifact 中下载：

- `PowerSupplyController-Windows-v2.0.1`
- `PowerSupplyController-Linux-v2.0.1`

当前版本：

- `v2.0.1`
- Windows 构建产物名：`PowerSupplyController-v2.0.1-windows.exe`
- Linux 构建产物名：`PowerSupplyController-v2.0.1-linux`
