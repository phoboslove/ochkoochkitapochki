"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

type S = { error: Error | null };

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, S> {
  state: S = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error) { console.error("[ErrorBoundary]", error); }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="m-6 rounded-lg border border-destructive/30 bg-destructive/5 p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-destructive mt-0.5" />
          <div className="flex-1">
            <div className="text-sm font-semibold">Something went wrong on this page.</div>
            <div className="mt-1 text-xs text-muted-foreground font-mono break-all">{this.state.error.message}</div>
            <div className="mt-3 flex gap-2">
              <Button size="sm" onClick={() => this.setState({ error: null })}>
                <RefreshCw className="h-3.5 w-3.5" /> Retry
              </Button>
              <Button size="sm" variant="outline" onClick={() => location.reload()}>Reload page</Button>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
