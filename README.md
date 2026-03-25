# 数控直流电源控制器

基于 PyQt6 开发的数控直流电源上位机软件，支持通过串口控制电源的电压、电流和输出开关。

## 功能特性

- 串口自动检测和连接
- 电压设置和读取
- 电流设置和读取
- 输出开关控制
- 实时状态监控

## 开发环境

### 依赖安装

```bash
pip install -r requirements.txt
```

### 运行程序

```bash
cd src
python main.py
```

## 打包部署

### 本地打包

```bash
pip install pyinstaller
pyinstaller PowerSupplyController.spec
```

可执行文件生成在 `dist/` 目录下。

### GitHub Actions 自动打包

1. 创建版本标签触发自动构建：
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. 或在 GitHub 仓库页面手动触发 workflow

3. 构建完成后在 Actions → Artifacts 下载 Windows exe

## 通信协议

- 波特率: 9600 bps
- 数据位: 8 位
- 校验位: 无
- 停止位: 1 位

### 帧格式

```
帧头(2B) + 设备地址(1B) + 命令码(1B) + 数据长度(1B) + 数据(NB) + 校验和(1B)
```

### 命令码

| 命令码 | 功能 |
|--------|------|
| 0x01 | 读取电压 |
| 0x02 | 设置电压 |
| 0x03 | 读取电流 |
| 0x04 | 设置电流 |
| 0x05 | 输出开关控制 |

## 项目结构

```
power-supply-controller/
├── src/
│   ├── main.py           # 主入口
│   ├── protocol.py       # 通信协议
│   ├── serial_port.py    # 串口管理
│   └── ui/
│       └── main_window.py # 主界面
├── .github/
│   └── workflows/
│       └── build.yml     # 自动打包配置
├── requirements.txt      # Python依赖
├── PowerSupplyController.spec  # PyInstaller配置
└── README.md
```

## 许可证

MIT License
