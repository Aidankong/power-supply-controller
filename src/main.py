"""
数控直流电源控制器 - 主入口
"""
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import main

if __name__ == "__main__":
    main()
