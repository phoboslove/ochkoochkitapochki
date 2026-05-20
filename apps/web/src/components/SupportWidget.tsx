"use client";

import { useEffect, useRef, useState } from "react";
import { LifeBuoy, Send, X, Sparkles, Minus } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type Msg = { role: "user" | "assistant"; content: string };

const STORAGE_KEY = "buchuchet.support.history";
const GREETING: Msg = {
  role: "assistant",
  content:
    "Hi! I'm the Buchuchet support assistant — here to help you find your way around.\n\n" +
    "Quick tips:\n" +
    "• **AI Assistant** in the sidebar runs real actions (\"Create invoice for TOO ABC for 450000\").\n" +
    "• **Approvals** is where invoices and AI actions wait for your OK.\n" +
    "• **Settings → Telegram** lets you approve from your phone.\n" +
    "• **Dashboard → Load demo data** populates realistic invoices, approvals, documents.\n\n" +
    "What would you like to do?",
};

const SUGGESTIONS = [
  "How do I create an invoice?",
  "Where do I approve actions?",
  "How do I connect Telegram?",
  "Where can I see metrics?",
];

export function SupportWidget() {
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([GREETING]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Restore history from localStorage on mount.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as Msg[];
        if (Array.isArray(parsed) && parsed.length > 0) setMsgs(parsed);
      }
    } catch { /* ignore */ }
  }, []);

  // Persist + scroll on every message change.
  useEffect(() => {
    if (typeof window !== "undefined") {
      try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs.slice(-30))); } catch { /* ignore */ }
    }
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs]);

  const ask = useMutation({
    mutationFn: ({ message, history }: { message: string; history: Msg[] }) =>
      api.post<{ reply: string }>("/support/chat", { message, history }),
  });

  const send = (text: string) => {
    if (!text.trim() || ask.isPending) return;
    const next: Msg[] = [...msgs, { role: "user", content: text }];
    setMsgs(next);
    setInput("");
    const history = next.slice(0, -1).filter((m) => m !== GREETING);
    ask.mutate(
      { message: text, history },
      {
        onSuccess: (r) => setMsgs((m) => [...m, { role: "assistant", content: r.reply }]),
        onError:   (e) => setMsgs((m) => [...m, {
          role: "assistant",
          content: `I couldn't reach the assistant just now (${(e as Error).message.slice(0, 80)}). Try again in a moment.`,
        }]),
      },
    );
  };

  const reset = () => {
    setMsgs([GREETING]);
    if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
  };

  if (!open) {
    return (
      <button
        onClick={() => { setOpen(true); setMinimized(false); }}
        className="fixed bottom-5 right-5 z-50 h-11 w-11 rounded-full bg-card border border-border text-foreground shadow-md flex items-center justify-center hover:shadow-lg hover:bg-accent transition-all"
        aria-label="Open support chat"
      >
        <LifeBuoy className="h-4 w-4" strokeWidth={1.75} />
        <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-[hsl(var(--success))] ring-2 ring-background" />
      </button>
    );
  }

  // Minimized header pill.
  if (minimized) {
    return (
      <button
        onClick={() => setMinimized(false)}
        className="fixed bottom-5 right-5 z-50 h-10 px-4 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center gap-2 text-sm hover:scale-[1.02] transition-transform"
      >
        <LifeBuoy className="h-4 w-4" /> Support
      </button>
    );
  }

  return (
    <div className={cn(
      "fixed z-50 bg-card border shadow-2xl rounded-xl flex flex-col",
      "bottom-5 right-5 w-[min(380px,calc(100vw-2rem))] h-[min(560px,calc(100vh-2rem))]",
    )}>
      {/* Header */}
      <header className="flex items-center gap-3 px-4 py-3 border-b">
        <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
          <LifeBuoy className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold leading-none">Buchuchet support</div>
          <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Online · 24/7
          </div>
        </div>
        <button onClick={() => setMinimized(true)} className="text-muted-foreground hover:text-foreground p-1" aria-label="Minimize">
          <Minus className="h-4 w-4" />
        </button>
        <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground p-1" aria-label="Close">
          <X className="h-4 w-4" />
        </button>
      </header>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex gap-2"}>
            {m.role === "assistant" && (
              <div className="h-6 w-6 shrink-0 rounded-full bg-muted flex items-center justify-center">
                <Sparkles className="h-3 w-3" />
              </div>
            )}
            <div className={cn(
              "max-w-[82%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap leading-relaxed",
              m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted",
            )}>
              {m.content}
            </div>
          </div>
        ))}
        {ask.isPending && (
          <div className="flex gap-2 items-center text-xs text-muted-foreground pl-8">
            <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
            <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse [animation-delay:120ms]" />
            <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse [animation-delay:240ms]" />
            typing
          </div>
        )}

        {msgs.length === 1 && (
          <div className="pt-2 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)}
                className="rounded-full border px-3 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground">
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Input */}
      <form
        onSubmit={(e) => { e.preventDefault(); send(input); }}
        className="border-t p-3 flex gap-2"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything about Buchuchet…"
          className="flex-1"
        />
        <Button type="submit" size="icon" disabled={ask.isPending} aria-label="Send">
          <Send className="h-4 w-4" />
        </Button>
      </form>

      <button onClick={reset} className="text-[10px] text-muted-foreground hover:underline pb-2 px-3 text-left">
        Clear conversation
      </button>
    </div>
  );
}
