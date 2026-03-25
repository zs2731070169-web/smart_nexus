from agents import Runner, RunConfig, function_tool

from agent.node_agents import consult_agent, navigation_agent
from infra.logging.logger import log


@function_tool
async def route_consult_agent(query: str) -> str:
    """
    **售后咨询专家**：专门负责处理用户技术售后咨询
    比如：
        电脑开机后蓝屏怎么解决？
        MacBook M3 如何通过 Thunderbolt 外接独立显卡？

    :param str query: 用户的咨询问题，可能涉及电脑、电视、手机等电子设备的技术售后问题
    :return:
    """
    try:
        log.info(f"路由到售后咨询专家，处理用户问题: {query}")

        run_result = await Runner.run(
            starting_agent=consult_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True)
        )

        log.info(f"售后咨询专家运行完成，结果: {run_result.final_output}")
        return run_result.final_output
    except Exception as e:
        log.error(f"运行售后咨询专家过程中发生未预期的异常: {e}")
        return f"运行售后咨询专家过程中发生未预期的异常: {e}"


@function_tool
async def route_navigation_agent(query: str) -> str:
    """
    **售后服务站导航专家**：专门负责处理用户关于线下售后服务站点的导航问题
    比如：
        哪里有联想电脑售后？
        附近有vivo官方维修点吗？
        帮我找一下附近的小米之家旗舰店，我要换屏

    :param str query: 用户咨询的售后站点导航问题
    :return:
    """
    try:
        log.info(f"路由到售后服务站导航专家，处理用户问题: {query}")

        run_result = await Runner.run(
            starting_agent=navigation_agent,
            input=query,
            run_config=RunConfig(tracing_disabled=True)
        )

        log.info(f"售后服务站导航专家运行完成，结果: {run_result.final_output}")
        return run_result.final_output
    except Exception as e:
        log.error(f"运行售后服务站导航专家过程中发生未预期的异常: {e}")
        return f"运行售后服务站导航专家过程中发生未预期的异常: {e}"


AGENT_ROUTER = [
    route_consult_agent,
    route_navigation_agent,
]
