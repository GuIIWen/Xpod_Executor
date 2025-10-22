"""
日志系统 - 统一的日志管理
"""
import os
import logging
import colorlog
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from tabulate import tabulate

from config.settings import config_manager
from core.task_executor import TaskResult


class LoggerManager:
    """日志管理器"""
    
    def __init__(self):
        self.console = Console()
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志配置"""
        logging_config = config_manager.get_logging_config()
        
        # 创建日志目录
        log_dir = os.path.dirname(logging_config.file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 配置根日志记录器
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, logging_config.level))
        
        # 清除已有的处理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 文件处理器
        file_handler = logging.FileHandler(
            logging_config.file, encoding='utf-8'
        )
        file_formatter = logging.Formatter(logging_config.format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # 控制台处理器（带颜色）
        console_handler = colorlog.StreamHandler()
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    def print_banner(self, title: str):
        """打印标题横幅"""
        self.console.print(f"\n[bold blue]{'='*60}[/bold blue]")
        self.console.print(f"[bold blue]{title:^60}[/bold blue]")
        self.console.print(f"[bold blue]{'='*60}[/bold blue]\n")
    
    def print_section(self, title: str):
        """打印章节标题"""
        self.console.print(f"\n[bold yellow]{title}[/bold yellow]")
        self.console.print("[dim]" + "-" * len(title) + "[/dim]")
    
    def print_node_list(self, nodes):
        """打印节点列表"""
        if not nodes:
            self.console.print("[red]没有找到节点[/red]")
            return
        
        table = Table(title="节点列表", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("名称", style="green", width=15)
        table.add_column("IP地址", style="blue", width=15)
        table.add_column("状态", style="white", width=8)
        
        for node in nodes:
            status = "[green]启用[/green]" if node.enabled else "[red]禁用[/red]"
            table.add_row(str(node.id), node.name, node.ip, status)
        
        self.console.print(table)
    
    def print_connection_status(self, results: dict):
        """打印连接状态"""
        table = Table(title="连接状态", show_header=True, header_style="bold magenta")
        table.add_column("节点ID", style="cyan", width=8)
        table.add_column("状态", style="white", width=10)
        
        for node_id, success in results.items():
            status = "[green]✓ 已连接[/green]" if success else "[red]✗ 连接失败[/red]"
            table.add_row(str(node_id), status)
        
        self.console.print(table)
    
    def print_task_results(self, results: list[TaskResult]):
        """打印任务执行结果"""
        if not results:
            self.console.print("[red]没有执行结果[/red]")
            return
        
        # 统计信息
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success
        
        self.print_section(f"执行结果汇总: {success}/{total} 成功")
        
        # 结果表格
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("节点", style="cyan", width=12)
        table.add_column("IP", style="blue", width=15)
        table.add_column("状态", style="white", width=8)
        table.add_column("退出码", style="yellow", width=8)
        table.add_column("执行时间", style="green", width=10)
        table.add_column("重试次数", style="dim", width=8)
        
        for result in results:
            if result.success:
                status = "[green]✓ 成功[/green]"
                exit_code = str(result.exit_code) if result.exit_code is not None else "N/A"
            else:
                status = "[red]✗ 失败[/red]"
                exit_code = str(result.exit_code) if result.exit_code is not None else "ERROR"
            
            exec_time = f"{result.execution_time:.2f}s"
            retry_count = str(result.retry_count)
            
            table.add_row(
                result.node_name,
                result.node_ip,
                status,
                exit_code,
                exec_time,
                retry_count
            )
        
        self.console.print(table)
        
        # 显示失败的详细信息
        failed_results = [r for r in results if not r.success]
        if failed_results:
            self.print_section("失败节点详情")
            for result in failed_results:
                self.console.print(f"[red]节点 {result.node_name} ({result.node_ip}):[/red]")
                if result.error_message:
                    self.console.print(f"  错误: {result.error_message}")
                if result.stderr:
                    self.console.print(f"  标准错误: {result.stderr[:200]}...")
                self.console.print()
    
    def print_success_outputs(self, results: list[TaskResult], max_length: int = 500):
        """打印成功执行的输出"""
        success_results = [r for r in results if r.success and r.stdout.strip()]
        
        if not success_results:
            self.console.print("[yellow]没有成功执行的输出[/yellow]")
            return
        
        self.print_section("执行输出")
        
        for result in success_results:
            self.console.print(f"[bold cyan]节点 {result.node_name} ({result.node_ip}):[/bold cyan]")
            output = result.stdout.strip()
            if len(output) > max_length:
                output = output[:max_length] + "..."
            self.console.print(f"[dim]{output}[/dim]")
            self.console.print()
    
    def create_progress(self, description: str = "执行中"):
        """创建进度条"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )
    
    def export_results_to_file(self, results: list[TaskResult], filename: str):
        """导出结果到文件"""
        try:
            # 准备数据
            data = []
            for result in results:
                data.append([
                    result.node_id,
                    result.node_name,
                    result.node_ip,
                    "成功" if result.success else "失败",
                    result.exit_code if result.exit_code is not None else "N/A",
                    f"{result.execution_time:.2f}s",
                    result.retry_count,
                    result.error_message if result.error_message else "",
                    result.stdout[:100] + "..." if len(result.stdout) > 100 else result.stdout
                ])
            
            # 表头
            headers = ["节点ID", "节点名", "IP地址", "状态", "退出码", "执行时间", "重试次数", "错误信息", "输出"]
            
            # 写入文件
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(tabulate(data, headers=headers, tablefmt='grid'))
            
            self.console.print(f"[green]结果已导出到: {filename}[/green]")
            
        except Exception as e:
            self.console.print(f"[red]导出失败: {str(e)}[/red]")
    
    def log_command_execution(self, command: str, node_ids: Optional[list] = None):
        """记录命令执行"""
        logger = logging.getLogger(__name__)
        
        if node_ids:
            logger.info(f"执行命令: {command} (节点: {node_ids})")
        else:
            logger.info(f"执行命令: {command} (所有节点)")
    
    def log_docker_operation(self, operation: str, target: str, node_ids: Optional[list] = None):
        """记录Docker操作"""
        logger = logging.getLogger(__name__)
        
        if node_ids:
            logger.info(f"Docker {operation}: {target} (节点: {node_ids})")
        else:
            logger.info(f"Docker {operation}: {target} (所有节点)")


# 全局日志管理器实例
logger_manager = LoggerManager() 