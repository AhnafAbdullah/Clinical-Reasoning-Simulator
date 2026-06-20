"""Agent registry (Vol 4C).

Maps an agent capability to the template it uses and its decoding temperature.
The model itself is chosen by the Model Router from the template's profile, so
agents never name models. Adding an agent is adding an entry here plus a
versioned template in the registry.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings

PATIENT = "patient"
EXAMINER = "examiner"


@dataclass(frozen=True)
class AgentSpec:
    name: str
    prompt_id: str
    temperature: float


def get_agent_specs(settings: Settings | None = None) -> dict[str, AgentSpec]:
    s = settings or get_settings()
    return {
        PATIENT: AgentSpec(PATIENT, prompt_id="patient", temperature=s.llm_temperature_patient),
        EXAMINER: AgentSpec(EXAMINER, prompt_id="examiner", temperature=s.llm_temperature_examiner),
    }
