import os
import subprocess
import time
import sys

# 目标exe文件名称
TARGET_EXE = "我的世界回到游戏.exe"

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 构建完整的exe文件路径
exe_path = os.path.join(current_dir, TARGET_EXE)

# 检查文件是否存在
if not os.path.exists(exe_path):
    print(f"错误: 未找到文件 '{TARGET_EXE}'")
    print(f"请确保文件位于: {current_dir}")
    input("按Enter键退出...")
    exit(1)

print(f"找到文件: {exe_path}")

# 检查是否有auto_start参数
if len(sys.argv) > 1 and sys.argv[1] == 'auto_start':
    print("自动启动模式...")
    print(f"正在启动: {exe_path}")
    try:
        # 使用start命令运行exe文件
        subprocess.Popen(["start", "", exe_path], shell=True)
        print("程序已启动成功!")
    except Exception as e:
        print(f"启动失败: {str(e)}")
    exit(0)
else:
    print("输入 'start' 命令运行该文件，或输入 'exit' 退出")
    while True:
    command = input("请输入命令: ").strip().lower()

    if command == "start":
        print(f"正在启动: {exe_path}")
        try:
            # 使用start命令运行exe文件
            subprocess.Popen(["start", "", exe_path], shell=True)
            print("程序已启动成功!")
            break
        except Exception as e:
            print(f"启动失败: {str(e)}")
    elif command == "exit":
        print("程序已退出")
        break
    else:
        print("无效命令，请输入 'start' 或 'exit'")