"""LLM-assisted triage. The model may only recommend a key from the runbook registry."""

import json
import logging

from greenlight.core.config import settings
from greenlight.core.privacy import redact_for_llm
from greenlight.schemas import Severity, TriageDiagnosis
from greenlight.services.runbooks import RUNBOOKS

logger = logging.getLogger("greenlight.triage")

SYSTEM_PROMPT = (
    "You triage production incidents from log excerpts. Return only JSON with root_cause, "
    "severity (P0/P1/P2), suggested_fix, remediation_key, confidence_score. "
    f"The remediation_key MUST be one of: {', '.join(sorted(RUNBOOKS))}. "
    "If none clearly applies, return null for remediation_key. Never emit shell syntax. "
    "suggested_fix is descriptive only."
)


def no_recommendation(reason: str, source_severity: Severity = Severity.P1) -> TriageDiagnosis:
    return TriageDiagnosis(
        root_cause=f"No automated diagnosis available: {reason}",
        severity=source_severity,
        suggested_fix="Manual investigation required. No remediation runbook was recommended.",
        remediation_key=None,
        confidence_score=0.0,
    )


def sanitize_diagnosis(diagnosis: TriageDiagnosis) -> TriageDiagnosis:
    """The runbook registry is authoritative; the model cannot expand execution authority."""
    if diagnosis.remediation_key is not None and diagnosis.remediation_key not in RUNBOOKS:
        logger.warning({"event": "triage_key_rejected", "remediation_key": diagnosis.remediation_key[:64]})
        return diagnosis.model_copy(
            update={
                "remediation_key": None,
                "confidence_score": 0.0,
                "suggested_fix": (
                    "Model proposed a remediation outside the approved runbook set. " "Manual investigation required."
                ),
            }
        )
    return diagnosis


async def analyze(
    service_name: str,
    host_ip: str,
    error_trace: str,
    source_severity: Severity = Severity.P1,
) -> TriageDiagnosis:
    if not settings.llm_api_key:
        return no_recommendation("LLM triage is not configured", source_severity)

    try:
        from openai import AsyncOpenAI  # imported lazily: only needed when triage is configured

        client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Service: {service_name}\nHost: {host_ip}\n"
                        f"Source severity: {source_severity.value}\n"
                        f"Log:\n{redact_for_llm(error_trace)}"
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        diagnosis = TriageDiagnosis.model_validate(json.loads(content))
    except Exception:
        logger.exception("llm triage failed")
        return no_recommendation("LLM triage failed or returned invalid output", source_severity)

    return sanitize_diagnosis(diagnosis)
