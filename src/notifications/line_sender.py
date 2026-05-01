import os
from src.notifications.base import NotificationChannel

try:
    from linebot.v3.messaging import (
        Configuration,
        ApiClient,
        MessagingApi,
        PushMessageRequest,
        TextMessage,
    )
    LINE_SDK_AVAILABLE = True
except ImportError:
    LINE_SDK_AVAILABLE = False


class LineChannel(NotificationChannel):
    def __init__(self):
        self.token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
        self.default_user_id = os.environ.get("LINE_USER_ID", "")

    def is_configured(self) -> bool:
        return LINE_SDK_AVAILABLE and bool(self.token and self.default_user_id)

    def send(self, subject: str, body: str, recipient: str = "") -> bool:
        recipient = recipient or self.default_user_id
        if not self.is_configured():
            print("[LINE] Not configured — check LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID in .env")
            return False
        if not recipient:
            print("[LINE] No recipient (LINE User ID) configured.")
            return False

        # LINE messages have a 5000-char limit; chunk if needed
        chunks = [body[i:i+4900] for i in range(0, len(body), 4900)]

        try:
            config = Configuration(access_token=self.token)
            with ApiClient(config) as api_client:
                api = MessagingApi(api_client)
                for chunk in chunks:
                    api.push_message(
                        PushMessageRequest(
                            to=recipient,
                            messages=[TextMessage(type="text", text=chunk)],
                        )
                    )
            print(f"[LINE] Sent {len(chunks)} message(s) to {recipient}")
            return True
        except Exception as e:
            print(f"[LINE] Failed: {e}")
            return False


def get_channel(channel_name: str) -> NotificationChannel:
    """Factory — returns the right channel by name."""
    channels = {
        "email": None,   # imported lazily to avoid circular
        "line": LineChannel,
    }
    from src.notifications.email_sender import EmailChannel
    channels["email"] = EmailChannel
    cls = channels.get(channel_name.lower())
    if cls is None:
        raise ValueError(f"Unknown channel: {channel_name}. Supported: {list(channels.keys())}")
    return cls()
