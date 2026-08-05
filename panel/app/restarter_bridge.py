"""Bridge to wow-restarter.sh with env overrides from panel config."""
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable


ProgressCb = Callable[[str], None]


class RestarterBridge:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def _script(self) -> Path:
        path = Path(self.config["paths"]["restarter_script"])
        if not path.is_file():
            raise FileNotFoundError(f"Restarter script not found: {path}")
        return path

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        paths = self.config["paths"]
        auth_bin = paths.get("auth_bin", "")
        auth_conf = paths.get("auth_conf", "")
        root = paths.get("server_root", "") or ""
        if root.endswith("/etc"):
            root = str(Path(root).parent)
        if not root and auth_bin:
            root = str(Path(auth_bin).parent.parent)
        bin_dir = str(Path(auth_bin).parent) if auth_bin else f"{root}/bin"
        etc_dir = str(Path(auth_conf).parent) if auth_conf else f"{root}/etc"
        env.update(
            {
                "SERVER_ROOT": root,
                "BIN_DIR": bin_dir,
                "ETC_DIR": etc_dir,
                "AUTH_BIN": auth_bin,
                "WORLD_BIN": paths.get("world_bin", ""),
                "AUTH_CONF": auth_conf,
                "WORLD_CONF": paths.get("world_conf", ""),
                "LD_LIBRARY_PATH": bin_dir
                + ((":" + env["LD_LIBRARY_PATH"]) if env.get("LD_LIBRARY_PATH") else ""),
                "START_WAIT": env.get("START_WAIT", "8"),
                "PYTHONUNBUFFERED": "1",
            }
        )
        # line-buffered bash where possible
        env["BASH"] = env.get("BASH", "/bin/bash")
        return env

    def log_dir(self) -> Path:
        return self._script().parent / "logs"

    def _append_server_logs(self, out: str) -> str:
        log_dir = self.log_dir()
        chunks = [out] if out else []
        for name in ("authserver.out", "worldserver.out", "restarter.log"):
            path = log_dir / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            cleaned = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32 or ch == "\t")
            lines = cleaned.strip().splitlines()[-30:]
            if lines:
                chunks.append(f"--- {name} (хвост) ---\n" + "\n".join(lines))
        return "\n\n".join(chunks).strip()

    def run(
        self,
        command: str,
        timeout: int = 90,
        on_line: ProgressCb | None = None,
    ) -> tuple[int, str]:
        script = self._script()
        if on_line:
            on_line(f"$ {script.name} {command}")

        try:
            proc = subprocess.Popen(
                ["bash", "-c", f'stdbuf -oL -eL "{script}" {command}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=self._env(),
                bufsize=1,
            )
        except FileNotFoundError:
            # fallback without stdbuf
            proc = subprocess.Popen(
                [str(script), command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=self._env(),
                bufsize=1,
            )

        lines: list[str] = []
        assert proc.stdout is not None

        def reader() -> None:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                # strip simple ANSI
                cleaned = "".join(ch for ch in line if ord(ch) >= 32 or ch == "\t")
                lines.append(cleaned)
                if on_line and cleaned:
                    on_line(cleaned)

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            t.join(timeout=2)
            msg = f"Таймаут {timeout}с при '{command}'."
            if on_line:
                on_line(msg)
            partial = "\n".join(lines)
            return 124, self._append_server_logs(f"{msg}\n{partial}".strip())

        t.join(timeout=5)
        out = "\n".join(lines).strip()
        if code != 0 or command in {"start", "restart", "start-auth", "start-world"}:
            out = self._append_server_logs(out)
            if on_line and code != 0:
                on_line(f"[exit code {code}] см. хвост логов выше/ниже")
        elif on_line:
            on_line(f"[готово, code={code}]")
        return code, out

    def start(self, on_line: ProgressCb | None = None) -> tuple[int, str]:
        if on_line:
            on_line("=== START authserver + worldserver ===")
        return self.run("start", timeout=90, on_line=on_line)

    def stop(self, on_line: ProgressCb | None = None) -> tuple[int, str]:
        if on_line:
            on_line("=== STOP ===")
        return self.run("stop", timeout=60, on_line=on_line)

    def restart(self, on_line: ProgressCb | None = None) -> tuple[int, str]:
        if on_line:
            on_line("=== RESTART ===")
        return self.run("restart", timeout=120, on_line=on_line)

    def status(self, on_line: ProgressCb | None = None) -> tuple[int, str]:
        return self.run("status", timeout=15, on_line=on_line)

    def tail_file(self, name: str, n: int = 40) -> str:
        path = self.log_dir() / name
        if not path.is_file():
            return f"(нет файла {path})"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"(не прочитать {path}: {exc})"
        cleaned = "".join(ch for ch in text if ch == "\n" or ord(ch) >= 32 or ch == "\t")
        lines = cleaned.strip().splitlines()[-n:]
        return "\n".join(lines) if lines else "(пусто)"
