#!/usr/bin/env python3
"""
多节点批量管理系统 - 主程序入口
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.commands import cli


if __name__ == '__main__':
    try:
        cli()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"程序异常退出: {str(e)}")
        sys.exit(1) 