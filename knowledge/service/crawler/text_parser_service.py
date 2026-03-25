import re

from markdownify import markdownify as md
from utils.text_utils import TextUtils


class Parser:

    def parser_to_md(self, content: dict, knowledge_no: str) -> str:
        """
        抽取原始内容，并转换为Markdown格式
        :param knowledge_no:
        :param content: HTML内容
        :return: Markdown格式的文本
        """
        if not content:
            raise ValueError("文本为空")

        topic = f"# 知识库条目:{knowledge_no}\n\n"
        title_value = (content.get('title') or '暂无标题').strip()
        title = f"## 标题\n\n{title_value}\n\n"
        summary_value = (content.get('digest') or '暂无摘要').strip()
        summary = f"## 问题摘要\n\n{summary_value}\n\n"

        markdown_context = topic + title + summary

        first_topic_name = (content.get('firstTopicName') or '').strip()
        sub_topic_name = (content.get('subTopicName') or '').strip()
        if first_topic_name:
            topic_type = f"## 分类\n\n主分类:{first_topic_name}"
            if sub_topic_name:
                topic_type += f"\n子分类:{sub_topic_name}"
            markdown_context += topic_type + "\n\n"

        keyWords = content.get('keywords') or []
        clean_keywords = []
        if keyWords:
            # 清洗keywords，去除多余空格
            for keyword in keyWords:
                cleaned_keyword = re.sub(r'\s+', ' ', keyword)
                clean_keywords.append(cleaned_keyword.strip())
            markdown_context += f"## 关键词\n\n{', '.join(clean_keywords)}\n\n"

        create_time = (content.get('createTime') or '').strip()
        version_no = (content.get('versionNo') or '').strip()
        if create_time:
            meta = f"## 元数据\n\n创建时间:{create_time}"
            markdown_context += meta
        if version_no:
            meta = f"|版本:{version_no}\n\n"
            markdown_context += meta

        html_content = (content.get('content') or '').strip()
        if html_content:
            clean_content = TextUtils.clean_html(html_content) # 清洗html内容, 去除js、css、广告链接
            markdown_context += md(clean_content) # 转为md

        # 在结尾添加重要语义信息，避免切片后文本段语义丢失
        markdown_context += f"\n\n<!-- 文档主题:{title_value} Knowledge No: {knowledge_no} -->"

        return markdown_context