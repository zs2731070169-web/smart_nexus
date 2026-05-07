from agent.agent_router import agent_router_registry
from agent.node_agents import consult_agent, navigation_agent
from infra.logging.logger import log

agent_router_registry.register(
    consult_agent,
    description=(
        "**售后咨询专家**：专门负责处理用户技术售后咨询\n"
        "比如：\n"
        "    电脑开机后蓝屏怎么解决？\n"
        "    MacBook M3 如何通过 Thunderbolt 外接独立显卡？"
    ),
)
agent_router_registry.register(
    navigation_agent,
    description=(
        "**售后服务站导航专家**：专门负责处理用户关于线下售后服务站点的导航问题\n"
        "比如：\n"
        "    哪里有联想电脑售后？\n"
        "    附近有vivo官方维修点吗？\n"
        "    帮我找一下附近的小米之家旗舰店，我要换屏"
    ),
)
log.info("子 agent 路由注册完毕")
