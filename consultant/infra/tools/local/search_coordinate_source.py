import json

from pydantic import BaseModel, Field

from infra.logging.logger import log
from infra.tools.base import BaseTool, ToolResult
from infra.tools.mcp.mcp_client import baidu_map_mcp
from utils.ip_utils import get_public_net_ip
from utils.map_utils import coordinate_to_lng_lat


class SearchCoordinateSourceArgs(BaseModel):
    address: str = Field(description="地点名称")
    ip: str = Field(description="前端传递过来的用户ip")


class SearchCoordinateSource(BaseTool):
    name = "search_coordinate_source"
    description = "通过地点获取起点经纬度"
    input_model = SearchCoordinateSourceArgs

    async def execute(self, arguments: SearchCoordinateSourceArgs) -> ToolResult:
        address = arguments.address
        ip = arguments.ip
        try:
            log.info(f"开始查询坐标，用户输入地址：{address if address else '当前位置'}，用户输入ip：{ip if ip else ' '}")
            tool_result = await baidu_map_mcp.call_tool(
                tool_name="map_geocode",
                arguments={"address": address}
            )

            if tool_result.isError:
                log.warning(f"通过地点名称获取坐标失败，地址：{address}，错误信息：{tool_result.error}")
                raise ValueError(f"通过地点名称获取坐标失败，地址：{address}，错误信息：{tool_result.error}")

            content = tool_result.content[0]
            text = getattr(content, 'text', None)
            if not text:
                log.warning(f"通过地点名称获取坐标失败，地址：{address}，返回内容缺少text文本字段")
                raise ValueError("返回内容缺少text文本字段")

            result_dict = json.loads(text)
            if result_dict['status'] != 0:
                log.warning(f"通过地点名称获取坐标失败，地址：{address}，返回状态码非0，状态码：{result_dict['status']}")
                raise ValueError(f"返回状态码非0，状态码：{result_dict['status']}")

            result = result_dict['result']
            if not isinstance(result, dict) or not 'lng' in result['location'] or 'lat' not in result['location']:
                log.warning(f"通过地点名称获取坐标失败，地址：{address}，返回结果缺少经纬度字段")
                raise ValueError("返回结果缺少经纬度字段")

            lng, lat = result['location']['lng'], result['location']['lat']
            log.info(f"通过地点名称获取坐标成功，地址：{address}，经度：{lng}，纬度：{lat}")
            return ToolResult(output=json.dumps({
                "lng": float(lng),
                "lat": float(lat)
            }, ensure_ascii=False))
        except Exception as e:
            log.warning(f"获取坐标异常，地址：{address}，错误信息：{str(e)}，使用ip获取经纬度")

        try:
            if not ip or ip in ['127.0.0.1', '::1', 'localhost', '0.0.0.0']:
                ip = get_public_net_ip()
                log.info(f"使用工具自动获取公网IP: {ip}")
                if not ip:
                    raise ValueError("无法获取公网唯一IP")

            tool_result = await baidu_map_mcp.call_tool(
                tool_name="map_ip_location",
                arguments={"ip": ip}
            )

            if tool_result.isError:
                log.warning(f"通过ip获取坐标失败，ip：{ip}，错误信息：{tool_result.error}")
                raise ValueError(f"通过ip获取坐标失败，ip：{ip}，错误信息：{tool_result.error}")

            content = tool_result.content[0]
            text = getattr(content, 'text', None)
            if not text:
                log.warning(f"通过ip获取坐标失败，ip：{ip}，返回内容缺少text文本字段")
                raise ValueError("返回内容缺少text文本字段")

            result_dict = json.loads(text)
            if result_dict['status'] != 0:
                log.warning(f"通过ip获取坐标失败，ip：{ip}，返回状态码非0，状态码：{result_dict['status']}")
                raise ValueError(f"返回状态码非0，状态码：{result_dict['status']}")

            content = result_dict['content']
            if not isinstance(content, dict) or not 'point' in content:
                log.warning(f"通过ip获取坐标失败，ip：{ip}，返回结果缺少point字段")
                raise ValueError("返回结果缺少point字段")

            x = content['point']['x']
            y = content['point']['y']
            lng, lat = coordinate_to_lng_lat(float(x), float(y))
            log.info(f"通过ip获取坐标成功，ip：{ip}，经度：{lng}，纬度：{lat}")
            return ToolResult(output=json.dumps({
                "lng": float(lng),
                "lat": float(lat)
            }, ensure_ascii=False))
        except Exception as e:
            log.warning(f"通过ip获取坐标异常，错误信息：{str(e)}，使用默认经纬度")

        lng, lat = (116.4133836971231, 39.910924547299565)
        return ToolResult(output=json.dumps({
            "lng": lng,
            "lat": lat
        }, ensure_ascii=False))


search_coordinate_source = SearchCoordinateSource()
