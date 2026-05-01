from abc import ABC, abstractmethod


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, subject: str, body: str, recipient: str) -> bool:
        """Send a notification. Returns True on success."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if required credentials are available."""
        pass
