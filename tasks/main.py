"""
用户点单（Task）—— 只写"做什么菜"，不写"怎么做"。

厨师（Agent）自主决定用什么食材、什么顺序、怎么处理。
"""
from crewai import Task


def create_video_task(agent, topic: str, duration: int, language: str) -> Task:
    """创建视频制作任务（只描述目标，不规定步骤）"""
    return Task(
        description=(
            f"Create a {duration}-second {language}-language explainer video about '{topic}'. "
            f"The video should mix 2D and 3D visuals. Use the official ingredients available "
            f"to you — decide your own approach, tool order, and workflow. Produce a final "
            f"video file and return its path."
        ),
        expected_output="The file path of the final produced video.",
        agent=agent,
    )
