import sys

from . import cli

argv = sys.argv[1:]
if cli.wants_cli(argv):
    from . import library
    library.NO_SPAWN = True
    try:
        sys.exit(cli.run(argv, out=sys.stdout.write))
    except library.NeedSpawn:
        library.NO_SPAWN = False

from .app import main

sys.exit(main())
