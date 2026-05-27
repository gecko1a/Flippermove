# Flippermove

**Version 1.0**

Desktop-Tool für CachyOS/KDE (Python + PyQt6), das Pinball-Dateien und Verzeichnisse
aus einem lokalen Staging-Ordner auf einen Samba-Share verschiebt.

---

## Projektstand

| Datei | Inhalt |
|---|---|
| `flippermove.py` | Hauptprogramm |
| `flippermove.spec` | PyInstaller-Konfiguration |
| `build.fish` | Baut die Standalone-Binary (`dist/flippermove`) |
| `install.fish` | Installiert Binary + Icon ins KDE-Menü |
| `requirements.txt` | Python-Abhängigkeiten |
| `flippermove.png` | App-Icon (1008×1008) |
| `flippermove-256.png` | App-Icon (256×256) |
| `flippermove-48.png` | App-Icon (48×48) |

---

## Funktionsweise

- Zeigt alle Dateien **und Unterverzeichnisse** aus `/home/frank/Downloads/__Pinball/` an
- Verzeichnisse werden **cyan** dargestellt, unbekannte Dateitypen **grau**
- Die aktuelle **Versionsnummer** ist in der Titelleiste und oben rechts in der Oberfläche sichtbar
- Auf Knopfdruck werden folgende Typen automatisch zugeordnet und verschoben:

| Endung | Ziel auf dem Share |
|---|---|
| `.vpx` | `VisualPinball/Tables/` |
| `.directb2s` | `VisualPinball/Tables/` |
| `.pov` | `VisualPinball/Tables/` |
| `.zip` | `VisualPinball/VPinMAME/roms/` |

- Verzeichnisse und Dateien ohne Zuordnung → **Rückfrage**, ob sie nach `Transfer/` verschoben werden sollen
- Verzeichnisse werden **rekursiv** übertragen (komplette Unterstruktur)
- Das Samba-Passwort wird im **System-Keyring** gespeichert (kein Klartext)
- Nach dem Verschieben: Ergebnis-Dialog mit ✅ Erfolge / ❌ Fehler / ⏭️ Übersprungene
- Der Upload läuft in einem **Hintergrund-Thread** (UI bleibt reaktiv)

---

## Samba-Share-Struktur

```
smb://flipper@192.168.0.41/vPinball/
├── VisualPinball/
│   ├── Tables/          ← .vpx, .directb2s, .pov
│   └── VPinMAME/
│       └── roms/        ← .zip
└── Transfer/            ← alles ohne Kategorie (auf Anfrage)
```

---

## Voraussetzungen

```fish
# smbclient installieren
sudo pacman -S smbclient

# Python-Abhängigkeiten
pip install -r requirements.txt --break-system-packages
```

---

## App neu bauen und installieren

Nach jeder Änderung am Code oder an den Icons:

```fish
cd ~/projekte/Flippermove
git pull
fish build.fish      # erzeugt dist/flippermove (PyInstaller-Binary)
fish install.fish    # kopiert Binary + Icons, trägt ins KDE-Menü ein
```

Falls das Icon im Menü nicht sofort erscheint:

```fish
kbuildsycoca6 --noincremental
```

---

## Direkt als Script starten (ohne Build)

```fish
cd ~/projekte/Flippermove
python flippermove.py
```

Beim ersten Start wird das Samba-Passwort abgefragt und im Keyring gespeichert.
Das Passwort kann jederzeit über **„Passwort ändern"** aktualisiert werden.

---

## Konfiguration

Alle Verbindungsparameter und die Versionsnummer stehen am Anfang von `flippermove.py`:

```python
VERSION = "1.0"

SOURCE_DIR   = Path("/home/frank/Downloads/__Pinball")
SMB_HOST     = "192.168.0.41"
SMB_USER     = "flipper"
SMB_SHARE    = "vPinball"
TRANSFER_DIR = "Transfer"

ROUTES: dict[str, str] = {
    ".vpx":       "VisualPinball/Tables",
    ".directb2s": "VisualPinball/Tables",
    ".pov":       "VisualPinball/Tables",
    ".zip":       "VisualPinball/VPinMAME/roms",
}
```

Um einen neuen Dateityp hinzuzufügen: Eintrag in `ROUTES` ergänzen,
optional Icon-Emoji in `FILE_ICONS`, `VERSION` erhöhen, dann neu bauen.

---

## Versionsverlauf

| Version | Änderung |
|---|---|
| 1.0 | Initiale Version: .vpx/.directb2s/.pov/.zip, Verzeichnisse rekursiv, Transfer-Fallback, KDE-Menü-Integration |

---

## Deinstallieren

```fish
rm ~/.local/share/applications/flippermove.desktop
rm ~/.local/share/icons/hicolor/256x256/apps/flippermove.png
rm ~/.local/share/icons/hicolor/48x48/apps/flippermove.png
```
