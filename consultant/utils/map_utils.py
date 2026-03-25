# 地球赤道周长的一半（单位：米），也是 Web 墨卡托坐标系的 X/Y 最大值
import math
from typing import Tuple

# 地球赤道周长的一半（单位：米），也是 Web 墨卡托坐标系的 X/Y 最大值
_HALF_CIRCUMFERENCE = 20037508.342789244

def coordinate_to_lng_lat(x: float, y: float) -> Tuple[float, float]:
    """
    Web 墨卡托投影坐标 → WGS84 经纬度

    :param x: 墨卡托 X 坐标（米），对应经度方向
    :param y: 墨卡托 Y 坐标（米），对应纬度方向
    :return: (经度, 纬度)，单位为度
    """
    # 经度：线性映射，x 与经度成正比
    lng = x / _HALF_CIRCUMFERENCE * 180.0

    # 纬度：需要反双曲正切变换（墨卡托在纬度方向是非线性的）
    lat = y / _HALF_CIRCUMFERENCE * 180.0
    lat = 180.0 / math.pi * (2.0 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)

    return lng, lat

if __name__ == "__main__":
    # {"x": "11873215.19", "y": "3359067.87"}
    # "lng": 106.93667233768869, "lat": 28.96564056560186}
    lng, lat = coordinate_to_lng_lat(11873215.19, 3359067.87)
    print(f"墨卡托 ({11873215.19:.2f}, {3359067.87:.2f}) → 经纬度 ({lng}, {lat})")