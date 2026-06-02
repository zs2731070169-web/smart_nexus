import json
from typing import Optional, Tuple

from pydantic import BaseModel, Field

from infra.logging.logger import log
from infra.tools.base import BaseTool, ToolResult
from infra.tools.mcp.baidu_map_mcp import baidu_map_mcp


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

        # 用户明确给出出发地址 → 优先按地点名称做 POI 检索（尊重用户明确意图）
        if address:
            # 按地点名称做 POI 检索，返回最匹配地点的真实坐标
            coord = await self._call_search(address)
            if coord is not None:
                lng, lat = coord
                log.info(f"按地点名称检索坐标成功，地址：{address}，经度：{lng}，纬度：{lat}")
                return self._ok(lng, lat)
            # 检索失败或无有效结果：若有前端定位则回退，否则进入询问分支
            log.info(f"地点检索失败或无结果，地址：{address}，{'尝试回退前端定位' if has_gps else '且无前端定位'}")

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

    @staticmethod
    async def _call_search(address: str) -> Optional[Tuple[float, float]]:
        """单次调用 map_search_places，取首条带坐标的结果。失败/无结果返回 None（不抛异常）。"""
        try:
            log.info(f"开始按地点名称检索坐标，地址：{address}")
            tool_result = await baidu_map_mcp.call_tool(
                tool_name="map_search_places",
                arguments={"query": address}
            )

            if tool_result.isError:
                log.warning(f"地点检索失败，地址：{address}，错误信息：{tool_result.error}")
                return None

            content = tool_result.content[0]
            text = getattr(content, 'text', None)
            if not text:
                log.warning(f"地点检索失败，地址：{address}，返回内容缺少text文本字段")
                return None

            result_dict = json.loads(text)
            if result_dict.get('status') != 0:
                log.warning(f"地点检索失败，地址：{address}，返回状态码非0：{result_dict.get('status')}")
                return None

            # results 已按相关性/距离排序，取首条带坐标的 POI 即为最佳匹配
            for poi in result_dict.get('results') or []:
                location = poi.get('location') or {}
                if 'lng' in location and 'lat' in location:
                    log.info(f"地点检索命中，地址：{address}，匹配POI：{poi.get('name')}，"f"经度：{location['lng']}，纬度：{location['lat']}")
                    return location['lng'], location['lat']

            log.warning(f"地点检索无有效结果，地址：{address}")
            return None
        except Exception as e:
            log.warning(f"地点检索异常，地址：{address}，错误信息：{str(e)}")
            return None


search_coordinate_source = SearchCoordinateSource()
