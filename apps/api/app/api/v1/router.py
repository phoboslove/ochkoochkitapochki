from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai, anomalies, approvals, auth, billing, clients, companies, conversations, documents, files,
    integrations, invitations, invoices, logs, ops, recovery, reports, search,
    knowledge, settings as settings_ep, support, telegram, templates, webhooks, workflows,
)
from app.api.v1.endpoints import admin as admin_ep

api_router = APIRouter()
api_router.include_router(auth.router,         prefix="/auth",         tags=["auth"])
api_router.include_router(companies.router,    prefix="/companies",    tags=["companies"])
api_router.include_router(ai.router,           prefix="/ai",           tags=["ai"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(documents.router,    prefix="/documents",    tags=["documents"])
api_router.include_router(invoices.router,     prefix="/invoices",     tags=["invoices"])
api_router.include_router(workflows.router,    prefix="/workflows",    tags=["workflows"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(approvals.router,    prefix="/approvals",    tags=["approvals"])
api_router.include_router(clients.router,      prefix="/clients",      tags=["clients"])
api_router.include_router(reports.router,      prefix="/reports",      tags=["reports"])
api_router.include_router(logs.router,         prefix="/logs",         tags=["logs"])
api_router.include_router(templates.router,    prefix="/templates",    tags=["templates"])
api_router.include_router(search.router,       prefix="/search",       tags=["search"])
api_router.include_router(webhooks.router,     prefix="/webhooks",     tags=["webhooks"])
api_router.include_router(files.router,        prefix="/files",        tags=["files"])
api_router.include_router(invitations.router,  prefix="/invitations",  tags=["invitations"])
api_router.include_router(anomalies.router,    prefix="/anomalies",    tags=["anomalies"])
api_router.include_router(recovery.router,     prefix="/recovery",     tags=["recovery"])
api_router.include_router(ops.router,          prefix="/ops",          tags=["ops"])
api_router.include_router(telegram.router,     prefix="/telegram",     tags=["telegram"])
api_router.include_router(support.router,      prefix="/support",      tags=["support"])
api_router.include_router(settings_ep.router,  prefix="/settings",     tags=["settings"])
api_router.include_router(knowledge.router,    prefix="/knowledge",    tags=["knowledge"])
api_router.include_router(billing.router,      prefix="/billing",      tags=["billing"])
api_router.include_router(admin_ep.router,     prefix="/admin",        tags=["admin"])
