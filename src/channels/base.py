from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

from src.models.orm_models import ChannelType


@dataclass
class ChannelResult:
    """Result of a single send attempt."""

    success: bool
    provider_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Payload:
    """Normalized payload for sending."""

    recipient: str  # email address or phone
    subject: Optional[str] = None
    body: str = ""
    template_context: Optional[Dict] = None


class ChannelBase(ABC):
    """Interface for delivery channels. New channels implement this and register."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Channel identifier (e.g. 'email', 'sms')."""
        pass

    @abstractmethod
    def send(self, payload: Payload) -> ChannelResult:
        """Send the message. Returns success/failure and optional provider id."""
        pass

    def is_available(self) -> bool:
        """Whether the channel is configured and available. Override if needed."""
        return True


class ChannelRegistry:
    """Register and resolve channels by name."""

    def __init__(self) -> None:
        self._channels: Dict[str, ChannelBase] = {}

    def register(self, channel: ChannelBase) -> None:
        self._channels[channel.name] = channel

    def get(self, name: str) -> Optional[ChannelBase]:
        return self._channels.get(name)

    def get_available(self, name: str) -> Optional[ChannelBase]:
        ch = self.get(name)
        if ch and ch.is_available():
            return ch
        return None

    def list_channels(self) -> list[str]:
        return list(self._channels.keys())
