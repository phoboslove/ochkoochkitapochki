"""Billing/subscription enforcement errors.

Both carry a ready-to-show Russian message (the app's default tenant
language, matching the AI system prompt and existing UI copy) so every
call site — REST endpoint, AI tool result, Telegram reply — can surface
`str(exc)` directly without re-deriving wording.
"""
from __future__ import annotations

from datetime import datetime


class SubscriptionSuspendedError(Exception):
    def __init__(self, company_id: str, period_end: datetime):
        self.company_id = company_id
        self.period_end = period_end
        super().__init__(
            "Подписка приостановлена — оплаченный период и льготный срок истекли. "
            "Продлите подписку, чтобы возобновить создание документов.",
        )


class DocumentLimitExceededError(Exception):
    def __init__(self, used: int, limit: int):
        self.used = used
        self.limit = limit
        super().__init__(
            f"Лимит тарифа исчерпан: {used} из {limit} документов в этом месяце. "
            "Смените тариф, чтобы продолжить.",
        )
