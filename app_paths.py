"""Separate bundled read-only resources from persistent user data."""
import os
import sys
from pathlib import Path

RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
if os.environ.get('INKSHIELD_DATA_DIR'):
    DATA_ROOT = Path(os.environ['INKSHIELD_DATA_DIR']).expanduser().resolve()
elif getattr(sys, 'frozen', False):
    DATA_ROOT = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'Inkshield'
else:
    DATA_ROOT = RESOURCE_ROOT
RUNTIME_ROOT = DATA_ROOT / 'runtime'
