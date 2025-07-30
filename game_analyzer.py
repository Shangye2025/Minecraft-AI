import cv2
import numpy as np
import os
import sys

# 尝试导入PIL库（用于显示中文）
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

class GameStateAnalyzer:
    def __init__(self):
        # 基础颜色范围
        self.color_ranges = {
            # 白天和夜晚的天空颜色
            "day_sky": (
                np.array([100, 50, 100]),
                np.array([130, 255, 255])
            ),
            "night_sky": (
                np.array([100, 20, 10]),
                np.array([130, 80, 80])
            ),
            "grass": (
                np.array([35, 50, 50]),
                np.array([85, 255, 255])
            ),
            "tree": (
                np.array([30, 40, 30]),
                np.array([40, 255, 100])
            ),
            "sky": (
                np.array([100, 50, 50]),
                np.array([130, 255, 255])
            ),
            "dirt": (
                np.array([10, 50, 30]),
                np.array([20, 200, 150])
            ),
            # 新增1.21版本方块颜色
            "copper": (
                np.array([10, 100, 100]),
                np.array([20, 255, 200])
            ),
            "tuff": (
                np.array([100, 10, 50]),
                np.array([120, 50, 150])
            )
        }
        
        # 物品模板路径
        self.item_templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'item_templates')
        self.item_templates = self._load_item_templates()
        
        # 结构识别参数
        self.structure_patterns = {
            "village": {
                "min_building_size": 10,
                "roof_color": (np.array([15, 50, 50]), np.array([25, 255, 200])),  # 村庄屋顶颜色范围
                "threshold": 0.3
            },
            "ruin": {
                "min_block_count": 8,
                "block_color": (np.array([0, 0, 30]), np.array([30, 30, 80])),  # 遗迹石头颜色
                "threshold": 0.2
            }
        }
        
        # 玩家交互距离（方块）
        self.max_reach_distance = 4.5  # Minecraft默认最大挖掘距离
        self.reach_threshold = 120  # 屏幕中心区域阈值像素

    def _load_item_templates(self):
        """加载物品模板进行模板匹配"""
        templates = {}
        if not os.path.exists(self.item_templates_path):
            os.makedirs(self.item_templates_path)
            print(f"创建物品模板目录: {self.item_templates_path}")
            return templates
        
        for filename in os.listdir(self.item_templates_path):
            if filename.endswith(('.png', '.jpg')):
                item_name = os.path.splitext(filename)[0]
                template_path = os.path.join(self.item_templates_path, filename)
                template = cv2.imread(template_path, 0)
                if template is not None:
                    templates[item_name] = template
                    print(f"加载物品模板: {item_name}")
        return templates

    def _detect_items(self, frame):
        """检测屏幕中的物品"""
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detected_items = {}
        
        # 假设物品栏在屏幕底部区域
        height, width = gray_frame.shape
        inventory_region = gray_frame[int(height*0.85):, :]  # 底部15%区域
        
        for item_name, template in self.item_templates.items():
            w, h = template.shape[::-1]
            res = cv2.matchTemplate(inventory_region, template, cv2.TM_CCOEFF_NORMED)
            threshold = 0.8
            loc = np.where(res >= threshold)
            
            if len(loc[0]) > 0:
                detected_items[item_name] = len(loc[0])
                # 在画面上标记物品位置
                for pt in zip(*loc[::-1]):
                    cv2.rectangle(frame, (
                        pt[0], int(height*0.85) + pt[1]),
                        (pt[0] + w, int(height*0.85) + pt[1] + h),
                        (0, 255, 0), 2)
        
        return detected_items

    def _detect_health(self, frame):
        """检测玩家生命值（简单模拟，实际需根据游戏UI位置调整）"""
        # 假设生命值条在屏幕左上角
        height, width = frame.shape[:2]
        health_bar_region = frame[20:30, 20:220]  # 生命值条区域
        gray_health = cv2.cvtColor(health_bar_region, cv2.COLOR_BGR2GRAY)
        _, binary_health = cv2.threshold(gray_health, 50, 255, cv2.THRESH_BINARY)
        health_pixels = cv2.countNonZero(binary_health)
        total_pixels = health_bar_region.shape[0] * health_bar_region.shape[1]
        
        # 简单转换为生命值（0-20）
        return int((health_pixels / total_pixels) * 20) if total_pixels > 0 else 20

    def _detect_structures(self, frame):
        """检测村庄和遗迹等结构"""
        detected_structures = {}
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        height, width = frame.shape[:2]
        center_region = frame[int(height*0.3):int(height*0.7), int(width*0.3):int(width*0.7)]
        
        # 检测村庄
        village_params = self.structure_patterns["village"]
        roof_mask = cv2.inRange(hsv, *village_params["roof_color"])
        roof_pixels = cv2.countNonZero(roof_mask) / (height * width)
        
        if roof_pixels > village_params["threshold"]:
            # 简单形状分析判断建筑轮廓
            contours, _ = cv2.findContours(roof_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            large_buildings = [c for c in contours if cv2.contourArea(c) > village_params["min_building_size"]]
            
            if len(large_buildings) > 2:
                detected_structures["village"] = {
                    "confidence": roof_pixels,
                    "building_count": len(large_buildings)
                }
        
        # 检测遗迹
        ruin_params = self.structure_patterns["ruin"]
        ruin_mask = cv2.inRange(hsv, *ruin_params["block_color"])
        ruin_pixels = cv2.countNonZero(ruin_mask) / (height * width)
        
        if ruin_pixels > ruin_params["threshold"]:
            detected_structures["ruin"] = {
                "confidence": ruin_pixels
            }
        
        return detected_structures

    def is_night(self, frame):
        """检测是否为夜晚"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # 计算整体亮度
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg_brightness = np.mean(gray)
        
        # 检测天空颜色
        sky_mask_day = cv2.inRange(hsv, *self.color_ranges["day_sky"])
        sky_mask_night = cv2.inRange(hsv, *self.color_ranges["night_sky"])
        
        day_sky_ratio = cv2.countNonZero(sky_mask_day) / (frame.shape[0] * frame.shape[1])
        night_sky_ratio = cv2.countNonZero(sky_mask_night) / (frame.shape[0] * frame.shape[1])
        
        # 判断条件：亮度低且夜晚天空比例高
        return avg_brightness < 50 and night_sky_ratio > 0.2

    def is_menu_open(self, frame):
        """检测是否打开了ESC菜单"""
        # 菜单通常有特定的颜色和UI元素
        height, width = frame.shape[:2]
        
        # 方法1：检测顶部是否有深色条纹（菜单标题栏）
        top_region = frame[0:int(height*0.1), :]
        gray_top = cv2.cvtColor(top_region, cv2.COLOR_BGR2GRAY)
        avg_brightness_top = np.mean(gray_top)
        
        # 方法2：检测中心区域是否有菜单特有文字或按钮
        center_region = frame[int(height*0.3):int(height*0.7), int(width*0.3):int(width*0.7)]
        gray_center = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
        _, binary_center = cv2.threshold(gray_center, 80, 255, cv2.THRESH_BINARY)
        edge_density = cv2.countNonZero(binary_center) / (center_region.shape[0] * center_region.shape[1])
        
        # 方法3：检测底部是否有菜单按钮区域
        bottom_region = frame[int(height*0.9):, :]
        gray_bottom = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY)
        avg_brightness_bottom = np.mean(gray_bottom)
        
        # 综合判断：顶部较暗，中心区域边缘密度低，且底部较亮（按钮区域）
        # 调整阈值以提高准确性
        is_menu = (avg_brightness_top < 30 and 
                  edge_density < 0.1 and 
                  avg_brightness_bottom > 50)
        
        return is_menu
        return avg_brightness_top < 40 and edge_density < 0.15

    def analyze_frame(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        height, width = frame.shape[:2]
        total_pixels = height * width

        element_ratio = {}
        for name, (lower, upper) in self.color_ranges.items():
            mask = cv2.inRange(hsv, lower, upper)
            ratio = cv2.countNonZero(mask) / total_pixels
            element_ratio[name] = round(ratio, 3)

        # 生成中英文双语描述（确保至少有英文显示）
        # 检测物品和结构
        detected_items = self._detect_items(frame.copy())
        detected_structures = self._detect_structures(frame.copy())
        
        state_description_cn = []
        state_description_en = []
        
        # 添加物品信息
        if detected_items:
            item_desc = f"检测到物品: {', '.join([f'{k} x{v}' for k, v in detected_items.items()])}"
            state_description_cn.append(item_desc)
            state_description_en.append(f"Items detected: {', '.join(detected_items.keys())}")
        
        # 添加结构信息
        if detected_structures:
            for struct_type, data in detected_structures.items():
                struct_desc = f"发现{struct_type} (可信度: {data['confidence']:.2f})"
                state_description_cn.append(struct_desc)
                state_description_en.append(f"{struct_type.capitalize()} found (confidence: {data['confidence']:.2f})")
        
        if element_ratio["tree"] > 0.2:
            state_description_cn.append("前方有较多树木，可砍伐获取木材")
            state_description_en.append("Many trees ahead, can chop for wood")
        if element_ratio["grass"] > 0.4:
            state_description_cn.append("处于草地环境，适合探索")
            state_description_en.append("In grassy area, good for exploration")
        if element_ratio["sky"] > 0.3:
            state_description_cn.append("视野中天空较多，可能处于开阔地带")
            state_description_en.append("Lots of sky, might be in an open area")
        if element_ratio["dirt"] > 0.3:
            state_description_cn.append("周围有较多泥土，可能在地面或洞穴入口")
            state_description_en.append("Lots of dirt, might be near a cave")

        if not state_description_cn:
            state_description_cn.append("环境不明确，建议缓慢探索")
            state_description_en.append("Environment unclear, explore cautiously")

        return {
            "description_cn": "; ".join(state_description_cn),
            "description_en": "; ".join(state_description_en),
            "ratios": element_ratio,
            "frame": frame,
            "detected_items": detected_items,
            "detected_structures": detected_structures,
            "health": self._detect_health(frame)
        }

# 获取中文字体（优先使用指定字体，否则使用PIL备用方案）
def get_chinese_font():
    # 指定项目目录中的字体路径（需要先下载并保存字体文件）
    font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "SimHei.ttf")
    
    # 检查字体文件是否存在
    if os.path.exists(font_path):
        print(f"使用自定义中文字体：{font_path}")
        return font_path
    
    # 如果找不到指定字体，检查系统字体
    system_font_paths = [
        "C:/Windows/Fonts/simhei.ttf",  # 黑体
        "C:/Windows/Fonts/simsun.ttc",  # 宋体
        "C:/Windows/Fonts/microsoftyahei.ttf",  # 微软雅黑
    ]
    
    for path in system_font_paths:
        if os.path.exists(path):
            print(f"使用系统中文字体：{path}")
            return path
    
    # 如果找不到任何中文字体，检查是否可以使用PIL库
    if PIL_AVAILABLE:
        print("警告：未找到中文字体，将使用PIL默认字体（可能无法显示中文）")
        return None
    
    # 如果都不支持，使用默认字体（显示问号）
    print("警告：未找到中文字体且PIL库不可用，中文将显示为问号")
    return cv2.FONT_HERSHEY_SIMPLEX

# 使用PIL库在图像上绘制中文
def put_chinese_text(img, text, position, font_path, font_size, color):
    # 转换为PIL图像
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    
    # 加载指定的中文字体
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        # 使用PIL默认字体（可能无法显示中文，但至少不会报错）
        font = ImageFont.load_default()
    
    # 绘制文字（带黑色边框以提高可读性）
    x, y = position
    # 绘制黑色边框
    draw.text((x-1, y-1), text, font=font, fill=(0, 0, 0))
    draw.text((x+1, y-1), text, font=font, fill=(0, 0, 0))
    draw.text((x-1, y+1), text, font=font, fill=(0, 0, 0))
    draw.text((x+1, y+1), text, font=font, fill=(0, 0, 0))
    # 绘制白色文字
    draw.text(position, text, font=font, fill=(color[2], color[1], color[0]))
    
    # 转回OpenCV格式
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

# 测试分析功能
if __name__ == "__main__":
    from screen_capture import MinecraftScreenCapture

    capture = MinecraftScreenCapture()
    analyzer = GameStateAnalyzer()

    chinese_font = get_chinese_font()
    is_pil_font = chinese_font is None or isinstance(chinese_font, int)

    print("开始分析游戏画面（按ESC退出）...")
    try:
        while True:
            frame = capture.capture_frame()
            result = analyzer.analyze_frame(frame)
            
            # 选择使用中文或英文描述
            if is_pil_font:
                text = result["description_en"]  # 如果没有中文字体，使用英文描述
            else:
                text = result["description_cn"]  # 有中文字体，使用中文描述
            
            font_size = 16  # 字体大小
            text_color = (255, 255, 255)  # 白色文字
            
            # 计算文字位置（底部居中）
            text_x = 10
            text_y = result["frame"].shape[0] - 30
            
            # 在图像上添加文字
            if is_pil_font:
                # 使用PIL方案添加文字
                result["frame"] = put_chinese_text(result["frame"], text, (text_x, text_y), chinese_font, font_size, text_color)
            else:
                # 使用OpenCV方案添加文字
                result["frame"] = put_chinese_text(result["frame"], text, (text_x, text_y), chinese_font, font_size, text_color)
            
            # 缩小画面显示
            frame_small = cv2.resize(result["frame"], (0, 0), fx=0.7, fy=0.7)
            cv2.imshow("Game Analysis", frame_small)

            if cv2.waitKey(1) == 27:
                break
    except Exception as e:
        print(f"错误：{e}")
    finally:
        cv2.destroyAllWindows()
        print("分析结束")