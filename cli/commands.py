"""
CLI命令行界面
"""
import click
import os
from typing import List, Optional

from config.settings import config_manager
from core.node_manager import node_manager
from core.task_executor import task_executor
from core.script_executor import script_executor
from utils.logger import logger_manager
from cli.node_selector import node_selector


def parse_node_selection(ctx, param, value):
    """解析节点选择参数"""
    if not value:
        return None
    
    try:
        nodes = node_selector.parse_selection(value)
        return [node.id for node in nodes]
    except Exception as e:
        raise click.BadParameter(f'节点选择格式错误: {str(e)}\n{node_selector.get_selection_help()}')


@click.group()
@click.option('--config', '-c', default='config/nodes.yaml', 
              help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.pass_context
def cli(ctx, config, verbose):
    """多节点批量管理工具"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    ctx.obj['verbose'] = verbose
    
    # 设置配置文件路径
    if config != 'config/nodes.yaml':
        config_manager.config_path = config
    
    logger_manager.print_banner("多节点批量管理系统")


@cli.command()
@click.pass_context
def nodes(ctx):
    """显示节点列表"""
    try:
        nodes = config_manager.get_nodes(enabled_only=False)
        logger_manager.print_node_list(nodes)
        
        # 显示统计信息
        enabled_count = sum(1 for node in nodes if node.enabled)
        total_count = len(nodes)
        click.echo(f"\n总计: {total_count} 个节点，{enabled_count} 个启用")
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command()
@click.option('--nodes', '-n', callback=parse_node_selection, 
              help='目标节点 (支持: all, 0,1,2, 0-5, node-name, IP等)')
@click.option('--max-workers', '-w', type=int, 
              help='最大并发连接数')
@click.pass_context
def connect(ctx, nodes, max_workers):
    """连接到节点"""
    try:
        # 获取目标节点
        if nodes is None:
            target_nodes = config_manager.get_nodes()
        else:
            target_nodes = config_manager.get_nodes_by_ids(nodes)
        
        if not target_nodes:
            click.echo("没有找到目标节点", err=True)
            return
        
        logger_manager.print_section(f"连接到 {len(target_nodes)} 个节点")
        
        # 创建进度条
        with logger_manager.create_progress("连接中...") as progress:
            task = progress.add_task("连接节点", total=len(target_nodes))
            
            results = node_manager.connect_nodes(target_nodes, max_workers)
            progress.update(task, completed=len(target_nodes))
        
        # 显示结果
        logger_manager.print_connection_status(results)
        
        # 统计
        success_count = sum(1 for success in results.values() if success)
        click.echo(f"\n连接完成: {success_count}/{len(target_nodes)} 成功")
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command()
@click.argument('command')
@click.option('--nodes', '-n', callback=parse_node_selection,
              help='目标节点 (支持: all, 0,1,2, 0-5, node-name, IP等)')
@click.option('--timeout', '-t', type=int, default=300,
              help='命令超时时间(秒)')
@click.option('--output', '-o', type=click.Path(),
              help='导出结果到文件')
@click.option('--show-output', is_flag=True,
              help='显示命令输出')
@click.pass_context
def exec(ctx, command, nodes, timeout, output, show_output):
    """执行Shell命令"""
    try:
        logger_manager.print_section(f"执行命令: {command}")
        logger_manager.log_command_execution(command, nodes)
        
        # 执行命令
        with logger_manager.create_progress("执行中...") as progress:
            task = progress.add_task("执行命令", total=None)
            results = task_executor.execute_shell_command(
                command, node_ids=nodes, timeout=timeout
            )
            progress.update(task, completed=100)
        
        # 显示结果
        logger_manager.print_task_results(results)
        
        # 显示输出
        if show_output:
            logger_manager.print_success_outputs(results)
        
        # 导出结果
        if output:
            logger_manager.export_results_to_file(results, output)
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command(name='run-script')
@click.argument('script_path')
@click.option('--nodes', '-n', callback=parse_node_selection,
              help='目标节点 (支持: all, 0,1,2, 0-5, node-name, IP等)')
@click.option('--args', '-a', default='',
              help='脚本参数')
@click.option('--timeout', '-t', type=int, default=600,
              help='执行超时时间(秒)')
@click.option('--method', '-m', 
              type=click.Choice(['upload', 'inline', 'url'], case_sensitive=False),
              default='inline',
              help='执行方法: upload(上传文件), inline(内联执行), url(从URL下载)')
@click.option('--output', '-o', type=click.Path(),
              help='导出结果到文件')
@click.option('--show-output', is_flag=True,
              help='显示执行输出')
@click.pass_context
def run_script(ctx, script_path, nodes, args, timeout, method, output, show_output):
    """在远程节点执行Shell脚本"""
    try:
        logger_manager.print_section(f"执行脚本: {script_path}")
        
        # 根据方法选择执行方式
        if method == 'upload':
            # 上传文件并执行
            results = script_executor.upload_and_execute_script(
                script_path, node_ids=nodes, args=args, timeout=timeout
            )
        elif method == 'url':
            # 从URL下载并执行
            results = script_executor.execute_script_from_url(
                script_path, node_ids=nodes, args=args, timeout=timeout
            )
        else:  # inline
            # 内联执行（推荐）
            results = script_executor.execute_local_script_remotely(
                script_path, node_ids=nodes, args=args, timeout=timeout
            )
        
        # 显示结果
        logger_manager.print_task_results(results)
        
        # 显示输出
        if show_output:
            logger_manager.print_success_outputs(results)
        
        # 导出结果
        if output:
            logger_manager.export_results_to_file(results, output)
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command(name='run-script-content')
@click.argument('script_content')
@click.option('--nodes', '-n', callback=parse_node_selection,
              help='目标节点 (支持: all, 0,1,2, 0-5, node-name, IP等)')
@click.option('--args', '-a', default='',
              help='脚本参数')
@click.option('--timeout', '-t', type=int, default=600,
              help='执行超时时间(秒)')
@click.option('--output', '-o', type=click.Path(),
              help='导出结果到文件')
@click.option('--show-output', is_flag=True,
              help='显示执行输出')
@click.pass_context
def run_script_content(ctx, script_content, nodes, args, timeout, output, show_output):
    """直接执行脚本内容"""
    try:
        logger_manager.print_section("执行脚本内容")
        
        results = script_executor.execute_script_content(
            script_content, node_ids=nodes, args=args, timeout=timeout
        )
        
        # 显示结果
        logger_manager.print_task_results(results)
        
        # 显示输出
        if show_output:
            logger_manager.print_success_outputs(results)
        
        # 导出结果
        if output:
            logger_manager.export_results_to_file(results, output)
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command()
@click.argument('image')
@click.option('--nodes', '-n', callback=parse_node_selection,
              help='目标节点 (支持: all, 0,1,2, 0-5, node-name, IP等)')
@click.option('--timeout', '-t', type=int, default=600,
              help='拉取超时时间(秒)')
@click.option('--output', '-o', type=click.Path(),
              help='导出结果到文件')
@click.pass_context
def pull(ctx, image, nodes, timeout, output):
    """拉取Docker镜像"""
    try:
        logger_manager.print_section(f"拉取镜像: {image}")
        logger_manager.log_docker_operation("pull", image, nodes)
        
        # 拉取镜像
        with logger_manager.create_progress("拉取中...") as progress:
            task = progress.add_task("拉取镜像", total=None)
            results = task_executor.docker_pull(
                image, node_ids=nodes, timeout=timeout
            )
            progress.update(task, completed=100)
        
        # 显示结果
        logger_manager.print_task_results(results)
        
        # 导出结果
        if output:
            logger_manager.export_results_to_file(results, output)
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command()
@click.argument('dockerfile_path')
@click.argument('tag')
@click.option('--nodes', '-n', callback=parse_node_selection,
              help='目标节点 (支持: all, 0,1,2, 0-5, node-name, IP等)')
@click.option('--timeout', '-t', type=int, default=1800,
              help='构建超时时间(秒)')
@click.option('--output', '-o', type=click.Path(),
              help='导出结果到文件')
@click.pass_context
def build(ctx, dockerfile_path, tag, nodes, timeout, output):
    """构建Docker镜像"""
    try:
        logger_manager.print_section(f"构建镜像: {tag}")
        logger_manager.log_docker_operation("build", f"{dockerfile_path} -> {tag}", nodes)
        
        # 构建镜像
        with logger_manager.create_progress("构建中...") as progress:
            task = progress.add_task("构建镜像", total=None)
            results = task_executor.docker_build(
                dockerfile_path, tag, node_ids=nodes, timeout=timeout
            )
            progress.update(task, completed=100)
        
        # 显示结果
        logger_manager.print_task_results(results)
        
        # 导出结果
        if output:
            logger_manager.export_results_to_file(results, output)
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command()
@click.argument('image')
@click.option('--nodes', '-n', callback=parse_node_selection,
              help='目标节点 (支持: all, 0,1,2, 0-5, node-name, IP等)')
@click.option('--timeout', '-t', type=int, default=600,
              help='推送超时时间(秒)')
@click.option('--output', '-o', type=click.Path(),
              help='导出结果到文件')
@click.pass_context
def push(ctx, image, nodes, timeout, output):
    """推送Docker镜像"""
    try:
        logger_manager.print_section(f"推送镜像: {image}")
        logger_manager.log_docker_operation("push", image, nodes)
        
        # 推送镜像
        with logger_manager.create_progress("推送中...") as progress:
            task = progress.add_task("推送镜像", total=None)
            results = task_executor.docker_push(
                image, node_ids=nodes, timeout=timeout
            )
            progress.update(task, completed=100)
        
        # 显示结果
        logger_manager.print_task_results(results)
        
        # 导出结果
        if output:
            logger_manager.export_results_to_file(results, output)
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command()
@click.pass_context
def status(ctx):
    """检查节点连接状态"""
    try:
        logger_manager.print_section("检查连接状态")
        
        status_dict = node_manager.check_connections()
        if not status_dict:
            click.echo("当前没有活跃连接")
            return
        
        logger_manager.print_connection_status(status_dict)
        
        connected_count = sum(1 for connected in status_dict.values() if connected)
        total_count = len(status_dict)
        click.echo(f"\n状态: {connected_count}/{total_count} 连接正常")
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command()
@click.pass_context
def disconnect(ctx):
    """断开所有连接"""
    try:
        logger_manager.print_section("断开连接")
        
        node_manager.disconnect_all()
        click.echo("所有连接已断开")
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command()
@click.option('--node-id', type=int, required=True, help='节点ID')
@click.option('--enabled/--disabled', default=True, help='启用或禁用节点')
@click.pass_context
def toggle(ctx, node_id, enabled):
    """启用或禁用节点"""
    try:
        config_manager.update_node_status(node_id, enabled)
        status = "启用" if enabled else "禁用"
        click.echo(f"节点 {node_id} 已{status}")
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command()
@click.pass_context
def select(ctx):
    """交互式节点选择"""
    try:
        nodes = node_selector.interactive_select()
        
        if nodes:
            node_ids = [node.id for node in nodes]
            click.echo(f"\n已选择节点: {node_ids}")
            click.echo("你可以在后续命令中使用这些节点ID")
            click.echo(f"例如: python main.py exec 'hostname' --nodes {','.join(map(str, node_ids))}")
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


@cli.command(name='node-help')
@click.pass_context  
def node_help(ctx):
    """显示节点选择帮助"""
    try:
        click.echo(node_selector.get_available_nodes_info())
        click.echo(node_selector.get_selection_help())
        
    except Exception as e:
        click.echo(f"错误: {str(e)}", err=True)


if __name__ == '__main__':
    cli() 