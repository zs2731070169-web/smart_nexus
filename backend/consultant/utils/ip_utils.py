import requests

from infra.logging.logger import log


def get_public_net_ip():
    """获取公网IP（通过 HTTP API，通常 100~300ms）"""
    try:
        resp = requests.get("https://api.ipify.org", timeout=5)
        resp.raise_for_status()
        external_ip = resp.text.strip()
        log.info(f"公网IP: {external_ip}")
        return external_ip
    except Exception as e:
        log.error("所有公网IP查询服务均失败")
        return ""


if __name__ == '__main__':
    get_public_net_ip()
