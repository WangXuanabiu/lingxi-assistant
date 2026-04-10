#!/usr/bin/env python3
"""读取技能使用说明工具

从 SkillSystem 缓存中读取技能的 SKILL.md 文件内容，
提供详细的技能使用说明、参数说明和示例代码。
"""

import logging
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from lingxi.core.utils.Tool import ToolBase


class ReadSkillTool(ToolBase):
    """读取技能使用说明工具类"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, skill_system=None):
        """初始化工具
        
        Args:
            skill_system: SkillSystem 实例（可选，如果为 None 则需要手动设置）
        """
        super().__init__("read_skill", "读取技能使用说明工具，从 SkillSystem 缓存中读取技能的 SKILL.md 文件内容")
        self.skill_system = skill_system
    
    def set_skill_system(self, skill_system):
        """设置 SkillSystem 实例
        
        Args:
            skill_system: SkillSystem 实例
        """
        self.skill_system = skill_system
        self.logger.debug("SkillSystem 已设置")
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具 - 读取技能的 SKILL.md 文件内容
        
        Args:
            parameters: 工具参数，包含:
                - skill_name: 技能名称（必填）
                - file_path: 文件相对路径（可填，为 None 时默认读SKILL.md）
            
        Returns:
            执行结果字典，格式：
            {
                "status": "S" | "F",  # 成功/失败
                "content": [],  # 返回内容列表
                "error": ""  # 错误信息（成功时为空）
            }
        """
        skill_name = parameters.get("skill_name") #技能名称
        file_path = parameters.get("file_path") #文件相对路径
        
        result = {
            "status": "F",
            "content": [],
            "error": "",
            "result_description": f"加载技能: {skill_name}"
        }
        
        if not skill_name:
            result["error"] = "缺少必要参数: skill_name"
            return result
        
        if file_path is None:
            file_path = f"SKILL.md"
            
        
        # 从 SkillSystem 的缓存中读取 SKILL.md 内容
        skill_cache = self.skill_system.cache
        self.logger.debug(f"尝试读取 {file_path}，skill_name={skill_name}, skill_system={self.skill_system}, cache={skill_cache}")
        if skill_cache:
            cached_content = skill_cache.get_file_content(skill_name, file_path)
            self.logger.debug(f"get_file_content 返回结果：{cached_content}")
            if cached_content:
                self.logger.info(f"从缓存读取 {file_path}：{skill_name}")
                result["status"] = "S"
                result["content"] = cached_content
                return result
        
        # 如果缓存中没有，尝试从文件系统重新加载
        self.logger.debug(f"缓存未命中，尝试从文件系统加载：{skill_name}")
        content = self._load_from_filesystem(skill_name)
        if content:
            self.logger.info(f"从文件系统加载 SKILL.md：{skill_name}")
            # 重新缓存
            if skill_cache:
                skill_md_path = self._find_skill_file_path(skill_name)
                if skill_md_path:
                    skill_cache.set_md_content(skill_name, content, skill_md_path)
            result["status"] = "S"
            result["content"] = content
            return result
        
        # 如果文件系统中也没有，返回错误
        self.logger.warning(f"缓存和文件系统中均未找到 {file_path}：{skill_name}")
        result["error"] = f"缓存中未找到 {file_path}：{skill_name}"
        return result
    
    def _find_skill_file_path(self, skill_name: str, file_path: str = "SKILL.md") -> Optional[str]:
        """查找技能的文件路径
        
        Args:
            skill_name: 技能名称
            file_path: 文件相对路径，默认为 SKILL.md
            
        Returns:
            文件路径，如果未找到返回 None
        """
        # 获取技能目录配置
        skills_config = self.skill_system.loader
        if not skills_config:
            return None
        
        # 如果传入的是绝对路径，尝试提取技能相对路径
        if Path(file_path).is_absolute():
            self.logger.debug(f"检测到绝对路径: {file_path}")
            # 尝试从绝对路径中提取技能相对路径
            relative_path = self._extract_skill_relative_path(skill_name, file_path)
            if relative_path:
                self.logger.debug(f"从绝对路径提取技能相对路径: {file_path} -> {relative_path}")
                file_path = relative_path
            else:
                # 如果无法提取，尝试直接查找文件
                if Path(file_path).exists():
                    return file_path
                return None
        
        # 在内置技能目录和用户技能目录中查找
        for skills_path in [skills_config.builtin_skills_dir, skills_config.user_skills_dir]:
            if not skills_path:
                continue
            try:
                skill_dir = Path(skills_path) / skill_name
                skill_file_path = skill_dir / file_path
                if skill_file_path.exists():
                    return str(skill_file_path)
            except Exception:
                continue
        
        return None
    
    def _extract_skill_relative_path(self, skill_name: str, absolute_path: str) -> Optional[str]:
        """从绝对路径中提取技能的相对路径
        
        Args:
            skill_name: 技能名称
            absolute_path: 绝对路径
            
        Returns:
            技能相对路径，如果无法提取返回 None
        """
        skills_config = self.skill_system.loader
        if not skills_config:
            return None
        
        # 尝试在所有技能目录中查找匹配的技能路径
        for skills_path in [skills_config.builtin_skills_dir, skills_config.user_skills_dir]:
            if not skills_path:
                continue
            try:
                # 将技能目录路径转换为 Path 对象进行比较
                skills_dir_path = Path(skills_path).resolve()
                absolute_path_obj = Path(absolute_path).resolve()

                # 检查绝对路径是否在该技能目录下
                if skills_dir_path in absolute_path_obj.parents or skills_dir_path == absolute_path_obj.parent:
                    # 计算相对路径
                    skill_dir = skills_dir_path / skill_name
                    try:
                        relative_path = absolute_path_obj.relative_to(skill_dir)
                        # 统一使用正斜杠
                        return str(relative_path).replace('\\', '/')
                    except ValueError:
                        continue
            except Exception:
                continue
        
        # 尝试通用的路径提取：查找技能名称在路径中的位置
        try:
            abs_path_str = str(Path(absolute_path)).replace('\\', '/')
            skill_name_lower = skill_name.lower()

            # 查找路径中是否包含技能名称
            skill_name_pos = abs_path_str.lower().rfind(skill_name_lower)
            if skill_name_pos != -1:
                # 技能名称后的路径部分
                after_skill = abs_path_str[skill_name_pos + len(skill_name):]
                if after_skill.startswith('/'):
                    return after_skill[1:]
                elif after_skill == '' or after_skill.startswith('.'):
                    # 如果是技能名称本身或子路径
                    pass
        except Exception:
            pass
        
        return None
    
    def _load_from_filesystem(self, skill_name: str, file_path: str = "SKILL.md") -> Optional[str]:
        """从文件系统加载指定文件内容
        
        Args:
            skill_name: 技能名称
            file_path: 文件相对路径，默认为 SKILL.md
            
        Returns:
            文件内容，如果未找到返回 None
        """
        skill_file_path = self._find_skill_file_path(skill_name, file_path)
        if not skill_file_path:
            return None
        
        try:
            with open(skill_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"读取文件失败：{e}")
            return None
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Optional[str]:
        """验证参数
        
        Args:
            parameters: 工具参数
            
        Returns:
            错误信息（如果有），否则返回 None
        """
        skill_name = parameters.get("skill_name")
        if not skill_name:
            return "缺少必要参数: skill_name"
        return None
    

    
    
    
    
