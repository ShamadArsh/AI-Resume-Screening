# ============================================================
# scheduler/gmail.py — Gmail Email Service
# ============================================================
# Uses the Gmail API with OAuth credentials from .env.
# If credentials are absent, runs in *mock mode* — emails are
# logged instead of sent so the full pipeline still works.
# Email templates are configurable below.
# ============================================================

from __future__ import annotations

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from backend.config import settings
from utils.logger import logger

__all__ = ["EmailService", "get_email_service", "EmailTemplates"]


# ------------------------------------------------------------------
# Configurable Email Templates
# ------------------------------------------------------------------
class EmailTemplates:
    """Configurable HTML email templates for each workflow stage."""

    @staticmethod
    def _wrap(subject: str, body: str) -> tuple[str, str]:
        """Return (text, html) versions of an email body."""
        html = f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px;">
          <div style="background: #1a73e8; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">{settings.smtp_from_name}</h2>
          </div>
          <div style="background: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; border: 1px solid #dadce0;">
            {body}
          </div>
          <p style="color: #5f6368; font-size: 12px; margin-top: 16px;">
            This is an automated message from the AI Recruitment Platform.
          </p>
        </body></html>
        """
        return body, html

    @classmethod
    def application_received(cls, name: str) -> tuple[str, str]:
        return cls._wrap(
            "Application Received",
            f"<p>Dear <strong>{name}</strong>,</p>"
            f"<p>Thank you for your application. We have received your resume "
            f"and our AI system is reviewing it. You will hear from us soon.</p>"
            f"<p>Best regards,<br/>{settings.smtp_from_name}</p>",
        )

    @classmethod
    def shortlisted(cls, name: str, score: int, summary: str) -> tuple[str, str]:
        return cls._wrap(
            "🎉 Congratulations! You've Been Shortlisted!",
            f"<p>Dear <strong>{name}</strong>,</p>"
            f"<div style='background: #e6f4ea; padding: 15px; border-radius: 8px; margin: 10px 0;'>"
            f"<h3 style='color: #137333; margin: 0;'>🎉 Congratulations!</h3>"
            f"<p style='margin: 8px 0 0;'>Your application has been <strong>shortlisted</strong>!</p>"
            f"</div>"
            f"<p>We are impressed with your profile. Your application achieved an "
            f"<strong>AI Match Score of {score}/100</strong>, placing you among our top candidates.</p>"
            f"<p><strong>Here's what our AI recruiter had to say:</strong></p>"
            f"<p style='font-style: italic; background: #f1f3f4; padding: 12px; border-radius: 6px;'>{summary}</p>"
            f"<p>An <strong>interview invitation</strong> with the schedule and Google Meet link "
            f"will follow this email shortly. Please keep an eye on your inbox!</p>"
            f"<p>Once again, congratulations on being shortlisted. We look forward to speaking with you soon.</p>"
            f"<p>Best regards,<br/><strong>{settings.smtp_from_name}</strong></p>",
        )

    @classmethod
    def interview_invitation(
        cls, name: str, date: str, time: str, link: str
    ) -> tuple[str, str]:
        return cls._wrap(
            "📅 Interview Invitation — You're Scheduled!",
            f"<p>Dear <strong>{name}</strong>,</p>"
            f"<p>Following your shortlisting, your interview has been scheduled!</p>"
            f"<div style='background: #e8f0fe; padding: 15px; border-radius: 8px; margin: 10px 0;'>"
            f"<h3 style='color: #1a73e8; margin: 0 0 10px;'>📅 Interview Details</h3>"
            f"<table style='border-collapse: collapse; width: 100%;'>"
            f'<tr><td style="padding: 8px; font-weight: bold; width: 100px;">Date:</td><td style="padding: 8px;">{date}</td></tr>'
            f'<tr><td style="padding: 8px; font-weight: bold;">Time:</td><td style="padding: 8px;">{time}</td></tr>'
            f'<tr><td style="padding: 8px; font-weight: bold;">Meeting:</td><td style="padding: 8px;">'
            f'<a href="{link}" style="color: #1a73e8;">{link}</a></td></tr>'
            f"</table>"
            f"</div>"
            f"<p><strong>How to join:</strong> Click the meeting link above at the scheduled time. "
            f"A Google Calendar event has also been created and sent to you separately.</p>"
            f"<p>Please confirm your availability by replying to this email. "
            f"If you need to reschedule, let us know as soon as possible.</p>"
            f"<p>We look forward to meeting you!</p>"
            f"<p>Best regards,<br/><strong>{settings.smtp_from_name}</strong></p>",
        )

    @classmethod
    def rejected(cls, name: str) -> tuple[str, str]:
        return cls._wrap(
            "Application Update",
            f"<p>Dear <strong>{name}</strong>,</p>"
            f"<p>Thank you for your interest in joining our team. "
            f"After careful review, we have decided not to move forward "
            f"with your application at this time.</p>"
            f"<p>We appreciate your time and wish you the best in your job search.</p>"
            f"<p>Best regards,<br/>{settings.smtp_from_name}</p>",
        )


# ------------------------------------------------------------------
# Gmail Service
# ------------------------------------------------------------------
class EmailService:
    """
    Gmail API email service with graceful mock mode.
    """

    def __init__(self):
        self._service = None
        self._is_mock = False

        # Prefer dedicated Gmail token; fall back to shared token
        gmail_token = settings.gmail_refresh_token or settings.google_refresh_token
        if settings.google_client_id and settings.google_client_secret and gmail_token:
            try:
                self._service = self._build_service(gmail_token)
                # Verify the credentials work (use send scope, not readonly)
                logger.event("email_init", backend="gmail")
            except Exception as exc:
                logger.event("email_init_error", level=30, error=str(exc))
                self._is_mock = True
                logger.event("email_init", backend="mock", reason="Gmail init failed")
        else:
            self._is_mock = True
            logger.event("email_init", backend="mock", reason="Google OAuth creds not set")

    def _build_service(self, refresh_token: str = ""):
        """Build the Gmail API service from OAuth credentials."""
        from google.oauth2 import credentials
        from googleapiclient.discovery import build

        token = credentials.Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=[
                "https://www.googleapis.com/auth/gmail.send",
            ],
        )
        return build("gmail", "v1", credentials=token)

    @property
    def is_mock(self) -> bool:
        return self._is_mock

    def _create_message(
        self, to: str, subject: str, body_text: str, body_html: str
    ) -> dict[str, str]:
        """Create a base64-encoded Gmail message."""
        msg = MIMEMultipart("alternative")
        msg["to"] = to
        msg["from"] = settings.smtp_from_email
        msg["subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return {"raw": raw}

    def send_email(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: str = "",
    ) -> dict[str, Any]:
        """
        Send an email via Gmail API.
        Returns dict with {status, message_id, mock} fields.
        """
        if self._is_mock:
            logger.event(
                "email_sent_mock",
                to=to,
                subject=subject,
                body_preview=body_text[:200],
            )
            return {
                "status": "mock_sent",
                "message_id": f"mock_{hash(to + subject) & 0xFFFFFFFF:08x}",
                "mock": True,
            }

        try:
            message = self._create_message(to, subject, body_text, body_html or body_text)
            result = self._service.users().messages().send(
                userId="me", body=message
            ).execute()
            logger.event("email_sent", to=to, subject=subject, message_id=result.get("id"))
            return {
                "status": "sent",
                "message_id": result.get("id"),
                "mock": False,
            }
        except Exception as exc:
            logger.event("email_send_error", level=40, to=to, subject=subject, error=str(exc))
            return {
                "status": "error",
                "error": str(exc),
                "mock": False,
            }

    # ---- Convenience methods using templates ----
    def send_application_received(self, to: str, name: str) -> dict:
        text, html = EmailTemplates.application_received(name)
        return self.send_email(to, "Application Received", text, html)

    def send_shortlisted(self, to: str, name: str, score: int, summary: str) -> dict:
        text, html = EmailTemplates.shortlisted(name, score, summary)
        return self.send_email(to, "You've Been Shortlisted! 🎉", text, html)

    def send_interview_invitation(
        self, to: str, name: str, date: str, time: str, link: str
    ) -> dict:
        text, html = EmailTemplates.interview_invitation(name, date, time, link)
        return self.send_email(to, "Interview Invitation", text, html)

    def send_rejected(self, to: str, name: str) -> dict:
        text, html = EmailTemplates.rejected(name)
        return self.send_email(to, "Application Update", text, html)


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
