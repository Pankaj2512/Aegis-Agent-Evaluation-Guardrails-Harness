import { Button } from "@/components/ui/button";

/**
 * Compact inline failure row for a settings card. A failed list read must never
 * fall through to an empty state — "you have none of these" is a different (and
 * alarming) claim than "we couldn't reach the API".
 */
export function InlineQueryError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border border-destructive/25 bg-destructive/10 px-2.5 py-1.5">
      <p className="text-xs text-destructive">{message}</p>
      <Button variant="ghost" size="xs" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
