import { api } from "@/lib/api";

export type JobStatus = Awaited<ReturnType<typeof api.getJob>>;

const DEFAULT_TERMINAL_STATUSES = ["completed", "failed", "cancelled"];

export interface PollJobOptions {
  maxAttempts?: number;
  signal?: AbortSignal;
  terminalStatuses?: readonly string[];
}

export async function pollJob(
  jobId: string,
  options: PollJobOptions | number = {}
): Promise<JobStatus> {
  // Backward-compatible: pollJob(id, 60) still works.
  const opts: PollJobOptions =
    typeof options === "number" ? { maxAttempts: options } : options;
  const maxAttempts = opts.maxAttempts ?? 60;
  const terminal = new Set(opts.terminalStatuses ?? DEFAULT_TERMINAL_STATUSES);
  const signal = opts.signal;

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const job = await api.getJob(jobId);
    if (terminal.has(job.status)) {
      return job;
    }
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        signal?.removeEventListener("abort", onAbort);
        resolve();
      }, 1000);
      const onAbort = () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      };
      if (signal) signal.addEventListener("abort", onAbort, { once: true });
    });
  }
  throw new Error("Job timed out");
}