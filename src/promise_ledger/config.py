from datetime import date
from pathlib import Path
import random

SEED = 42
SIMULATION_DATE = date(2026, 8, 31)
ROOT_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = ROOT_DIR / "data" / "promise_ledger.db"


def make_rng() -> random.Random:
    """Return the single seeded RNG used by a generation run."""
    return random.Random(SEED)

