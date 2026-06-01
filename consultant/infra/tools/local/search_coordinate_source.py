import json
from typing import Optional, Tuple

from pydantic import BaseModel, Field

from infra.logging.logger import log
from infra.tools.base import BaseTool, ToolResult
from infra.tools.mcp.baidu_map_mcp import baidu_map_mcp

# 地址解析精度阈值, 低于此值时视为无效地址
_MIN_CONFIDENCE = 60


class SearchCoordinateSourceArgs(BaseModel):
    address: str = Field(default="", description="用户明确说出的出发地点名称；用户提到出发地就传入")
    lng: Optional[float] = Field(default=None, description="前端定位经度(BD09)；上下文给出用户经纬度就传入")
    lat: Optional[float] = Field(default=None, description="前端定位纬度(BD09)；上下文给出用户经纬度就传入")


class SearchCoordinateSource(BaseTool):
    name = "search_coordinate_source"
    description = "获取导航起点经纬度：优先按用户给出的地点名称反查，失败则回退前端定位坐标"
    input_model = SearchCoordinateSourceArgs

    async def execute(self, arguments: SearchCoordinateSourceArgs) -> ToolResult:
        address = arguments.address
        has_gps = arguments.lng is not None and arguments.lat is not None

        # 用户明确给出地址 → 优先按地址反查（尊重用户明确意图）
        if address:
            coord = await self._geocode(address)
            if coord is not None:
                lng, lat = coord
                log.info(f"按地点名称获取坐标成功，地址：{address}，经度：{lng}，纬度：{lat}")
                return self._ok(lng, lat)
            # 地址解析失败或精度过低：若有前端定位则回退，否则进入询问分支
            log.info(f"地址解析失败或精度过低，地址：{address}，{'尝试回退前端定位' if has_gps else '且无前端定位'}")

        # 前端 GPS 定位兜底（已统一为 BD09，直接采用）
        if has_gps:
            log.info(f"使用前端传入定位坐标(BD09)，经度：{arguments.lng}，纬度：{arguments.lat}")
            return self._ok(float(arguments.lng), float(arguments.lat))

        # 既无可用地址、也无前端定位：返回错误信号，由 agent 向用户询问出发地，避免静默给出错误起点
        log.warning(f"无法确定起点位置，地址：{address or '（空）'}，前端定位：无")
        return ToolResult(
            output=json.dumps({
                "status": "error",
                "error": "无法确定起点位置：地址无法解析为有效地点，也没有定位坐标，请向用户询问其具体出发地点"
            }, ensure_ascii=False),
            is_error=True,
        )

    @staticmethod
    def _ok(lng: float, lat: float) -> ToolResult:
        return ToolResult(output=json.dumps({"lng": lng, "lat": lat}, ensure_ascii=False))

    async def _geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """按地点名称反查坐标。失败或精度过低时返回 None（不抛异常），以便上层回退到前端定位。"""
        try:
            log.info(f"开始按地点名称查询坐标，地址：{address}")
            tool_result = await baidu_map_mcp.call_tool(
                tool_name="map_geocode",
                arguments={"address": address}
            )

            if tool_result.isError:
                log.warning(f"通过地点名称获取坐标失败，地址：{address}，错误信息：{tool_result.error}")
                return None

            content = tool_result.content[0]
            text = getattr(content, 'text', None)
            if not text:
                log.warning(f"通过地点名称获取坐标失败，地址：{address}，返回内容缺少text文本字段")
                return None

            result_dict = json.loads(text)
            if result_dict.get('status') != 0:
                log.warning(f"通过地点名称获取坐标失败，地址：{address}，返回状态码非0：{result_dict.get('status')}")
                return None

            result = result_dict.get('result') or {}
            location = result.get('location') or {}
            if 'lng' not in location or 'lat' not in location:
                log.warning(f"通过地点名称获取坐标失败，地址：{address}，返回结果缺少经纬度字段")
                return None

            # 防御式精度校验：仅当百度返回了 precise/confidence 字段时才判断，避免模糊地址被作为错误起点
            precise = result.get('precise')
            confidence = result.get('confidence')
            if precise == 0 and isinstance(confidence, (int, float)) and confidence < _MIN_CONFIDENCE:
                log.warning(f"地址解析精度过低，地址：{address}，precise={precise}，confidence={confidence}，视为无效")
                return None

            return location['lng'], location['lat']
        except Exception as e:
            log.warning(f"按地点名称获取坐标异常，地址：{address}，错误信息：{str(e)}")
            return None


search_coordinate_source = SearchCoordinateSource()
