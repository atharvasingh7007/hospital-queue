"""
Hospital Queue AI — Event Bus
In-memory pub/sub system for agent-to-agent communication.
Agents publish events, other agents react autonomously.
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger("hospital_queue.event_bus")


class EventBus:
    """Lightweight event bus enabling direct agent-to-agent communication."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._event_log: list[dict] = []
        self._max_log = 200

    def subscribe(self, event_type: str, handler: Callable):
        """Register a handler for an event type."""
        self._subscribers[event_type].append(handler)
        logger.info("Subscribed %s to '%s'", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: Callable):
        """Remove a handler from an event type."""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    async def publish(self, event_type: str, data: dict, source_agent: str = "system"):
        """Publish an event to all subscribers. Non-blocking."""
        event = {
            "type": event_type,
            "data": data,
            "source": source_agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._event_log.append(event)
        if len(self._event_log) > self._max_log:
            self._event_log = self._event_log[-self._max_log:]

        logger.info("[EVENT] %s → %s (from %s)", event_type, data.get("summary", ""), source_agent)

        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.error("Event handler %s failed: %s", handler.__name__, exc)

    def get_recent_events(self, limit: int = 20, event_type: str = None) -> list[dict]:
        """Get recent events from the log."""
        events = self._event_log
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        return events[-limit:]

    def get_stats(self) -> dict:
        """Get event bus statistics."""
        type_counts = defaultdict(int)
        for e in self._event_log:
            type_counts[e["type"]] += 1
        return {
            "total_events": len(self._event_log),
            "event_types": dict(type_counts),
            "subscriber_count": sum(len(h) for h in self._subscribers.values()),
        }


# Global singleton
event_bus = EventBus()


# ── Event Type Constants ──────────────────────────────

class Events:
    EMERGENCY_DETECTED = "emergency.detected"
    QUEUE_REBALANCED = "queue.rebalanced"
    DELAY_PREDICTED = "delay.predicted"
    PATIENT_NOTIFIED = "patient.notified"
    AGENT_HANDOFF = "agent.handoff"
    TRIAGE_COMPLETED = "triage.completed"
    QUEUE_POSITION_CHANGED = "queue.position_changed"
    DOCTOR_STATUS_CHANGED = "doctor.status_changed"
    CONSULTATION_COMPLETED = "consultation.completed"
