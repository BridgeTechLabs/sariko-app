from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

# The backend POSTs to whatever endpoint is stored, so only accept the browser
# push services — anything else would let a client aim our server at any URL.
PUSH_SERVICE_HOSTS = (
    "fcm.googleapis.com",           # Chrome, Edge, Android
    "push.services.mozilla.com",    # Firefox
    "push.apple.com",               # Safari, iOS home-screen apps
    "notify.windows.com",           # legacy Edge / Windows
)


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class RequestCreatePushSubscription(BaseModel):
    """Same shape as the browser's PushSubscription.toJSON()."""
    endpoint: str
    keys: PushSubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def endpoint_is_push_service(cls, value: str) -> str:
        url = urlparse(value)
        host = url.hostname or ""
        if url.scheme != "https" or not any(host == h or host.endswith("." + h) for h in PUSH_SERVICE_HOSTS):
            raise ValueError("endpoint is not a known push service")
        return value
