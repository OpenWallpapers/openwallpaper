# OpenWallpaper

Live-Wallpaper für Linux. Videos und Bilder als Desktop-Hintergrund, mit einer kleinen Bibliothek und einer Mediathek, aus der du direkt Wallpaper laden kannst.

Läuft unter **X11**. Wayland wird noch nicht unterstützt. Getestet habe ich es unter GNOME mit X11.

## Installieren

Du brauchst Flatpak und die GNOME-Runtime 50:

```sh
flatpak install flathub org.gnome.Sdk//50 org.gnome.Platform//50 org.flatpak.Builder
git clone https://github.com/OpenWallpapers/openwallpaper.git
cd openwallpaper
flatpak run org.flatpak.Builder --user --install --force-clean build-dir io.github.openwallpapers.OpenWallpaper.yml
flatpak run io.github.openwallpapers.OpenWallpaper
```

Ohne Flatpak brauchst du Python 3 mit PyGObject, GTK 4, libadwaita und GStreamer (mit den Plugins good, bad und libav sowie der Ausgabe für OpenGL und X11). Dann startest du mit `./openwallpaper.sh`.

## Was es kann

Du setzt ein Video oder Bild als Hintergrund, und es läuft weiter, auch wenn du das Fenster schließt. Die Bibliothek hat Suche, Favoriten und Tags. Dateien und ganze Ordner holst du per Menü oder Drag and Drop hinein, Duplikate werden erkannt.

Dazu kommen:

- eigene Wallpaper pro Monitor
- Diashow mit einstellbarem Intervall, auf Wunsch nur mit Favoriten oder einem Tag
- Wechsel zwischen Tag- und Nacht-Wallpaper nach Uhrzeit
- Pause bei Vollbild-Fenstern und im Akkubetrieb, Bildrate begrenzen, optional Ton
- Autostart und eine Sicherung der Bibliothek als ZIP

## Mediathek

| Quelle | Inhalt | Schlüssel nötig |
|---|---|---|
| Wallhaven | Bilder | nur für nicht jugendfreie Inhalte |
| Pixabay | Videos | ja, kostenlos |
| Wikimedia Commons | Videos mit freier Lizenz | nein |

Wallhaven kennt nur englische Tags. Deshalb übersetzt OpenWallpaper gängige deutsche Wörter selbst: aus `dunkler Wald` wird `dark forest`. Die Operatoren von Wallhaven gehen auch: `+forest +fog`, `forest -people`, `"dark forest"`, `@nutzer`, `like:ID`. Die Bilder dort haben keine Namen, nur IDs. Beim Anklicken lädt die App die Tags nach und bildet einen Titel daraus.

Die Wallhaven-Bilder sind nicht frei lizenziert, die Rechte bleiben bei den Urhebern. Wikimedia zeigt Lizenz und Urheber bei jedem Eintrag an. Die Inhalte von Wallpaper Engine lassen sich nicht über eine Mediathek anbinden. Wer das Spiel besitzt, kann seine Video-Wallpaper aber über das Menü importieren. Szenen und Web-Wallpaper gehen nicht.

Pexels fehlt, weil die API-Regeln Wallpaper-Apps ausschließen.

## Konsole

Praktisch für Tastenkürzel:

```sh
flatpak run io.github.openwallpapers.OpenWallpaper --next
flatpak run io.github.openwallpapers.OpenWallpaper --random
flatpak run io.github.openwallpapers.OpenWallpaper --set "Titel oder ID"
```

Außerdem `--pause`, `--resume`, `--stop`, `--status` und `--list`. Ohne Flatpak: `python3 -m openwallpaper --next`.

## Übersicht und Sperrbildschirm unter GNOME

GNOME zeichnet den Hintergrund in der Übersicht selbst. Deshalb setzt OpenWallpaper ein Standbild des Videos als normalen Hintergrund. Ohne Flatpak passiert das von allein. Das Flatpak kommt nicht an die GNOME-Einstellungen heran, dafür gibt es eine kleine Erweiterung:

```sh
./gnome-extension/install.sh
gnome-extensions enable openwallpaper-bg@openwallpapers.github.io
```

Die Erweiterung habe ich noch nicht getestet.

## Bekannte Grenzen

- Nur X11. Für Wayland bräuchte es einen eigenen Renderer.
- Desktop-Symbole, die ein anderes Programm zeichnet, können je nach Fenstermanager über dem Wallpaper liegen.
- Videos auf Wikimedia gibt es teils nur als riesiges Original. Alles über 300 MB lädt die App nicht.

## Ähnliche Projekte

[Hidamari](https://github.com/jeffshee/hidamari), [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) und [mpvpaper](https://github.com/GhostNaN/mpvpaper). Von dort ist kein Code übernommen.

## Lizenz

GPL-3.0-or-later, siehe [LICENSE](LICENSE).
