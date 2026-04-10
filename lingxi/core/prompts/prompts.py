"""提示词模板管理模块

该模块集中管理所有LLM提示词模板，提供统一的模板渲染接口。
支持参数化模板、复用和扩展。
支持上下文缓存（Context Cache）功能。
"""

import platform
import os
from typing import Dict, List, Any, Optional

from lingxi.core.context.task_context import TaskContext
from lingxi.utils.config import get_workspace_path


class PromptTemplates:
    """提示词模板类，集中管理所有提示词模板（单例模式）"""
    
    _instance = None  # 单例实例
    
    def __new__(cls):
        """单例模式：确保只创建一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @staticmethod
    def get_system_info(workspace_path: Optional[str] = None) -> Dict[str, str]:
        """获取系统环境信息

        Args:
            workspace_path: 工作目录路径（可选，如果不提供则使用 os.getcwd()）

        Returns:
            系统信息字典
        """
        from datetime import datetime
        system_info = platform.system()
        current_dir = workspace_path if workspace_path else os.getcwd()
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%H:%M:%S")
        return {
            "system_info": system_info,
            "os_info": f"{system_info} {platform.release()}",
            "current_dir": current_dir,
            "shell_type": "PowerShell" if system_info == "Windows" else "Bash",
            "current_date": current_date,
            "current_time": current_time
        }

    @staticmethod
    def format_skills_list(skills: List[Dict[str, str]]) -> str:
        """格式化技能列表

        Args:
            skills: 技能列表，每个技能包含name和description

        Returns:
            格式化后的技能列表字符串
        """
        if not skills:
            return "无可用技能"

        skills_list = ""
        for i, skill in enumerate(skills, 1):
            skill_name = skill.get('name', '')
            skill_desc = skill.get('description', '')
            skills_list += f"{i}. {skill_name} - {skill_desc}\n"
        return skills_list

    @staticmethod
    def format_history_context(session_history: List[Dict[str, str]], max_count: int = 5) -> str:
        """格式化历史上下文

        Args:
            session_history: 会话历史
            max_count: 最大历史消息数量

        Returns:
            格式化后的历史上下文字符串
        """
        if not session_history:
            return "无历史对话"

        context = ""
        for msg in session_history[-max_count:]:
            context += f"用户:{msg.get('user_input', '')}\n助手:{msg.get('result', '')}\n"
        return context

    @staticmethod
    def format_executed_steps(steps: List[Dict[str, str]], include_thought: bool = True, max_prev_length: int = 50) -> str:
        """格式化已执行步骤

        Args:
            steps: 执行步骤列表
            include_thought: 是否包含思考过程
            max_prev_length: 之前步骤内容最大长度（字符数）

        Returns:
            格式化后的步骤字符串
        """
        if not steps:
            return "无已执行步骤"

        formatted = ""
        total_steps = len(steps)
        
        for i, step in enumerate(steps):
            formatted += f"步骤 {i + 1}:\n"
            
            # 判断是否为最后一步
            is_last_step = (i == total_steps - 1)
            
            if include_thought and step.get('thought'):
                thought = step.get('thought', '')
                if not is_last_step:
                    thought = thought[:max_prev_length] + ('...' if len(thought) > max_prev_length else '')
                else:
                    thought = thought.replace('\n', '\\n')
                formatted += f"思考: {thought}\n"
            
            # 处理 action_input，可能是字符串或字典
            action_input = step.get('action_input', '')
            if isinstance(action_input, dict):
                params_str = ', '.join([f"{k}={v}" for k, v in action_input.items()])
                if is_last_step:
                    # 最后一步完整显示
                    params_str_escaped = params_str.replace('\n', '\\n')
                    formatted += f"行动: {step.get('action', '')} - {params_str_escaped}\n"
                else:
                    # 之前步骤截断显示
                    if len(params_str) > max_prev_length:
                        params_str = params_str[:max_prev_length] + '...'
                    params_str_escaped = params_str.replace('\n', '\\n')
                    formatted += f"行动: {step.get('action', '')} - {params_str_escaped}\n"
            else:
                if is_last_step:
                    # 最后一步完整显示
                    action_input_str = str(action_input).replace('\n', '\\n')
                    formatted += f"行动: {step.get('action', '')} - {action_input_str}\n"
                else:
                    # 之前步骤截断显示
                    action_input_str = str(action_input).replace('\n', '\\n')
                    if len(action_input_str) > max_prev_length:
                        action_input_str = action_input_str[:max_prev_length] + '...'
                    formatted += f"行动: {step.get('action', '')} - {action_input_str}\n"
            
            if step.get('observation'):
                observation = step.get('observation', '')
                if not is_last_step:
                    observation = observation[:max_prev_length] + ('...' if len(observation) > max_prev_length else '')
                else:
                    observation = observation
                observation_escaped = observation.replace('\n', '\\n')
                formatted += f"观察: {observation_escaped}\n"
            formatted += "\n"
        return formatted

    @staticmethod
    def build_final_response_prompt(
        user_input: str,
        steps: List[Dict[str, str]],
        include_thought: bool = False
    ) -> str:
        """构建最终响应提示词

        Args:
            user_input: 用户输入
            steps: 执行步骤
            include_thought: 是否包含思考过程

        Returns:
            最终响应提示词
        """
        if include_thought:
            steps_str = PromptTemplates.format_executed_steps(steps, include_thought=True, max_prev_length=5000)
        else:
            steps_str = PromptTemplates.format_executed_steps(steps,include_thought=False,max_prev_length=5000)

        prompt = f"""
        请根据以下执行步骤，为用户输入生成最终响应:

        用户输入:
        {user_input}

        执行步骤:
        {steps_str}
        请生成简洁、友好的最终响应:
        """
        return prompt

    @staticmethod
    def build_cached_text_content(text: str, enable_cache: bool = True) -> Dict[str, Any]:
        """构建带缓存标记的文本内容

        Args:
            text: 文本内容
            enable_cache: 是否启用缓存

        Returns:
            结构化内容字典
        """
        if enable_cache:
            return {
                "type": "text",
                "text": text,
                "cache_control": {"type": "ephemeral"}
            }
        else:
            return {
                "type": "text",
                "text": text
            }

    @staticmethod
    def build_react_messages_with_cache(
        context: TaskContext,
        history_context: str,
        skills_list: str,
        #steps: List[Dict[str, str]],
        system_info: Optional[Dict[str, str]] = None,
        task_plan: str = None,
    ) -> List[Dict[str, Any]]:
        """构建ReAct模式消息列表（支持上下文缓存）

        将静态上下文标记为可缓存，动态内容不标记缓存。
        缓存策略：
        - 系统信息、任务信息、技能列表等静态内容标记为缓存
        - 已执行步骤的动态内容不标记缓存

        Args:
            user_input: 用户输入
            task_info: 任务信息
            history_context: 历史上下文
            skills_list: 可用技能列表
            #steps: 已执行步骤
            system_info: 系统信息（可选）

        Returns:
            消息列表，支持 cache_control 标记
        """
        if system_info is None:
            system_info = PromptTemplates.get_system_info()

        #executed_steps = PromptTemplates.format_executed_steps(steps, include_thought=False, max_prev_length=5000)

        system_prompt = f"""你是灵犀智能助手

