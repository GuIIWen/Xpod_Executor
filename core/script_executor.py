"""
脚本执行器 - 支持在远程节点执行shell脚本文件
"""
import os
import tempfile
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

from config.settings import NodeConfig, config_manager
from core.task_executor import task_executor, TaskResult, TaskType
from core.node_manager import node_manager

logger = logging.getLogger(__name__)


class ScriptExecutor:
    """脚本执行器"""
    
    def __init__(self):
        self.execution_config = config_manager.get_execution_config()
    
    def upload_and_execute_script(self, script_path: str, node_ids: Optional[List[int]] = None,
                                args: str = "", timeout: int = 600, 
                                remote_path: str = "/tmp") -> List[TaskResult]:
        """
        上传脚本文件到远程节点并执行
        
        Args:
            script_path: 本地脚本文件路径
            node_ids: 目标节点ID列表
            args: 脚本参数
            timeout: 执行超时时间
            remote_path: 远程存储路径
            
        Returns:
            List[TaskResult]: 执行结果列表
        """
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"脚本文件不存在: {script_path}")
        
        script_name = os.path.basename(script_path)
        remote_script_path = f"{remote_path}/{script_name}"
        
        # 读取脚本内容
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        logger.info(f"开始上传并执行脚本: {script_path}")
        
        # 获取目标节点
        if node_ids is None:
            nodes = config_manager.get_nodes()
        else:
            nodes = config_manager.get_nodes_by_ids(node_ids)
        
        results = []
        
        for node in nodes:
            result = self._execute_script_on_node(
                node, script_content, remote_script_path, args, timeout
            )
            results.append(result)
        
        return results
    
    def execute_script_content(self, script_content: str, node_ids: Optional[List[int]] = None,
                             args: str = "", timeout: int = 600,
                             script_name: str = "temp_script.sh") -> List[TaskResult]:
        """
        直接执行脚本内容（不需要本地文件）
        
        Args:
            script_content: 脚本内容
            node_ids: 目标节点ID列表  
            args: 脚本参数
            timeout: 执行超时时间
            script_name: 临时脚本文件名
            
        Returns:
            List[TaskResult]: 执行结果列表
        """
        remote_script_path = f"/tmp/{script_name}"
        
        logger.info(f"开始执行脚本内容")
        
        # 获取目标节点
        if node_ids is None:
            nodes = config_manager.get_nodes()
        else:
            nodes = config_manager.get_nodes_by_ids(node_ids)
        
        results = []
        
        for node in nodes:
            result = self._execute_script_on_node(
                node, script_content, remote_script_path, args, timeout
            )
            results.append(result)
        
        return results
    
    def _execute_script_on_node(self, node: NodeConfig, script_content: str,
                               remote_script_path: str, args: str, timeout: int) -> TaskResult:
        """在单个节点上执行脚本"""
        import time
        
        start_time = time.time()
        result = TaskResult(
            node_id=node.id,
            node_name=node.name,
            node_ip=node.ip,
            task_type=TaskType.SHELL_COMMAND,
            command=f"执行脚本: {remote_script_path} {args}",
            success=False
        )
        
        try:
            # 获取连接
            connection = node_manager.get_connection(node)
            
            # 确保连接可用
            if not connection.is_alive():
                if not connection.connect():
                    raise Exception(f"无法连接到节点 {node.name}")
            
            # 步骤1: 创建脚本文件
            create_script_command = f"""
cat > {remote_script_path} << 'EOF'
{script_content}
EOF
"""
            exit_code, stdout, stderr = connection.execute_command(
                create_script_command, timeout=30
            )
            
            if exit_code != 0:
                raise Exception(f"创建脚本文件失败: {stderr}")
            
            # 步骤2: 设置执行权限
            chmod_command = f"chmod +x {remote_script_path}"
            exit_code, stdout, stderr = connection.execute_command(
                chmod_command, timeout=10
            )
            
            if exit_code != 0:
                raise Exception(f"设置脚本权限失败: {stderr}")
            
            # 步骤3: 执行脚本 - 智能选择解释器
            # 检查文件扩展名和shebang行选择合适的解释器
            script_extension = os.path.splitext(remote_script_path)[1].lower()
            
            if script_extension == '.py':
                # Python脚本，使用python3执行
                execute_command = f"python3 {remote_script_path} {args}"
            elif script_content.startswith('#!/usr/bin/env python') or script_content.startswith('#!/usr/bin/python'):
                # 有Python shebang的脚本
                execute_command = f"python3 {remote_script_path} {args}"
            elif script_extension in ['.sh', '.bash'] or script_content.startswith('#!/bin/bash') or script_content.startswith('#!/usr/bin/bash'):
                # Bash脚本
                execute_command = f"bash {remote_script_path} {args}"
            else:
                # 默认尝试让系统根据shebang行执行，如果没有shebang则用bash
                if script_content.startswith('#!'):
                    execute_command = f"{remote_script_path} {args}"
                else:
                    execute_command = f"bash {remote_script_path} {args}"
            
            logger.info(f"使用命令执行脚本: {execute_command}")
            exit_code, stdout, stderr = connection.execute_command(
                execute_command, timeout=timeout
            )
            
            result.exit_code = exit_code
            result.stdout = stdout
            result.stderr = stderr
            result.success = (exit_code == 0)
            
            # 步骤4: 清理临时文件
            cleanup_command = f"rm -f {remote_script_path}"
            connection.execute_command(cleanup_command, timeout=10)
            
        except Exception as e:
            result.error_message = str(e)
            logger.error(f"节点 {node.name} 执行脚本失败: {str(e)}")
        
        result.execution_time = time.time() - start_time
        return result
    
    def execute_script_from_url(self, script_url: str, node_ids: Optional[List[int]] = None,
                               args: str = "", timeout: int = 600) -> List[TaskResult]:
        """
        从URL下载并执行脚本
        
        Args:
            script_url: 脚本文件URL
            node_ids: 目标节点ID列表
            args: 脚本参数  
            timeout: 执行超时时间
            
        Returns:
            List[TaskResult]: 执行结果列表
        """
        # 构建下载并执行的命令
        script_name = os.path.basename(script_url)
        remote_script_path = f"/tmp/{script_name}"
        
        command = f"""
# 下载脚本
curl -fsSL -o {remote_script_path} "{script_url}" || wget -q -O {remote_script_path} "{script_url}"

# 设置执行权限
chmod +x {remote_script_path}

# 执行脚本
bash {remote_script_path} {args}

# 清理文件
rm -f {remote_script_path}
"""
        
        logger.info(f"开始从URL下载并执行脚本: {script_url}")
        
        return task_executor.execute_shell_command(
            command, node_ids=node_ids, timeout=timeout
        )
    
    def execute_local_script_remotely(self, script_path: str, node_ids: Optional[List[int]] = None,
                                    args: str = "", timeout: int = 600) -> List[TaskResult]:
        """
        将本地脚本内容作为命令执行（推荐方法）
        
        Args:
            script_path: 本地脚本文件路径
            node_ids: 目标节点ID列表
            args: 脚本参数
            timeout: 执行超时时间
            
        Returns:
            List[TaskResult]: 执行结果列表
        """
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"脚本文件不存在: {script_path}")
        
        # 读取脚本内容
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read().strip()
        
        # 如果有参数，需要处理脚本中的$1, $2等参数
        if args:
            # 构建设置参数的前缀
            args_list = args.split()
            escaped_args = [f'"{arg}"' for arg in args_list]
            param_setup = f'set -- {" ".join(escaped_args)}'
            script_content = f"{param_setup}\n{script_content}"
        
        logger.info(f"开始远程执行本地脚本: {script_path}")
        
        return task_executor.execute_shell_command(
            script_content, node_ids=node_ids, timeout=timeout
        )


# 全局脚本执行器实例
script_executor = ScriptExecutor() 