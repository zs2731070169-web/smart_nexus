import requests

from infra.logging.logger import log


def get_public_net_ip():
    """获取公网IP（通过 HTTP API 查询多个服务，返回第一个成功的结果）"""
    services = [
        "https://myip.ipip.net",
        "https://ip.3322.net",
        "https://api.ipify.org"
    ]
    for url in services:
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            external_ip = resp.text.strip()
            log.info(f"公网IP: {external_ip} (来源: {url})")
            return external_ip
        except Exception:
            log.warning(f"IP查询服务不可用: {url}")
    log.error("所有公网IP查询服务均失败")
    return ""


if __name__ == '__main__':
    get_public_net_ip()
