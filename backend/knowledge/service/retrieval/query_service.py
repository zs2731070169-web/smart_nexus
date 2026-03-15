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
                    你是一位经验丰富的高级电脑技术顾问，请严格根据以下资料回答用户问题，
                    **重要格式要求**
                    - 请直接保留和返回**完整的图片URL**（例如：https://example.com/image.png），每张图占一行。
                    - 图片URL不要使用 Markdown 语法（如 ![描述](链接)）。
                    - 对应图片URL紧随每个步骤描述的下方。
                    - 分析参考资料是否符合用户意图，过滤掉不符合用户意图的资料。
                    - 不要提及具体设备型号、品牌或软件版本（如“联想”、“UltraISO”等），除非问题明确要求。例如：将“联想手机设置”泛化为“手机设置”；将“打开联想电脑管家”泛化为“打开系统管理软件”或“相关设置工具”。
                    - 严禁回答资料中未提及的信息，如果当前问题和资料中的信息不相关或者没有参考资料，直接回复“资料中未提及相关信息”。
                    
                    资料：```
                    {context_text}
                    ```
            
                    回答格式：
                    - 结构清晰，语言风格应简洁、专业、直接，避免寒暄和废话。
                    - 如果是操作步骤，请使用有序列表（1. 2. 3.）。
                    - 在回答的最后，请列出参考文档的名称（例如：【资料:如何使用U盘安装Windows 7操作系统】）。
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

