#!/usr/bin/env fish
# build.fish – Baut Flippermove als eigenständige Binärdatei via PyInstaller
#
# Verwendung:
#   fish build.fish

set SCRIPT_DIR (dirname (realpath (status filename)))
cd $SCRIPT_DIR

echo "==> Prüfe PyInstaller …"
if not command -q pyinstaller
    echo "    PyInstaller nicht gefunden, wird installiert …"
    pip install pyinstaller --break-system-packages -q
    or begin
        echo "❌  Installation fehlgeschlagen."
        exit 1
    end
end

echo "==> Prüfe Pillow (für Icon-Konvertierung) …"
python3 -c "import PIL" 2>/dev/null
or pip install Pillow --break-system-packages -q

echo "==> Starte Build …"
pyinstaller flippermove.spec --noconfirm
or begin
    echo "❌  Build fehlgeschlagen."
    exit 1
end

echo ""
echo "✅  Fertig! Binary liegt unter:"
echo "    $SCRIPT_DIR/dist/flippermove"
echo ""
echo "    Jetzt 'fish install.fish' ausführen, um ins KDE-Menü einzutragen."
