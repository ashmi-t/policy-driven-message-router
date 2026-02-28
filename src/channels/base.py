"""Abstract channel interface and registry. Add new channels by implementing ChannelBase and registering."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ChannelResult:
    success: bool
    provider_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class Payload:
    recipient: str
    subject: Optional[str] = None
    body: str = ""
    template_context: Optional[Dict] = None


class ChannelBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def send(self, payload: Payload) -> ChannelResult:
        pass

    def is_available(self) -> bool:
        """Override to check credentials/config. Used to skip unconfigured channels."""
        return True


class ChannelRegistry:
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
