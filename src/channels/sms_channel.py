"""SMS channel via Twilio."""
import logging
from typing import Optional

from src.channels.base import ChannelBase, ChannelResult, Payload
from src.config import settings

logger = logging.getLogger(__name__)


class SMSChannel(ChannelBase):
    """Send SMS using Twilio API."""

    @property
    def name(self) -> str:
        return "sms"

    def is_available(self) -> bool:
        return bool(settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number)

    def send(self, payload: Payload) -> ChannelResult:
        if not all([settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number]):
            return ChannelResult(success=False, error="Twilio not configured")
        try:
            from twilio.rest import Client

            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            msg = client.messages.create(
                body=payload.body,
                from_=settings.twilio_from_number,
                to=payload.recipient,
            )
            return ChannelResult(success=True, provider_id=msg.sid)
        except Exception as e:
            logger.exception("Twilio send failed")
            return ChannelResult(success=False, error=str(e))