## 系统工具
file : 用于对本地文本文件进行安全、可控的读取/删除/创建/改操作，支持整文件/行级两种粒度，带文件大小安全限制 
execute : 用于执行shell命令，支持powershell、bash等多种shell类型
read_skill : 用于读取技能的详细使用说明，默认读取 SKILL.md 文件，可指定该技能下面的其它文件读取，传入 file_path 参数即可,当skill有参考文档读取指定文件时，注意一定使用read_skill工具而不是file工具

## 工具调用示例
- file 工具调用示例

```json
{{
  "file_path": "文件路径，字符串，必填",
  "encoding": "编码，默认 utf-8",
  "operation_type": "read/write/delete/create，必填",
  "operate_scope": "full/line，默认 full",
  "line_params": {{
    "start_line": "开始行号，数字，行操作时生效",
    "end_line": "结束行号，数字，行操作时生效",
    "filter_rule": "读取时过滤关键词，字符串"
  }},
  "content": "操作内容，字符串，必填，create/write/insert 时必填"
}}
```
- execute 工具调用示例

```json
{{
  "cwd": "当前工作目录,必填",
  "command": "python -c \"print('Hello World')\"",
  "shell_type": "powershell|bash"
}}
```
- read_skill 工具调用示例

```json
{{
  "skill_name": "技能名称，字符串，必填",
  "file_path": "文件相对路径，字符串，可填，默认 SKILL.md"
}}
```

