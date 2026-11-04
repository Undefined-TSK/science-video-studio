"""
厨师（Agent）—— 走进食材超市，自主选材炒菜。

所有货架摆满：
  tools=  → 眼前货架 A：厨具（一个共享 E2B 沙箱 + 文件工具）
  mcps=   → 眼前货架 B：远程能力窗口（Blender 官方 MCP）
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
from crewai.mcp import MCPServerStdio
from crewai.agent.planning_config import PlanningConfig
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource
from crewai_tools import (
    FileReadTool,
    FileWriterTool,
    E2BPythonTool,
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

# Blender 官方 MCP 服务器（Blender Lab 源码，原样放在 vendor/ 下）
_blender_dir = Path(os.getenv("BLENDER_MCP_DIR", "vendor/blender_mcp"))
BLENDER_MCP_DIR = (
    _blender_dir if _blender_dir.is_absolute() else PROJECT_ROOT / _blender_dir
)

# 同机本地端口：host/port 由配置层注入，默认本机直连
BLENDER_MCP_HOST = os.getenv("BLENDER_MCP_HOST", "localhost")
BLENDER_MCP_PORT = os.getenv("BLENDER_MCP_PORT", "9876")

knowledge_sources = [
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
    # Blender 官方工具清单（运行期内容；手册由 MCP 的 search_manual_docs 工具按需检索）
    TextFileKnowledgeSource(
        file_paths=[DOCS / "blender" / "mcp-tools.rst"],
        collection_name="blender",
    ),
    # ElevenLabs 官方文档 + 官方 OpenAPI 契约
    TextFileKnowledgeSource(
        file_paths=[
            DOCS / "elevenlabs" / "llms-full.txt",
            DOCS / "elevenlabs" / "openapi.json",
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
        "- 3D assets: Blender Lab official MCP (26 tools) is connected on localhost and ready. "
        "Call its tools directly. If a Blender tool fails, stop and report it "
        "as an environment problem for a human; environment setup is outside the team's scope. "
        "Then take the exported glb into three.js (GLTFLoader), or build procedural geometry "
        "inside Remotion/three.js\n"
        "- TTS: ElevenLabs REST POST /v1/text-to-speech/{voice_id} (xi-api-key header) "
        "+ Alibaba Bailian models (qwen3-tts-flash, qwen-audio-3.1-tts-flash/plus, "
        "cosyvoice-v3-flash/plus/v2, sambert-zhichu-v1, MiniMax/speech-2.8-hd)\n"
        "- SFX: ElevenLabs REST POST /v1/sound-generation + Alibaba Bailian "
        "qwen-audio-3.1-tts-next (Audiogen)\n"
        "- BGM: ElevenLabs REST POST /v1/music + Alibaba Bailian fun-music-v1/preview\n\n"
        "You have exactly one E2B sandbox. Use it for shell commands (Remotion, HyperFrames), "
        "file operations, and Python code. Pip-install `requests` or the official `elevenlabs` "
        "SDK inside it, then call the official REST endpoints with the API keys already present "
        "in the sandbox environment (ELEVENLABS_API_KEY, DASHSCOPE_API_KEY). "
        "The full ElevenLabs OpenAPI contract is in your knowledge sources. Decide your own workflow."
    ),

    # ── 货架标签 + 商品本体（方法论）──
    skills=[
        PROJECT_ROOT / "skills" / "remotion",      # 13 个官方 SKILL（remotion-dev/codex-plugin）
        PROJECT_ROOT / "skills" / "hyperframes",   # 9 个官方 SKILL（heygen-com/hyperframes）
    ],

    # ── 眼前货架 B（远程可调用物）──
    mcps=[
        # Blender Lab 官方 MCP（26 工具）：uv --directory <blender_mcp> run blender-mcp
        # 前提：Blender 5.1+ 已安装官方 add-on 并运行，add-on 负责与 MCP 服务器 TCP 通信
        MCPServerStdio(
            command=os.getenv("BLENDER_MCP_COMMAND", "uv"),
            args=[
                "--directory",
                str(BLENDER_MCP_DIR),
                "run",
                "blender-mcp",
            ],
            env={
                "BLENDER_MCP_HOST": BLENDER_MCP_HOST,
                "BLENDER_MCP_PORT": BLENDER_MCP_PORT,
            },
        ),
        # ElevenLabs 官方托管 MCP 已移除：它是 ElevenAgents 管理工具，
        # 不提供通用 TTS/SFX/BGM，且会带来 workspace agent 管理权限。
    ],

    # ── 眼前货架 A（厨具 + 本地可调用物执行器）──
    tools=[
        # 通用文件工具（宿主机）
        FileReadTool(),
        FileWriterTool(),
        # 唯一 E2B 沙箱：shell / Python / 文件操作都在这一个沙箱里
        # 密钥通过 envs 注入沙箱，Agent 用 requests 调官方 REST
        E2BPythonTool(
            persistent=True,
            envs={
                k: v
                for k in ("ELEVENLABS_API_KEY", "DASHSCOPE_API_KEY")
                if (v := os.getenv(k))
            },
        ),
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
