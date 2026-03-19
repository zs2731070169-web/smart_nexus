import asyncio
import json

from agents import function_tool

from infra.db.database import get_cursor
from infra.logging.logger import log
from infra.tools.mcp.mcp_client import baidu_map_mcp
from utils.ip_utils import get_public_net_ip
from utils.map_utils import coordinate_to_lng_lat


@function_tool
async def search_coordinate_source(address: str, ip: str) -> str:
    """
    通过地点获取起点经纬度
    :param str ip: 前端传递过来的用户公网ip
    :param str address: 地点名称
    :return: 查询结果 JSON 字符串
    :rtype: str
    """
    try:
        log.info(f"开始查询坐标，用户输入地址：{address if address else '当前位置'}，用户输入ip：{ip if ip else ' '}")
        # 先使用地点名称获取坐标
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

        result_dict = json.loads(text)  # 反序列化为字典
        if result_dict['status'] != 0:
            log.warning(f"通过地点名称获取坐标失败，地址：{address}，返回状态码非0，状态码：{result_dict['status']}")
            raise ValueError(f"返回状态码非0，状态码：{result_dict['status']}")

        result = result_dict['result']
        if not isinstance(result, dict) or not 'lng' in result['location'] or 'lat' not in result['location']:
            log.warning(f"通过地点名称获取坐标失败，地址：{address}，返回结果缺少经纬度字段")
            raise ValueError("返回结果缺少经纬度字段")

        lng, lat = result['location']['lng'], result['location']['lat']
        log.info(f"通过地点名称获取坐标成功，地址：{address}，经度：{lng}，纬度：{lat}")
        return json.dumps({
            "lng": float(lng),
            "lat": float(lat)
        }, ensure_ascii=False)
    except Exception as e:
        log.warning(f"获取坐标异常，地址：{address}，错误信息：{str(e)}，使用ip获取经纬度")

    # 无法通过地名获取经纬度，再使用ip源获取坐标
    try:
        # 获取公网唯一ip
        if not ip:
            ip = get_public_net_ip()
            log.info(f"使用工具自动获取公网IP: {ip}")
            if not ip and ip in ['127.0.0.1', '::1', 'localhost', '0.0.0.0']:
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

        result_dict = json.loads(text)  # 反序列化为字典
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
        return json.dumps({
            "lng": float(lng),
            "lat": float(lat)
        }, ensure_ascii=False)
    except Exception as e:
        log.warning(f"通过ip获取坐标异常，错误信息：{str(e)}，使用默认经纬度")

    # 使用默认地点(北京)经纬度兜底
    lng, lat = (116.4133836971231, 39.910924547299565)
    return json.dumps({
        "lng": lng,
        "lat": lat
    }, ensure_ascii=False)


@function_tool
async def navigation_sites(lng: float, lat: float, limit: int = 3) -> str:
    """
    根据经纬度导航服务站地点

    :param float lng: 起点经度
    :param float lat: 起点维度
    :param int limit: 查找的记录数
    :return: 查询结果 JSON 字符串
    :rtype: str
    """
    try:
        log.info(f"开始查询最近维修站，起点经纬度：({lat}, {lng})，查询记录数：{limit})")

        if lat <= 0.0 or lng <= 0.0:
            log.warning(f"无效查询，起点经纬度：({lat}, {lng})，查询记录数：{limit})")
            return json.dumps({
                "status": "error",
                "query": {
                    "lng": lng,
                    "lat": lat,
                    "count": 0
                },
                "error": "无效查询，不是有效经纬度"
            })

        sql = """
              SELECT id,
                     service_station_name,
                     province,
                     city,
                     district,
                     address,
                     phone,
                     manager,
                     manager_phone,
                     opening_hours,
                     repair_types,
                     repair_specialties,
                     repair_services,
                     rating,
                     service_station_description,
                     latitude,
                     longitude,
                     supported_brands,
                     ROUND(6371 * 2 * ASIN(SQRT(
                             POWER(SIN((latitude - %s) * PI() / 180 / 2), 2)
                                 + COS(%s * PI() / 180) * COS(latitude * PI() / 180)
                                 * POWER(SIN((longitude - %s) * PI() / 180 / 2), 2)
                             )),
                           2
                     ) AS distance
              FROM repair_shops
              WHERE longitude IS NOT NULL
                AND latitude IS NOT NULL
                AND ABS(latitude) <= 90
                AND ABS(longitude) <= 180
              ORDER BY distance ASC 
              LIMIT %s
              """

        async with get_cursor() as cursor:
            limit = max(1, min(int(limit), 3)) # 防止传入小数、过大的值、负数、0

            await asyncio.to_thread(cursor.execute, sql, (lat, lat, lng, limit))
            rows = await asyncio.to_thread(cursor.fetchall)
            log.info(f"查询最近维修站成功，共 {len(rows)} 条记录")

            return json.dumps({
                "status": "success",
                "query": {
                    "lng": lng,
                    "lat": lat,
                    "count": len(rows)
                },
                "data": rows
            }, ensure_ascii=False, default=str)
    except Exception as e:
        log.error(f"查询最近维修站失败: {e}")
        return json.dumps({
            "status": "error",
            "query": {
                "lng": lng,
                "lat": lat,
                "count": 0
            },
            "error": f"数据库查询失败：{str(e)}"
        }, ensure_ascii=False)
