#!/usr/bin/env fish
# install.fish – Trägt Flippermove ins KDE-Anwendungsmenü ein
#
# Voraussetzung: vorher 'fish build.fish' ausgeführt haben
#
# Verwendung:
#   fish install.fish

set SCRIPT_DIR (dirname (realpath (status filename)))
set BINARY     $SCRIPT_DIR/dist/flippermove
set ICON_DIR   $HOME/.local/share/icons/hicolor
set DESK_DIR   $HOME/.local/share/applications

# ── Prüfen ob Binary existiert ────────────────────────────────────────────────
if not test -f $BINARY
    echo "❌  Binary nicht gefunden: $BINARY"
    echo "    Bitte zuerst 'fish build.fish' ausführen."
    exit 1
end

# ── Icons installieren ─────────────────────────────────────────────────────────
echo "==> Installiere Icons …"

mkdir -p $ICON_DIR/256x256/apps
mkdir -p $ICON_DIR/48x48/apps
mkdir -p $ICON_DIR/scalable/apps

cp $SCRIPT_DIR/flippermove-256.png $ICON_DIR/256x256/apps/flippermove.png
cp $SCRIPT_DIR/flippermove-48.png  $ICON_DIR/48x48/apps/flippermove.png
cp $SCRIPT_DIR/flippermove-256.png $ICON_DIR/scalable/apps/flippermove.png

# ── .desktop-Datei erstellen ─────────────────────────────────────────────────────
echo "==> Erstelle .desktop-Eintrag …"

mkdir -p $DESK_DIR

printf "[Desktop Entry]
Name=Flippermove
GenericName=Pinball File Mover
Comment=Pinball-Dateien auf Samba-Share verschieben
Exec=%s
Icon=flippermove
Terminal=false
Type=Application
Categories=Utility;FileTools;
Keywords=pinball;vpx;samba;transfer;
StartupNotify=true
" $BINARY > $DESK_DIR/flippermove.desktop

chmod +x $DESK_DIR/flippermove.desktop

# ── Icon-Cache aktualisieren ────────────────────────────────────────────────────
echo "==> Aktualisiere Icon-Cache …"
gtk-update-icon-cache -f -t $ICON_DIR 2>/dev/null; or true
update-desktop-database $DESK_DIR 2>/dev/null; or true
kbuildsycoca6 --noincremental 2>/dev/null; or \
    kbuildsycoca5 --noincremental 2>/dev/null; or true

echo ""
echo "✅  Flippermove ist jetzt im KDE-Menü eingetragen."
echo "    Suche nach 'Flippermove' oder schau unter Hilfsprogramme / Dienstprogramme."
echo ""
echo "    Zum Deinstallieren:"
echo "    rm $DESK_DIR/flippermove.desktop"
echo "    rm $ICON_DIR/256x256/apps/flippermove.png"
echo "    rm $ICON_DIR/48x48/apps/flippermove.png"
