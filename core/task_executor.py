"""
任务执行器 - 负责并发执行shell命令和Docker镜像操作
"""
import time
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass
from enum import Enum
import logging

from config.settings import NodeConfig, config_manager
from core.node_manager import node_manager


logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型枚举"""
    SHELL_COMMAND = "shell_command"
    DOCKER_PULL = "docker_pull"
    DOCKER_BUILD = "docker_build"
    DOCKER_PUSH = "docker_push"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"


@dataclass
class TaskResult:
    """任务执行结果"""
    node_id: int
    node_name: str
    node_ip: str
    task_type: TaskType
    command: str
    success: bool
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0
    error_message: str = ""
    retry_count: int = 0


@dataclass
class Task:
    """任务定义"""
    task_type: TaskType
    command: str
    node_ids: List[int]
    timeout: int = 300
    retry_count: int = 3
    retry_delay: int = 5
    extra_params: Dict[str, Any] = None


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self):
        self.execution_config = config_manager.get_execution_config()
    
    def execute_task_on_node(self, node: NodeConfig, task: Task) -> TaskResult:
        """在单个节点上执行任务"""
        start_time = time.time()
        result = TaskResult(
            node_id=node.id,
            node_name=node.name,
            node_ip=node.ip,
            task_type=task.task_type,
            command=task.command,
            success=False
        )
        
        try:
            # 获取连接
            connection = node_manager.get_connection(node)
            
            # 确保连接可用
            if not connection.is_alive():
                if not connection.connect():
                    raise Exception(f"无法连接到节点 {node.name}")
            
            # 执行任务
            if task.task_type == TaskType.SHELL_COMMAND:
                exit_code, stdout, stderr = connection.execute_command(
                    task.command, timeout=task.timeout
                )
                result.exit_code = exit_code
                result.stdout = stdout
                result.stderr = stderr
                result.success = (exit_code == 0)
                
            elif task.task_type == TaskType.DOCKER_PULL:
                image_name = task.command
                pull_command = f"docker pull {image_name}"
                exit_code, stdout, stderr = connection.execute_command(
                    pull_command, timeout=task.timeout
                )
                result.exit_code = exit_code
                result.stdout = stdout
                result.stderr = stderr
                result.success = (exit_code == 0)
                
            elif task.task_type == TaskType.DOCKER_BUILD:
                dockerfile_path = task.command
                tag = task.extra_params.get('tag', 'latest') if task.extra_params else 'latest'
                build_command = f"docker build -t {tag} {dockerfile_path}"
                exit_code, stdout, stderr = connection.execute_command(
                    build_command, timeout=task.timeout
                )
                result.exit_code = exit_code
                result.stdout = stdout
                result.stderr = stderr
                result.success = (exit_code == 0)
                
            elif task.task_type == TaskType.DOCKER_PUSH:
                image_name = task.command
                push_command = f"docker push {image_name}"
                exit_code, stdout, stderr = connection.execute_command(
                    push_command, timeout=task.timeout
                )
                result.exit_code = exit_code
                result.stdout = stdout
                result.stderr = stderr
                result.success = (exit_code == 0)
            
            else:
                raise Exception(f"不支持的任务类型: {task.task_type}")
            
        except Exception as e:
            result.error_message = str(e)
            logger.error(f"节点 {node.name} 执行任务失败: {str(e)}")
        
        result.execution_time = time.time() - start_time
        return result
    
    def execute_task_with_retry(self, node: NodeConfig, task: Task) -> TaskResult:
        """带重试的任务执行"""
        last_result = None
        
        for attempt in range(task.retry_count + 1):
            result = self.execute_task_on_node(node, task)
            result.retry_count = attempt
            
            if result.success:
                if attempt > 0:
                    logger.info(f"节点 {node.name} 在第 {attempt + 1} 次尝试后成功")
                return result
            
            last_result = result
            
            if attempt < task.retry_count:
                logger.warning(f"节点 {node.name} 第 {attempt + 1} 次尝试失败，{task.retry_delay}秒后重试")
                time.sleep(task.retry_delay)
        
        logger.error(f"节点 {node.name} 在 {task.retry_count + 1} 次尝试后仍然失败")
        return last_result
    
    def execute_task(self, task: Task) -> List[TaskResult]:
        """执行任务到指定节点"""
        # 获取节点配置
        if not task.node_ids:
            nodes = config_manager.get_nodes()
        else:
            nodes = config_manager.get_nodes_by_ids(task.node_ids)
        
        if not nodes:
            logger.warning("没有找到可用的节点")
            return []
        
        logger.info(f"开始在 {len(nodes)} 个节点上执行任务: {task.command}")
        
        # 并发执行
        max_workers = min(len(nodes), self.execution_config.max_concurrent)
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            future_to_node = {
                executor.submit(self.execute_task_with_retry, node, task): node
                for node in nodes
            }
            
            # 收集结果
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.success:
                        logger.info(f"✓ 节点 {node.name} 执行成功")
                    else:
                        logger.error(f"✗ 节点 {node.name} 执行失败: {result.error_message}")
                        
                except Exception as e:
                    logger.error(f"节点 {node.name} 任务执行异常: {str(e)}")
                    # 创建错误结果
                    error_result = TaskResult(
                        node_id=node.id,
                        node_name=node.name,
                        node_ip=node.ip,
                        task_type=task.task_type,
                        command=task.command,
                        success=False,
                        error_message=str(e)
                    )
                    results.append(error_result)
        
        # 统计结果
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)
        
        logger.info(f"任务执行完成: {success_count}/{total_count} 成功")
        
        return results
    
    def execute_shell_command(self, command: str, node_ids: Optional[List[int]] = None, 
                            timeout: int = 300) -> List[TaskResult]:
        """执行Shell命令"""
        task = Task(
            task_type=TaskType.SHELL_COMMAND,
            command=command,
            node_ids=node_ids or [],
            timeout=timeout,
            retry_count=self.execution_config.retry_count,
            retry_delay=self.execution_config.retry_delay
        )
        return self.execute_task(task)
    
    def docker_pull(self, image_name: str, node_ids: Optional[List[int]] = None, 
                   timeout: int = 600) -> List[TaskResult]:
        """拉取Docker镜像"""
        task = Task(
            task_type=TaskType.DOCKER_PULL,
            command=image_name,
            node_ids=node_ids or [],
            timeout=timeout,
            retry_count=self.execution_config.retry_count,
            retry_delay=self.execution_config.retry_delay
        )
        return self.execute_task(task)
    
    def docker_build(self, dockerfile_path: str, tag: str, node_ids: Optional[List[int]] = None, 
                    timeout: int = 1800) -> List[TaskResult]:
        """构建Docker镜像"""
        task = Task(
            task_type=TaskType.DOCKER_BUILD,
            command=dockerfile_path,
            node_ids=node_ids or [],
            timeout=timeout,
            retry_count=self.execution_config.retry_count,
            retry_delay=self.execution_config.retry_delay,
            extra_params={'tag': tag}
        )
        return self.execute_task(task)
    
    def docker_push(self, image_name: str, node_ids: Optional[List[int]] = None, 
                   timeout: int = 600) -> List[TaskResult]:
        """推送Docker镜像"""
        task = Task(
            task_type=TaskType.DOCKER_PUSH,
            command=image_name,
            node_ids=node_ids or [],
            timeout=timeout,
            retry_count=self.execution_config.retry_count,
            retry_delay=self.execution_config.retry_delay
        )
        return self.execute_task(task)


# 全局任务执行器实例
task_executor = TaskExecutor() 