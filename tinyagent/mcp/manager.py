"""
TinyAgent MCP Manager (Simplified)
管理MCP服务器连接和工具发现 - 遵循专家版本的简洁原则
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# Try to import MCP functionality
try:
    from agents.mcp import MCPServerStdio, MCPServerSse, MCPServerStreamableHttp
    MCP_AVAILABLE = True
except ImportError as e:
    logging.warning(f"MCP functionality not available: {e}")
    MCP_AVAILABLE = False

from ..core.config import MCPServerConfig

logger = logging.getLogger(__name__)

@dataclass
class ToolInfo:
    """简化的工具信息"""
    name: str
    description: str
    server_name: str
    schema: Dict[str, Any]

@dataclass
class ServerInfo:
    """简化的服务器信息"""
    name: str
    type: str
    status: str
    tools: List[ToolInfo]

class MCPManager:
    """
    简化的MCP管理器 - 专注核心功能
    
    遵循专家版本原则:
    - 单一职责: 只管理MCP连接和工具发现
    - 简单缓存: 内存缓存，避免复杂持久化
    - 透明错误: 错误直接抛出，不隐藏
    """
    
    def __init__(self, server_configs: List[MCPServerConfig]):
        """
        初始化MCP管理器
        
        Args:
            server_configs: MCP服务器配置列表
        """
        self.server_configs = server_configs
        self.servers: Dict[str, Any] = {}  # 服务器实例
        self.tools_cache: Dict[str, List[ToolInfo]] = {}  # 简单内存缓存
        self.logger = logging.getLogger(__name__)
        
        if not MCP_AVAILABLE:
            self.logger.warning("MCP功能不可用 - openai-agents MCP类未找到")
    
    async def initialize_servers(self) -> Dict[str, List[ToolInfo]]:
        """
        初始化服务器并发现工具
        
        Returns:
            Dict[server_name, tools]: 服务器名称到工具列表的映射
        """
        if not MCP_AVAILABLE:
            self.logger.error("无法初始化服务器 - MCP类不可用")
            return {}
        
        all_tools = {}
        
        for config in self.server_configs:
            if not config.enabled:
                self.logger.debug(f"跳过禁用的服务器: {config.name}")
                continue
            
            try:
                # 创建服务器连接
                server = await self._create_server(config)
                if server:
                    self.servers[config.name] = server
                    
                    # 发现工具
                    tools = await self._discover_tools(config.name, server)
                    if tools:
                        all_tools[config.name] = tools
                        self.tools_cache[config.name] = tools
                        self.logger.info(f"服务器 {config.name} 发现 {len(tools)} 个工具")
                    else:
                        self.logger.warning(f"服务器 {config.name} 未发现工具")
                
            except Exception as e:
                self.logger.error(f"初始化服务器 {config.name} 失败: {e}")
                # 透明错误处理 - 继续处理其他服务器
                continue
        
        self.logger.info(f"服务器初始化完成: {len(all_tools)} 个服务器可用")
        return all_tools
    
    async def _create_server(self, config: MCPServerConfig) -> Optional[Any]:
        """创建MCP服务器连接"""
        try:
            if config.type == "stdio":
                stdio_params = {
                    "command": config.command,
                    "args": config.args or [],
                    "env": config.env or {}
                }
                server = MCPServerStdio(name=config.name, params=stdio_params)
                await server.connect()
                return server
                
            elif config.type == "sse":
                sse_params = {
                    "url": config.url,
                    "headers": config.headers or {},
                    "timeout": config.timeout or 30.0,
                    "sse_read_timeout": config.sse_read_timeout or 120.0
                }
                server = MCPServerSse(name=config.name, params=sse_params)
                await server.connect()
                return server
                
            elif config.type == "http":
                http_params = {
                    "url": config.url,
                    "headers": config.headers or {},
                    "timeout": config.timeout or 30.0
                }
                server = MCPServerStreamableHttp(name=config.name, params=http_params)
                await server.connect()
                return server
            else:
                self.logger.error(f"不支持的服务器类型: {config.type}")
                return None
                
        except Exception as e:
            self.logger.error(f"创建服务器连接失败 {config.name}: {e}")
            raise
    
    async def _discover_tools(self, server_name: str, server: Any) -> List[ToolInfo]:
        """发现服务器工具"""
        try:
            # 调用MCP接口列出工具
            tools_response = await server.list_tools()
            
            # 🔧 DEBUG: 详细的响应格式调试
            self.logger.info(f"服务器 {server_name} 工具响应类型: {type(tools_response)}")
            self.logger.info(f"服务器 {server_name} 工具响应属性: {dir(tools_response)}")
            
            # 处理不同的响应格式
            tools_list = []
            if hasattr(tools_response, 'tools'):
                tools_list = tools_response.tools
                self.logger.info(f"服务器 {server_name} 使用 .tools 属性，工具数量: {len(tools_list)}")
            elif isinstance(tools_response, list):
                tools_list = tools_response
                self.logger.info(f"服务器 {server_name} 直接列表响应，工具数量: {len(tools_list)}")
            else:
                # 🔧 ENHANCED: 尝试更多响应格式
                if hasattr(tools_response, 'result') and hasattr(tools_response.result, 'tools'):
                    tools_list = tools_response.result.tools
                    self.logger.info(f"服务器 {server_name} 使用 .result.tools 属性，工具数量: {len(tools_list)}")
                elif hasattr(tools_response, 'content'):
                    # 可能是包装在content中的响应
                    content = tools_response.content
                    if isinstance(content, list):
                        tools_list = content
                        self.logger.info(f"服务器 {server_name} 使用 .content 列表，工具数量: {len(tools_list)}")
                    elif hasattr(content, 'tools'):
                        tools_list = content.tools
                        self.logger.info(f"服务器 {server_name} 使用 .content.tools，工具数量: {len(tools_list)}")
                    else:
                        self.logger.warning(f"服务器 {server_name} content格式未知: {type(content)}")
                        return []
                else:
                    self.logger.warning(f"服务器 {server_name} 工具响应格式未知: {type(tools_response)}")
                    # 🔧 DEBUG: 打印更多信息帮助调试
                    try:
                        self.logger.warning(f"响应内容: {str(tools_response)[:200]}...")
                    except:
                        self.logger.warning("无法打印响应内容")
                    return []
            
            # 转换为ToolInfo对象
            discovered_tools = []
            for tool in tools_list:
                try:
                    tool_info = ToolInfo(
                        name=tool.name,
                        description=getattr(tool, 'description', '') or "",
                        server_name=server_name,
                        schema=getattr(tool, 'inputSchema', {}) or {}
                    )
                    discovered_tools.append(tool_info)
                    self.logger.debug(f"发现工具: {tool.name} - {tool_info.description}")
                except Exception as tool_error:
                    self.logger.warning(f"处理工具 {getattr(tool, 'name', 'unknown')} 失败: {tool_error}")
                    continue
            
            self.logger.info(f"服务器 {server_name} 成功发现 {len(discovered_tools)} 个工具")
            return discovered_tools
            
        except Exception as e:
            self.logger.error(f"发现服务器 {server_name} 工具失败: {e}")
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            raise
    
    def get_all_tools(self) -> Dict[str, List[ToolInfo]]:
        """获取所有缓存的工具"""
        return self.tools_cache.copy()
    
    def get_tools_by_server(self, server_name: str) -> List[ToolInfo]:
        """获取指定服务器的工具"""
        return self.tools_cache.get(server_name, [])
    
    def get_tool_by_name(self, tool_name: str) -> Optional[ToolInfo]:
        """根据名称查找工具"""
        for tools in self.tools_cache.values():
            for tool in tools:
                if tool.name == tool_name:
                    return tool
        return None
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """调用指定工具"""
        # 查找工具所属服务器
        tool_info = self.get_tool_by_name(tool_name)
        if not tool_info:
            raise ValueError(f"工具未找到: {tool_name}")
        
        server = self.servers.get(tool_info.server_name)
        if not server:
            raise RuntimeError(f"服务器未连接: {tool_info.server_name}")
        
        try:
            # 调用工具
            result = await server.call_tool(tool_name, parameters)
            return result
        except Exception as e:
            self.logger.error(f"调用工具 {tool_name} 失败: {e}")
            raise
    
    def get_server_status(self) -> List[ServerInfo]:
        """获取所有服务器状态"""
        status_list = []
        
        for config in self.server_configs:
            if not config.enabled:
                continue
                
            tools = self.tools_cache.get(config.name, [])
            status = "connected" if config.name in self.servers else "disconnected"
            
            server_info = ServerInfo(
                name=config.name,
                type=config.type,
                status=status,
                tools=tools
            )
            status_list.append(server_info)
        
        return status_list
    
    async def shutdown(self):
        """关闭所有服务器连接"""
        for server_name, server in self.servers.items():
            try:
                # 🔧 FIX: MCP服务器使用不同的关闭方法
                if hasattr(server, '__aexit__'):
                    # 对于上下文管理器，使用 __aexit__
                    await server.__aexit__(None, None, None)
                elif hasattr(server, 'close'):
                    await server.close()
                elif hasattr(server, 'shutdown'):
                    await server.shutdown()
                elif hasattr(server, 'disconnect'):
                    await server.disconnect()
                else:
                    # 如果没有明确的关闭方法，尝试删除引用
                    self.logger.debug(f"服务器 {server_name} 没有明确的关闭方法，删除引用")
                self.logger.debug(f"服务器 {server_name} 已关闭")
            except Exception as e:
                self.logger.warning(f"关闭服务器 {server_name} 时出错: {e}")
        
        self.servers.clear()
        self.tools_cache.clear()
        self.logger.info("所有MCP服务器已关闭")


# 全局管理器实例
_global_mcp_manager: Optional[MCPManager] = None

def get_mcp_manager(config=None) -> MCPManager:
    """获取全局MCP管理器实例"""
    global _global_mcp_manager
    
    if _global_mcp_manager is None:
        if config and hasattr(config, 'mcp') and hasattr(config.mcp, 'servers'):
            server_configs = []
            for server_name in config.mcp.enabled_servers:
                if server_name in config.mcp.servers:
                    server_config = config.mcp.servers[server_name]
                    server_configs.append(server_config)
            _global_mcp_manager = MCPManager(server_configs)
        else:
            _global_mcp_manager = MCPManager([])
    
    return _global_mcp_manager

async def shutdown_mcp_manager():
    """关闭全局MCP管理器"""
    global _global_mcp_manager
    if _global_mcp_manager:
        await _global_mcp_manager.shutdown()
        _global_mcp_manager = None 