"""Channel abstraction and implementations."""
from src.channels.base import ChannelBase, ChannelResult, ChannelRegistry
from src.channels.mailjet_channel import MailjetChannel
from src.channels.sms_channel import SMSChannel

registry = ChannelRegistry()
registry.register(MailjetChannel())
registry.register(SMSChannel())

__all__ = [
    "ChannelBase",
    "ChannelResult",
    "ChannelRegistry",
    "MailjetChannel",
    "SMSChannel",
    "registry",
]
