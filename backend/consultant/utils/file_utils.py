from pathlib import Path

from config.settings import settings
from infra.logging.logger import log


def load_prompt(file_path: str) -> str:
    """
    指定文件路径，加载该目录下的指定文件
    :param filename:
    :param path:
    :return:
    """
    try:
        path = Path(file_path)
        if not path.exists():
            log.warning(f"文件路径不存在: {file_path}")
            return ""

        # 路径是否有效
        if not path.is_file():
            log.warning(f"不是有效路径: {file_path}，要求是一个文件路径")
            return ""

        # 分批次读取文件
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        log.error(f"文件操作错误: {str(e)}")
        raise
    except Exception as e:
        log.error(f"加载文件失败: {str(e)}")
        raise


if __name__ == '__main__':
    prompt_content = load_prompt(settings.PROMPTS_FILE_DIR + "/consult_agent.md")
    print(prompt_content)
