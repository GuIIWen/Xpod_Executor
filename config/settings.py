"""
配置管理模块
"""
import os
import yaml
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class NodeConfig(BaseModel):
    """节点配置模型"""
    id: int
    ip: str
    name: str
    enabled: bool = True
    username: Optional[str] = None
    password: Optional[str] = None
    port: Optional[int] = None


class SSHConfig(BaseModel):
    """SSH配置模型"""
    username: str = "root"
    port: int = 22
    timeout: int = 30
    key_file: Optional[str] = None
    password: Optional[str] = None


class ExecutionConfig(BaseModel):
    """执行配置模型"""
    max_concurrent: int = 10
    retry_count: int = 3
    retry_delay: int = 5
    command_timeout: int = 300


class LoggingConfig(BaseModel):
    """日志配置模型"""
    level: str = "INFO"
    file: str = "logs/execution.log"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Config(BaseModel):
    """主配置模型"""
    nodes: List[NodeConfig]
    ssh: SSHConfig
    execution: ExecutionConfig
    logging: LoggingConfig


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config/nodes.yaml"):
        self.config_path = config_path
        self._config: Optional[Config] = None
    
    def load_config(self) -> Config:
        """加载配置文件"""
        if self._config is None:
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            self._config = Config(**config_data)
        
        return self._config
    
    def get_nodes(self, enabled_only: bool = True) -> List[NodeConfig]:
        """获取节点列表"""
        config = self.load_config()
        if enabled_only:
            return [node for node in config.nodes if node.enabled]
        return config.nodes
    
    def get_node_by_id(self, node_id: int) -> Optional[NodeConfig]:
        """根据ID获取节点"""
        nodes = self.get_nodes(enabled_only=False)
        for node in nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_nodes_by_ids(self, node_ids: List[int]) -> List[NodeConfig]:
        """根据ID列表获取节点"""
        nodes = []
        for node_id in node_ids:
            node = self.get_node_by_id(node_id)
            if node:
                nodes.append(node)
        return nodes
    
    def get_ssh_config(self) -> SSHConfig:
        """获取SSH配置"""
        config = self.load_config()
        return config.ssh
    
    def get_execution_config(self) -> ExecutionConfig:
        """获取执行配置"""
        config = self.load_config()
        return config.execution
    
    def get_logging_config(self) -> LoggingConfig:
        """获取日志配置"""
        config = self.load_config()
        return config.logging
    
    def update_node_status(self, node_id: int, enabled: bool):
        """更新节点状态"""
        config = self.load_config()
        for node in config.nodes:
            if node.id == node_id:
                node.enabled = enabled
                break
        
        # 保存配置
        self.save_config(config)
    
    def save_config(self, config: Config):
        """保存配置到文件"""
        config_dict = config.model_dump()
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
        
        # 清除缓存
        self._config = None


# 全局配置管理器实例
config_manager = ConfigManager() 
