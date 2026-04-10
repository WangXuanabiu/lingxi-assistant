import asyncio
import logging
import json
from typing import Dict, Any, TYPE_CHECKING

from starlette.middleware import P
from lingxi.core.context.task_context import TaskContext
from lingxi.core.event import global_event_publisher

if TYPE_CHECKING:
    from lingxi.core.session.session_manager import SessionManager
from lingxi.core.session.task_manager import TaskManager


class SessionStoreSubscriber:
    """会话存储事件订阅者（单例模式）"""
    
    _instance = None  # 单例实例
    
    def __new__(cls, sessionManage: 'SessionManager' = None):
        """单例模式：确保只创建一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, sessionManage: 'SessionManager' = None):
        # 防止重复初始化
        if hasattr(self, '_initialized'):
            return
        # 如果首次初始化时传入了 sessionManage，则保存
        if sessionManage:
            self.sessionManage = sessionManage
        self.taskManage = TaskManager()
        self.logger = logging.getLogger(__name__)
        self._subscribe_to_events()
        self._initialized = True

    def _subscribe_to_events(self):
        """订阅事件"""
        global_event_publisher.subscribe('task_start', self.handle_task_start)
        global_event_publisher.subscribe('plan_start', self.handle_plan_start)
        global_event_publisher.subscribe('plan_final', self.handle_plan_final)
        global_event_publisher.subscribe('step_end', self.handle_step_end)
        global_event_publisher.subscribe('task_failed', self.handle_task_failed)
        global_event_publisher.subscribe('task_end', self.handle_task_end)
        global_event_publisher.subscribe('task_stopped', self.handle_task_end)

        self.logger.info("会话存储订阅者已初始化，开始监听事件")

    def _unsubscribe_from_events(self):
        """取消订阅事件"""
        global_event_publisher.unsubscribe('plan_start', self.handle_plan_start)
        global_event_publisher.unsubscribe('plan_final', self.handle_plan_final)
        global_event_publisher.unsubscribe('step_end', self.handle_step_end)
        global_event_publisher.unsubscribe('task_end', self.handle_task_end)
        global_event_publisher.unsubscribe('task_failed', self.handle_task_failed)
        global_event_publisher.unsubscribe('task_stopped', self.handle_task_end)

        self.logger.info("会话存储订阅者已停止监听事件")



    def handle_task_start(self, context: TaskContext, **kwargs):
        """处理任务处理开始事件

        Args:
            context: 任务上下文
            **kwargs: 其他参数
        """
        task_id = context.task_id
        user_input = context.user_input
        task_level = context.task_info.task_type
        session_id = context.session_id
        self.logger.debug(f"收到 task_start 事件：session={session_id}, task_id={task_id}")
        if not task_id:
            self.logger.warning(f"处理 task_start 事件时缺少 task_id: {session_id}, kwargs={kwargs}")
            return
            
        if self.sessionManage:
            session_info = self.sessionManage.get_session_info(session_id)
            if not session_info:
                self.logger.debug(f"会话不存在，创建新会话：session={session_id}")
                self.sessionManage.create_session_by_id(session_id=session_id)
            
            existing_task = self.taskManage.get_task(task_id)
            if existing_task:
                self.logger.debug(f"任务已存在，跳过创建：session={session_id}, task={task_id}")
                return
            
            self.taskManage.create_task(
                session_id=session_id,
                task_id=task_id,
                task_type='task',
                user_input=user_input,
                task_level=task_level
            )
        else:
            self.logger.warning("sessionManage 未初始化")

    def handle_plan_start(self, context: TaskContext, **kwargs):
        """处理任务规划开始事件

        Args:
            context: 任务上下文
            **kwargs: 其他参数
        """
        task_id = context.task_id
        task_input = context.user_input
        task_level = context.task_info.task_type
        summary = context.description
        session_id = context.session_id
        self.logger.debug(f"收到 plan_start 事件：session={session_id}, task_id={task_id}")
        if not task_id:
            self.logger.warning(f"处理 plan_start 事件时缺少 task_id: {session_id}, kwargs={kwargs}")
            return
            
        if self.sessionManage:
            # 检查会话是否存在，不存在则创建
            session_info = self.sessionManage.get_session_info(session_id)
            if not session_info:
                self.sessionManage.create_session_by_id(session_id=session_id)
                # 新会话，保存 LLM 返回的摘要到 title 字段
                if summary:
                    self.sessionManage.update_session_title(session_id, summary)
                    self.logger.debug(f"新会话，已设置摘要：session={session_id}, summary={summary[:50]}...")
            else:
                self.logger.debug(f"会话已存在：session={session_id}")
                # 会话已存在，检查 title 是否为默认值
                title = session_info.get('title', '')
                if title == '新会话' and summary:
                    # 是默认值，更新为 LLM 返回的摘要
                    self.sessionManage.update_session_title(session_id, summary)
                    self.logger.debug(f"会话 title 为默认值，已更新摘要：session={session_id}, summary={summary[:50]}...")
            
            # 检查任务是否已存在，避免重复创建
            existing_task = self.taskManage.get_task(task_id)
            if existing_task:
                self.logger.debug(f"任务已存在，跳过创建：session={session_id}, task={task_id}")
                return
            
            # 创建任务
            self.taskManage.create_task(
                session_id=session_id,
                task_id=task_id,
                task_type='plan',
                user_input=task_input,
                task_level=task_level
            )
        else:
            self.logger.warning("sessionManage 未初始化")
    def handle_task_failed(self, context: TaskContext, **kwargs):
        task_id = context.task_id
        self.logger.debug(f"收到 task_failed 事件：session={context.session_id}, task_id={task_id}")
        if not task_id:
            self.logger.warning(f"处理 task_failed 事件时缺少 task_id: {context.session_id}, kwargs={kwargs}")
            return
            
        if self.sessionManage:
            self.taskManage.set_task_result(
                session_id=context.session_id,
                task_id=task_id,
                result=kwargs.get('error', ''),
                user_input=context.user_input,
                status='failed'
            )
        else:
            self.logger.warning("sessionManage 未初始化")

    def handle_plan_final(self, context: TaskContext, **kwargs):
        """处理任务规划完成事件

        Args:
            context: 任务上下文
            **kwargs: 其他参数
        """
        task_id = context.task_id
        self.logger.debug(f"当前任务ID：{task_id}")
        if not task_id:
            self.logger.warning(f"处理 plan_final 事件时缺少 task_id: {context.session_id}")
            return
            
        if self.sessionManage:
            self.taskManage.save_plan(
                session_id=context.session_id,
                task_id=task_id,
                plan=context.task_info.plan
            )

    def handle_step_end(self, context: TaskContext, step_index: int, **kwargs):
        """处理步骤执行结束事件

        Args:
            context: 任务上下文
            step_index: 步骤索引
            result: 步骤执行结果（字符串或字典格式）
            **kwargs: 其他参数
        """
        task_id = context.task_id
        session_id = context.session_id
        result=context.steps[-1].result
        result_description=context.steps[-1].result_description
        status=context.steps[-1].status
        thought=context.steps[-1].thought
        action=context.steps[-1].skill_call
        action_input=context.steps[-1].result
        description=context.steps[-1].description
        self.logger.debug(f"收到 step_end 事件：session={context.session_id}, task_id={task_id}, step={step_index}")
        if not task_id:
            self.logger.warning(f"处理 step_end 事件时缺少 task_id: {context.session_id}, kwargs={kwargs}")
            return
        
        # 如果 result 是字典，转换为 JSON 字符串
        if isinstance(result, dict):
            result = json.dumps(result, ensure_ascii=False)
            
        if self.sessionManage:
            self.sessionManage.step_manager.add_step(
                session_id=session_id,
                task_id=task_id,
                step_index=step_index,
                result=result,
                status=status,
                thought=thought,
                action=action,
                action_input=action_input,
                description=description,
                result_description=result_description
            )
        else:
            self.logger.warning("sessionManage 未初始化")

    def handle_task_end(self, context: TaskContext, result: Any, **kwargs):
        """处理任务处理最终结果输出事件

        Args:
            context: 任务上下文
            result: 最终结果（字符串或字典格式）
            **kwargs: 其他参数
        """
        task_id = context.task_id
        session_id = context.session_id
        user_input = context.user_input
        status=context.task_info.status
        self.logger.debug(f"收到 task_end 事件：session={context.session_id}, task_id={task_id}")
        if not task_id:
            self.logger.warning(f"处理 task_end 事件时缺少 task_id: {session_id}, kwargs={kwargs}")
            return
        
        if isinstance(result, dict):
            result = json.dumps(result, ensure_ascii=False)
            
        if self.sessionManage:
            self.taskManage.set_task_result(
                session_id=session_id,
                task_id=task_id,
                result=result,
                user_input=user_input,
                status= status or 'completed'
            )
            
            input_tokens = context.input_tokens
            output_tokens = context.output_tokens
            if input_tokens or output_tokens:
                self.taskManage.update_task_tokens(task_id, input_tokens, output_tokens)
                self.sessionManage.update_session_tokens(session_id, input_tokens, output_tokens)
                self.logger.debug(f"任务 Token 总计：input={input_tokens}, output={output_tokens}")
            
        else:
            self.logger.warning("sessionManage 未初始化")

    def __del__(self):
        """析构函数，清理订阅"""
        try:
            self._unsubscribe_from_events()
        except Exception:
            pass
