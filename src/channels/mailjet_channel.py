"""Email delivery via Mailjet API v3.1."""
import logging

import httpx

from src.channels.base import ChannelBase, ChannelResult, Payload
from src.config import settings

logger = logging.getLogger(__name__)

MAILJET_SEND_URL = "https://api.mailjet.com/v3.1/send"


class MailjetChannel(ChannelBase):
    @property
    def name(self) -> str:
        return "email"

    def is_available(self) -> bool:
        return bool(settings.mailjet_api_key and settings.mailjet_api_secret)

    def send(self, payload: Payload) -> ChannelResult:
        if not settings.mailjet_api_key or not settings.mailjet_api_secret:
            return ChannelResult(success=False, error="Mailjet API key/secret not configured")
        try:
            body = {
                "Messages": [
                    {
                        "From": {
                            "Email": settings.mailjet_from_email,
                            "Name": settings.mailjet_from_name,
                        },
                        "To": [{"Email": payload.recipient}],
                        "Subject": payload.subject or "(No subject)",
                        "TextPart": payload.body,
                    }
                ]
            }
            with httpx.Client() as client:
                r = client.post(
                    MAILJET_SEND_URL,
                    json=body,
                    auth=(settings.mailjet_api_key, settings.mailjet_api_secret),
                    timeout=30.0,
                )
            if r.status_code >= 200 and r.status_code < 300:
                data = r.json() or {}
                messages = data.get("Messages") or []
                message_id = None
                if messages and messages[0].get("To"):
                    message_id = str(messages[0]["To"][0].get("MessageID", ""))
                return ChannelResult(success=True, provider_id=message_id or str(r.status_code))
            return ChannelResult(success=False, error=f"Mailjet API {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.exception("Mailjet send failed")
            return ChannelResult(success=False, error=str(e))
