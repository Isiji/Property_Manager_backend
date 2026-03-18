from twilio.rest import Client
from app.core.config import settings


def _get_twilio_client() -> Client:
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise ValueError("Twilio credentials are not configured")
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def send_sms(to_phone: str, message: str) -> str:
    if not settings.TWILIO_SMS_FROM:
        raise ValueError("TWILIO_SMS_FROM is not configured")

    client = _get_twilio_client()
    result = client.messages.create(
        body=message,
        from_=settings.TWILIO_SMS_FROM,
        to=to_phone,
    )
    return result.sid


def send_whatsapp(to_phone: str, message: str) -> str:
    client = _get_twilio_client()

    if not to_phone.startswith("whatsapp:"):
        to_phone = f"whatsapp:{to_phone}"

    result = client.messages.create(
        body=message,
        from_=settings.TWILIO_WHATSAPP_FROM,
        to=to_phone,
    )
    return result.sid