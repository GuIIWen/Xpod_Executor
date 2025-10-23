# 多节点批量管理系统

## 项目概述

这是一个用于批量管理多个节点的Python工程，支持：
- 批量SSH登录到多个节点
- 并发执行shell命令
- Docker镜像操作（构建、推送、拉取）
- 详细的日志记录和错误处理
- 灵活的配置管理

## 架构设计

```
多节点管理系统
├── 配置管理层
│   ├── 节点列表配置
│   ├── SSH认证配置
│   └── 任务配置
├── 连接管理层
│   ├── SSH连接池
│   ├── 连接状态监控
│   └── 重连机制
├── 任务执行层
│   ├── 并发任务调度
│   ├── 命令执行器
│   └── 镜像操作器
└── 监控日志层
    ├── 执行结果记录
    ├── 错误日志
    └── 性能监控
```

## 功能特性

- **并发执行**: 支持同时操作多个节点，提高效率
- **容错机制**: 自动重试和错误恢复
- **灵活配置**: 支持多种认证方式和执行策略
- **详细日志**: 完整的操作记录和状态跟踪
- **模块化设计**: 易于扩展和维护

## 快速开始

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置节点信息
```bash
cp config/nodes.example.yaml config/nodes.yaml
# 编辑节点配置
```

3. 执行批量命令
```bash
python main.py exec "docker ps" --nodes all
```

## 使用示例

### 批量执行命令
```bash
# 在所有节点执行命令
python main.py exec "uptime" --nodes all

# 在指定节点执行命令
python main.py exec "df -h" --nodes 0,1,2
```

### 批量执行脚本

```bash
# 运行exec命令，前置需要多机挂载同一块nfs硬盘
```python
python main.py exec "python /mnt/xxx/test.py" --nodes all

```bash
python main.py exec "bash /mnt/xxx/test.sh" --nodes all
