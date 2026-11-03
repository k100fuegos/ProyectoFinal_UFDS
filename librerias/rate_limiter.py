import os
import time
import math
import threading
from typing import Optional, Tuple
from fastapi import Request
from dotenv import load_dotenv

load_dotenv()


class LoginRateLimiter:
    """
    Controlador de límite de intentos para inicio de sesión en memoria y seguro para hilos.
    Bloquea temporalmente un usuario/IP al alcanzar 3 intentos fallidos (por defecto),
    con incremento progresivo/exponencial del tiempo de espera en bloqueos consecutivos.
    """

    def __init__(
        self,
        max_attempts: Optional[int] = None,
        lockout_seconds: Optional[int] = None,
        max_lockout_seconds: Optional[int] = None,
        lockout_multiplier: Optional[float] = None,
        escalation_window: Optional[int] = None,
    ):
        if max_attempts is None:
            max_attempts = int(os.getenv("LOGIN_MAX_ATTEMPTS", "3"))
        if lockout_seconds is None:
            lockout_seconds = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "60"))
        if max_lockout_seconds is None:
            max_lockout_seconds = int(os.getenv("LOGIN_MAX_LOCKOUT_SECONDS", "900"))
        if lockout_multiplier is None:
            lockout_multiplier = float(os.getenv("LOGIN_LOCKOUT_MULTIPLIER", "2.0"))
        if escalation_window is None:
            escalation_window = int(os.getenv("LOGIN_ESCALATION_RESET_SECONDS", "1800"))

        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self.max_lockout_seconds = max_lockout_seconds
        self.lockout_multiplier = lockout_multiplier
        self.escalation_window = escalation_window
        self._records: dict[str, dict] = {}
        self._lock = threading.Lock()

    def get_client_key(self, request: Request, username: str) -> str:
        client_ip = "127.0.0.1"
        if request.headers.get("x-forwarded-for"):
            forwarded = request.headers.get("x-forwarded-for", "")
            client_ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host

        clean_username = (username or "").strip().lower()
        return f"{client_ip}:{clean_username}"

    def is_locked(self, key: str) -> Tuple[bool, int]:
        now = time.time()
        with self._lock:
            record = self._records.get(key)
            if not record:
                return False, 0

            locked_until = record.get("locked_until", 0)
            if locked_until > now:
                remaining = max(1, math.ceil(locked_until - now))
                return True, remaining

            if record.get("attempts", 0) >= self.max_attempts:
                record["attempts"] = 0
                record["locked_until"] = 0

            if now - record.get("last_attempt", 0) > self.escalation_window:
                record["lockout_count"] = 0

            return False, 0

    def record_failure(self, key: str) -> Tuple[int, bool, int]:
        now = time.time()
        with self._lock:
            self._cleanup_stale_entries(now)

            record = self._records.setdefault(
                key,
                {
                    "attempts": 0,
                    "locked_until": 0,
                    "last_attempt": now,
                    "lockout_count": 0,
                },
            )

            if record["locked_until"] > 0 and record["locked_until"] <= now:
                record["attempts"] = 0
                record["locked_until"] = 0

            if now - record.get("last_attempt", 0) > self.escalation_window:
                record["lockout_count"] = 0

            record["attempts"] += 1
            record["last_attempt"] = now

            if record["attempts"] >= self.max_attempts:
                record["lockout_count"] = record.get("lockout_count", 0) + 1
                exponent = max(0, record["lockout_count"] - 1)
                wait_time = int(
                    min(
                        self.lockout_seconds * (self.lockout_multiplier ** exponent),
                        self.max_lockout_seconds,
                    )
                )
                record["locked_until"] = now + wait_time
                return record["attempts"], True, wait_time

            return record["attempts"], False, 0

    def record_success(self, key: str) -> None:
        with self._lock:
            self._records.pop(key, None)

    def reset_all(self) -> None:
        with self._lock:
            self._records.clear()

    def _cleanup_stale_entries(self, now: float) -> None:
        if len(self._records) < 500:
            return

        stale_threshold = max(self.escalation_window, 1800)
        keys_to_remove = [
            k
            for k, v in self._records.items()
            if (now - v.get("last_attempt", 0) > stale_threshold)
            and (v.get("locked_until", 0) <= now)
        ]
        for k in keys_to_remove:
            self._records.pop(k, None)


login_rate_limiter = LoginRateLimiter()
