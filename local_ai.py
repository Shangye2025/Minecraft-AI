import time
import requests
import json
import os

class DeepSeekAI:
    def __init__(self, model_name="deepseek-r1:8b", api_base="http://localhost:11434"):
        """初始化DeepSeek AI，添加学习记忆功能"""
        self.model_name = model_name
        self.api_base = api_base
        self.model_loaded = self._check_model()
        
        # 性能优化参数
        self.max_inference_time = 0.8  # 最大推理时间(秒)
        self.cache_ttl = 5  # 缓存过期时间(秒)
        self.prompt_cache = {}
        
        # 自主学习系统
        self.learning_memory = {
            "success_actions": {},  # {情境: {动作: 成功率}}
            "failure_actions": [],  # 失败动作记录，使用列表代替集合以便JSON序列化
            "last_state": None,
            "last_action": None,
            "learning_rate": 0.1
        }
        
        # 加载学习数据
        self.learning_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'learning_data.json')
        self._load_learning_data()

    def _check_model(self):
        """检查模型是否已在Ollama中可用"""
        try:
            response = requests.get(f"{self.api_base}/api/tags")
            response.raise_for_status()
            models = [model["name"] for model in response.json().get("models", [])]
            if self.model_name in models:
                print(f"Ollama模型 {self.model_name} 可用")
                return True
            else:
                print(f"错误：Ollama中未找到模型 {self.model_name}")
                print(f"可用模型：{models}")
                return False
        except Exception as e:
            print(f"连接Ollama API失败：{e}")
            print("请确保Ollama服务已启动：`ollama serve`")
            return False

    def _load_learning_data(self):
        """加载历史学习数据"""
        if os.path.exists(self.learning_data_path):
            try:
                with open(self.learning_data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 确保failure_actions是列表类型
                    if "failure_actions" in data and isinstance(data["failure_actions"], list):
                        self.learning_memory = data
                    else:
                        # 如果格式不正确，使用默认值
                        print("学习数据格式不正确，使用默认值")
                print(f"加载学习数据: {self.learning_data_path}")
            except Exception as e:
                print(f"加载学习数据失败: {e}")
                # 使用默认学习记忆
                pass
        
    def _save_learning_data(self):
        """保存学习数据"""
        try:
            with open(self.learning_data_path, 'w', encoding='utf-8') as f:
                json.dump(self.learning_memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存学习数据失败: {e}")
        
    def _update_learning_memory(self, success):
        """更新学习记忆，基于上一个动作的结果"""
        if not self.last_state or not self.last_action:
            return
        
        state_key = self._get_state_key(self.last_state)
        
        # 更新成功/失败记录
        if success:
            if state_key not in self.learning_memory["success_actions"]:
                self.learning_memory["success_actions"][state_key] = {}
            action_stats = self.learning_memory["success_actions"][state_key]
            action_stats[self.last_action] = action_stats.get(self.last_action, 0) + self.learning_memory["learning_rate"]
            
            # 如果动作成功，从失败记录中移除
            if self.last_action in self.learning_memory["failure_actions"]:
                self.learning_memory["failure_actions"].remove(self.last_action)
        else:
            if self.last_action not in self.learning_memory["failure_actions"]:
                self.learning_memory["failure_actions"].append(self.last_action)
        
        # 保存学习数据
        self._save_learning_data()
        
    def _get_state_key(self, game_state):
        """将游戏状态转换为哈希键"""
        return hash(frozenset(game_state["ratios"].items())) % 1000  # 限制状态数量
        
    def create_situation_hash(self, game_state):
        """创建情境哈希值"""
        return self._get_state_key(game_state)
        
    def _optimize_prompt(self, game_state):
        """优化提示词以减少推理时间"""
        state_key = self._get_state_key(game_state)
        
        # 检查缓存
        current_time = time.time()
        if state_key in self.prompt_cache and current_time - self.prompt_cache[state_key]["time"] < self.cache_ttl:
            return self.prompt_cache[state_key]["prompt"]
        
        # 构建精简提示词
        env_desc = game_state["description_cn"][:100]  # 限制描述长度
        
        # 加入学习经验
        state_actions = self.learning_memory["success_actions"].get(state_key, {})
        if state_actions:
            best_action = max(state_actions, key=state_actions.get)
            learning_hint = f"历史最佳动作: {best_action}"
        else:
            learning_hint = "无历史成功动作"
        
        prompt = f"我的世界生存专家，根据环境和历史经验决定最佳操作。环境: {env_desc}。{learning_hint}。可选操作:前进(w),后退(s),左移(a),右移(d),左转(鼠标左移),右转(鼠标右移),跳跃(空格),攻击/砍伐(左键点击),打开背包(e)。仅返回操作符，如w/a/s/d/空格/左键点击/e"
        
        # 更新缓存
        self.prompt_cache[state_key] = {
            "prompt": prompt,
            "time": current_time
        }
        
        return prompt
        
    def get_action(self, game_state):
        """根据游戏状态生成操作指令"""
        if not self.model_loaded:
            return self._simple_rule_based_action(game_state)
        
        # 记录当前状态用于学习
        self.last_state = game_state
        
        # 优化提示词并检查缓存
        prompt = self._optimize_prompt(game_state)
        
        # 检查失败动作，避免重复
        state_key = self._get_state_key(game_state)

        # 调用Ollama API
        try:
            # 设置超时和优化参数
            start_time = time.time()
            response = requests.post(
                f"{self.api_base}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1 if state_key in self.learning_memory["success_actions"] else 0.3,  # 有历史经验时降低随机性
                    "max_tokens": 5,  # 进一步限制输出长度
                    "top_p": 0.5,  # 减少候选词多样性以加速推理
                    "stop": ["\n"]  # 遇到换行立即停止
                },
                timeout=self.max_inference_time  # 设置超时
            )
            inference_time = time.time() - start_time
            
            if inference_time > self.max_inference_time * 0.8:
                print(f"警告：推理时间过长({inference_time:.2f}s)")
            response.raise_for_status()
            result = response.json()
            
            # 从响应中提取操作
            text = result.get("response", "").strip()
            action_map = {
                "前进": "w", "后退": "s", "左移": "a", "右移": "d",
                "左转": "鼠标左移", "右转": "鼠标右移",
                "跳跃": "空格", "攻击/砍伐": "左键点击", "打开背包": "e"
            }
            
            # 快速匹配操作
            for keyword, key in action_map.items():
                if keyword in text or key in text:
                    self.last_action = key
                    return key
            
            # 如果没找到匹配的操作，使用最佳历史动作或默认
            self.last_action = max(state_actions, key=state_actions.get) if state_actions else "w"
            return self.last_action
            
        except requests.exceptions.Timeout:
            print(f"推理超时，使用规则动作")
            self.last_action = self._simple_rule_based_action(game_state)
            return self.last_action
        except Exception as e:
            print(f"调用API失败：{e}")
            self.last_action = self._simple_rule_based_action(game_state)
            return self.last_action

    def feedback_success(self):
        """反馈动作成功"""
        self._update_learning_memory(success=True)
        
    def feedback_failure(self):
        """反馈动作失败"""
        self._update_learning_memory(success=False)
        
    def _simple_rule_based_action(self, game_state):
        """基于规则的简单决策（API调用失败时使用）"""
        import random
        desc = game_state["description_cn"].lower()
        
        # 树木/木头识别
        wood_keywords = ["树木", "木头", "树干", "原木", "树苗"]
        if any(keyword in desc for keyword in wood_keywords):
            return "左键点击"
        
        # 敌人识别
        enemy_keywords = ["怪物", "敌人", "僵尸", "骷髅", "爬行者"]
        if any(keyword in desc for keyword in enemy_keywords):
            return "左键点击"  # 攻击敌人
        
        # 资源识别
        resource_keywords = ["矿石", "铁", "金", "钻石", "煤"]
        if any(keyword in desc for keyword in resource_keywords):
            return "左键点击"  # 挖掘资源
        
        # 环境导航
        if "草地" in desc or "开阔" in desc:
            # 70%几率前进，30%几率随机转向探索
            return "w" if random.random() < 0.7 else random.choice(["a", "d"])
        elif "泥土" in desc or "洞穴" in desc:
            return "a"
        elif "水" in desc:
            return "空格"  # 跳跃
        
        # 默认动作：70%前进，15%左转，15%右转
        if random.random() < 0.7:
            return "w"
        elif random.random() < 0.85:
            return "a"
        else:
            return "d"