## 技能:
{skills_list}

finish(answer) - 完成任务并返回答案

## 记忆
{context.userMemory or ""}

## 模型
qwen3.5-plus

## workspace        
当前工作目录:{get_workspace_path()}

## 系统环境
{system_info['os_info']}

## Shell类型
{system_info['shell_type']}

当前时间：{system_info['current_date']} {system_info['current_time']}


## 【重要】必须严格按照以下 JSON 格式输出，不要包含任何其他文字：
{{"thought": "你的思考过程", "description": "当前步骤的摘要", "action": "工具或者技能名称","action_type":"tool or skill", "action_input": {{"参数名": "参数值"}}}}

### 正确示例：
{{"thought": "用户要求创建 test.txt 文件并写入内容", "description": "创建文件", "action": "file","action_type":"tool", "action_input": {{"file_path": "test.txt","operation_type": "create", "content": "hello world!!!"}}}}
{{"thought": "用户要求读取 data.txt 前5行文件", "description": "读取文件", "action": "file","action_type":"tool", "action_input": {{"file_path": "data.txt","operation_type": "read", "operate_scope": "line", "line_params": {{"start_line": 1, "end_line": 5}}}}}}
{{"thought": "用户要求读取 data.txt 前5行文件包含 python 关键词的行内容，返回行内容", "description": "读取文件", "action": "file","action_type":"tool", "action_input": {{"file_path": "data.txt","operation_type": "read", "operate_scope": "line", "line_params": {{"filter_rule": "python","start_line": 1, "end_line": 50}}}}}}
{{"thought": "我需要查看技能的详细使用说明", "description": "加载技能说明文件", "action": "read_skill","action_type":"tool", "action_input": {{"skill_name": "xlsx","file_path": "SKILL.md"}}}}
{{"thought": "用户要求分析 Excel 文件", "description": "分析 Excel", "action": "xlsx","action_type":"skill", "action_input": {{"file_path": "data.xlsx", "operation": "read"}}}}
{{"thought": "任务已完成，返回最终答案", "description": "完成任务", "action": "finish","action_type":"tool", "action_input": "任务已成功完成"}}

### 错误示例（不要这样输出）：
Thought: 用户要求创建文件...
Action: create_file
Action Input: {{"file_path": "test.txt"}}

