"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Send, Sparkles, FileText, ListChecks, Receipt, CornerDownLeft,
  Plus, Trash2, MessageSquarePlus,
} from "lucide-react";
import {
  useConversation, useConversations, useDeleteConversation, useSendChat,
} from "@/lib/hooks";
import { AssistantActionCard } from "@/components/AssistantActionCard";
import { toast } from "@/components/Toaster";
import { cn } from "@/lib/utils";

type ToolCall = { name: string; args: any; result: any };
type Msg = { role: "user" | "assistant"; content: string; tools?: ToolCall[]; pending?: boolean; at?: number };

const SUGGESTIONS = [
  { icon: Receipt,    text: "Create invoice for TOO ABC for 450000 KZT" },
  { icon: ListChecks, text: "Show unpaid invoices" },
  { icon: FileText,   text: "List overdue invoices" },
];

const GREETING: Msg = {
  role: "assistant",
  content: "Ready. I can create invoices, list pending items, run reports and trigger workflows. Every state-changing action will create an approval for you to confirm.",
  at: Date.now(),
};

export default function AssistantPageWrapper() {
  // Wrap useSearchParams() in Suspense so the page is statically prerenderable
  // (Next.js 15 strictly requires this and fails the build otherwise).
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <AssistantPage />
    </Suspense>
  );
}

