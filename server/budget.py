"""Daily caps on Sarvam spend, counted per Asia/Kolkata day. Both limits are read from the environment on every call:
SARVAM_DAILY_STT_CALLS (speech-to-text requests sent) and SARVAM_DAILY_TTS_CHARS (characters sent to text-to-speech;
a phrase served from the voice cache costs nothing). Unset or empty means no limit, so a local or Docker run with a
tester's own key behaves as before. "0" turns that half of Sarvam off."""
import os
import threading

from .events import today

STT_CALLS = "SARVAM_DAILY_STT_CALLS"
TTS_CHARS = "SARVAM_DAILY_TTS_CHARS"

# ponytail: the counters live in memory, so a restart resets them; the ceiling is one extra day's spend per restart.
# Keep them in the database if the host starts restarting often.
_lock = threading.Lock()
_day = None
_used = {}


class BudgetReached(Exception):
    """Sending this request would pass today's limit; nothing was counted and nothing was sent."""


def spend(limit_var: str, amount: int) -> None:
    """Counts `amount` against today's limit named by `limit_var`, or raises BudgetReached when it would pass it.
    Call it just before the request goes to Sarvam."""
    raw = os.environ.get(limit_var, "").strip()
    if not raw:
        return
    limit = int(raw)  # a value that is not a whole number fails every call (500) rather than spend without a cap
    global _day
    with _lock:
        day = today()
        if day != _day:
            _day = day
            _used.clear()
        if _used.get(limit_var, 0) + amount > limit:
            raise BudgetReached(limit_var)
        _used[limit_var] = _used.get(limit_var, 0) + amount
