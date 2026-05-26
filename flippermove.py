#!/usr/bin/env python3
"""
Flippermove – verschiebt Pinball-Dateien und -Verzeichnisse auf einen Samba-Share.
"""

import sys
import shutil
import subprocess
from pathlib import Path

import keyring
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QDialog, QTextEdit, QDialogButtonBox,
    QInputDialog, QLineEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# ── Konfiguration ──────────────────────────────────────────────────────────────
SOURCE_DIR   = Path("/home/frank/Downloads/__Pinball")
SMB_HOST     = "192.168.0.41"
SMB_USER     = "flipper"
SMB_SHARE    = "vPinball"
KEYRING_SVC  = "flippermove"
TRANSFER_DIR = "Transfer"

ROUTES: dict[str, str] = {
    ".vpx":       "VisualPinball/Tables",
    ".directb2s": "VisualPinball/Tables",
    ".zip":       "VisualPinball/VPinMAME/roms",
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


def _smb_run(commands: list[str], password: str, timeout: int = 120) -> tuple[bool, str]:
    """Führt eine Liste von smbclient-Kommandos in einem einzigen Aufruf aus."""
    cmd = [
        "smbclient",
        f"//{SMB_HOST}/{SMB_SHARE}",
        f"--user={SMB_USER}%{password}",
        "-c", "; ".join(commands),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    if result.returncode != 0 or "NT_STATUS" in stdout or "NT_STATUS" in stderr:
        detail = stderr or stdout or f"Exit-Code {result.returncode}"
        return False, detail
    return True, ""


def smb_put(local_path: Path, remote_dir: str, password: str) -> tuple[bool, str]:
    """Überträgt eine einzelne Datei auf den Share."""
    return _smb_run(
        [f'put "{local_path}" "{remote_dir}/{local_path.name}"'],
        password,
    )


def smb_put_dir(local_dir: Path, remote_base: str, password: str) -> tuple[bool, str]:
    """Überträgt ein Verzeichnis rekursiv auf den Share.

    Erstellt zuerst alle nötigen Unterverzeichnisse, dann lädt es alle
    Dateien hoch – alles in einem smbclient-Aufruf pro Batch.
    """
    dir_name   = local_dir.name
    remote_top = f"{remote_base}/{dir_name}"

    # Alle Einträge sortiert sammeln (Verzeichnisse vor Dateien)
    all_items = sorted(local_dir.rglob("*"))
    dirs  = [p for p in all_items if p.is_dir()]
    files = [p for p in all_items if p.is_file()]

    commands: list[str] = []

    # Zielverzeichnis anlegen
    commands.append(f'mkdir "{remote_top}"')

    # Unterverzeichnisse anlegen
    for d in dirs:
        rel          = d.relative_to(local_dir)
        remote_path  = f"{remote_top}/{rel.as_posix()}"
        commands.append(f'mkdir "{remote_path}"')

    # Dateien hochladen
    for f in files:
        rel         = f.relative_to(local_dir)
        remote_path = f"{remote_top}/{rel.parent.as_posix()}" if rel.parent != Path(".") \
                      else remote_top
        commands.append(f'put "{f}" "{remote_path}/{f.name}"')

    if not commands:
        return True, ""  # leeres Verzeichnis – trotzdem Erfolg

    ok, err = _smb_run(commands, password, timeout=600)
    return ok, err


# ── Transfer-Rückfrage-Dialog ──────────────────────────────────────────────────

class TransferDialog(QDialog):
    """Listet Dateien/Verzeichnisse ohne Kategorie und fragt nach Transfer/."""

    def __init__(self, unknown: list[Path], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keine Kategorie zugeordnet")
        self.resize(580, 360)
        layout = QVBoxLayout(self)

        dirs  = [p for p in unknown if p.is_dir()]
        files = [p for p in unknown if p.is_file()]

        parts = []
        if files:
            parts.append(f"{len(files)} Datei(en) unbekannten Typs")
        if dirs:
            parts.append(f"{len(dirs)} Verzeichnis(se)")
        summary = " und ".join(parts)

        info = QLabel(
            f"{summary} können keiner Zielkategorie zugeordnet werden.\n"
            "Sollen sie nach <b>Transfer/</b> verschoben werden?"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setWordWrap(True)
        layout.addWidget(info)

        lst = QListWidget()
        lst.setFont(QFont("Monospace", 10))
        for p in unknown:
            icon = "📁" if p.is_dir() else "📄"
            lst.addItem(f"{icon}  {p.name}")
        layout.addWidget(lst)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        bb.button(QDialogButtonBox.StandardButton.Yes).setText("Ja, nach Transfer/ verschieben")
        bb.button(QDialogButtonBox.StandardButton.No).setText("Nein, überspringen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)


# ── Worker-Thread ──────────────────────────────────────────────────────────────

class MoveWorker(QThread):
    """Führt Upload + lokales Löschen im Hintergrund durch."""

    # (name, status, detail)
    # status: "ok" | "error" | "del_error" | "skipped"
    done = pyqtSignal(list)

    def __init__(
        self,
        items: list[Path],
        password: str,
        move_unknown: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.items        = items
        self.password     = password
        self.move_unknown = move_unknown

    def run(self) -> None:
        results: list[tuple[str, str, str]] = []

        for item in self.items:
            is_dir = item.is_dir()
            ext    = item.suffix.lower() if not is_dir else ""

            # Ziel bestimmen
            if not is_dir and ext in ROUTES:
                remote_dir = ROUTES[ext]
            elif self.move_unknown:
                remote_dir = TRANSFER_DIR
            else:
                results.append((item.name, "skipped", "Kein Ziel zugeordnet"))
                continue

            # Upload
            if is_dir:
                ok, err = smb_put_dir(item, remote_dir, self.password)
            else:
                ok, err = smb_put(item, remote_dir, self.password)

            if ok:
                try:
                    if is_dir:
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    results.append((item.name, "ok", remote_dir))
                except OSError as e:
                    results.append((item.name, "del_error", str(e)))
            else:
                results.append((item.name, "error", err))

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
        text.setPlainText("\n".join(lines) if lines else "Keine Einträge verarbeitet.")
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
        self._items: list[Path] = []   # Dateien UND Verzeichnisse

        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setSpacing(8)

        hdr = QLabel(f"📁  {SOURCE_DIR}")
        hdr.setFont(QFont("Sans", 10, QFont.Weight.Bold))
        vbox.addWidget(hdr)

        self.file_list = QListWidget()
        self.file_list.setFont(QFont("Monospace", 10))
        self.file_list.setAlternatingRowColors(True)
        vbox.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄  Aktualisieren")
        self.btn_move    = QPushButton("🚀  Verschieben")
        self.btn_pw      = QPushButton("🔑  Passwort ändern")
        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_move)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_pw)
        vbox.addLayout(btn_row)

        self.status_label = QLabel("")
        vbox.addWidget(self.status_label)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_move.clicked.connect(self.start_move)
        self.btn_pw.clicked.connect(self.change_password)

        self.refresh()

    # ── Verzeichnis einlesen ───────────────────────────────────────────────────

    def refresh(self) -> None:
        self.file_list.clear()
        self._items.clear()

        if not SOURCE_DIR.exists():
            self.status_label.setText(f"⚠️  Verzeichnis nicht gefunden: {SOURCE_DIR}")
            return

        # Verzeichnisse zuerst, dann Dateien – jeweils alphabetisch
        entries = sorted(SOURCE_DIR.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))

        for entry in entries:
            if entry.is_dir():
                item = QListWidgetItem(f"📁  {entry.name}/")
                item.setForeground(Qt.GlobalColor.darkCyan)
            else:
                ext  = entry.suffix.lower()
                icon = FILE_ICONS.get(ext, "📄")
                item = QListWidgetItem(f"{icon}  {entry.name}")
                if ext not in ROUTES:
                    item.setForeground(Qt.GlobalColor.gray)

            self.file_list.addItem(item)
            self._items.append(entry)

        n_dirs     = sum(1 for p in self._items if p.is_dir())
        n_files    = sum(1 for p in self._items if p.is_file())
        n_moveable = sum(1 for p in self._items if p.is_file() and p.suffix.lower() in ROUTES)
        n_unknown  = (n_files - n_moveable) + n_dirs

        parts = []
        if n_dirs:
            parts.append(f"{n_dirs} Verzeichnis(se)")
        if n_files:
            parts.append(f"{n_files} Datei(en), davon {n_moveable} zugeordnet")
        if n_unknown:
            parts.append(f"{n_unknown} ohne Ziel (grau/cyan)")
        self.status_label.setText("  |  ".join(parts) if parts else "Verzeichnis ist leer.")

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

        if not self._items:
            self.status_label.setText("ℹ️  Keine Einträge im Quellverzeichnis.")
            return

        pw = self._ensure_password()
        if not pw:
            return

        # Einträge ohne zugeordnetes Ziel ermitteln
        unknown = [
            p for p in self._items
            if p.is_dir() or p.suffix.lower() not in ROUTES
        ]
        move_unknown = False
        if unknown:
            dlg = TransferDialog(unknown, self)
            move_unknown = dlg.exec() == QDialog.DialogCode.Accepted

        self.btn_move.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.status_label.setText("⏳  Wird verschoben …")

        self._worker = MoveWorker(list(self._items), pw, move_unknown, self)
        self._worker.done.connect(self.on_move_done)
        self._worker.start()

    def on_move_done(self, results: list[tuple[str, str, str]]) -> None:
        self.btn_move.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        ResultDialog(results, self).exec()
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
