"""The five seed rows from PRD 3.3, inserted by server/db.py when the rows table is empty."""
from datetime import datetime, timedelta

# batch_no, machine, temperature_c, rejects
SEED = [(9, "Oven 1", 178, 1), (10, "Oven 2", 182, 0), (11, "Oven 1", 196, 2), (12, "Oven 2", 181, 7), (13, "Oven 1", 176, 3)]


def seed_rows(start: datetime) -> list[tuple[datetime, dict]]:
    """(created_at, fields) pairs, oldest first, 40 minutes apart from `start` (three hours before first start)."""
    return [(start + timedelta(minutes=40 * i),
             {"batch_no": b, "machine": m, "temperature_c": t, "rejects": r,
              "transcript": "", "source": "seed", "audio_url": None})
            for i, (b, m, t, r) in enumerate(SEED)]
