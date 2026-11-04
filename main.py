"""
餐厅营业逻辑（Flow）—— 只开门迎客，不参与后厨做菜。

用户点单 → Doctor 门禁 → 交给厨师团队（Crew）→ 厨师自主选材炒菜
"""
# 必须在所有 crewai / crewai_tools import 之前加载 .env
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import sys
from crew import create_crew
from doctor import DoctorFlow, DoctorError


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <topic> [duration] [language]")
        print("Example: python main.py 'how a gearbox works' 60 Chinese")
        sys.exit(1)

    topic = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    language = sys.argv[3] if len(sys.argv) > 3 else "Chinese"

    flow = DoctorFlow(
        on_ready=lambda _: create_crew(topic, duration, language).kickoff()
    )
    try:
        result = flow.kickoff()
    except DoctorError as error:
        print(error)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("视频制作完成")
    print("=" * 60)
    print(result.raw)


if __name__ == "__main__":
    main()

