"""Befehle für die Konsole."""

HELP = """OpenWallpaper

  openwallpaper                 Fenster oeffnen
  openwallpaper --restore       Zuletzt gesetztes Wallpaper starten (Autostart)
  openwallpaper --list          Bibliothek anzeigen
  openwallpaper --set NAME      Wallpaper setzen (ID oder Teil des Titels)
  openwallpaper --random        Zufaelliges Wallpaper
  openwallpaper --next          Naechstes Wallpaper
  openwallpaper --pause         Pausieren
  openwallpaper --resume        Fortsetzen
  openwallpaper --stop          Stoppen und GNOME-Hintergrund zuruecksetzen
  openwallpaper --status        Zeigt, was gerade laeuft
"""

COMMANDS = {"--restore", "--list", "--set", "--random", "--next", "--pause",
            "--resume", "--stop", "--status", "--help", "-h"}


def wants_cli(argv):
    return any(a in COMMANDS for a in argv)


def run(argv, out=print):
    from . import library
    cmd = next(a for a in argv if a in COMMANDS)
    rest = [a for a in argv if a != cmd and not a.startswith("-")]

    if cmd in ("--help", "-h"):
        out(HELP)
        return 0
    if cmd == "--restore":
        return 0 if library.restore() else 1
    if cmd == "--list":
        cur = library.load_config().get("current")
        for it in library.load_items():
            mark = "*" if it["id"] == cur else " "
            fav = "★" if it.get("fav") else " "
            out(f'{mark} {fav} {it["id"]}  {it["kind"]:5}  {it["title"]}\n')
        return 0
    if cmd == "--status":
        it = library.current_item()
        out(f'läuft: {library.is_running()}\naktuell: {it["title"] if it else "-"}\n')
        return 0
    if cmd == "--stop":
        library.stop_and_restore()
        return 0
    if cmd in ("--pause", "--resume"):
        library.set_config(paused=(cmd == "--pause"))
        return 0 if library.is_running() else 1

    if cmd == "--set":
        if not rest:
            out("Name oder ID fehlt\n")
            return 2
        it = library.find_item(" ".join(rest))
        if not it:
            out("Nichts gefunden\n")
            return 1
    elif cmd == "--random":
        it = library.random_item()
    else:
        it = library.next_item()
    if not it:
        out("Die Bibliothek ist leer\n")
        return 1
    library.apply(it)
    out(it["title"] + "\n")
    return 0
