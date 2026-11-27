"use client";

import { useSyncExternalStore } from "react";

const CSRF_STORAGE_KEY = "eii_csrf_token";
const CSRF_CHANGE_EVENT = "eii:csrf-token-change";

function getSnapshot(): string | null {
  try {
    return window.sessionStorage.getItem(CSRF_STORAGE_KEY);
  } catch {
    return null;
  }
}

function getServerSnapshot(): null {
  return null;
}

function subscribe(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  window.addEventListener(CSRF_CHANGE_EVENT, onStoreChange);
  window.addEventListener("storage", onStoreChange);

  return () => {
    window.removeEventListener(CSRF_CHANGE_EVENT, onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}

function notifyCsrfTokenChange(): void {
  window.dispatchEvent(new Event(CSRF_CHANGE_EVENT));
}

export function useCsrfToken(): string | null {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function storeCsrfToken(token: string): void {
  window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
  notifyCsrfTokenChange();
}

export function clearCsrfToken(): void {
  window.sessionStorage.removeItem(CSRF_STORAGE_KEY);
  notifyCsrfTokenChange();
}
