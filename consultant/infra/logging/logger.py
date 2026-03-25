import logging
import sys
from logging.handlers import TimedRotatingFileHandler # 文件处理器
from pathlib import Path

# 路径创建
BASE_DIR = Path(__file__).resolve().parent.parent.parent / "log"

# 确保文件夹存在，parents=True 表示递归创建，exist_ok=True 表示已存在时不报错
BASE_DIR.mkdir(parents=True, exist_ok=True)

# 定义格式
FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s:%(lineno)d - %(message)s"
CONSOLE_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


# 日志样式配置
class LoggerFormatter(logging.Formatter):
    grey = "\x1b[38;20m"  # 灰色
    green = "\x1b[32;20m"  # 绿色
    yellow = "\x1b[33;20m"  # 黄色
    red = "\x1b[31;20m"  # 红色
    bold_red = "\x1b[31;1m"  # 加粗红色
    reset = "\x1b[0m"  # 重置颜色（否则后面所有字都会变色）

    FORMAT = {
        logging.DEBUG: grey + CONSOLE_FORMAT + reset,
        logging.INFO: green + CONSOLE_FORMAT + reset,
        logging.WARNING: yellow + CONSOLE_FORMAT + reset,
        logging.ERROR: red + CONSOLE_FORMAT + reset,
        logging.CRITICAL: bold_red + CONSOLE_FORMAT + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        format = LoggerFormatter.FORMAT[record.levelno]
        return logging.Formatter(format, datefmt="%H:%M:%S").format(record)


# 初始化Logger实例
def get_logger(name: str = "smart_nexus_consultant") -> logging.Logger:
    logger = logging.getLogger(name)

    # logger.handlers 是一个列表，包含了所有已经添加到这个 logger 上的 handler。如果这个列表不为空，说明已经配置过了，就直接返回这个 logger 实例，避免重复配置导致日志重复输出的问题。
    if logger.handlers:
        return logger

    # 设置到最低级别，具体由handler自己决定日志等级
    logger.setLevel(logging.DEBUG)

    # 控制台输出
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(LoggerFormatter())
    logger.addHandler(stdout_handler)

    # info日志备份
    info_file_handler = TimedRotatingFileHandler(
        filename=str(BASE_DIR / f"{name}_info.log"),  # 日志存储路径
        when="midnight",  # 日志保存时间
        interval=1,  # 日志保存间隔
        encoding="utf-8",  # 日志字符集，防止中文乱码
        backupCount=7,  # 备份天数
    )
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    logger.addHandler(info_file_handler)

    # error日志备份
    error_file_handler = TimedRotatingFileHandler(
        filename=str(BASE_DIR / f"{name}_error.log"),
        when="midnight",
        interval=1,
        encoding="utf-8",
        backupCount=30,
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    logger.addHandler(error_file_handler)

    # debug日志备份
    debug_file_handler = TimedRotatingFileHandler(
        filename=str(BASE_DIR / f"{name}_debug.log"),
        when="midnight",
        interval=1,
        encoding="utf-8",
        backupCount=7,
    )
    debug_file_handler.setLevel(logging.DEBUG)
    debug_file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    logger.addHandler(debug_file_handler)

    return logger


log = get_logger()


if __name__ == '__main__':
    log.debug("这是一个debug日志")
    log.info("这是一个info日志")
    log.warning("这是一个warning日志")
    log.error("这是一个error日志")
    log.critical("这是一个critical日志")
