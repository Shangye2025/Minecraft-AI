# main.py
import sys
import os
import cv2
import time
import traceback

def main():
    try:
        print(f"Python版本: {sys.version}")
        print(f"工作目录: {os.getcwd()}")
        
        # 添加项目目录到搜索路径
        project_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.append(project_dir)
        print(f"项目目录: {project_dir}")

        # 导入模块
        try:
            from screen_capture import MinecraftScreenCapture
            from game_analyzer import GameStateAnalyzer, put_chinese_text, get_chinese_font
            from game_controller import GameController
            from local_ai import DeepSeekAI
            print("所有模块导入成功！")
        except ImportError as e:
            print(f"模块导入失败: {e}")
            print(traceback.format_exc())
            input("按Enter键退出...")
            return

        # 初始化各模块
        print("\n初始化模块...")
        try:
            capture = MinecraftScreenCapture()
            analyzer = GameStateAnalyzer()
            ai = DeepSeekAI(model_name="deepseek-r1:8b")
            # 初始化控制器，设置回到游戏模式：1=直接运行回到游戏exe文件
            controller = GameController(back_to_game_mode=1)
            chinese_font = get_chinese_font()
            print("模块初始化完成")
        except Exception as e:
            print(f"初始化失败: {e}")
            print(traceback.format_exc())
            input("按Enter键退出...")
            return


        print("\n开始AI自动生存（按ESC退出）...")
        frame_count = 0
        start_time = time.time()
        last_state = None
        
        # 游戏状态跟踪
        game_stats = {
            "score": 0,
            "deaths": 0,
            "crafted_items": 0,
            "mobs_killed": 0,
            "structures_found": 0
        }
        
        try:
            while True:
                frame_count += 1
                loop_start = time.time()
                
                try:
                    # 1. 捕获游戏画面
                    frame = capture.capture_frame()
                    if frame is None:
                        time.sleep(0.1)
                        continue

                    # 2. 分析环境
                    game_state = analyzer.analyze_frame(frame)
                    state_desc = game_state["description_cn"]
                    
                    # 更新游戏统计
                    if "村庄" in state_desc or "神殿" in state_desc or "密室" in state_desc:
                        game_stats["structures_found"] += 1
                    
                    # 检查是否打开了菜单
                    is_menu = analyzer.is_menu_open(frame)
                    if is_menu:
                        print("检测到菜单已打开，尝试关闭...")
                        
                        # 确保游戏窗口被激活
                        try:
                            import win32gui
                            hwnd = win32gui.FindWindow(None, win32gui.GetWindowText(win32gui.GetForegroundWindow()))
                            if hwnd:
                                win32gui.SetForegroundWindow(hwnd)
                                print("已激活游戏窗口")
                                time.sleep(0.5)  # 等待窗口激活
                        except Exception as e:
                            print(f"激活窗口时出错: {e}")
                        
                        # 执行回到游戏操作
                        controller.execute_action("回到游戏")
                        
                        # 增加等待时间至10秒，确保回到游戏操作完成
                        time.sleep(10)
                        
                        # 多次检查菜单是否关闭，最多重试3次
                        retry_count = 0
                        max_retries = 3
                        while retry_count < max_retries:
                            new_frame = capture.capture_frame()
                            if new_frame is None:
                                print("无法捕获新画面，重试...")
                                time.sleep(2)
                                retry_count += 1
                                continue
                            
                            if analyzer.is_menu_open(new_frame):
                                print(f"菜单仍然打开，第{retry_count+1}次尝试关闭...")
                                controller.execute_action("回到游戏")
                                time.sleep(5)
                                retry_count += 1
                            else:
                                print("菜单已成功关闭")
                                break
                        
                        if retry_count >= max_retries:
                            print("多次尝试关闭菜单失败，继续执行...")
                        
                        continue

                    # 检查是否为夜晚
                    is_night = analyzer.is_night(frame)
                    if is_night:
                        print("当前为夜晚模式，调整视觉分析参数...")
                        # 可以在这里调整AI决策参数以适应夜晚环境
                        game_state["is_night"] = True
                    else:
                        game_state["is_night"] = False

                    # 3. AI决策 (超时控制)
                    ai_timeout = max(0, 1.0 - game_state.get("processing_time", 0.0))
                    action_start = time.time()
                    action = ai.get_action(game_state)
                    ai_time = time.time() - action_start
                    
                    # 根据AI响应时间调整分数
                    if ai_time > 0.8:
                        game_stats["score"] -= 1
                        print("响应过慢 -1分")
                    elif ai_time < 0.3:
                        game_stats["score"] += 1
                        print("响应迅速 +1分")
                    
                    # 4. 执行操作
                    new_game_state = None
                    try:
                        previous_health = game_state.get('health', 20)
                        controller.execute_action(action)

                        # 5. 获取执行后的游戏状态
                        new_frame = capture.capture_frame()
                        new_game_state = analyzer.analyze_frame(new_frame)
                    except Exception as e:
                        print(f"执行过程中发生错误: {e}")
                        game_stats["score"] -= 5
                        print("执行操作失败 -5分")
                    finally:
                        # 确保资源正确释放
                        pass

                    # 检查new_game_state是否被成功创建
                    success = False
                    if new_game_state is not None:
                        current_health = new_game_state.get('health', 20)
                        success = True
                        
                        # 判断失败条件：生命值降低或跌落
                        if current_health < previous_health:
                            success = False
                            game_stats['deaths'] += 1
                            print(f"动作失败：生命值减少 {previous_health - current_health}")
                        elif '跌落' in new_game_state['description_cn']:
                            success = False
                            print("动作失败：发生跌落")
                    else:
                        print("未能获取新游戏状态，动作失败")
                    
                    # 判断成功条件：发现新结构或获取物品
                    if new_game_state is not None and (new_game_state['detected_structures'] or new_game_state['detected_items']):
                        success = True
                        print("动作成功：发现新结构或物品")
                    
                    # 更新学习记忆
                    if success:
                        ai.feedback_success()
                        game_stats['score'] += 2
                    else:
                        ai.feedback_failure()
                        game_stats['score'] -= 1
                    
                    # 5. 学习系统 - 评估行动结果
                    if last_state:
                        # 简单的评估：如果状态改善则视为成功
                        current_resources = sum(game_state["ratios"].values())
                        last_resources = sum(last_state["ratios"].values())

                        if current_resources > last_resources:
                            ai.feedback_success()
                            print("行动成功 - 已记录")
                        elif "死亡" in state_desc:  # 简化死亡检测
                            ai.feedback_failure()
                            game_stats["deaths"] += 1
                            game_stats["score"] -= 10
                            print("死亡 -10分")
                    
                    # 保存当前状态用于下次评估
                    last_state = {
                        "situation_hash": ai.create_situation_hash(game_state),
                        "ratios": game_state["ratios"],
                        "structures": game_state.get("detected_structures", {}),
                        "inventory": game_state.get("detected_items", {})
                    }
                    
                    # 6. 显示画面
                    display_text = f"{state_desc} | 操作: {action} | 分数: {game_stats['score']}"
                    display_frame = put_chinese_text(
                        frame, display_text, (10, 30),
                        chinese_font, 16, (255, 255, 255)
                    )
                    cv2.imshow("Minecraft AI", display_frame)
                    
                    # 检查是否击败末影龙（简化版）
                    if game_stats["score"] >= 10000:
                        print("恭喜！击败末影龙！游戏胜利！")
                        break

                    # 按ESC退出
                    key = cv2.waitKey(1)
                    if key == 27:
                        print("准备退出游戏...")
                        break
                    
                    # 控制循环频率
                    loop_time = time.time() - loop_start
                    if loop_time < 1.0:
                        time.sleep(1.0 - loop_time)
                        
                except KeyboardInterrupt:
                    print("\n用户中断程序")
                    break
                except Exception as e:
                    print(f"\n运行时错误: {e}")
                    print(traceback.format_exc())
                    time.sleep(1)

        finally:
            cv2.destroyAllWindows()
            total_time = time.time() - start_time
            fps = frame_count / total_time if total_time > 0 else 0
            print("\n===== 游戏统计 =====")
            print(f"总帧数: {frame_count}")
            print(f"平均FPS: {fps:.1f}")
            print(f"最终分数: {game_stats['score']}")
            print(f"死亡次数: {game_stats['deaths']}")
            print(f"发现结构: {game_stats['structures_found']}")
            print("===================")
            
    except Exception as e:
        print(f"\n主程序错误: {e}")
        print(traceback.format_exc())
    finally:
        input("按Enter键退出...")

if __name__ == "__main__":
    main()