function AssistantPage() {
  const router = useRouter();
  const params = useSearchParams();
  const urlConvId = params.get("c");

  const [conversationId, setConversationId] = useState<string | null>(urlConvId);
  const [msgs, setMsgs] = useState<Msg[]>([GREETING]);
  const [input, setInput] = useState("");

  const { data: conversations = [] } = useConversations();
  const { data: history } = useConversation(conversationId);
  const chat = useSendChat();
  const del = useDeleteConversation();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Sync URL → state.
  useEffect(() => { if (urlConvId !== conversationId) setConversationId(urlConvId); }, [urlConvId]); // eslint-disable-line

  // When history loads (or changes), restore the message buffer.
  useEffect(() => {
    if (history && history.id === conversationId) {
      setMsgs(history.messages.map((m) => ({
        role: m.role, content: m.content, at: new Date(m.at).getTime(),
        tools: m.tool_calls?.length ? m.tool_calls : undefined,
      })) as Msg[]);
    }
  }, [history?.id, history?.messages.length]); // eslint-disable-line

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs, chat.isPending]);

  const newConversation = () => {
    setConversationId(null);
    setMsgs([GREETING]);
    router.replace("/assistant");
  };

  const openConversation = (id: string) => {
    setConversationId(id);
    router.replace(`/assistant?c=${id}`);
  };

  // Allow nested action cards (e.g. ProposalCard's "Подтвердить" button) to
  // post a follow-up message through the same send pipeline — keeps the
  // single source of truth without prop drilling.
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      if (typeof detail === "string" && detail.trim()) send(detail);
    };
    window.addEventListener("assistant:send", handler);
    return () => window.removeEventListener("assistant:send", handler);
  });

  const send = (text: string) => {
    if (!text.trim() || chat.isPending) return;
    setMsgs((m) => [...m,
      { role: "user", content: text, at: Date.now() },
      { role: "assistant", content: "", pending: true, at: Date.now() },
    ]);
    setInput("");
    chat.mutate(
      { message: text, conversation_id: conversationId },
      {
        onSuccess: (res) => {
          if (!conversationId) {
            setConversationId(res.conversation_id);
            router.replace(`/assistant?c=${res.conversation_id}`);
          }
          setMsgs((m) => [...m.slice(0, -1), {
            role: "assistant", content: res.reply,
            tools: res.tool_calls, at: Date.now(),
          }]);
          const created = res.tool_calls?.find((t) => t.name === "create_invoice" && t.result?.approval_id);
          if (created) toast.warn("Approval requested", `${created.result.number} awaiting your decision`);
        },
        onError: (e) => {
          setMsgs((m) => [...m.slice(0, -1), {
            role: "assistant", content: `Error: ${(e as Error).message}`, at: Date.now(),
          }]);
          toast.error("Assistant error", (e as Error).message);
        },
      },
    );
  };

  // One-shot handoff from the dashboard's quick-create widget: it can't reuse
  // the `assistant:send` event (that only reaches a listener already mounted
  // on this page), so it navigates here with `?send=` instead. Fire once on
  // arrival, then strip the param so a refresh/back doesn't resend it.
  const sentPrefillRef = useRef(false);
  useEffect(() => {
    const prefill = params.get("send");
    if (!prefill || sentPrefillRef.current) return;
    sentPrefillRef.current = true;
    send(decodeURIComponent(prefill));
    router.replace("/assistant");
  }, [params]); // eslint-disable-line

  return (
    <>
      <PageHeader
        eyebrow="Automation"
        title="AI Assistant"
        description="Operational copilot connected to your real data. Conversations persist across sessions."
        actions={
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={newConversation}>
              <MessageSquarePlus className="h-3.5 w-3.5" /> New
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-5">
        {/* ── Conversation history sidebar ── */}
        <aside className="hidden lg:block">
          <Card className="h-[calc(100vh-220px)] overflow-hidden flex flex-col">
            <div className="px-4 py-3 border-b border-border flex items-center justify-between">
              <span className="text-[10.5px] uppercase tracking-wider text-muted-foreground">History</span>
              <button onClick={newConversation}
                className="text-muted-foreground hover:text-foreground" title="New conversation">
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
            <ul className="flex-1 overflow-y-auto p-1.5 space-y-0.5">
              {conversations.length === 0 && (
                <li className="text-[11.5px] text-muted-foreground text-center py-6 px-3">
                  No conversations yet. Send a message to start.
                </li>
              )}
              {conversations.map((c) => (
                <li key={c.id} className="group relative">
                  <button
                    onClick={() => openConversation(c.id)}
                    className={cn(
                      "w-full text-left rounded-md px-2.5 py-1.5 transition-colors",
                      c.id === conversationId
                        ? "bg-[hsl(var(--brand-subtle))]"
                        : "hover:bg-accent/60",
                    )}
                  >
                    <div className="text-[12.5px] font-medium truncate pr-6">{c.title}</div>
                    <div className="text-[10.5px] text-muted-foreground tabular-nums">
                      {new Date(c.created_at).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })} · {c.message_count} msg
                    </div>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!confirm("Delete this conversation?")) return;
                      del.mutate(c.id, {
                        onSuccess: () => {
                          if (conversationId === c.id) newConversation();
                          toast.success("Conversation deleted");
                        },
                      });
                    }}
                    className="absolute right-1.5 top-1.5 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-[hsl(var(--danger))] transition-opacity"
                    title="Delete"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </aside>

        {/* ── Chat window ── */}
        <Card className="flex flex-col h-[calc(100vh-220px)] sm:h-[calc(100vh-240px)] overflow-hidden surface-spotlight">
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-4">
            {msgs.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : "flex gap-2.5"}>
                {m.role === "assistant" && (
                  <div className="h-7 w-7 shrink-0 rounded-full bg-[hsl(var(--brand-subtle))] border border-[hsl(var(--brand)/0.3)] grid place-items-center mt-0.5">
                    <Sparkles className="h-3.5 w-3.5 text-[hsl(var(--brand))]" strokeWidth={1.75} />
                  </div>
                )}
                <div className={m.role === "user" ? "max-w-[80%]" : "max-w-[88%] flex-1 min-w-0"}>
                  {m.role === "assistant" ? (
                    <>
                      <div className="rounded-lg border border-border bg-surface-2 px-3.5 py-2.5 text-[13px] leading-relaxed shadow-xs">
                        {m.pending ? <Typing /> : <span className="whitespace-pre-wrap">{m.content}</span>}
                      </div>
                      {m.tools?.map((tc, idx) => <AssistantActionCard key={idx} tc={tc} />)}
                    </>
                  ) : (
                    <div className="rounded-lg bg-[hsl(var(--brand))] text-[hsl(var(--brand-foreground))] px-3.5 py-2.5 text-[13px] leading-relaxed shadow-brand">
                      {m.content}
                    </div>
                  )}
                  {m.at && !m.pending && (
                    <div className={"mt-1 text-[10px] text-muted-foreground " + (m.role === "user" ? "text-right" : "")}>
                      {new Date(m.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-border px-4 sm:px-5 py-3 bg-surface-2">
            {msgs.length <= 1 && (
              <div className="mb-2.5 flex flex-wrap gap-1.5">
                {SUGGESTIONS.map(({ icon: Icon, text }) => (
                  <button key={text} onClick={() => send(text)}
                    className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1 text-[11.5px] text-muted-foreground hover:bg-[hsl(var(--brand-subtle))] hover:border-[hsl(var(--brand)/0.4)] hover:text-foreground transition-all">
                    <Icon className="h-3 w-3" strokeWidth={1.75} /> {text}
                  </button>
                ))}
              </div>
            )}
            <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex gap-2">
              <Input value={input} onChange={(e) => setInput(e.target.value)}
                     placeholder={conversationId ? "Continue the conversation…" : "Ask, request, or run an operation…"}
                     className="flex-1 h-9" />
              <Button type="submit" size="md" disabled={chat.isPending || !input.trim()}>
                <Send className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Send</span>
                <span className="kbd ml-1 hidden sm:inline-flex">
                  <CornerDownLeft className="h-2.5 w-2.5" />
                </span>
              </Button>
            </form>
          </div>
        </Card>
      </div>
    </>
  );
}

function Typing() {
  return (
    <span className="inline-flex items-center gap-1 text-muted-foreground">
      <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
      <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse [animation-delay:120ms]" />
      <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse [animation-delay:240ms]" />
      <span className="ml-1.5 text-[11px]">processing</span>
    </span>
  );
}
