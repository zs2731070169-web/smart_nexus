# 地球赤道周长的一半（单位：米），也是 Web 墨卡托坐标系的 X/Y 最大值
import math
from typing import Tuple
from urllib.parse import quote

# 地球赤道周长的一半（单位：米），也是 Web 墨卡托坐标系的 X/Y 最大值
_HALF_CIRCUMFERENCE = 20037508.342789244

# ===== 坐标系转换常量（WGS84 → GCJ02 → BD09）=====
_X_PI = math.pi * 3000.0 / 180.0
_A = 6378245.0                       # 克拉索夫斯基椭球长半轴（GCJ02 偏移算法所用）
_EE = 0.00669342162296594323         # 椭球偏心率平方


def _out_of_china(lng: float, lat: float) -> bool:
    """是否在中国境外。境外坐标 GCJ02 与 WGS84 一致，无需偏移。"""
    return not (73.66 < lng < 135.05 and 3.86 < lat < 53.55)


def _transform_lat(lng: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * math.pi) + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320.0 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * math.pi) + 40.0 * math.sin(lng / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * math.pi) + 300.0 * math.sin(lng / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """WGS84（GPS 原始）→ GCJ02（火星坐标，国测局加密）"""
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrt_magic) * math.pi)
    dlng = (dlng * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * math.pi)
    return lng + dlng, lat + dlat


def gcj02_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """GCJ02（火星坐标）→ BD09（百度坐标）"""
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * _X_PI)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * _X_PI)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def wgs84_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """WGS84（浏览器 navigator.geolocation 原始坐标）→ BD09（百度系，DB/MCP 统一使用）"""
    g_lng, g_lat = wgs84_to_gcj02(lng, lat)
    return gcj02_to_bd09(g_lng, g_lat)


def build_baidu_direction_url(
        origin_lng: float,
        origin_lat: float,
        dest_lng: float,
        dest_lat: float,
        dest_name: str,
        region: str,
        origin_name: str = "当前位置",
        mode: str = "driving",
) -> str:
    """拼接百度地图 direction 导航链接

    :param origin_lng: 起点经度(BD09)
    :param origin_lat: 起点纬度(BD09)
    :param dest_lng: 终点经度(BD09)
    :param dest_lat: 终点纬度(BD09)
    :param dest_name: 终点名称（服务站名）
    :param region: 导航所在城市
    :param origin_name: 起点名称，默认“当前位置”
    :param mode: 导航模式，取值 driving / walking / riding / transit
    :return: 完整的百度 direction 链接
    """
    # name / region 可能含中文与特殊字符，统一处理特殊符号
    origin = f"latlng:{origin_lat},{origin_lng}|name:{quote(origin_name)}"
    destination = f"latlng:{dest_lat},{dest_lng}|name:{quote(dest_name)}"
    return (
        "https://api.map.baidu.com/direction"
        f"?origin={origin}"
        f"&destination={destination}"
        f"&mode={mode}"
        "&output=html"
        "&coord_type=bd09ll"
        "&src=webapp.baidu.openAPIdemo"
        f"&region={quote(region)}"
    )

