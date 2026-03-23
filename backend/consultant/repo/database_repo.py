import asyncio

from infra.db.database import get_cursor, write_cursor
from infra.logging.logger import log


class DatabaseRepo:

    async def query_list_by_lng_lat(self, lat: float, lng: float, limit: int) -> list:
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
            limit = max(1, min(int(limit), 3))  # 防止传入小数、过大的值、负数、0

            await asyncio.to_thread(cursor.execute, sql, (lat, lat, lng, limit))
            rows = await asyncio.to_thread(cursor.fetchall)

            log.info(f"查询最近维修站成功，共 {len(rows)} 条记录")

            return rows

    async def user_login(self, user_info: dict):
        async with write_cursor() as cursor:
            sql = """
                INSERT INTO user_login (id, username, phone, is_login, login_time)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    id = VALUES(id),
                    phone = VALUES(phone),
                    is_login = VALUES(is_login),
                    login_time = VALUES(login_time)
                  """
            await asyncio.to_thread(cursor.execute, sql, (
                user_info.get("id"),
                user_info.get("username"),
                user_info.get("phone"),
                user_info.get("is_login"),
                user_info.get("login_time"),
            ))
            log.info(f"保存/更新用户信息成功，用户ID: {user_info.get('id')}")

    async def query_login_status(self, phone: str) -> dict:
        """获取用户信息"""
        async with get_cursor() as cursor:
            sql = """
                SELECT id, is_login
                FROM user_login
                WHERE phone = %s
                LIMIT 1
            """

            await asyncio.to_thread(cursor.execute, sql, (phone,))
            row = await asyncio.to_thread(cursor.fetchone)
            return row

    async def user_logout(self, user_id):
        async with write_cursor() as cursor:
            sql = """
                UPDATE user_login 
                SET is_login = FALSE
                WHERE id = %s
            """
            await asyncio.to_thread(cursor.execute, sql, (user_id, ))
            log.info(f"用户注销成功，用户ID: {user_id}")

    async def query_login_time(self, user_id: str) -> dict:
        """获取用户信息"""
        async with get_cursor() as cursor:
            sql = """
                SELECT login_time
                FROM user_login
                WHERE id = %s AND is_login = True
                LIMIT 1
            """

            await asyncio.to_thread(cursor.execute, sql, (user_id,))
            row = await asyncio.to_thread(cursor.fetchone)
            return row

database_repo = DatabaseRepo()
