"""
节点管理器 - 负责SSH连接管理和节点状态监控
"""
import os
import time
import paramiko
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import logging

from config.settings import NodeConfig, SSHConfig, config_manager


logger = logging.getLogger(__name__)


class SSHConnection:
    """SSH连接封装类"""
    
    def __init__(self, node: NodeConfig, ssh_config: SSHConfig):
        self.node = node
        self.ssh_config = ssh_config
        self.client: Optional[paramiko.SSHClient] = None
        self.connected = False
        self.last_activity = time.time()
        self._lock = Lock()
    
    def connect(self) -> bool:
        """建立SSH连接"""
        with self._lock:
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # 获取认证信息
                username = self.node.username or self.ssh_config.username
                port = self.node.port or self.ssh_config.port
                
                # 连接参数
                connect_kwargs = {
                    'hostname': self.node.ip,
                    'port': port,
                    'username': username,
                    'timeout': self.ssh_config.timeout
                }
                
                # 优先使用密钥认证，如果有密钥就忽略密码
                key_file = self.node.key_file if hasattr(self.node, 'key_file') and self.node.key_file else self.ssh_config.key_file
                
                if key_file:
                    # 展开路径
                    expanded_key_file = os.path.expanduser(key_file)
                    if os.path.exists(expanded_key_file):
                        connect_kwargs['key_filename'] = expanded_key_file
                        logger.info(f"使用SSH密钥认证: {expanded_key_file}")
                    else:
                        logger.warning(f"SSH密钥文件不存在: {expanded_key_file}，尝试密码认证")
                        # 密钥文件不存在时才尝试密码
                        password = self.node.password or self.ssh_config.password or os.getenv('SSH_PASSWORD')
                        if password:
                            connect_kwargs['password'] = password
                        else:
                            raise ValueError(f"节点 {self.node.name} 缺少认证信息")
                else:
                    # 没有配置密钥时使用密码
                    password = self.node.password or self.ssh_config.password or os.getenv('SSH_PASSWORD')
                    if password:
                        connect_kwargs['password'] = password
                    else:
                        raise ValueError(f"节点 {self.node.name} 缺少认证信息")
                
                self.client.connect(**connect_kwargs)
                self.connected = True
                self.last_activity = time.time()
                
                logger.info(f"成功连接到节点 {self.node.name} ({self.node.ip})")
                return True
                
            except Exception as e:
                logger.error(f"连接节点 {self.node.name} ({self.node.ip}) 失败: {str(e)}")
                self.connected = False
                if self.client:
                    self.client.close()
                    self.client = None
                return False
    
    def disconnect(self):
        """断开SSH连接"""
        with self._lock:
            if self.client:
                self.client.close()
                self.client = None
            self.connected = False
            logger.info(f"断开节点 {self.node.name} 的连接")
    
    def execute_command(self, command: str, timeout: int = 300) -> Tuple[int, str, str]:
        """执行命令"""
        if not self.connected or not self.client:
            raise Exception(f"节点 {self.node.name} 未连接")
        
        try:
            with self._lock:
                stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
                
                # 读取输出
                exit_code = stdout.channel.recv_exit_status()
                stdout_data = stdout.read().decode('utf-8', errors='ignore')
                stderr_data = stderr.read().decode('utf-8', errors='ignore')
                
                self.last_activity = time.time()
                
                return exit_code, stdout_data, stderr_data
                
        except Exception as e:
            logger.error(f"在节点 {self.node.name} 执行命令失败: {str(e)}")
            raise
    
    def is_alive(self) -> bool:
        """检查连接是否存活"""
        if not self.connected or not self.client:
            return False
        
        try:
            # 发送简单命令测试连接
            transport = self.client.get_transport()
            if transport and transport.is_active():
                return True
        except:
            pass
        
        return False


class NodeManager:
    """节点管理器"""
    
    def __init__(self):
        self.connections: Dict[int, SSHConnection] = {}
        self.ssh_config = config_manager.get_ssh_config()
        self.execution_config = config_manager.get_execution_config()
        self._lock = Lock()
    
    def get_connection(self, node: NodeConfig) -> SSHConnection:
        """获取或创建节点连接"""
        with self._lock:
            if node.id not in self.connections:
                self.connections[node.id] = SSHConnection(node, self.ssh_config)
            return self.connections[node.id]
    
    def connect_node(self, node: NodeConfig) -> bool:
        """连接单个节点"""
        connection = self.get_connection(node)
        return connection.connect()
    
    def connect_nodes(self, nodes: List[NodeConfig], max_workers: Optional[int] = None) -> Dict[int, bool]:
        """并发连接多个节点"""
        if max_workers is None:
            max_workers = min(len(nodes), self.execution_config.max_concurrent)
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交连接任务
            future_to_node = {
                executor.submit(self.connect_node, node): node 
                for node in nodes
            }
            
            # 收集结果
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    success = future.result()
                    results[node.id] = success
                except Exception as e:
                    logger.error(f"连接节点 {node.name} 时出错: {str(e)}")
                    results[node.id] = False
        
        # 统计结果
        success_count = sum(1 for success in results.values() if success)
        total_count = len(nodes)
        
        logger.info(f"节点连接完成: {success_count}/{total_count} 成功")
        
        return results
    
    def disconnect_node(self, node_id: int):
        """断开单个节点连接"""
        with self._lock:
            if node_id in self.connections:
                self.connections[node_id].disconnect()
                del self.connections[node_id]
    
    def disconnect_all(self):
        """断开所有节点连接"""
        with self._lock:
            for connection in self.connections.values():
                connection.disconnect()
            self.connections.clear()
            logger.info("所有节点连接已断开")
    
    def get_connected_nodes(self) -> List[int]:
        """获取已连接的节点ID列表"""
        connected = []
        for node_id, connection in self.connections.items():
            if connection.is_alive():
                connected.append(node_id)
        return connected
    
    def check_connections(self) -> Dict[int, bool]:
        """检查所有连接状态"""
        status = {}
        for node_id, connection in self.connections.items():
            status[node_id] = connection.is_alive()
        return status
    
    def reconnect_failed_nodes(self, nodes: List[NodeConfig]) -> Dict[int, bool]:
        """重连失败的节点"""
        failed_nodes = []
        
        for node in nodes:
            if node.id in self.connections:
                connection = self.connections[node.id]
                if not connection.is_alive():
                    connection.disconnect()
                    failed_nodes.append(node)
            else:
                failed_nodes.append(node)
        
        if failed_nodes:
            logger.info(f"尝试重连 {len(failed_nodes)} 个失败节点")
            return self.connect_nodes(failed_nodes)
        
        return {}
    
    def cleanup_idle_connections(self, idle_timeout: int = 3600):
        """清理空闲连接"""
        current_time = time.time()
        to_remove = []
        
        with self._lock:
            for node_id, connection in self.connections.items():
                if current_time - connection.last_activity > idle_timeout:
                    connection.disconnect()
                    to_remove.append(node_id)
            
            for node_id in to_remove:
                del self.connections[node_id]
        
        if to_remove:
            logger.info(f"清理了 {len(to_remove)} 个空闲连接")


# 全局节点管理器实例
node_manager = NodeManager() 