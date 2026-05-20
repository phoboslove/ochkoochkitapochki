"""WhatsApp provider abstraction.

Pick a provider per-company via the Integration row's `config.provider`:
  * "meta_cloud" — Meta WhatsApp Cloud API
  * "twilio"     — Twilio WhatsApp
  * "mock"       — dev/test (no network)

Each provider implements `WhatsAppProvider`; the service is the only thing
the rest of the app talks to.
"""
from app.services.integrations.whatsapp.base import WhatsAppMessage, WhatsAppProvider
from app.services.integrations.whatsapp.factory import build_whatsapp_provider

__all__ = ["WhatsAppMessage", "WhatsAppProvider", "build_whatsapp_provider"]
