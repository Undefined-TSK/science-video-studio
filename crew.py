"""
厨师团队（Crew）—— 当前阶段暂用一个厨师。
"""
from crewai import Crew
from agents.video_producer import video_producer
from tasks.main import create_video_task


def create_crew(topic: str, duration: int = 60, language: str = "Chinese") -> Crew:
    task = create_video_task(video_producer, topic, duration, language)
    return Crew(
        agents=[video_producer],
        tasks=[task],
        verbose=True,
    )
