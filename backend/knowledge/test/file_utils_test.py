from utils.file_utils import FileUtils

filename = FileUtils.extract_filename(
    r"F:\projects\smart_nexus\backend\knowledge\data\crawl\0005_XP_Vista系统下如何清理系统盘.md"
)
print(filename)