## 注意事项：
- 当任务已经完成时，必须使用finish行动结束任务
- finish的action_input应该是对用户的最终回答（字符串）
- 不要在任务完成后继续执行其他行动
- 必须返回有效的JSON格式，返回的字符串中如果包含双引号，大括号，方括号，反斜杠，请使用转义后的字符如(\")包裹字符串，避免使用未转义的特殊字符
- action_input是参数对象，不是字符串
- action_type是tool或者skill，必填
- 参数值如果是字符串，必须用双引号包裹
- 参数值可以包含换行符等特殊字符
- 在处理长文本文件时，使用file工具搜索读取文件内容，请按行读取
- 调用技能之前先要通过file工具熟读技能的使用说明
- 除了skill里面指定的参考文档外，所有返回的跟路径相关的参数，都必须是绝对路径，例如：当前工作目录\\1.txt
- 【代码生成注意事项】：
  - 使用execute执行Python代码时，字符串中如果包含双引号，请使用转义(\")或使用单引号包裹字符串
  - 避免在字符串中使用未转义的特殊字符
  - 确保生成的Python代码语法正确，不会导致JSON解析错误
  - 确保生成的代码里面使用的所有路径都是绝对路径，例如：当前工作目录\\1.txt

## SOUL
{context.soul_prompt or ""}

## MEMORY
{context.userMemory or ""}

## 当前用户输入:
{context.user_input}

## 当前任务计划:
{task_plan or "无"}

"""

        steps_part = f"""## 历史上下文:
{history_context}
现在请输出下一步:"""

        messages = [
            {
                "role": "system",
                "content": [PromptTemplates.build_cached_text_content(system_prompt, enable_cache=True)]
            },
            {
                "role": "user",
                "content": [
                    PromptTemplates.build_cached_text_content(steps_part, enable_cache=False)
                ]
            }
        ]

        return messages

    @staticmethod
    def build_task_analysis_messages_with_cache(
        task: str,
        history_context: str,
        skills_list: str,
        context: TaskContext
    ) -> List[Dict[str, Any]]:
        """构建任务分析消息列表（支持上下文缓存）

        统一分析任务并输出处理方案，一次 LLM 调用完成分类 + 计划 + 行动。
        缓存策略：
        - 系统信息、工具列表等静态内容标记为缓存
        - 用户任务、历史上下文等动态内容不标记缓存

        Args:
            task: 用户任务
            history_context: 历史上下文
            skills_list: 可用技能列表
            system_info: 系统信息（可选）
            max_plan_steps: 最大计划步骤数
            context: 任务上下文

        Returns:
            消息列表，支持 cache_control 标记
        """
        system_info = PromptTemplates.get_system_info()

        # 构建基础系统提示词
        base_system_prompt = f"""你是灵犀智能助手

## 系统工具
file : 用于对本地文本文件进行安全、可控的读取/删除/创建/改操作，支持整文件/行级两种粒度，带文件大小安全限制 
execute : 用于执行shell命令，支持powershell、bash等多种shell类型
read_skill : 用于读取技能的详细使用说明

## 技能:
{skills_list}

#### 模型
qwen3.5-plus

## workspace        
{get_workspace_path()}

## 系统环境
{system_info['os_info']}

## Shell类型
{system_info['shell_type']}

当前时间：{system_info['current_date']} {system_info['current_time']}

## 回复格式
**请严格按照JSON格式返回，不要返回多余的其它内容**
**JSON格式示例：**
{{
  
  "thought": "你的思考过程",
  "level": "direct|simple|complex",
  "confidence": 0.0-1.0,
  "reason": "分类理由",
  "direct_answer": "如果是简单问候或可直接回答的问题，在此给出答案",
  "plan": [
    {{"step": 1, "description": "步骤描述"}},
    {{"step": 2, "description": "步骤描述"}}
  ],
  "summary": "任务摘要"
}}

## 分类标准：
- simple: 单一步骤、无法直接调用工具、只能简单问答（如：查天气、翻译、读取文件、问候）
- complex: 多步骤、多工具调用、需要规划（如：旅行规划、数据分析、多文件处理）

## 注意事项：
- 如果是 simple 任务，plan 字段可以为空数组
- 如果是 complex 任务，必须填写 plan 字段
- 如果是问候类或可直接回答的问题，level 设为 direct，direct_answer 为回答内容
- 如果是 complex 任务，请合理的规划plan，每个步骤描述要精炼
- 必须严格返回JSON格式，不要返回多余的其它内容

{context.soul_prompt or ""}

# MEMORY
这些记忆是你对这个世界的认知，你需要运用memory技能好好的维护这些记忆

{context.userMemory or ""}

"""
    
        system_prompt = base_system_prompt

        history_part = f"""历史上下文：
{history_context if history_context else "无"}"""

        user_input_part = f"""用户输入：{task}\n 请输出下一步："""

        messages = [
            {
                "role": "system",
                "content": [PromptTemplates.build_cached_text_content(system_prompt, enable_cache=True)]
            },
            {
                "role": "user",
                "content": [
                    PromptTemplates.build_cached_text_content(history_part, enable_cache=False),
                    PromptTemplates.build_cached_text_content(user_input_part, enable_cache=False)
                ]
            }
        ]

        return messages

    @staticmethod
    def format_task_plan(task_plan: List[str]) -> str:
        """格式化任务计划

        Args:
            task_plan: 原始任务计划字符串

        Returns:
            格式化后的任务计划字符串
        """
        res_str=''
        for index,step in enumerate(task_plan):
            step_clean = step.strip().replace('\n', ' ')
            res_str += f"{index+1}. {step_clean} "
        return f"任务计划: {res_str if len(task_plan) > 1 else ''}" 
