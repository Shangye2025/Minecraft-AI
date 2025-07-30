# game_controller.py
import os
import subprocess
import time
print("加载game_controller模块...")  # 用于调试

class GameController:
    def __init__(self, back_to_game_mode=0):
        print("初始化GameController类...")  # 用于调试
        # 设置回到游戏模式：0=点击方式，1=直接运行回到游戏exe文件
        self.back_to_game_mode = back_to_game_mode
        # 操作映射：AI输出→键盘/鼠标动作
        self.action_map = {
            "w": lambda: self._press_key("w", 0.5),  # 前进
            "s": lambda: self._press_key("s", 0.5),  # 后退
            "a": lambda: self._press_key("a", 0.3),  # 左移
            "d": lambda: self._press_key("d", 0.3),  # 右移
            "左键点击": lambda: self._click_mouse("left"),  # 攻击/砍伐
            "空格": lambda: self._press_key("space", 0.2),  # 跳跃
            "e": lambda: self._press_key("e", 0.2),  # 打开背包
            "鼠标左移": lambda: self._move_mouse(-50, 0),  # 左转
            "鼠标右移": lambda: self._move_mouse(50, 0),    # 右转
            "esc": lambda: self._press_key("esc", 0.1),  # 按ESC键
            "回到游戏": lambda: self._back_to_game(),  # 回到游戏(根据模式选择方式)

        }
        self.min_action_interval = 0.5  # 操作间隔（秒）
        self.last_action_time = 0

    # 辅助方法：按住按键
    def _press_key(self, key, duration):
        import pyautogui
        import time
        pyautogui.keyDown(key)
        time.sleep(duration)
        pyautogui.keyUp(key)

    # 辅助方法：鼠标点击
    def _click_mouse(self, button):
        import pyautogui
        pyautogui.click(button=button)

    # 辅助方法：点击特定位置
    def _click_position(self, x, y):
        import pyautogui
        pyautogui.click(x, y)

    # 辅助方法：鼠标移动
    def _move_mouse(self, x, y):
        import pyautogui
        pyautogui.moveRel(x, y, duration=0.2)

    # 统一入口方法，根据模式选择执行方式
    def _back_to_game(self):
        if self.back_to_game_mode == 1:
            self._run_exe_back_to_game()
        else:
            self._click_back_to_game()
            
    # 辅助方法：直接运行回到游戏exe文件
    def _run_exe_back_to_game(self):
        print("直接运行回到游戏exe文件...")
        try:
            # 确保在正确的工作目录
            exe_dir = os.path.dirname(os.path.abspath(__file__))
            os.chdir(exe_dir)
            
            # 直接运行exe文件
            exe_path = os.path.join(exe_dir, "mchd.exe")
            if not os.path.exists(exe_path):
                print(f"错误: 找不到回到游戏exe文件: {exe_path}\n请确保mchd.exe文件存在于Minecraft目录下")
                return
            
            print(f"启动回到游戏exe: {exe_path}")
            process = subprocess.Popen([exe_path],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             text=True)
            
            # 增加等待时间至8秒，确保exe有足够时间执行
            time.sleep(8)  # 进一步延长等待时间至8秒
            
            # 检查进程是否仍在运行
            if process.poll() is None:
                print("回到游戏exe进程仍在运行，继续等待...")
                time.sleep(5)  # 再等待5秒
                
                # 再次检查，如果仍在运行则尝试终止
                if process.poll() is None:
                    print("回到游戏exe进程长时间运行，尝试终止...")
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    print("回到游戏exe进程已终止")
            
            # 获取输出和错误信息
            stdout, stderr = process.communicate()
            if stdout:
                print(f"回到游戏exe输出: {stdout}")
            if stderr:
                print(f"回到游戏exe错误: {stderr}")
            
            # 检查退出码
            exit_code = process.returncode
            if exit_code == 0:
                print("回到游戏exe执行成功")
            else:
                print(f"回到游戏exe执行失败，退出码: {exit_code}")
                return
            
            print("回到游戏操作完成")
        except Exception as e:
            print(f"运行回到游戏exe时出错: {str(e)}")
    
    # 辅助方法：点击回到游戏按钮（原有逻辑）
    def _click_back_to_game(self):
        # 导入必要的模块
        import win32gui
        # 获取游戏窗口区域
        from screen_capture import MinecraftScreenCapture
        capture = MinecraftScreenCapture()
        if not capture.game_region:
            capture.find_game_window()
        
        # 确保窗口被激活
        hwnd = win32gui.FindWindow(None, win32gui.GetWindowText(win32gui.GetForegroundWindow()))
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)  # 等待窗口激活
        
        # 计算回到游戏按钮的位置
        window_top = capture.game_region["top"]
        window_left = capture.game_region["left"]
        window_width = capture.game_region["width"]
        window_height = capture.game_region["height"]
        
        # 回到游戏按钮通常在菜单顶部中央
        # 垂直位置系数：0.25表示顶部1/4，可根据实际情况调整
        vertical_position_ratio = 0.25
        button_x = window_left + window_width // 2
        button_y = window_top + int(window_height * vertical_position_ratio)
        
        print(f"点击回到游戏按钮位置：({button_x}, {button_y}) (垂直位置系数: {vertical_position_ratio})")
        
        # 移动鼠标到按钮位置，然后点击
        import pyautogui
        pyautogui.moveTo(button_x, button_y, duration=0.5)  # 缓慢移动鼠标，便于观察
        self._click_position(button_x, button_y)
        time.sleep(0.5)  # 等待点击生效


    # 执行操作的主方法
    def execute_action(self, action):
        import time
        current_time = time.time()
        
        # 控制操作间隔，避免太频繁
        if current_time - self.last_action_time < self.min_action_interval:
            time.sleep(self.min_action_interval - (current_time - self.last_action_time))
        
        # 执行操作
        if action in self.action_map:
            print(f"执行操作：{action}")
            self.action_map[action]()
            self.last_action_time = current_time
        else:
            print(f"无法识别的操作：{action}，跳过执行")

# 测试代码（单独运行时执行）
if __name__ == "__main__":
    import time  # 补充time模块导入
    print("测试GameController类...")
    controller = GameController()
    test_actions = ["w", "左键点击", "空格"]
    for action in test_actions:
        controller.execute_action(action)
        time.sleep(1)  # 间隔1秒