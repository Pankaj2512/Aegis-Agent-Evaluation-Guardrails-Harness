"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { RecoveryState } from "@/components/ui/recovery-state";

interface ErrorBoundaryProps {
  children: ReactNode;
  title?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
  retryKey: number;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, retryKey: 0 };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error boundary caught:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="page-container flex min-h-[60vh] items-center justify-center">
          <RecoveryState
            title={this.props.title || "This workspace section stopped rendering"}
            description="The UI boundary isolated the fault. Retry the section in place or reload the app shell to restore the session."
            primaryAction={
              <Button
                onClick={() =>
                  this.setState((state) => ({
                    error: null,
                    retryKey: state.retryKey + 1,
                  }))
                }
              >
                Try again
              </Button>
            }
            secondaryAction={
              <Button
                variant="outline"
                onClick={() => {
                  this.setState({ error: null, retryKey: 0 });
                  window.location.reload();
                }}
              >
                Reload page
              </Button>
            }
          />
        </div>
      );
    }

    return <div key={this.state.retryKey}>{this.props.children}</div>;
  }
}
