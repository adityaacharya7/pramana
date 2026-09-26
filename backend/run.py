"""Run the CLI from any working directory:  python backend/run.py serve --demo"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pramana.cli import main  # noqa: E402

main()
