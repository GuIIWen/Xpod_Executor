#!/bin/bash
# 封装 cluster 命令，支持多种操作
# 请根据实际使用场景，增加需要的指令

case $1 in
    "ps")
        # 示例：cluster ps [节点范围] → 执行 docker ps
        nodes=${2:-all}  # 默认节点为 all
        python main.py exec "docker ps" --nodes $nodes --show-output
        ;;
    "pull")
        # 示例：cluster pull 镜像名 [节点范围]
        image=$2
        nodes=${3:-all}
        if [ -z "$image" ]; then
            echo "请指定镜像名，用法：cluster pull 镜像名 [节点范围]"
            exit 1
        fi
        python main.py pull $image --nodes $nodes
        ;;
    "run-script")
        # 示例：cluster run [节点范围] → 执行脚本
        nodes=${2:-all}
        python main.py run-script "./run_container.sh" --nodes $nodes --show-output
        ;;
    "exec")
        # 用法：cluster exec "命令内容" [节点范围]
        command=$2  # 第二个参数是要执行的命令（需用引号包裹）
        nodes=${3:-all}  # 第三个参数是节点范围，默认 all
        
        # 检查命令是否为空
        if [ -z "$command" ]; then
            echo "请指定要执行的命令，用法：cluster exec \"命令内容\" [节点范围]"
            echo "示例：cluster exec \"ls /tmp\" 0-5  # 在节点0-5执行 ls /tmp"
            exit 1
        fi
        # 执行命令
        python main.py exec "$command" --nodes $nodes --show-output
        ;;
    "nodes")
        # 查看节点列表
        python main.py nodes
        ;;
    *)
        echo "用法："
        echo "  cluster ps [节点范围]        → 在节点执行 docker ps"
        echo "  cluster pull 镜像名 [节点范围] → 拉取镜像"
        echo "  cluster run [节点范围]        → 执行 run_container.sh"
        echo "  cluster nodes                 → 查看节点列表"
        ;;
esac