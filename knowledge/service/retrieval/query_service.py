import logging

from langchain_classic.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config.settings import settings

# 日志打印
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryService:
    def __init__(self):
        self.llm = init_chat_model(
            model_provider="openai",
            model=settings.MODEL,
            base_url=settings.BASE_URL,
            api_key=settings.API_KEY,
            temperature=0,
        )

    def query(self, query: str, documents: list[Document]) -> str:
        """
        根据用户问题和返回个数进行知识库检索
        :param documents:
        :param query:
        :return:
        """

        logger.info(f"开始执行模型答复，用户问题：{query}, 参考资料：{len(documents)} 条")

        # 文档列表转为字符串
        context_text = "\n\n".join(f"【参考资料：{index + 1}】\n{doc.page_content}"
            for index, doc in enumerate(documents)
        ) if documents else ""

        # 构建提示词模板
        prompt_template = ChatPromptTemplate(messages=[
            (
                "system",
                """
                    身份设定：
                    你是一位经验丰富的高级电脑技术顾问，请严格基于提供的“参考资料”回答用户问题。
                    
                    重要格式要求(优先级最高)
                    - 请直接保留和返回完整的图片URL，图片必须以纯文本 URL 形式展示，独占一行，紧随对应步骤下方。
                    - 严禁使用 ![描述](URL) 格式，仅允许直接粘贴 URL。例如：
                      错误输出：![图1](https://example.com/1.png)
                      正确输出：https://example.com/1.png
                    - 内容过滤：仅保留与用户意图高度相关的资料，剔除无关干扰项。
                    - 品牌中立化：严禁出现任何具体品牌、设备型号或软件版本（如：联想、Lenovo、华硕、UltraISO、Win10等），除非用户明确要求。例如：
                      将“联想电脑管家”替换为“系统管理工具”；将“联想官方驱动”替换为“官方驱动程序”。
                    - 严格忠实资料：严禁回答资料中未提及的信息，如果当前问题和资料中的信息不相关或者没有参考资料，直接回复“资料中未提及相关信息”。
                    
                    参考资料：
                    ```
                    {context_text}
                    ```
            
                    回答格式：
                    - 语言风格：简洁、专业、直接，禁止寒暄。
                    - 结构：使用有序列表 (1. 2. 3.)。
                    - 结尾：必须注明参考文档名称，格式为【资料:文档标题】（例如：【资料:如何使用U盘安装Windows 7操作系统】）。
                """
            ),
            ("user", "用户问题：{question}")
        ])

        # 执行连构建
        chain = (prompt_template | self.llm | StrOutputParser())

        # 注入参考上下文，使用大模型生成回复
        llm_output = chain.invoke({
            "question": query,
            "context_text": context_text,
        })

        logger.info(f"模型答复完成，用户问题：{query}, 参考资料：{len(documents)} 条, 模型回复：{llm_output}")

        return llm_output

