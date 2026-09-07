import { toast as sonner } from "sonner";

export const toast = {
  success: (message: string, description?: string) =>
    sonner.success(message, description ? { description } : undefined),

  error: (message: string, description?: string) =>
    sonner.error(message, description ? { description } : undefined),

  info: (message: string, description?: string) =>
    sonner.info(message, description ? { description } : undefined),

  warning: (message: string, description?: string) =>
    sonner.warning(message, description ? { description } : undefined),

  loading: (message: string) => sonner.loading(message),

  dismiss: (id?: string | number) => sonner.dismiss(id),

  promise: sonner.promise,
};