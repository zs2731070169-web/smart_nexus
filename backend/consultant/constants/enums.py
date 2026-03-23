from enum import Enum


class RenderType(Enum):
    """
    内容语义分类，在前端分情况渲染：
    """
    THINKING = "THINKING"  # 渲染推理思考时内容
    PROCESSING = "PROCESSING"  # 渲染工具调用/过程处理内容
    ANSWER = "ANSWER"  # 渲染最终回答


class StreamStatus(Enum):
    """
    流式状态，控制SSE生命周期
    """
    PROCESSING = "PROCESSING"  # 正在流式输出
    FINISHED = "FINISHED"  # 流式输出结束


class FinishedReason(Enum):
    """
    agent结束原因，只有在finished时才有意义
    """
    NORMAL = "NORMAL"  # 正常结束
    MAX_TOKEN = "MAX_TOKEN"  # 达到最大token上限结束
    EXCEPTION = "EXCEPTION"  # 异常结束


TOOL_NAME_MAPPING = {
    # 搜索MCP工具
    "tavily_search": "联网搜索",

    # 百度地图MCP工具
    "map_geocode": "地址解析",
    "map_ip_location": "IP定位",
    "map_url": "生成导航链接",

    # 本地工具
    "retrieval_knowledge": "查询知识库",
    "search_coordinate_source": "位置解析",
    "navigation_sites": "查询附近服务站",

    # Agent Tools
    "route_consult_agent": "咨询技术专家",
    "route_navigation_agent": "服务站导航专家",
}

AGENT_NAME_MAPPING = {
    # Agent
    "coordination_agent": "协调Agent",
    "consult_agent": "咨询Agent",
    "navigation_agent": "导航Agent",
}
