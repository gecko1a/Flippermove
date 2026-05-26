#!/usr/bin/env python3
"""
Flippermove – verschiebt Pinball-Dateien auf einen Samba-Share.
"""

import sys
import os
import subprocess
from pathlib import Path

import keyring
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QDialog, QTextEdit, QDialogButtonBox,
    QInputDialog, QLineEdit, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# ── Konfiguration ──────────────────────────────────────────────────────────────
SOURCE_DIR  = Path("/home/frank/Downloads/__Pinball")
SMB_HOST    = "192.168.0.41"
SMB_USER    = "flipper"
SMB_SHARE   = "vPinball"
KEYRING_SVC = "flippermove"

ROUTES: dict[str, str] = {
    ".vpx":       "VisualPinball/Tables",
    ".directb2s": "VisualPinball/Tables",
    ".zip":       "VPinMAME/roms",
}

FILE_ICONS: dict[str, str] = {
    ".vpx":       "🎯",
    ".directb2s": "🖼️",
    ".zip":       "📦",
}
# ──────────────────────────────────────────────────────────────────────────────


def get_password() -> str | None:
    return keyring.get_password(KEYRING_SVC, SMB_USER)


def set_password(pw: str) -> None:
    keyring.set_password(KEYRING_SVC, SMB_USER, pw)


