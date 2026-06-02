import json

from pydantic import BaseModel, Field

from infra.logging.logger import log
from infra.tools.base import BaseTool, ToolResult
from repo.database_repo import database_repo
from utils.map_utils import build_baidu_direction_url


class NavigationSitesArgs(BaseModel):
    lng: float = Field(description="起点经度")
    lat: float = Field(description="起点维度")
    limit: int = Field(default=3, description="查找的记录数")


class NavigationSites(BaseTool):
    name = "navigation_sites"
    description = "根据经纬度导航服务站地点"
    input_model = NavigationSitesArgs

    async def execute(self, arguments: NavigationSitesArgs) -> ToolResult:
        lng, lat, limit = arguments.lng, arguments.lat, arguments.limit
        try:
            log.info(f"开始查询最近维修站，起点经纬度：({lat}, {lng})，查询记录数：{limit})")

            if lat <= 0.0 or lng <= 0.0:
                log.warning(f"无效查询，起点经纬度：({lat}, {lng})，查询记录数：{limit})")
                return ToolResult(
                    output=json.dumps({
                        "status": "error",
                        "query": {"lng": lng, "lat": lat, "count": 0},
                        "error": "无效查询，不是有效经纬度"
                    }),
                    is_error=True,
                )

            rows = await database_repo.query_list_by_lng_lat(lat=lat, lng=lng, limit=limit)

            # 确定性生成完整导航链接，挂到每条记录上
            for row in rows:
                dest_lng = row.get("longitude")
                dest_lat = row.get("latitude")
                if dest_lng is not None and dest_lat is not None:
                    row["navigation_url"] = build_baidu_direction_url(
                        origin_lng=lng,
                        origin_lat=lat,
                        dest_lng=float(dest_lng),
                        dest_lat=float(dest_lat),
                        dest_name=row.get("service_station_name") or "目标服务站",
                        region=row.get("city") or "",
                    )

            return ToolResult(output=json.dumps({
                "status": "success",
                "query": {"lng": lng, "lat": lat, "count": len(rows)},
                "data": rows
            }, ensure_ascii=False, default=str))
        except Exception as e:
            log.error(f"查询最近维修站失败: {e}")
            return ToolResult(
                output=json.dumps({
                    "status": "error",
                    "query": {"lng": lng, "lat": lat, "count": 0},
                    "error": f"数据库查询失败：{str(e)}"
                }, ensure_ascii=False),
                is_error=True,
            )

navigation_sites = NavigationSites()
