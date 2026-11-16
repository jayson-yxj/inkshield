"""Launch Inkshield with ``python -m inkshield``."""
import multiprocessing

from .desktop import main


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