def smb_put(local_path: Path, remote_dir: str, password: str) -> tuple[bool, str]:
    """Überträgt eine Datei via smbclient auf den Share."""
    cmd = [
        "smbclient",
        f"//{SMB_HOST}/{SMB_SHARE}",
        f"--user={SMB_USER}%{password}",
        "-c",
        f'put "{local_path}" "{remote_dir}/{local_path.name}"',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()

    # smbclient gibt manchmal 0 zurück, meldet aber trotzdem NT_STATUS-Fehler
    if result.returncode != 0 or "NT_STATUS" in stdout or "NT_STATUS" in stderr:
        detail = stderr or stdout or f"Exit-Code {result.returncode}"
        return False, detail

    return True, ""


# ── Worker-Thread ──────────────────────────────────────────────────────────────

class MoveWorker(QThread):
    """Führt den Upload + lokales Löschen im Hintergrund durch."""

    # (dateiname, status, detail)
    # status: "ok" | "error" | "del_error" | "skipped"
    done = pyqtSignal(list)

    def __init__(self, files: list[Path], password: str, parent=None):
        super().__init__(parent)
        self.files    = files
        self.password = password

    def run(self) -> None:
        results: list[tuple[str, str, str]] = []
        for f in self.files:
            ext = f.suffix.lower()
            if ext not in ROUTES:
                results.append((f.name, "skipped", "Dateityp nicht zugeordnet"))
                continue

            remote_dir = ROUTES[ext]
            ok, err    = smb_put(f, remote_dir, self.password)

            if ok:
                try:
                    f.unlink()
                    results.append((f.name, "ok", remote_dir))
                except OSError as e:
                    results.append((f.name, "del_error", str(e)))
            else:
                results.append((f.name, "error", err))

        self.done.emit(results)


# ── Ergebnis-Dialog ────────────────────────────────────────────────────────────

class ResultDialog(QDialog):
    def __init__(self, results: list[tuple[str, str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ergebnis")
        self.resize(650, 420)
        layout = QVBoxLayout(self)

        ok_list      = [r for r in results if r[1] == "ok"]
        error_list   = [r for r in results if r[1] in ("error", "del_error")]
        skipped_list = [r for r in results if r[1] == "skipped"]

        lines: list[str] = []

        if ok_list:
            lines.append(f"✅  Erfolgreich verschoben ({len(ok_list)}):")
            for name, _, dest in ok_list:
                lines.append(f"    {name}")
                lines.append(f"      → {dest}")
            lines.append("")

        if error_list:
            lines.append(f"❌  Fehler ({len(error_list)}):")
            for name, status, detail in error_list:
                tag = "Upload" if status == "error" else "Lokales Löschen"
                lines.append(f"    {name}  [{tag}-Fehler]")
                if detail:
                    lines.append(f"      {detail}")
            lines.append("")

        if skipped_list:
            lines.append(f"⏭️   Nicht verschoben ({len(skipped_list)}):")
            for name, _, reason in skipped_list:
                lines.append(f"    {name}  ({reason})")

        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("Monospace", 10))
        text.setPlainText("\n".join(lines) if lines else "Keine Dateien verarbeitet.")
        layout.addWidget(text)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bb.accepted.connect(self.accept)
        layout.addWidget(bb)


# ── Hauptfenster ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flippermove")
        self.resize(720, 520)
        self._worker: MoveWorker | None = None
        # Bildet Listeneintrag-Index → Path-Objekt ab
        self._paths: list[Path] = []

        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setSpacing(8)

        # Quellverzeichnis-Label
        hdr = QLabel(f"📁  {SOURCE_DIR}")
        hdr.setFont(QFont("Sans", 10, QFont.Weight.Bold))
        vbox.addWidget(hdr)

        # Dateiliste
        self.file_list = QListWidget()
        self.file_list.setFont(QFont("Monospace", 10))
        self.file_list.setAlternatingRowColors(True)
        vbox.addWidget(self.file_list)

        # Button-Zeile
        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄  Aktualisieren")
        self.btn_move    = QPushButton("🚀  Verschieben")
        self.btn_pw      = QPushButton("🔑  Passwort ändern")
        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_move)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_pw)
        vbox.addLayout(btn_row)

        # Statuszeile
        self.status_label = QLabel("")
        vbox.addWidget(self.status_label)

        # Signale verbinden
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_move.clicked.connect(self.start_move)
        self.btn_pw.clicked.connect(self.change_password)

        self.refresh()

    # ── Verzeichnis einlesen ───────────────────────────────────────────────────

    def refresh(self) -> None:
        self.file_list.clear()
        self._paths.clear()

        if not SOURCE_DIR.exists():
            self.status_label.setText(f"⚠️  Verzeichnis nicht gefunden: {SOURCE_DIR}")
            return

        files = sorted(f for f in SOURCE_DIR.iterdir() if f.is_file())

        for f in files:
            ext  = f.suffix.lower()
            icon = FILE_ICONS.get(ext, "📄")
            item = QListWidgetItem(f"{icon}  {f.name}")

            if ext not in ROUTES:
                # Grau = wird beim Verschieben nicht angefasst
                item.setForeground(Qt.GlobalColor.gray)

            self.file_list.addItem(item)
            self._paths.append(f)

        total    = len(self._paths)
        moveable = sum(1 for f in self._paths if f.suffix.lower() in ROUTES)
        self.status_label.setText(
            f"{total} Datei(en) gefunden, davon {moveable} zum Verschieben vorgesehen."
        )

    # ── Passwort-Verwaltung ────────────────────────────────────────────────────

    def _ensure_password(self) -> str | None:
        pw = get_password()
        if pw:
            return pw
        return self._ask_password("Samba-Passwort einrichten")

    def _ask_password(self, title: str) -> str | None:
        pw, ok = QInputDialog.getText(
            self,
            title,
            f"Passwort für {SMB_USER}@{SMB_HOST}:",
            QLineEdit.EchoMode.Password,
        )
        if ok and pw:
            set_password(pw)
            return pw
        return None

    def change_password(self) -> None:
        pw = self._ask_password("Passwort ändern")
        if pw:
            self.status_label.setText("✅  Passwort im Keyring gespeichert.")

    # ── Verschiebevorgang ──────────────────────────────────────────────────────

    def start_move(self) -> None:
        if self._worker and self._worker.isRunning():
            return

        if not self._paths:
            self.status_label.setText("ℹ️  Keine Dateien im Quellverzeichnis.")
            return

        pw = self._ensure_password()
        if not pw:
            return

        self.btn_move.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.status_label.setText("⏳  Dateien werden verschoben …")

        self._worker = MoveWorker(list(self._paths), pw, self)
        self._worker.done.connect(self.on_move_done)
        self._worker.start()

    def on_move_done(self, results: list[tuple[str, str, str]]) -> None:
        self.btn_move.setEnabled(True)
        self.btn_refresh.setEnabled(True)

        dlg = ResultDialog(results, self)
        dlg.exec()
        self.refresh()


# ── Einstiegspunkt ─────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Flippermove")
    app.setOrganizationName("gecko1a")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
