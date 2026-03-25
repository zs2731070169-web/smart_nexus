import re

from bs4 import BeautifulSoup, Tag


class TextUtils:

    @staticmethod
    def clean_html(raw_html: str) -> str:
        """
        清洗HTML内容，去除JS、CSS、广告链接等
        :param raw_html: 原始HTML内容
        :return: 清洗后的文本内容
        """
        soup = BeautifulSoup(raw_html, 'html.parser')

        # 去除script和style标签
        for script in soup(["script", "style", "styles", "noscript"]):
            script.decompose()

        # 去除特定广告和无用元素,.mceNonEditable是富文本编辑器产生的功能性标记，这个类标签是预设的模板、插件或外部注入的广告，不允许编辑人员修改
        for tag in soup.select(".mceNonEditable"):
            tag.decompose()

        # 合并连续的同名标签，例如 <strong>a</strong><strong>b</strong><strong>c</strong> 合并为 <strong>abc</strong>
        for tag in soup.find_all(['strong', 'b']):
            if not tag.parent:
                continue
            # 持续合并所有连续的同名兄弟标签
            while True:
                next_tag = tag.next_sibling
                if next_tag and isinstance(next_tag, Tag) and tag.name == next_tag.name:
                    tag.extend(next_tag.contents)
                    next_tag.decompose()
                else:
                    break

        # 获取清洗后的html内容
        cleaned_text = str(soup)

        return cleaned_text

    @staticmethod
    def clean_filename(raw_text: str) -> str:
        """
        清洗文件名里的特殊字符和前后空格
        :param raw_text:
        :return:
        """
        cleaned = re.sub(r'[\\/*?:"<>|]', '_', raw_text)
        return cleaned.strip()