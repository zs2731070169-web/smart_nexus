import random
import re
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from config.settings import settings
from infra.logging.logger import log
from repo.cache_repo import redis_operation
from repo.database_repo import database_repo
from utils.time_utils import get_expire_datetime, delay_time, datetime_format


class LoginService:

    async def get_code(self, user_phone: str) -> str:
        """
        获取验证码
        :param user_phone:
        :return:
        """
        user_phone = user_phone.strip()

        # 手机号码校验
        self._valide_phone(user_phone)

        key = f"phone_code:{user_phone}"

        # 如果缓存有这个phone则不能再次获取
        if await redis_operation.exists_key(key):
            log.warning(f"获取验证码失败，手机号 {user_phone} 已经获取过验证码，请勿重复获取")
            raise Exception(f"获取验证码失败，手机号 {user_phone} 已经获取过验证码，请勿重复获取")

        # 模拟发短信
        log.info(f"获取验证码接口被调用，模拟向手机号 {user_phone} 发送验证码...")
        code = str(random.randint(100000, 999999))
        log.info(f"验证码 {code} 已发送到手机号 {user_phone}，请注意查收！")

        # 验证码存入缓存，有效期60秒
        expires = delay_time(seconds=60)
        ttl = get_expire_datetime(expires)
        if not await redis_operation.save_with_ex(key, code, ttl):
            log.warning(f"验证码 {code} 存入缓存失败，手机号 {user_phone} 无法获取验证码，请稍后再试...")
            raise Exception("无法获取验证码，请稍后再试...")

        log.info(f"验证码 {code} 已存入缓存，60秒内有效，过期时间: {datetime_format(expires)}")

        return code

    async def user_login(self, user_phone: str, user_code: str) -> str:
        """
        用户登录
        :param user_phone:
        :param user_code:
        :return:
        """
        user_phone = user_phone.strip()

        # 电话号码验证
        self._valide_phone(user_phone)

        # 获取已存在用户id
        login_status = await database_repo.query_login_status(user_phone)

        # 校验是否已经登陆过
        if login_status and login_status.get('is_login') == '1': raise Exception("用户已登录，请勿重复登录")

        # 用户验证码非空校验
        if user_code is None or not user_code.strip(): raise Exception("登录失败，验证码不能为空")

        phone_code_key = f"phone_code:{user_phone}"

        # 验证码有效性校验（match_code 为 None 表示 Redis 中已无该 key，即验证码过期或未获取）
        match_code = await redis_operation.get_value(phone_code_key)
        if not match_code: raise Exception("登录失败，验证码已过期，请重新获取")

        # 校验验证码是否正确
        if match_code != user_code: raise Exception("登录失败，验证码不正确，请重新输入")

        # 删除验证码
        await redis_operation.delete_value(phone_code_key)

        # 生成或获取用户ID
        user_id = login_status.get('id') if login_status else None
        new_user_id = user_id if user_id else uuid.uuid4().hex

        # 更新/添加登录状态
        await database_repo.user_login({
            "id": new_user_id,
            "phone": user_phone,
            "username": f"user_{new_user_id[:8]}",
            "is_login": True,
            "login_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        })

        log.info(f"用户登录成功，手机号: {user_phone}，用户ID: {new_user_id}")

        # 使用user_id生成auth_token
        return self._generate_auth_token(new_user_id)

    def _valide_phone(self, user_phone: str) -> bool:
        """
        验证手机号码
        :param user_phone:
        :return:
        """
        if user_phone is None or not user_phone:
            log.error("登录失败，手机号无效")
            raise Exception("登录失败，手机号无效")

        pattern = r'^(?:\+86|0086)?1[3-9]\d{9}$'
        if not re.match(pattern, user_phone):
            log.warning("获取验证码失败，手机号格式不符合 +86 标准")
            raise Exception("获取验证码失败，手机号格式不符合 +86 标准")

        return True

    def _generate_auth_token(self, user_id: str) -> str:
        """
        基于user_id生成auth_token
        :param user_id:
        :return:
        """
        china_tz = timezone(timedelta(hours=8))
        payload = {
            "user_id": user_id,
            "exp": datetime.now(china_tz) + timedelta(hours=settings.TOKEN_EXPIRE_HOURS),
            "iat": datetime.now(china_tz),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async def user_logout(self, user_id: str):
        """
        用户注销登录
        :param user_id:
        :return:
        """
        await database_repo.user_logout(user_id)
        log.info(f"用户注销登录成功，用户ID: {user_id}")


login_service = LoginService()
