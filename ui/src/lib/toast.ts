type ToastType = "success" | "error" | "warning" | "info";

type ToastListener = (type: ToastType, message: string) => void;
const listeners = new Set<ToastListener>();

export const toast = {
  error: (message: string) => {
    listeners.forEach((fn) => fn("error", message));
  },
  success: (message: string) => {
    listeners.forEach((fn) => fn("success", message));
  },
  info: (message: string) => {
    listeners.forEach((fn) => fn("info", message));
  },
  warning: (message: string) => {
    listeners.forEach((fn) => fn("warning", message));
  },
  subscribe: (fn: ToastListener) => {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
};
