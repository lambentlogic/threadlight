"""
Background scheduler for memory decay.

Runs decay cycles periodically to fade unused memories.
This implements consentful forgetting -- memories naturally
fade unless reinforced through access.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from threadlight.decay.engine import DecayEngine, DecayResult

logger = logging.getLogger(__name__)


class DecayScheduler:
    """
    Background scheduler for running memory decay cycles.

    Periodically triggers decay on memories that haven't been accessed,
    allowing them to naturally fade over time. Sacred memories are
    never affected by decay.

    Features:
    - Configurable interval (default: 1 hour)
    - Graceful shutdown on app exit
    - Prevents concurrent decay passes
    - Handles errors gracefully (logs but doesn't crash)

    Example:
        scheduler = DecayScheduler(decay_engine, interval_seconds=3600)
        scheduler.start()
        # ... later ...
        scheduler.stop()

    Thread Safety:
        This class is thread-safe. The decay cycle runs in a background
        thread, and all state access is protected by locks.
    """

    def __init__(
        self,
        decay_engine: DecayEngine,
        interval_seconds: int = 3600,
        on_decay_complete: Optional[Callable[[DecayResult], None]] = None,
    ):
        """
        Initialize the decay scheduler.

        Args:
            decay_engine: The DecayEngine instance to use for decay cycles
            interval_seconds: Seconds between decay cycles (default: 3600 = 1 hour)
            on_decay_complete: Optional callback invoked after each decay cycle
        """
        self.decay_engine = decay_engine
        self.interval_seconds = interval_seconds
        self.on_decay_complete = on_decay_complete

        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._decay_lock = threading.Lock()

        # Statistics
        self._cycles_completed = 0
        self._last_run: Optional[datetime] = None
        self._last_result: Optional[DecayResult] = None

    @property
    def running(self) -> bool:
        """Check if the scheduler is currently running."""
        return self._running

    @property
    def cycles_completed(self) -> int:
        """Get the number of decay cycles completed."""
        return self._cycles_completed

    @property
    def last_run(self) -> Optional[datetime]:
        """Get the timestamp of the last decay run."""
        return self._last_run

    @property
    def last_result(self) -> Optional[DecayResult]:
        """Get the result of the last decay cycle."""
        return self._last_result

    def start(self) -> None:
        """
        Start the background decay scheduler.

        If already running, this is a no-op.
        """
        if self._running:
            logger.debug("Decay scheduler already running")
            return

        self._running = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_loop,
            name="DecayScheduler",
            daemon=True,  # Don't prevent app exit
        )
        self._thread.start()

        logger.info(
            f"Decay scheduler started (interval: {self.interval_seconds}s)"
        )

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the background decay scheduler.

        Args:
            timeout: Maximum seconds to wait for the thread to stop

        If already stopped, this is a no-op.
        """
        if not self._running:
            logger.debug("Decay scheduler not running")
            return

        logger.info("Stopping decay scheduler...")
        self._running = False
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(
                    "Decay scheduler thread did not stop within timeout"
                )
            self._thread = None

        logger.info("Decay scheduler stopped")

    def run_now(self) -> Optional[DecayResult]:
        """
        Run a decay cycle immediately.

        This can be called manually regardless of whether the scheduler
        is running. It respects the concurrency lock, so if a decay
        cycle is already in progress, this will return None.

        Returns:
            DecayResult if decay ran successfully, None if skipped
        """
        return self._run_decay_cycle()

    def _run_loop(self) -> None:
        """Main loop for the background thread."""
        logger.debug("Decay scheduler loop started")

        while self._running:
            # Wait for the interval or until stopped
            # Use wait() so we can be interrupted by stop()
            stopped = self._stop_event.wait(timeout=self.interval_seconds)

            if stopped:
                # Stop was requested
                break

            # Run a decay cycle
            self._run_decay_cycle()

        logger.debug("Decay scheduler loop ended")

    def _run_decay_cycle(self) -> Optional[DecayResult]:
        """
        Execute a single decay cycle.

        Uses a lock to prevent concurrent decay passes.
        Logs results and any errors.

        Returns:
            DecayResult if decay ran, None if skipped (already running)
        """
        # Try to acquire the lock without blocking
        acquired = self._decay_lock.acquire(blocking=False)
        if not acquired:
            logger.debug("Decay cycle skipped (already in progress)")
            return None

        try:
            logger.debug("Starting decay cycle...")
            start_time = datetime.utcnow()

            result = self.decay_engine.run_decay_cycle()

            self._last_run = start_time
            self._last_result = result
            self._cycles_completed += 1

            # Log the results
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(
                f"Decay cycle #{self._cycles_completed} completed: "
                f"{result.capsules_decayed}/{result.capsules_processed} decayed, "
                f"{result.capsules_dormant} dormant "
                f"({duration_ms:.1f}ms)"
            )

            # Invoke callback if provided
            if self.on_decay_complete:
                try:
                    self.on_decay_complete(result)
                except Exception as e:
                    logger.warning(f"Decay callback failed: {e}")

            return result

        except Exception as e:
            # Log but don't crash -- decay failures shouldn't break the app
            logger.error(f"Decay cycle failed: {e}", exc_info=True)
            return None

        finally:
            self._decay_lock.release()

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the scheduler.

        Returns:
            Dictionary with scheduler statistics
        """
        return {
            "running": self._running,
            "interval_seconds": self.interval_seconds,
            "cycles_completed": self._cycles_completed,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_result": self._last_result.to_dict() if self._last_result else None,
        }

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return (
            f"DecayScheduler({status}, "
            f"interval={self.interval_seconds}s, "
            f"cycles={self._cycles_completed})"
        )
