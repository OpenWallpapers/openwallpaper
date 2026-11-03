"""Befehle für die Konsole."""
from .i18n import tr

def help_text():
    rows = [
        ("openwallpaper", tr("Open the window")),
        ("openwallpaper --restore", tr("Start the last wallpaper (autostart)")),
        ("openwallpaper --list", tr("Show the library")),
        ("openwallpaper --set NAME", tr("Set a wallpaper (ID or part of the title)")),
        ("openwallpaper --random", tr("Random wallpaper")),
        ("openwallpaper --next", tr("Next wallpaper")),
        ("openwallpaper --pause", tr("Pause")),
        ("openwallpaper --resume", tr("Resume")),
        ("openwallpaper --stop", tr("Stop and restore the GNOME background")),
        ("openwallpaper --status", tr("Show what is running")),
    ]
    return "OpenWallpaper\n\n" + "\n".join(f"  {a:<28}{b}" for a, b in rows) + "\n"


COMMANDS = {"--restore", "--list", "--set", "--random", "--next", "--pause",
            "--resume", "--stop", "--status", "--help", "-h"}


def wants_cli(argv):
    return any(a in COMMANDS for a in argv)


def run(argv, out=print):
    from . import library
    cmd = next(a for a in argv if a in COMMANDS)
    rest = [a for a in argv if a != cmd and not a.startswith("-")]

    if cmd in ("--help", "-h"):
        out(help_text())
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
        out(tr("running: {}\ncurrent: {}\n").format(tr("yes") if library.is_running() else tr("no"),
                                                         it["title"] if it else "-"))
        return 0
    if cmd == "--stop":
        library.stop_and_restore()
        return 0
    if cmd in ("--pause", "--resume"):
        library.set_config(paused=(cmd == "--pause"))
        return 0 if library.is_running() else 1

    if cmd == "--set":
        if not rest:
            out(tr("Name or ID missing") + "\n")
            return 2
        it = library.find_item(" ".join(rest))
        if not it:
            out(tr("Nothing found") + "\n")
            return 1
    elif cmd == "--random":
        it = library.random_item()
    else:
        it = library.next_item()
    if not it:
        out(tr("The library is empty") + "\n")
        return 1
    library.apply(it)
    out(it["title"] + "\n")
    return 0
