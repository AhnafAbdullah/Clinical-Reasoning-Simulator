"""Model Router (Vol 4A §14).

Maps an abstract profile to a concrete OpenRouter model id. The application
never hardcodes model names; it asks for a profile and the router resolves it
from configuration. ``fallbacks`` gives the Retry Manager an ordered list to
escalate through.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.domain.ai import ModelProfile


class ModelRouter:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _resolve(self, profile: ModelProfile) -> str:
        s = self._settings
        return {
            ModelProfile.DEFAULT: s.model_default,
            ModelProfile.REASONING: s.model_reasoning,
            ModelProfile.LATENCY: s.model_latency,
        }[profile]

    def select(self, profile: str | ModelProfile) -> str:
        return self._resolve(ModelProfile(profile))

    def fallbacks(self, profile: str | ModelProfile) -> list[str]:
        """Ordered models to try: the profile's model first, then a more capable
        fallback, de-duplicated while preserving order."""
        primary = self.select(profile)
        candidates = [primary, self._settings.model_reasoning, self._settings.model_default]
        ordered: list[str] = []
        for model in candidates:
            if model and model not in ordered:
                ordered.append(model)
        return ordered
