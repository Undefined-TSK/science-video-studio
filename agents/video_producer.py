"""
厨师（Agent）—— 走进食材超市，自主选材炒菜。

所有货架摆满：
  tools=  → 眼前货架 A：厨具（E2B 三件套 + 文件工具）
  mcps=   → 眼前货架 B：远程能力窗口（ElevenLabs-TTS）
  skills= → 方法论货架（Remotion / HyperFrames / CrewAI 官方 SKILL）
  knowledge_sources= → 导购广播（6 家官方文档原文）
  memory= → 回头客记忆
  planning_config= → 厨师自己写菜单

没有菜谱（没有固定步骤、没有 @tool 包装、没有 Flow 写死逻辑）。
厨师根据点单（Task）自主决定用什么食材、什么顺序、怎么处理。
"""
import os
from pathlib import Path
from crewai import Agent
from crewai.mcp import MCPServerHTTP
from crewai.agent.planning_config import PlanningConfig
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource
from crewai_tools import (
    FileReadTool,
    FileWriterTool,
    E2BExecTool,
    E2BPythonTool,
    E2BFileTool,
)

# 项目根目录（agents/video_producer.py → 上两级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ═══════════════════════════════════════════════════════════════
# 导购广播：6 家官方文档原文（执行时自动 RAG 推送）
#
# 注意：必须传 Path 对象，不能传 str。
# 因为 TextFileKnowledgeSource.convert_to_path 会给 str 路径强行
# 前置 "knowledge/" 目录，而 Path 对象原样保留。
# ═══════════════════════════════════════════════════════════════
DOCS = PROJECT_ROOT / "docs"

knowledge_sources = [
    # CrewAI 官方文档
    TextFileKnowledgeSource(
        file_paths=[DOCS / "crewai" / "llms.txt", DOCS / "crewai" / "llms-full.txt"],
        collection_name="crewai",
    ),
    # Remotion 官方文档
    TextFileKnowledgeSource(
        file_paths=[DOCS / "remotion" / "llms.txt"],
        collection_name="remotion",
    ),
    # three.js 官方文档
    TextFileKnowledgeSource(
        file_paths=[DOCS / "three" / "llms.txt", DOCS / "three" / "llms-full.txt"],
        collection_name="three",
    ),
    # Blender glTF 导出文档
    TextFileKnowledgeSource(
        file_paths=[DOCS / "blender" / "gltf-export.html"],
        collection_name="blender",
    ),
    # ElevenLabs 官方文档
    TextFileKnowledgeSource(
        file_paths=[
            DOCS / "elevenlabs" / "llms-full.txt",
            DOCS / "elevenlabs" / "hosted-mcp.md",
            DOCS / "elevenlabs" / "tts-best-practices.md",
            DOCS / "elevenlabs" / "music-best-practices.md",
        ],
        collection_name="elevenlabs",
    ),
    # 阿里云百炼模型文档
    TextFileKnowledgeSource(
        file_paths=[
            DOCS / "bailian" / "qwen3-tts-flash.html",
            DOCS / "bailian" / "qwen-audio-3-1-tts-flash.html",
            DOCS / "bailian" / "qwen-audio-3-1-tts-plus.html",
            DOCS / "bailian" / "qwen-audio-3-1-tts-next.html",
            DOCS / "bailian" / "fun-music-api.html",
        ],
        collection_name="bailian",
    ),
]

# ═══════════════════════════════════════════════════════════════
# 厨师（Agent）
# ═══════════════════════════════════════════════════════════════
video_producer = Agent(
    # ── 门口招牌 + 告示牌 ──
    role="2D+3D Video Producer",
    goal="Produce mixed 2D+3D explainer videos",
    backstory=(
        "You are a senior video producer who creates mixed 2D+3D explainer videos. "
        "Your kitchen is stocked with official ingredients — choose freely what to use, "
        "in what order, and how to process each one.\n\n"
        "Available official capabilities:\n"
        "- 2D+3D rendering: Remotion (React + @remotion/three), HyperFrames (HTML+GSAP)\n"
        "- 3D assets: procedural geometry inside Remotion/three.js; Blender supplies the official "
        "glTF export reference only (Blender has no official MCP, so do not call a Blender MCP)\n"
        "- TTS: ElevenLabs (MCP, use TTS tools only — do not touch ElevenAgents management tools) "
        "+ Alibaba Bailian models (qwen3-tts-flash, qwen-audio-3.1-tts-flash/plus, "
        "cosyvoice-v3-flash/plus/v2, sambert-zhichu-v1, MiniMax/speech-2.8-hd)\n"
        "- SFX: ElevenLabs REST + Alibaba Bailian qwen-audio-3.1-tts-next (Audiogen)\n"
        "- BGM: ElevenLabs REST + Alibaba Bailian fun-music-v1/preview\n\n"
        "Use the E2B sandbox to run CLI commands (Remotion, HyperFrames) and Python code "
        "(dashscope SDK, ElevenLabs REST). Decide your own workflow."
    ),

    # ── 货架标签 + 商品本体（方法论）──
    skills=[
        PROJECT_ROOT / "skills" / "remotion",      # 13 个官方 SKILL（remotion-dev/codex-plugin）
        PROJECT_ROOT / "skills" / "hyperframes",   # 9 个官方 SKILL（heygen-com/hyperframes）
        PROJECT_ROOT / "skills" / "crewai",        # 10 个官方 SKILL
    ],

    # ── 眼前货架 B（远程可调用物）──
    mcps=[
        # ElevenLabs 官方托管 MCP：只用 TTS 工具
        MCPServerHTTP(
            url="https://api.elevenlabs.io/v1/mcp",
            headers={"Authorization": f"Bearer {os.getenv('ELEVENLABS_TOKEN', '')}"},
            streamable=True,
            cache_tools_list=True,
        ),
    ],

    # ── 眼前货架 A（厨具 + 本地可调用物执行器）──
    tools=[
        # 通用文件工具
        FileReadTool(),
        FileWriterTool(),
        # E2B 沙箱三件套（厨具）
        E2BExecTool(persistent=True),      # 任意 shell：npx remotion render, hyperframes render, pip install dashscope
        E2BPythonTool(persistent=True),    # 任意 Python：from dashscope import Generation; requests.post(ElevenLabs REST)
        E2BFileTool(persistent=True),      # 任意文件：写 React/HTML/glb/音频
    ],

    # ── 导购广播（官方文档原文）──
    knowledge_sources=knowledge_sources,

    # ── 回头客记忆 + 自己写菜单 ──
    memory=True,
    planning_config=PlanningConfig(
        reasoning_effort="medium",  # 每步观察，失败时重规划
        max_steps=20,               # 计划最多 20 步
        max_replans=3,              # 最多重规划 3 次
    ),

    # ── 营业时间 / 监控 ──
    max_iter=20,
    verbose=True,
    allow_delegation=False,
)
