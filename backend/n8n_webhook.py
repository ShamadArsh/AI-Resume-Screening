# ============================================================
# backend/n8n_webhook.py — n8n Webhook Client
# ============================================================
# Sends candidate data to an n8n workflow webhook which handles
# all workflow automation:
#   - Google Calendar event creation
#   - Google Meet link generation
#   - Gmail interview invitation
#   - Airtable status update
#
# This module is the ONLY bridge between FastAPI and n8n.
# If n8n is unavailable, the call degrades gracefully — the
# AI pipeline result is returned regardless.
# ============================================================

from __future__ import annotations

from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import settings
from utils.logger import logger

__all__ = ["N8nWebhookClient", "notify_n8n", "WebhookPayload"]


# ------------------------------------------------------------------
# Typed payload model
# ------------------------------------------------------------------
class WebhookPayload:
    """
    Strongly-typed payload sent to the n8n webhook.

    Matches the spec contract:
        {
            "candidate_name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "+1-555-0100",
            "match_score": 92,
            "application_status": "Shortlisted",
            "candidate_id": "recXXXXX",
            "skills": ["Python", "FastAPI"],
            "matching_skills": ["Python"],
            "missing_skills": ["Celery"],
            "ai_summary": "Strong candidate...",
            "recommendation": "Strongly Recommended"
        }
    """

    def __init__(
        self,
        candidate_name: str,
        email: str,
        phone: str,
        match_score: int,
        application_status: str,
        candidate_id: str = "",
        skills: Optional[list[str]] = None,
        matching_skills: Optional[list[str]] = None,
        missing_skills: Optional[list[str]] = None,
        ai_summary: str = "",
        recommendation: str = "",
    ):
        self.candidate_name = candidate_name
        self.email = email
        self.phone = phone
        self.match_score = match_score
        self.application_status = application_status
        self.candidate_id = candidate_id
        self.skills = skills or []
        self.matching_skills = matching_skills or []
        self.missing_skills = missing_skills or []
        self.ai_summary = ai_summary
        self.recommendation = recommendation

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_name": self.candidate_name,
            "email": self.email,
            "phone": self.phone,
            "match_score": self.match_score,
            "application_status": self.application_status,
            "candidate_id": self.candidate_id,
            "skills": self.skills,
            "matching_skills": self.matching_skills,
            "missing_skills": self.missing_skills,
            "ai_summary": self.ai_summary,
            "recommendation": self.recommendation,
        }


# ------------------------------------------------------------------
# Webhook client with retry
# ------------------------------------------------------------------
class N8nWebhookClient:
    """
    HTTP client that POSTs candidate data to an n8n webhook.

    Retries on connection errors and 5xx responses with exponential
    backoff (0.5s → 1s → 2s).  After 3 attempts it logs the failure
    and returns a failure dict — it never raises.
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.webhook_url = webhook_url if webhook_url is not None else settings.n8n_webhook_url
        self.api_key = api_key if api_key is not None else settings.n8n_api_key
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def is_configured(self) -> bool:
        """True if a non-empty webhook URL is set."""
        return bool(self.webhook_url)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key
        return headers

    @retry(
        retry=retry_if_exception_type(
            (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=False,
    )
    def _post_with_retry(self, payload: dict[str, Any]) -> httpx.Response:
        """Single POST attempt — wrapped in tenacity retry."""
        response = httpx.post(
            self.webhook_url,
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    def send(self, payload: WebhookPayload) -> dict[str, Any]:
        """
        Send candidate data to the n8n webhook.

        Returns dict with:
            - status: "sent" | "skipped" | "failed"
            - detail: human-readable info
            - response: n8n response body (if available)
        """
        if not self.is_configured:
            logger.event(
                "n8n_webhook_skipped",
                reason="N8N_WEBHOOK_URL not configured",
                candidate=payload.candidate_name,
            )
            return {
                "status": "skipped",
                "detail": "N8N_WEBHOOK_URL not configured — workflow automation skipped",
            }

        body = payload.to_dict()
        logger.event(
            "n8n_webhook_send",
            url=self.webhook_url,
            candidate=payload.candidate_name,
            score=payload.match_score,
            status=payload.application_status,
        )

        try:
            response = self._post_with_retry(body)
            logger.event(
                "n8n_webhook_sent",
                status_code=response.status_code,
                candidate=payload.candidate_name,
            )
            return {
                "status": "sent",
                "detail": f"n8n responded {response.status_code}",
                "response": self._safe_json(response),
            }
        except Exception as exc:
            logger.event(
                "n8n_webhook_failed",
                level=30,
                error=str(exc),
                candidate=payload.candidate_name,
                attempts=self.max_retries,
            )
            return {
                "status": "failed",
                "detail": f"Webhook delivery failed after {self.max_retries} attempts: {exc}",
            }

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return response.text


# ------------------------------------------------------------------
# Module-level convenience function
# ------------------------------------------------------------------
_client: Optional[N8nWebhookClient] = None


def get_client() -> N8nWebhookClient:
    """Singleton webhook client."""
    global _client
    if _client is None:
        _client = N8nWebhookClient()
    return _client


def notify_n8n(payload: WebhookPayload) -> dict[str, Any]:
    """
    Convenience: send a webhook notification to n8n using the
    singleton client.  Never raises — returns a result dict.
    """
    return get_client().send(payload)
