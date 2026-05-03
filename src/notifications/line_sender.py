import os
from typing import Union
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

    def send(self, subject: str, body: str, recipient: Union[str, list] = "") -> bool:
        """Send to one or multiple LINE user IDs. recipient can be a string or list of strings."""
        recipients = recipient if isinstance(recipient, list) else [recipient or self.default_user_id]
        recipients = [r for r in recipients if r]  # drop empty strings

        if not self.is_configured():
            print("[LINE] Not configured — check LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID in .env")
            return False
        if not recipients:
            print("[LINE] No recipient (LINE User ID) configured.")
            return False

        chunks = [body[i:i+4900] for i in range(0, len(body), 4900)]
        success = True
        try:
            config = Configuration(access_token=self.token)
            with ApiClient(config) as api_client:
                api = MessagingApi(api_client)
                for uid in recipients:
                    for chunk in chunks:
                        api.push_message(
                            PushMessageRequest(
                                to=uid,
                                messages=[TextMessage(type="text", text=chunk)],
                            )
                        )
                    print(f"[LINE] Sent {len(chunks)} message(s) to {uid}")
        except Exception as e:
            print(f"[LINE] Failed: {e}")
            success = False
        return success


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
