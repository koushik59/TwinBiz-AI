"use client";

import { api, setToken } from "@/lib/api";
import { useToast } from "@/components/ui";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/* Google Identity Services — minimal typings for the pieces we use */
type GsiButtonOptions = {
  theme?: string; size?: string; width?: number; text?: string; shape?: string; logo_alignment?: string;
};
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
          renderButton: (el: HTMLElement, options: GsiButtonOptions) => void;
        };
      };
    };
  }
}

const GSI_SRC = "https://accounts.google.com/gsi/client";
const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

/**
 * "Continue with Google" button. Renders nothing when
 * NEXT_PUBLIC_GOOGLE_CLIENT_ID is not configured, so the app
 * keeps working with email/password only.
 */
export function GoogleAuthButton() {
  const router = useRouter();
  const { toast } = useToast();
  const slot = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!CLIENT_ID || !slot.current) return;
    const el = slot.current;

    const render = () => {
      if (!window.google || !el.isConnected) return;
      window.google.accounts.id.initialize({
        client_id: CLIENT_ID,
        callback: async ({ credential }) => {
          try {
            const res = await api.post<{ access_token: string; has_business: boolean }>(
              "/api/auth/google", { credential });
            setToken(res.access_token);
            router.push(res.has_business ? "/dashboard" : "/setup");
          } catch (err) {
            toast(err instanceof Error ? err.message : "Google sign-in failed", "critical");
          }
        },
      });
      window.google.accounts.id.renderButton(el, {
        theme: "outline", size: "large", shape: "pill", text: "continue_with",
        width: Math.min(el.offsetWidth || 320, 400),
      });
    };

    if (window.google?.accounts) {
      render();
      return;
    }
    let script = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    if (!script) {
      script = document.createElement("script");
      script.src = GSI_SRC;
      script.async = true;
      document.head.appendChild(script);
    }
    script.addEventListener("load", render);
    script.addEventListener("error", () => setFailed(true));
    return () => script?.removeEventListener("load", render);
  }, [router, toast]);

  if (!CLIENT_ID || failed) return null;
  return (
    <>
      <div className="my-4 flex items-center gap-3 text-[11px] uppercase tracking-widest text-muted">
        <span className="h-px flex-1 bg-line" />
        or
        <span className="h-px flex-1 bg-line" />
      </div>
      <div ref={slot} className="flex min-h-[44px] justify-center" />
    </>
  );
}
