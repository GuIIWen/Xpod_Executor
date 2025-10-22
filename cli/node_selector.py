"""
节点选择器 - 提供灵活的节点选择功能
"""
import re
from typing import List, Optional, Union
from config.settings import config_manager, NodeConfig


class NodeSelector:
    """节点选择器"""
    
    def __init__(self):
        self.all_nodes = config_manager.get_nodes(enabled_only=False)
    
    def parse_selection(self, selection: str) -> List[NodeConfig]:
        """
        解析节点选择字符串
        
        支持格式:
        - "all": 所有启用的节点
        - "all-enabled": 所有启用的节点
        - "all-disabled": 所有禁用的节点
        - "all-all": 所有节点（包括禁用的）
        - "0,1,2": 指定节点ID
        - "0-5": 节点ID范围
        - "0,2-5,8": 混合格式
        - "node-0,node-1": 节点名称
        - "192.168.0.227,192.168.0.48": IP地址
        """
        if not selection or selection.strip() == '':
            return config_manager.get_nodes()  # 默认返回启用的节点
        
        selection = selection.strip().lower()
        
        # 处理特殊关键字
        if selection == 'all' or selection == 'all-enabled':
            return config_manager.get_nodes(enabled_only=True)
        elif selection == 'all-disabled':
            return [node for node in self.all_nodes if not node.enabled]
        elif selection == 'all-all':
            return self.all_nodes
        
        # 解析具体选择
        selected_nodes = []
        parts = [part.strip() for part in selection.split(',')]
        
        for part in parts:
            if not part:
                continue
            
            # 处理范围格式 (如: 0-5)
            if '-' in part and self._is_range_format(part):
                range_nodes = self._parse_range(part)
                selected_nodes.extend(range_nodes)
            else:
                # 处理单个标识符
                node = self._find_single_node(part)
                if node:
                    selected_nodes.append(node)
        
        # 去重并保持顺序
        seen_ids = set()
        unique_nodes = []
        for node in selected_nodes:
            if node.id not in seen_ids:
                seen_ids.add(node.id)
                unique_nodes.append(node)
        
        return unique_nodes
    
    def _is_range_format(self, part: str) -> bool:
        """检查是否是范围格式"""
        pattern = r'^\d+-\d+$'
        return re.match(pattern, part) is not None
    
    def _parse_range(self, range_str: str) -> List[NodeConfig]:
        """解析范围字符串"""
        try:
            start_str, end_str = range_str.split('-')
            start_id = int(start_str)
            end_id = int(end_str)
            
            if start_id > end_id:
                start_id, end_id = end_id, start_id  # 交换顺序
            
            range_nodes = []
            for node in self.all_nodes:
                if start_id <= node.id <= end_id:
                    range_nodes.append(node)
            
            return range_nodes
        except (ValueError, IndexError):
            return []
    
    def _find_single_node(self, identifier: str) -> Optional[NodeConfig]:
        """根据标识符查找单个节点"""
        # 尝试按ID查找
        if identifier.isdigit():
            node_id = int(identifier)
            for node in self.all_nodes:
                if node.id == node_id:
                    return node
        
        # 尝试按名称查找
        for node in self.all_nodes:
            if node.name.lower() == identifier:
                return node
        
        # 尝试按IP查找
        for node in self.all_nodes:
            if node.ip == identifier:
                return node
        
        return None
    
    def get_selection_help(self) -> str:
        """获取选择帮助信息"""
        return """
节点选择格式:
  all              - 所有启用的节点
  all-enabled      - 所有启用的节点
  all-disabled     - 所有禁用的节点
  all-all          - 所有节点（包括禁用的）
  0,1,2            - 指定节点ID
  0-5              - 节点ID范围
  0,2-5,8          - 混合格式
  node-0,node-1    - 节点名称
  192.168.0.227    - IP地址

示例:
  --nodes all                    # 所有启用节点
  --nodes 0,1,2                  # 节点0,1,2
  --nodes 0-10                   # 节点0到10
  --nodes 0,5-10,15              # 节点0,5到10,15
  --nodes node-0,node-1          # 指定名称的节点
  --nodes 192.168.0.227,192.168.0.48  # 指定IP的节点
        """
    
    def validate_selection(self, selection: str) -> tuple[bool, str]:
        """验证选择字符串是否有效"""
        try:
            nodes = self.parse_selection(selection)
            if not nodes:
                return False, f"没有找到匹配的节点: {selection}"
            return True, f"找到 {len(nodes)} 个节点"
        except Exception as e:
            return False, f"选择格式错误: {str(e)}"
    
    def get_available_nodes_info(self) -> str:
        """获取可用节点信息"""
        enabled_nodes = [n for n in self.all_nodes if n.enabled]
        disabled_nodes = [n for n in self.all_nodes if not n.enabled]
        
        info = f"可用节点信息:\n"
        info += f"  总计: {len(self.all_nodes)} 个节点\n"
        info += f"  启用: {len(enabled_nodes)} 个节点\n"
        info += f"  禁用: {len(disabled_nodes)} 个节点\n\n"
        
        if enabled_nodes:
            info += "启用的节点:\n"
            for node in enabled_nodes[:10]:  # 只显示前10个
                info += f"  {node.id}: {node.name} ({node.ip})\n"
            if len(enabled_nodes) > 10:
                info += f"  ... 还有 {len(enabled_nodes) - 10} 个节点\n"
        
        return info
    
    def interactive_select(self) -> List[NodeConfig]:
        """交互式节点选择"""
        print(self.get_available_nodes_info())
        print(self.get_selection_help())
        
        while True:
            selection = input("\n请选择节点 [all]: ").strip() or "all"
            
            is_valid, message = self.validate_selection(selection)
            if is_valid:
                nodes = self.parse_selection(selection)
                print(f"✓ {message}")
                
                # 显示选择的节点
                if len(nodes) <= 10:
                    print("选择的节点:")
                    for node in nodes:
                        status = "启用" if node.enabled else "禁用"
                        print(f"  {node.id}: {node.name} ({node.ip}) - {status}")
                else:
                    print(f"选择的节点: {nodes[0].name}...等 {len(nodes)} 个节点")
                
                confirm = input("确认选择? (Y/n): ").strip().lower()
                if confirm in ['', 'y', 'yes']:
                    return nodes
            else:
                print(f"✗ {message}")


# 全局节点选择器实例
node_selector = NodeSelector() 