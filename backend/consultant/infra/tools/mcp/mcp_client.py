import asyncio
import json
from typing import Any

from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

from config.settings import settings
from infra.logging.logger import log

"""
tavily联网搜索 MCP
"""
web_search_mcp = MCPServerStreamableHttp(
    name="tavily联网搜索",
    params=MCPServerStreamableHttpParams(
        url=f"{settings.TAVILY_BASE_URL}?tavilyApiKey={settings.TAVILY_API_KEY}",
        timeout=60,
        sse_read_timeout=60
    ),
    client_session_timeout_seconds=120,
    cache_tools_list=True
)

"""
百度地图 MCP
"""
baidu_map_mcp = MCPServerStreamableHttp(
    name="百度地图搜索",
    params=MCPServerStreamableHttpParams(
        url=f"{settings.BAIDUMAP_BASE_URL}?ak={settings.BAIDUMAP_AK}",
        timeout=60,
        sse_read_timeout=60
    ),
    client_session_timeout_seconds=120,
    cache_tools_list=True
)


async def call_mcp(mcp_instance: MCPServerStreamableHttp, mcp_name: str, params: dict[str, Any]):
    """
    调用 MCP 工具并返回结果文本。

    分阶段执行：连接 → 列工具 → 调用工具 → 解析结果，
    每个阶段独立捕获异常并附带上下文信息，便于定位失败原因。

    :param mcp_instance: MCP 服务实例
    :param mcp_name: 要调用的 MCP 工具名称
    :param params: 工具调用参数
    :return: 工具返回的文本结果
    :raises ConnectionError: 连接阶段失败
    :raises RuntimeError: 列工具 / 调用工具 / 解析结果阶段失败
    """
    connected = False
    try:
        # ── 阶段1：建立 MCP 连接 ──
        await mcp_instance.connect()
        connected = True
        log.info(f"成功连接 MCP")

        # ── 阶段2：遍历 MCP 工具列表 ──
        tools = await mcp_instance.list_tools()
        if tools:
            log.info(f"MCP工具列表 - 共 {len(tools)} 个工具")
            for tool in tools:
                log.info(f"MCP工具列表 - 函数名称: {tool.name}")
                log.info(f"MCP工具列表 - 参数: {json.dumps(tool.inputSchema, indent=2, ensure_ascii=False)}")
                log.info(f"MCP工具列表 - 输出结果: {tool.outputSchema}")
                log.info(f"MCP工具列表 - 描述: {tool.description}\n\n")
        else:
            log.warning(f"MCP 返回的工具列表为空")

        # ── 阶段3：调用 MCP 工具 ──
        result = await mcp_instance.call_tool(
            tool_name=mcp_name,
            arguments=params
        )
        log.info(f"成功调用 MCP 工具 {mcp_name}")

        # ── 阶段4：解析返回结果 ──
        if not result.content:
            log.warning(f"MCP 工具 {mcp_name} 返回内容为空")
            return ""

        for tool_result in result.content:
            if hasattr(tool_result, 'text'):
                try:
                    text = json.loads(tool_result.text) # 反序列化为字典
                except json.decoder.JSONDecodeError:
                    text = tool_result.text
                log.info(f"MCP 工具 返回结果：{json.dumps(text, ensure_ascii=False)}") # 序列化为json字符串

    except Exception as e:
        # 兜底：捕获未预料的异常，补充上下文后重新抛出
        log.error(f"MCP 发生未预期的异常: {e}")
        raise RuntimeError(
            f"MCP 工具调用过程中发生未预期的异常: {e}"
        ) from e
    finally:
        # 清理连接：仅记录异常，不覆盖主流程已抛出的异常
        if connected:
            try:
                await mcp_instance.cleanup()
                log.info(f"已断开 MCP 工具连接")
            except Exception as cleanup_err:
                log.error(f"断开 MCP 工具连接时发生错误: {cleanup_err}")


async def main(mcp_instance: MCPServerStreamableHttp, mcp_name: str = "", params: dict[str, Any] = ""):
    await call_mcp(mcp_instance, mcp_name, params)


if __name__ == '__main__':
    # asyncio.run(main(
    #     mcp_instance=web_search_mcp,
    #     mcp_name="tavily_search",
    #     params={
    #         "query": "阿里巴巴集团的创始人是谁？"
    #     })
    # )

    # asyncio.run(main(
    #     mcp_instance=baidu_map_mcp,
    #     mcp_name="map_geocode", # 通过地址获取经纬度
    #     params={
    #         "address": "北京"
    #     }
    # ))

    # asyncio.run(main(
    #     mcp_instance=baidu_map_mcp,
    #     mcp_name="map_ip_location", # 根据唯一ip（公网）获取MC坐标，公网使用 curl cip.cc 可查看
    #     params={
    #         "ip": "106.89.59.112"
    #     }
    # ))

    asyncio.run(main(
        mcp_instance=baidu_map_mcp,
        mcp_name="map_uri",
        params={
            "service": "direction"
        }
    ))
