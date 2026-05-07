from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agents import FunctionTool
from agents.mcp import MCPServer
from openai import BaseModel


@dataclass(frozen=True)
class ToolResult:
    """工具执行结果."""

    output: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """工具基类."""

    name: str
    description: str
    # type[BaseModel] 表示这是一个模型类本身，而非其实例。用于定义工具参数的 schema，可调用 model_json_schema() 生成 JSON schema
    input_model: type[BaseModel]

    @abstractmethod
    async def execute(self, arguments: BaseModel) -> ToolResult:
        """执行工具."""

    def invoke(self) -> FunctionTool:
        """适配为 agents 框架的 FunctionTool."""

        async def on_invoke(_ctx, args_json: str):
            arguments = self.input_model.model_validate_json(args_json or "{}")
            result = await self.execute(arguments)
            return result.output

        return FunctionTool(
            name=self.name,
            description=self.description,
            params_json_schema=self.input_model.model_json_schema(),
            on_invoke_tool=on_invoke,
        )


class ToolRegistry:
    """Map tool names to implementations."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._mcp_servers: list[MCPServer] = []

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def register_mcp(self, server: MCPServer) -> None:
        """注册 MCP server."""
        self._mcp_servers.append(server)

    def list_tools(self) -> list[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def function_tools(self) -> list[FunctionTool]:
        """返回全部已注册工具的 FunctionTool，用于直接挂到 Agent.tools."""
        return [tool.invoke() for tool in self._tools.values()]

    def mcp_servers(self) -> list[MCPServer]:
        """返回全部已注册 MCP server，用于直接挂到 Agent.mcp_servers."""
        return list(self._mcp_servers)


tool_registry = ToolRegistry()
