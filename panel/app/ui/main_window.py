"""Main PySide6 window for WoW Server Panel."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QFileDialog,
    QMenu,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config_store import load_config, save_config
from app.mysql_service import MySQLService
from app.restarter_bridge import RestarterBridge
from app.soap_client import SOAPClient

PANEL_DIR = Path(__file__).resolve().parents[2]

class SimpleJob(QThread):
    """Лёгкий job для MySQL/SOAP. Сигналы — на самом QThread (безопасно для Qt)."""

    line = Signal(str)
    fail = Signal(str)

    def __init__(self, kind: str, config: dict[str, Any]) -> None:
        super().__init__()
        self.kind = kind
        self.config = config

    def run(self) -> None:
        try:
            if self.kind == "mysql":
                self.line.emit("Проверка MySQL…")
                _ok, msg = MySQLService(self.config).ping()
                self.line.emit(msg)
            elif self.kind == "online":
                self.line.emit("Запрос online…")
                _ok, msg = MySQLService(self.config).online_count()
                self.line.emit(msg)
            elif self.kind == "soap":
                self.line.emit("SOAP .server info…")
                _ok, msg = SOAPClient(self.config).execute("server info")
                self.line.emit(msg)
            else:
                self.fail.emit(f"unknown job: {self.kind}")
        except Exception as exc:  # noqa: BLE001
            self.fail.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WoW Server Panel — OrstetCore / AzerothCore")
        self.resize(1000, 740)

        self.config = load_config()
        self._force_quit = False
        self._tray: Optional[QSystemTrayIcon] = None
        self._proc: Optional[QProcess] = None
        self._bot_proc: Optional[QProcess] = None
        self._jobs: list[SimpleJob] = []
        self._busy_label = ""

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        header = QHBoxLayout()
        title = QLabel("WoW Server Panel")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch(1)
        self.bot_status_label = QLabel("Бот: выкл")
        self.bot_status_label.setStyleSheet("color: #a33;")
        header.addWidget(self.bot_status_label)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self._build_paths_tab()
        self._build_telegram_tab()
        self._build_mysql_soap_tab()
        self._build_control_tab()
        self._build_console_tab()

        bottom = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить настройки")
        self.save_btn.clicked.connect(self.save_settings)
        bottom.addWidget(self.save_btn)

        self.tray_minimize_cb = QCheckBox("Сворачивать в трей")
        self.tray_minimize_cb.setChecked(True)
        bottom.addWidget(self.tray_minimize_cb)
        bottom.addStretch(1)

        to_tray_btn = QPushButton("В трей")
        to_tray_btn.clicked.connect(self.hide_to_tray)
        bottom.addWidget(to_tray_btn)
        layout.addLayout(bottom)

        self._setup_tray()
        self._load_fields_from_config()
        self.console_write("Панель запущена.")
        self.console_write("Серверы и бот живут отдельно — закрытие окна не гасит world/auth.")

        QTimer.singleShot(700, self._maybe_autostart_bot)
        QTimer.singleShot(1100, self.do_status)

    # ----- console -----
    @Slot(str)
    def console_write(self, text: str) -> None:
        if not text:
            return
        self.console.appendPlainText(text)
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def append_log(self, text: str) -> None:
        self.console_write(text)

    def show_console(self) -> None:
        idx = self.tabs.indexOf(self.console_page)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)

    def _set_bot_status(self, text: str, *, ok: bool) -> None:
        self.bot_status_label.setText(text)
        self.bot_status_label.setStyleSheet("color: #2a7;" if ok else "color: #a33;")

    # ----- config -----
    def gather_config(self) -> dict[str, Any]:
        cfg = deepcopy(self.config)
        root = self.server_root_edit.text().strip().rstrip("/")
        if root.endswith("/etc"):
            root = root[: -len("/etc")].rstrip("/")
        cfg["paths"] = {
            "restarter_script": self.restarter_edit.text().strip(),
            "server_root": root,
            "auth_bin": self.auth_bin_edit.text().strip(),
            "world_bin": self.world_bin_edit.text().strip(),
            "auth_conf": self.auth_conf_edit.text().strip(),
            "world_conf": self.world_conf_edit.text().strip(),
        }
        owner_raw = self.tg_owner_edit.text().strip()
        try:
            owner_id = int(owner_raw) if owner_raw else 0
        except ValueError:
            owner_id = 0
        cfg["telegram"] = {
            "bot_token": self.tg_token_edit.text().strip(),
            "owner_id": owner_id,
        }
        cfg["mysql"] = {
            "host": self.mysql_host.text().strip(),
            "port": int(self.mysql_port.value()),
            "user": self.mysql_user.text().strip(),
            "password": self.mysql_pass.text(),
            "database": self.mysql_db.text().strip(),
        }
        cfg["soap"] = {
            "host": self.soap_host.text().strip(),
            "port": int(self.soap_port.value()),
            "username": self.soap_user.text().strip(),
            "password": self.soap_pass.text(),
        }
        return cfg

    def _load_fields_from_config(self) -> None:
        p = self.config["paths"]
        self.restarter_edit.setText(p.get("restarter_script", ""))
        self.server_root_edit.setText(p.get("server_root", ""))
        self.auth_bin_edit.setText(p.get("auth_bin", ""))
        self.world_bin_edit.setText(p.get("world_bin", ""))
        self.auth_conf_edit.setText(p.get("auth_conf", ""))
        self.world_conf_edit.setText(p.get("world_conf", ""))

        tg = self.config["telegram"]
        self.tg_token_edit.setText(tg.get("bot_token", ""))
        self.tg_owner_edit.setText(str(tg.get("owner_id") or ""))

        m = self.config["mysql"]
        self.mysql_host.setText(m.get("host", "127.0.0.1"))
        self.mysql_port.setValue(int(m.get("port") or 3306))
        self.mysql_user.setText(m.get("user", ""))
        self.mysql_pass.setText(m.get("password", ""))
        self.mysql_db.setText(m.get("database", ""))

        s = self.config["soap"]
        self.soap_host.setText(s.get("host", "127.0.0.1"))
        self.soap_port.setValue(int(s.get("port") or 7878))
        self.soap_user.setText(s.get("username", ""))
        self.soap_pass.setText(s.get("password", ""))

    def _persist(self, *, notify: bool = True) -> dict[str, Any]:
        self.config = self.gather_config()
        save_config(self.config)
        self.console_write("Настройки сохранены в config.json")
        if notify:
            QMessageBox.information(self, "Сохранено", "config.json обновлён.")
        return self.config

    @Slot()
    def save_settings(self) -> None:
        self._persist(notify=True)

    # ----- UI builders -----
    def _path_row(self, parent_layout: QFormLayout, label: str) -> tuple[QLineEdit, QPushButton]:
        edit = QLineEdit()
        btn = QPushButton("Обзор…")
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(edit, stretch=1)
        hl.addWidget(btn)

        def browse() -> None:
            start = edit.text() or "/"
            path, _ = QFileDialog.getOpenFileName(self, label, start)
            if path:
                edit.setText(path)

        btn.clicked.connect(browse)
        parent_layout.addRow(label, row)
        return edit, btn

    def _build_paths_tab(self) -> None:
        page = QWidget()
        form = QFormLayout(page)
        self.restarter_edit, _ = self._path_row(form, "wow-restarter.sh")
        self.server_root_edit = QLineEdit()
        root_row = QWidget()
        hl = QHBoxLayout(root_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.server_root_edit, stretch=1)
        root_btn = QPushButton("Обзор…")

        def browse_root() -> None:
            path = QFileDialog.getExistingDirectory(self, "Server root", self.server_root_edit.text() or "/")
            if path:
                self.server_root_edit.setText(path)

        root_btn.clicked.connect(browse_root)
        hl.addWidget(root_btn)
        form.addRow("Server root", root_row)
        self.auth_bin_edit, _ = self._path_row(form, "authserver")
        self.world_bin_edit, _ = self._path_row(form, "worldserver")
        self.auth_conf_edit, _ = self._path_row(form, "authserver.conf")
        self.world_conf_edit, _ = self._path_row(form, "worldserver.conf")
        self.tabs.addTab(page, "Пути")

    def _build_telegram_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.tg_token_edit = QLineEdit()
        self.tg_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Bot Token", self.tg_token_edit)
        self.tg_owner_edit = QLineEdit()
        form.addRow("Owner User ID", self.tg_owner_edit)
        layout.addLayout(form)

        btns = QHBoxLayout()
        self.bot_start_btn = QPushButton("Запустить бота")
        self.bot_stop_btn = QPushButton("Остановить бота")
        self.bot_stop_btn.setEnabled(False)
        self.bot_start_btn.clicked.connect(lambda: self.start_bot(silent=False))
        self.bot_stop_btn.clicked.connect(self.stop_bot)
        btns.addWidget(self.bot_start_btn)
        btns.addWidget(self.bot_stop_btn)
        btns.addStretch(1)
        layout.addLayout(btns)

        note = QLabel(
            "Бот работает отдельным процессом (не роняет панель).\n"
            "Напишите боту /start, потом /status.\n"
            "Опасные: /restart , /stop"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        self.tabs.addTab(page, "Telegram")

    def _build_mysql_soap_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        mysql_box = QGroupBox("MySQL")
        mf = QFormLayout(mysql_box)
        self.mysql_host = QLineEdit()
        self.mysql_port = QSpinBox()
        self.mysql_port.setRange(1, 65535)
        self.mysql_user = QLineEdit()
        self.mysql_pass = QLineEdit()
        self.mysql_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.mysql_db = QLineEdit()
        mf.addRow("Host", self.mysql_host)
        mf.addRow("Port", self.mysql_port)
        mf.addRow("User", self.mysql_user)
        mf.addRow("Password", self.mysql_pass)
        mf.addRow("Database", self.mysql_db)
        layout.addWidget(mysql_box)

        soap_box = QGroupBox("SOAP")
        sf = QFormLayout(soap_box)
        self.soap_host = QLineEdit()
        self.soap_port = QSpinBox()
        self.soap_port.setRange(1, 65535)
        self.soap_user = QLineEdit()
        self.soap_pass = QLineEdit()
        self.soap_pass.setEchoMode(QLineEdit.EchoMode.Password)
        sf.addRow("Host", self.soap_host)
        sf.addRow("Port", self.soap_port)
        sf.addRow("GM Username", self.soap_user)
        sf.addRow("GM Password", self.soap_pass)
        layout.addWidget(soap_box)

        btns = QHBoxLayout()
        for text, slot in (
            ("Проверить MySQL", self.test_mysql),
            ("Онлайн", self.test_online),
            ("SOAP .server info", self.test_soap),
        ):
            b = QPushButton(text)
            b.clicked.connect(slot)
            btns.addWidget(b)
        btns.addStretch(1)
        layout.addLayout(btns)
        layout.addStretch(1)
        self.tabs.addTab(page, "MySQL / SOAP")

    def _build_control_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        row1 = QHBoxLayout()
        for text, slot in (
            ("Start", self.do_start),
            ("Stop", self.do_stop),
            ("Restart", self.do_restart),
            ("Status", self.do_status),
        ):
            b = QPushButton(text)
            b.setMinimumHeight(36)
            b.clicked.connect(slot)
            row1.addWidget(b)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        for text, name in (
            ("Хвост authserver", "authserver.out"),
            ("Хвост worldserver", "worldserver.out"),
        ):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, n=name: self._show_tail(n))
            row2.addWidget(b)
        open_c = QPushButton("Открыть консоль")
        open_c.clicked.connect(self.show_console)
        row2.addWidget(open_c)
        row2.addStretch(1)
        layout.addLayout(row2)

        hint = QLabel(
            "Вывод команд — вкладка «Консоль».\n"
            "Start/Stop НЕ закрывают панель: auth/world — отдельные процессы."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)
        self.tabs.addTab(page, "Управление")

    def _build_console_tab(self) -> None:
        self.console_page = QWidget()
        layout = QVBoxLayout(self.console_page)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(8000)
        font = QFont("DejaVu Sans Mono")
        if not font.exactMatch():
            font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.console.setFont(font)
        self.console.setStyleSheet(
            "QPlainTextEdit { background:#1e1e1e; color:#d4d4d4; border:1px solid #333; }"
        )

        bar = QHBoxLayout()
        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self.console.clear)
        refresh_btn = QPushButton("Status сейчас")
        refresh_btn.clicked.connect(self.do_status)
        bar.addWidget(clear_btn)
        bar.addWidget(refresh_btn)
        bar.addStretch(1)
        layout.addLayout(bar)
        layout.addWidget(self.console, stretch=1)
        self.tabs.addTab(self.console_page, "Консоль")

    def _show_tail(self, name: str) -> None:
        cfg = self.gather_config()
        self.show_console()
        self.console_write(f"===== {name} =====")
        self.console_write(RestarterBridge(cfg).tail_file(name, 60))

    # ----- QProcess restarter -----
    def _restarter_env(self, cfg: dict[str, Any]) -> QProcessEnvironment:
        bridge = RestarterBridge(cfg)
        env = QProcessEnvironment.systemEnvironment()
        for key, value in bridge._env().items():  # noqa: SLF001
            env.insert(key, value)
        return env

    def _run_restarter(self, command: str, label: str) -> None:
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self.console_write("Уже выполняется команда, подождите…")
            return

        cfg = self.gather_config()
        script = Path(cfg["paths"]["restarter_script"])
        if not script.is_file():
            self.console_write(f"Нет скрипта: {script}")
            return

        self.show_console()
        self._busy_label = label
        self.console_write(f"→ {label}…")
        self.console_write(f"$ {script.name} {command}")

        proc = QProcess(self)
        proc.setProgram("/bin/bash")
        proc.setArguments([str(script), command])
        proc.setWorkingDirectory(str(script.parent))
        proc.setProcessEnvironment(self._restarter_env(cfg))
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_proc_output)
        proc.finished.connect(self._on_proc_finished)
        proc.errorOccurred.connect(self._on_proc_error)
        self._proc = proc
        proc.start()

    @Slot()
    def _on_proc_output(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for raw in data.splitlines():
            cleaned = "".join(ch for ch in raw if ord(ch) >= 32 or ch == "\t")
            if cleaned:
                self.console_write(cleaned)

    @Slot(int, QProcess.ExitStatus)
    def _on_proc_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        label = self._busy_label or "команда"
        self.console_write(f"✔ {label} — exit={code}")
        if code != 0:
            cfg = self.gather_config()
            bridge = RestarterBridge(cfg)
            self.console_write("--- authserver.out ---")
            self.console_write(bridge.tail_file("authserver.out", 25))
            self.console_write("--- worldserver.out ---")
            self.console_write(bridge.tail_file("worldserver.out", 25))
        self._busy_label = ""
        self._proc = None

    @Slot(QProcess.ProcessError)
    def _on_proc_error(self, err: QProcess.ProcessError) -> None:
        self.console_write(f"✖ Ошибка процесса: {err}")

    def _run_simple_job(self, kind: str, label: str) -> None:
        self.show_console()
        self.console_write(f"→ {label}…")
        cfg = self.gather_config()
        job = SimpleJob(kind, cfg)
        job.line.connect(self.console_write)
        job.fail.connect(self._on_job_fail)
        job.finished.connect(self._on_job_finished)
        # keep label for finished message
        job.setProperty("label", label)
        job.finished.connect(job.deleteLater)
        self._jobs = [j for j in self._jobs if j.isRunning()]
        self._jobs.append(job)
        self._last_job_label = label
        job.start()

    @Slot(str)
    def _on_job_fail(self, msg: str) -> None:
        self.console_write(f"✖ {msg}")

    @Slot()
    def _on_job_finished(self) -> None:
        label = getattr(self, "_last_job_label", "job")
        self.console_write(f"✔ {label} — готово")

    # ----- actions -----
    @Slot()
    def test_mysql(self) -> None:
        self._run_simple_job("mysql", "MySQL ping")

    @Slot()
    def test_online(self) -> None:
        self._run_simple_job("online", "Online count")

    @Slot()
    def test_soap(self) -> None:
        self._run_simple_job("soap", "SOAP server info")

    @Slot()
    def do_start(self) -> None:
        cfg = self.gather_config()
        ok, msg = MySQLService(cfg).ping()
        self.show_console()
        self.console_write(msg)
        if not ok:
            self.console_write("ОТМЕНА: sudo systemctl start mysql")
            return
        self._run_restarter("start", "Start servers")

    @Slot()
    def do_stop(self) -> None:
        self._run_restarter("stop", "Stop servers")

    @Slot()
    def do_restart(self) -> None:
        reply = QMessageBox.question(
            self,
            "Restart",
            "Перезапустить authserver и worldserver?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        cfg = self.gather_config()
        ok, msg = MySQLService(cfg).ping()
        self.show_console()
        self.console_write(msg)
        if not ok:
            self.console_write("ОТМЕНА: MySQL недоступен")
            return
        self._run_restarter("restart", "Restart servers")

    @Slot()
    def do_status(self) -> None:
        self._run_restarter("status", "Status")

    # ----- telegram bot as separate process -----
    @Slot()
    def _maybe_autostart_bot(self) -> None:
        cfg = self.gather_config()
        token = (cfg["telegram"].get("bot_token") or "").strip()
        owner = int(cfg["telegram"].get("owner_id") or 0)
        if token and owner > 0:
            self.console_write("Автозапуск Telegram-бота…")
            self.start_bot(silent=True)

    def start_bot(self, silent: bool = False) -> None:
        if self._bot_proc and self._bot_proc.state() != QProcess.ProcessState.NotRunning:
            if not silent:
                self.console_write("Бот уже запущен")
            return
        cfg = self.gather_config()
        if not cfg["telegram"]["bot_token"] or int(cfg["telegram"]["owner_id"] or 0) <= 0:
            if not silent:
                QMessageBox.warning(self, "Telegram", "Нужны Bot Token и Owner User ID")
            return
        self._persist(notify=False)

        bot_script = PANEL_DIR / "run_bot.py"
        py = PANEL_DIR / "venv" / "bin" / "python"
        if not py.is_file():
            py = Path(sys_executable())

        proc = QProcess(self)
        proc.setProgram(str(py))
        proc.setArguments([str(bot_script)])
        proc.setWorkingDirectory(str(PANEL_DIR))
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_bot_output)
        proc.finished.connect(self._on_bot_finished)
        self._bot_proc = proc
        proc.start()
        self.bot_start_btn.setEnabled(False)
        self.bot_stop_btn.setEnabled(True)
        self._set_bot_status("Бот: запуск…", ok=False)
        self.console_write("Telegram-бот: отдельный процесс запущен")

    @Slot()
    def stop_bot(self) -> None:
        if not self._bot_proc:
            return
        self.console_write("Останавливаю бота…")
        self._bot_proc.terminate()
        if not self._bot_proc.waitForFinished(5000):
            self._bot_proc.kill()
            self._bot_proc.waitForFinished(2000)
        self._bot_proc = None
        self.bot_start_btn.setEnabled(True)
        self.bot_stop_btn.setEnabled(False)
        self._set_bot_status("Бот: выкл", ok=False)

    @Slot()
    def _on_bot_output(self) -> None:
        if not self._bot_proc:
            return
        data = bytes(self._bot_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            self.console_write(f"[bot] {line}")
            if line.startswith("READY "):
                self._set_bot_status(f"Бот: {line[6:]}", ok=True)
            elif line.startswith("ERROR"):
                self._set_bot_status("Бот: ошибка", ok=False)

    @Slot(int, QProcess.ExitStatus)
    def _on_bot_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        self.console_write(f"[bot] процесс завершён (code={code})")
        self._bot_proc = None
        self.bot_start_btn.setEnabled(True)
        self.bot_stop_btn.setEnabled(False)
        self._set_bot_status("Бот: выкл", ok=False)

    # ----- tray -----
    @staticmethod
    def _make_tray_icon() -> QIcon:
        size = 64
        pix = QPixmap(size, size)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(32, 90, 167))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(2, 2, size - 4, size - 4, 12, 12)
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Sans Serif")
        font.setBold(True)
        font.setPixelSize(28)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "W")
        painter.end()
        return QIcon(pix)

    def has_tray(self) -> bool:
        return self._tray is not None

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.console_write("Трей недоступен")
            return
        self._tray = QSystemTrayIcon(self._make_tray_icon(), self)
        self._tray.setToolTip("WoW Server Panel")
        menu = QMenu()
        act_show = QAction("Показать", self)
        act_show.triggered.connect(self.show_from_tray)
        act_hide = QAction("Скрыть в трей", self)
        act_hide.triggered.connect(self.hide_to_tray)
        act_status = QAction("Status", self)
        act_status.triggered.connect(self.do_status)
        act_quit = QAction("Выход", self)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_show)
        menu.addAction(act_hide)
        menu.addSeparator()
        menu.addAction(act_status)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    @Slot()
    def hide_to_tray(self) -> None:
        if not self._tray:
            self.showMinimized()
            return
        self.hide()

    @Slot()
    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    @Slot(QSystemTrayIcon.ActivationReason)
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.isVisible() and not self.isMinimized():
                self.hide_to_tray()
            else:
                self.show_from_tray()

    @Slot()
    def quit_app(self) -> None:
        self._force_quit = True
        self.stop_bot()
        if self._tray:
            self._tray.hide()
        self.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def changeEvent(self, event) -> None:  # noqa: N802
        if (
            event.type() == event.Type.WindowStateChange
            and self.isMinimized()
            and self.tray_minimize_cb.isChecked()
            and self._tray
        ):
            event.accept()
            QTimer.singleShot(0, self.hide_to_tray)
            return
        super().changeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if (
            not self._force_quit
            and self.tray_minimize_cb.isChecked()
            and self._tray
        ):
            event.ignore()
            self.hide_to_tray()
            return
        # НЕ гасим auth/world — только UI и бота (бот гасим при полном выходе)
        if self._force_quit:
            self.stop_bot()
        if self._tray:
            self._tray.hide()
        event.accept()
        super().closeEvent(event)


def sys_executable() -> str:
    import sys

    return sys.executable
