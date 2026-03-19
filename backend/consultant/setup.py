from setuptools import setup, find_packages

setup(
    name='smart_nexus',
    version='0.0.1',
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "python-dotenv",
        "pydantic",
        "pydantic-settings",
        "openai",
        "openai-agent",
        "pymysql",
        "dbutils",
        "pystun3"
    ]
)
