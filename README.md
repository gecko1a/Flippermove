# Flippermove

Kleines Desktop-Tool für CachyOS/KDE, das Pinball-Dateien aus einem lokalen Download-Ordner auf einen Samba-Share verschiebt.

## Funktionsweise

- Zeigt alle Dateien aus `/home/frank/Downloads/__Pinball/` an
- Auf Knopfdruck werden folgende Dateitypen verschoben:

| Endung | Ziel auf dem Share |
|---|---|
| `.vpx` | `VisualPinball/Tables/` |
| `.directb2s` | `VisualPinball/Tables/` |
| `.zip` | `VPinMAME/roms/` |

- Alle anderen Dateitypen werden grau dargestellt und nicht angefasst
- Das Passwort wird sicher im System-Keyring gespeichert (kein Klartext)
- Nach dem Verschieben gibt es eine Zusammenfassung (Erfolge, Fehler, Übersprungene)

## Voraussetzungen

```
# smbclient muss installiert sein
sudo pacman -S smbclient

# Python-Abhängigkeiten
pip install -r requirements.txt
```

## Starten

```
python flippermove.py
```

Beim ersten Start wird das Samba-Passwort abgefragt und im Keyring gespeichert.  
Das Passwort kann jederzeit über **„Passwort ändern"** aktualisiert werden.

## Konfiguration

Die Verbindungsparameter stehen am Anfang von `flippermove.py`:

```python
SOURCE_DIR  = Path("/home/frank/Downloads/__Pinball")
SMB_HOST    = "192.168.0.41"
SMB_USER    = "flipper"
SMB_SHARE   = "vPinball"
```
