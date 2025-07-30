import cv2
import numpy as np
import mss
import win32gui
import win32api
import time
import win32con

class MinecraftScreenCapture:
    def __init__(self):  # 不再需要手动指定标题，改为自动模糊匹配
        self.game_region = None  # 游戏窗口区域（top, left, width, height）
        # 分析记录文字的相对位置（相对于游戏窗口左上角）
        self.relative_x = 2000
        self.relative_y = 600

    def find_game_window(self):
        """精确匹配Minecraft游戏窗口，排除编辑器等其他窗口"""
        def callback(hwnd, extra):
            # 获取窗口标题并转为小写（忽略大小写）
            window_title = win32gui.GetWindowText(hwnd).lower()
            # 条件：窗口可见
            if win32gui.IsWindowVisible(hwnd):
                extra.append((hwnd, window_title))
        
        windows = []
        win32gui.EnumWindows(callback, windows)  # 遍历所有窗口
        
        # 打印所有可见窗口，帮助调试
        print("找到的可见窗口：")
        for hwnd, title in windows:
            print(f"- {title}")
        
        # 筛选出包含"minecraft"的窗口，但排除编辑器相关窗口
        # 排除关键词：trae, editor, code, studio, vscode, pycharm等
        exclude_keywords = ["trae", "editor", "code", "studio", "vscode", "pycharm"]
        minecraft_windows = []
        for hwnd, title in windows:
            if "minecraft" in title:
                # 检查是否包含排除关键词
                exclude = False
                for keyword in exclude_keywords:
                    if keyword in title:
                        exclude = True
                        break
                if not exclude:
                    minecraft_windows.append((hwnd, title))
        
        if not minecraft_windows:
            # 更详细的错误提示，方便排查
            raise Exception("未找到我的世界窗口！请检查：\n1. 游戏已启动且处于窗口化模式（非全屏）\n2. 窗口未被最小化\n3. 窗口标题中包含'Minecraft'（如启动器或游戏内标题）")
        
        # 如果找到多个Minecraft窗口，让用户选择
        if len(minecraft_windows) > 1:
            print("找到多个Minecraft窗口，请选择：")
            for i, (hwnd, title) in enumerate(minecraft_windows):
                print(f"{i+1}. {title}")
            try:
                choice = int(input("请输入选择 (1-{}): ".format(len(minecraft_windows)))) - 1
                if 0 <= choice < len(minecraft_windows):
                    hwnd, title = minecraft_windows[choice]
                else:
                    print("输入无效，选择第一个窗口")
                    hwnd, title = minecraft_windows[0]
            except ValueError:
                print("输入无效，选择第一个窗口")
                hwnd, title = minecraft_windows[0]
        else:
            hwnd, title = minecraft_windows[0]
        
        print(f"选择窗口：{title}")
        # 激活窗口（确保能捕获到画面）
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)  # 等待窗口激活
        
        # 获取窗口坐标（去除标题栏，只保留游戏画面）
        rect = win32gui.GetWindowRect(hwnd)
        # 标题栏高度可能因系统而异，这里增加调试信息
        title_bar_height = 30
        self.game_region = {
            "top": rect[1] + title_bar_height,
            "left": rect[0],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1] - title_bar_height
        }
        print(f"游戏窗口定位成功：{self.game_region} (标题栏高度: {title_bar_height})")
        return True

    def capture_frame(self):
        """捕获游戏画面，返回OpenCV格式图像（BGR）"""
        if not self.game_region:
            self.find_game_window()
        
        with mss.mss() as sct:
            # 截取游戏窗口区域
            monitor = {
                "top": self.game_region["top"],
                "left": self.game_region["left"],
                "width": self.game_region["width"],
                "height": self.game_region["height"]
            }
            sct_img = sct.grab(monitor)
            # 转换为OpenCV格式（BGR）
            frame = np.array(sct_img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            return frame

    def find_text_position(self, text_to_find="分析记录"):
        """在游戏画面中查找指定文字的位置（基于图像识别）

        Args:
            text_to_find (str): 要查找的文字，默认为"分析记录"

        Returns:
            tuple: (x, y) 文字中心位置的屏幕坐标，如果未找到则返回None
        """
        print(f"使用传统图像识别查找文字'{text_to_find}'的位置...")
        
        # 捕获游戏画面
        frame = self.capture_frame()
        if frame is None:
            print("无法捕获游戏画面，无法进行图像识别")
            return None
        
        # 转换为HSV色彩空间，更容易进行颜色筛选
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 定义文字区域的颜色范围（假设是白色文字，扩大范围以提高识别率）
        # 白色的HSV范围（低饱和度，高亮度）
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 50, 255])
        
        # 创建掩码
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # 对掩码进行形态学操作，去除噪声
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 筛选合适大小的轮廓（调整阈值以提高识别率）
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 30 < area < 2000:  # 扩大范围以提高识别率
                valid_contours.append(contour)
        
        # 如果找到有效轮廓，取面积最大的那个
        if valid_contours:
            # 按面积排序
            valid_contours.sort(key=lambda c: cv2.contourArea(c), reverse=True)
            largest_contour = valid_contours[0]
            
            # 计算轮廓的中心坐标
            M = cv2.moments(largest_contour)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # 转换为屏幕坐标
                screen_x = self.game_region["left"] + cx
                screen_y = self.game_region["top"] + cy
                
                print(f"通过图像识别找到文字位置: ({screen_x}, {screen_y})")
                return (screen_x, screen_y)
        
        # 如果图像识别失败，使用备用方案（相对位置）
        print("图像识别失败，使用备用相对位置...")
        screen_x = self.game_region["left"] + self.relative_x
        screen_y = self.game_region["top"] + self.relative_y
        print(f"使用备用位置: ({screen_x}, {screen_y})")
        return (screen_x, screen_y)



    def set_analysis_record_position(self, x, y):
        """手动设置分析记录文字的位置

        Args:
            x (int): 相对于游戏窗口左侧的距离
            y (int): 相对于游戏窗口顶部的距离
        """
        self.relative_x = x
        self.relative_y = y
        print(f"已设置分析记录文字位置: ({x}, {y}) (相对于游戏窗口)")
        
    def verify_click_success(self, x, y, threshold=5):
        """验证点击是否成功

        Args:
            x (int): 点击的X坐标
            y (int): 点击的Y坐标
            threshold (int): 颜色变化阈值，降低阈值以提高灵敏度

        Returns:
            bool: 点击是否成功
        """
        import time
        
        # 点击前捕获画面
        before_frame = self.capture_frame()
        if before_frame is None:
            print("无法捕获点击前画面，无法验证点击成功")
            return False
        
        # 等待点击生效
        time.sleep(1)
        
        # 点击后捕获画面
        after_frame = self.capture_frame()
        if after_frame is None:
            print("无法捕获点击后画面，无法验证点击成功")
            return False
        
        # 转换为HSV色彩空间
        before_hsv = cv2.cvtColor(before_frame, cv2.COLOR_BGR2HSV)
        after_hsv = cv2.cvtColor(after_frame, cv2.COLOR_BGR2HSV)
        
        # 定义一个小区域来检查颜色变化（以点击坐标为中心）
        roi_size = 10
        x1, y1 = max(0, x - roi_size), max(0, y - roi_size)
        x2, y2 = min(before_frame.shape[1], x + roi_size), min(before_frame.shape[0], y + roi_size)
        
        # 提取ROI
        before_roi = before_hsv[y1:y2, x1:x2]
        after_roi = after_hsv[y1:y2, x1:x2]
        
        # 计算颜色差异
        diff = cv2.absdiff(before_roi, after_roi)
        mean_diff = diff.mean()
        
        print(f"点击区域颜色差异: {mean_diff}")
        
        # 如果颜色差异超过阈值，则认为点击成功
        return mean_diff > threshold

    def get_mouse_position(self):
        """获取当前鼠标位置

        Returns:
            tuple: (x, y) 鼠标的屏幕坐标
        """
        x, y = win32api.GetCursorPos()
        print(f"当前鼠标位置: ({x}, {y})")
        return (x, y)

    def capture_full_screen(self, include_mouse_pos=True):
        """捕获整个屏幕画面，返回OpenCV格式图像（BGR）、屏幕分辨率和可选的鼠标位置

        Args:
            include_mouse_pos (bool): 是否包含鼠标位置信息

        Returns:
            tuple: (frame, screen_width, screen_height, mouse_pos) 屏幕图像、分辨率和鼠标位置
        """
        # 获取屏幕分辨率
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)
        print(f"当前屏幕分辨率: {screen_width}x{screen_height}")

        # 获取鼠标位置
        mouse_pos = None
        if include_mouse_pos:
            mouse_pos = self.get_mouse_position()
            # 调整鼠标位置 - 这里可以根据需要添加调整逻辑
            # 例如：如果鼠标在屏幕边缘，可以向内调整一定距离
            if mouse_pos:
                mx, my = mouse_pos
                # 示例调整：确保鼠标位置在屏幕内并且有一定边距
                mx = max(10, min(mx, screen_width - 10))
                my = max(10, min(my, screen_height - 10))
                mouse_pos = (mx, my)
                print(f"调整后鼠标位置: ({mx}, {my})")
            
        with mss.mss() as sct:
            # 截取整个屏幕
            monitor = {"top": 0, "left": 0, "width": screen_width, "height": screen_height}
            sct_img = sct.grab(monitor)
            # 转换为OpenCV格式（BGR）
            frame = np.array(sct_img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            if include_mouse_pos and mouse_pos:
                # 在图像上标记鼠标位置
                mx, my = mouse_pos
                cv2.circle(frame, (mx, my), 5, (0, 0, 255), -1)  # 绘制红色圆点
                cv2.putText(frame, f"Mouse: ({mx}, {my})", (mx + 10, my - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
            return frame, screen_width, screen_height, mouse_pos

    def find_back_to_game_button(self):
        """在全屏画面中查找"回到游戏"按钮的位置

        Returns:
            tuple: (x, y) 按钮中心位置的屏幕坐标，如果未找到则返回None
        """
        print("查找'回到游戏'按钮的位置...")
        
        # 捕获全屏画面(不包含鼠标位置信息)
        frame, screen_width, screen_height, _ = self.capture_full_screen(include_mouse_pos=False)
        
        # 转换为HSV色彩空间，更容易进行颜色筛选
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 定义按钮区域的颜色范围（扩大绿色范围以提高识别率）
        # 调整后的绿色HSV范围
        lower_green = np.array([30, 40, 40])
        upper_green = np.array([80, 255, 255])
        
        # 创建掩码
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # 对掩码进行形态学操作，去除噪声并增强轮廓
        kernel = np.ones((7, 7), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 筛选合适大小的轮廓（扩大面积范围）
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 200 < area < 8000:  # 扩大面积范围以提高识别率
                valid_contours.append(contour)
        
        # 如果找到有效轮廓，取面积最大的那个
        if valid_contours:
            # 按面积排序
            valid_contours.sort(key=lambda c: cv2.contourArea(c), reverse=True)
            largest_contour = valid_contours[0]
            
            # 计算轮廓的边界矩形，以获取更准确的按钮位置
            x, y, w, h = cv2.boundingRect(largest_contour)
            cx = x + w // 2
            cy = y + h // 2
            
            # 针对y轴坐标偏小的问题，增加一个偏移量
            cy += 15  # 增加15像素的偏移量以纠正按钮位置
            
            print(f"通过图像识别找到'回到游戏'按钮位置: ({cx}, {cy})")
            # 记录坐标和分辨率信息，指定编码格式为utf-8
            with open("back_to_game_button_log.txt", "a", encoding="utf-8") as f:
                f.write(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}, 分辨率: {screen_width}x{screen_height}, 坐标: ({cx}, {cy})\n")
            return (cx, cy)
        
        print("未找到'回到游戏'按钮")
        return None

    def click_back_to_game_button(self):
        """查找并点击'回到游戏'按钮

        Returns:
            bool: 点击是否成功
        """
        import time
        import pyautogui
        import win32gui
        import win32con
        
        button_position = self.find_back_to_game_button()
        if not button_position:
            print("未找到'回到游戏'按钮，无法执行点击")
            return False
        
        x, y = button_position
        print(f"点击'回到游戏'按钮位置：({x}, {y})")
        
        try:
            # 确保游戏窗口获得焦点
            def find_minecraft_window():
                """查找Minecraft窗口"""
                minecraft_windows = []
                def callback(hwnd, extra):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if 'minecraft' in title.lower():
                            minecraft_windows.append(hwnd)
                win32gui.EnumWindows(callback, None)
                return minecraft_windows[0] if minecraft_windows else None
            
            minecraft_hwnd = find_minecraft_window()
            if minecraft_hwnd:
                # 激活窗口
                win32gui.SetForegroundWindow(minecraft_hwnd)
                # 等待窗口激活
                time.sleep(0.5)
                print("已激活Minecraft窗口")
            else:
                print("未找到Minecraft窗口")
            
            # 移动鼠标到按钮位置（增加额外的y轴偏移以确保点击按钮中心）
            pyautogui.moveTo(x, y + 5, duration=0.5)
            
            # 执行双击操作
            pyautogui.doubleClick()
            # 再额外添加一次单击
            time.sleep(0.2)
            pyautogui.click()
            
            # 等待按钮消失（增加等待时间）
            time.sleep(2.0)
            
            # 验证点击是否成功（检查按钮是否仍然存在）
            new_button_position = self.find_back_to_game_button()
            if not new_button_position:
                print("点击成功：'回到游戏'按钮已消失")
                return True
            else:
                # 尝试第二次点击
                print(f"点击失败，尝试第二次点击: {new_button_position}")
                pyautogui.moveTo(new_button_position[0], new_button_position[1] + 5, duration=0.5)
                pyautogui.doubleClick()
                time.sleep(0.2)
                pyautogui.click()
                time.sleep(2.0)
                
                # 再次验证
                new_button_position2 = self.find_back_to_game_button()
                if not new_button_position2:
                    print("第二次点击成功：'回到游戏'按钮已消失")
                    return True
                else:
                    print(f"第二次点击失败：'回到游戏'按钮仍然存在于位置: {new_button_position2}")
                    return False
        except Exception as e:
            print(f"点击过程中出错: {e}")
            return False
            
            # 确保游戏窗口获得焦点
            try:
                # 模糊查找Minecraft窗口
                def find_minecraft_window():
                    minecraft_hwnd = None
                    
                    def callback(hwnd, extra):
                        nonlocal minecraft_hwnd
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd).lower()
                            if "minecraft" in title:
                                minecraft_hwnd = hwnd
                                return False  # 停止枚举
                    
                    win32gui.EnumWindows(callback, None)
                    return minecraft_hwnd
                
                hwnd = find_minecraft_window()
                if hwnd:
                    # 激活窗口
                    win32gui.SetForegroundWindow(hwnd)
                    print("已激活Minecraft窗口")
                    time.sleep(0.5)  # 等待窗口激活
                else:
                    print("未找到Minecraft窗口，尝试直接点击")
            except Exception as e:
                print(f"激活窗口时出错: {e}")
            
            # 移动鼠标到位置，然后点击
            try:
                import pyautogui
                pyautogui.moveTo(x, y, duration=0.5)  # 缓慢移动鼠标
                # 尝试三次点击
                for i in range(3):
                    pyautogui.click(x, y)
                    print(f"执行第{i+1}次点击")
                    time.sleep(0.3)  # 每次点击间隔
                time.sleep(1)  # 等待点击生效
            except Exception as e:
                print(f"点击操作出错: {e}")
                return False
            
            # 验证点击是否成功
            after_position = self.find_back_to_game_button()
            if not after_position:
                print("点击验证成功：'回到游戏'按钮已消失")
                return True
            else:
                print(f"点击验证失败：按钮仍然存在于位置: {after_position}")
                return False
        else:
            print("无法点击'回到游戏'按钮，因为未找到其位置")
            return False

    # 原verify_click_success方法的剩余部分
        # 等待点击生效
        import time
        time.sleep(0.5)
        
        # 点击后捕获画面
        after_frame = self.capture_frame()
        if after_frame is None:
            print("无法捕获点击后画面，无法验证点击成功")
            return False
        
        # 转换为游戏窗口内的相对坐标
        rel_x = x - self.game_region["left"]
        rel_y = y - self.game_region["top"]
        
        # 确保坐标在画面范围内
        if rel_x < 0 or rel_x >= self.game_region["width"] or rel_y < 0 or rel_y >= self.game_region["height"]:
            print(f"点击坐标({x}, {y})超出游戏窗口范围")
            return False
        
        # 提取点击区域周围的颜色（使用3x3区域的平均值）
        kernel_size = 3
        half_kernel = kernel_size // 2
         
        # 确保区域在画面范围内
        if rel_y - half_kernel < 0 or rel_y + half_kernel >= self.game_region["height"] or \
           rel_x - half_kernel < 0 or rel_x + half_kernel >= self.game_region["width"]:
            print("点击区域靠近边缘，无法使用区域验证")
            # 退化为单点验证
            before_color = before_frame[rel_y, rel_x]
            after_color = after_frame[rel_y, rel_x]
            color_diff = np.linalg.norm(before_color - after_color)
        else:
            # 计算区域平均值
            before_region = before_frame[rel_y-half_kernel:rel_y+half_kernel+1, rel_x-half_kernel:rel_x+half_kernel+1]
            after_region = after_frame[rel_y-half_kernel:rel_y+half_kernel+1, rel_x-half_kernel:rel_x+half_kernel+1]
            before_color_avg = np.mean(before_region, axis=(0, 1))
            after_color_avg = np.mean(after_region, axis=(0, 1))
            color_diff = np.linalg.norm(before_color_avg - after_color_avg)
         
        print(f"点击前后颜色差异: {color_diff}")
         
        # 如果颜色差异超过阈值，则认为点击成功
        if color_diff > threshold:
            print("点击成功，颜色发生明显变化")
            return True
        else:
            print("点击可能未成功，颜色变化不明显")
            return False        
        # 等待点击生效
        import time
        time.sleep(0.5)
        
        # 点击后捕获画面
        after_frame = self.capture_frame()
        if after_frame is None:
            print("无法捕获点击后画面，无法验证点击成功")
            return False
        
        # 转换为游戏窗口内的相对坐标
        rel_x = x - self.game_region["left"]
        rel_y = y - self.game_region["top"]
        
        # 确保坐标在画面范围内
        if rel_x < 0 or rel_x >= self.game_region["width"] or rel_y < 0 or rel_y >= self.game_region["height"]:
            print(f"点击坐标({x}, {y})超出游戏窗口范围")
            return False
        
        # 提取点击区域周围的颜色（使用3x3区域的平均值）
        kernel_size = 3
        half_kernel = kernel_size // 2
         
        # 确保区域在画面范围内
        if rel_y - half_kernel < 0 or rel_y + half_kernel >= self.game_region["height"] or \
           rel_x - half_kernel < 0 or rel_x + half_kernel >= self.game_region["width"]:
            print("点击区域靠近边缘，无法使用区域验证")
            # 退化为单点验证
            before_color = before_frame[rel_y, rel_x]
            after_color = after_frame[rel_y, rel_x]
            color_diff = np.linalg.norm(before_color - after_color)
        else:
            # 计算区域平均值
            before_region = before_frame[rel_y-half_kernel:rel_y+half_kernel+1, rel_x-half_kernel:rel_x+half_kernel+1]
            after_region = after_frame[rel_y-half_kernel:rel_y+half_kernel+1, rel_x-half_kernel:rel_x+half_kernel+1]
            before_color_avg = np.mean(before_region, axis=(0, 1))
            after_color_avg = np.mean(after_region, axis=(0, 1))
            color_diff = np.linalg.norm(before_color_avg - after_color_avg)
         
        print(f"点击前后颜色差异: {color_diff}")
         
        # 如果颜色差异超过阈值，则认为点击成功
        if color_diff > threshold:
            print("点击成功，颜色发生明显变化")
            return True
        else:
            print("点击可能未成功，颜色变化不明显")
            return False

# 测试画面捕获
if __name__ == "__main__":
    capture = MinecraftScreenCapture()
    while True:
        try:
            frame = capture.capture_frame()
            # 显示捕获的画面（窗口大小缩放为原窗口的70%，避免太大）
            frame_small = cv2.resize(frame, (0, 0), fx=0.7, fy=0.7)
            cv2.imshow("Minecraft Capture (按ESC退出)", frame_small)
        except Exception as e:
            print(f"错误：{e}")
            time.sleep(2)  # 等待2秒后重试
        
        # 按ESC键退出
        if cv2.waitKey(1) == 27:
            break
    cv2.destroyAllWindows()