"""
Doctor Flow —— 纯程序门禁：Blender 环境不合格时，Crew 不启动。

只做三件能确定判断的事：
  1. uv 命令是否存在
  2. vendor/blender_mcp/pyproject.toml 是否完整
  3. localhost:PORT 是否可达（add-on 端口，可重试）

不消耗 LLM token，不做 GUI/安装层操作。
"""
import os
import shutil
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import Field

from crewai.flow.flow import Flow, listen, start

PROJECT_ROOT = Path(__file__).resolve().parent

# 同机本地端口：host/port 由配置层注入，默认本机直连
_DEFAULT_HOST = "localhost"

_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 1.5
_SOCKET_TIMEOUT_SECONDS = 2.0


class DoctorError(RuntimeError):
    """环境未就绪，Crew 不得启动。"""


@dataclass
class CheckResult:
    name: str
    ok: bool
    retryable: bool  # True=可重试，False=立即上报
    detail: str
    hint: str = ""


def _socket_reachable(host: str, port: int, timeout: float = _SOCKET_TIMEOUT_SECONDS) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _blender_dir() -> Path:
    vendor = Path(os.getenv("BLENDER_MCP_DIR", "vendor/blender_mcp"))
    return vendor if vendor.is_absolute() else PROJECT_ROOT / vendor


class BlenderChecker:
    name = "blender-mcp"

    def check(self) -> list[CheckResult]:
        command = os.getenv("BLENDER_MCP_COMMAND", "uv")
        host = os.getenv("BLENDER_MCP_HOST", _DEFAULT_HOST)
        raw_port = os.getenv("BLENDER_MCP_PORT", "9876")

        results: list[CheckResult] = [
            CheckResult(
                name="blender-uv",
                ok=shutil.which(command) is not None,
                retryable=False,
                detail=f"{command} 可用" if shutil.which(command) else f"{command} 未找到",
                hint=f"请安装 {command}",
            ),
            CheckResult(
                name="blender-vendor",
                ok=(_blender_dir() / "pyproject.toml").is_file(),
                retryable=False,
                detail="vendor 完整" if (_blender_dir() / "pyproject.toml").is_file() else "vendor 缺失",
                hint="请补全 vendor/blender_mcp/",
            ),
        ]

        try:
            port = int(raw_port)
        except ValueError:
            results.append(
                CheckResult(
                    name="blender-port",
                    ok=False,
                    retryable=False,
                    detail=f"BLENDER_MCP_PORT={raw_port!r} 不是合法端口",
                    hint="请在 .env 中设置合法的 BLENDER_MCP_PORT",
                )
            )
            return results

        reachable = _socket_reachable(host, port)
        results.append(
            CheckResult(
                name="blender-socket",
                ok=reachable,
                retryable=True,
                detail=f"{host}:{port} " + ("可达" if reachable else "不可达"),
                hint=f"请确认 Blender 已启动且 add-on 正在监听 {port}",
            )
        )
        return results


class DoctorFlow(Flow):
    """顶层 Flow 的第一段：检测 → 诊断 → 放行或拦截。"""

    on_ready: Any = None
    checkers: list[Any] = Field(default_factory=lambda: [BlenderChecker()])
    max_retries: int = _MAX_RETRIES
    retry_delay: float = _RETRY_DELAY_SECONDS

    @start()
    def detect(self) -> list[CheckResult]:
        return self._run_checks()

    @listen(detect)
    def diagnose(self, results: list[CheckResult]) -> dict:
        return self._triage(results)

    @listen(diagnose)
    def launch(self, verdict: dict):
        if not verdict["ready"]:
            raise DoctorError(verdict["report"])
        if self.on_ready is not None:
            return self.on_ready(verdict)
        return verdict

    def _run_checks(self) -> list[CheckResult]:
        out: list[CheckResult] = []
        for checker in self.checkers:
            out.extend(checker.check())
        return out

    def _triage(self, results: list[CheckResult]) -> dict:
        current = results
        for attempt in range(1, self.max_retries + 1):
            failed = [r for r in current if not r.ok]
            fatal = [r for r in failed if not r.retryable]
            retryable = [r for r in failed if r.retryable]

            if not failed:
                return self._verdict(True, attempt, current)
            if fatal:
                return self._verdict(False, attempt, current)
            if attempt == self.max_retries:
                break

            time.sleep(self.retry_delay)
            current = self._run_checks()

        return self._verdict(False, self.max_retries, current)

    @staticmethod
    def _verdict(ready: bool, attempt: int, results: list[CheckResult]) -> dict:
        lines = [f"Doctor 第 {attempt} 次检查：{'通过' if ready else '未通过'}"]
        for r in results:
            lines.append(f"  [{r.name}] {'通过' if r.ok else '失败'}: {r.detail}")
            if not r.ok and r.hint:
                lines.append(f"      修复：{r.hint}")
        return {"ready": ready, "attempts": attempt, "report": "\n".join(lines)}
