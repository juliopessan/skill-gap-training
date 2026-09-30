"use client";

import { useEffect } from "react";
import { FAVICON_BUSY_STATIC_STEP, FAVICON_STEPS, faviconFrameUrl } from "@/lib/brand";

const FRAME_MS = 300;

/**
 * Progressive enhancement: while `busy`, cycle the tab icon through the brand frames; when idle the
 * ORIGINAL href is restored exactly. Reduced motion: one static "busy" frame instead of a loop.
 * The frame is chosen per tick from the browser colour scheme, like the static icon.
 */
export function useBusyFavicon(busy: boolean): void {
  useEffect(() => {
    if (!busy) return;
    const dark = window.matchMedia("(prefers-color-scheme: dark)");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Every icon <link> (Next emits favicon.ico and icon.svg) is swapped, keeping its own attributes.
    const saved = new Map<HTMLLinkElement, { href: string | null; type: string | null; sizes: string | null }>();
    let step = 0;
    let timer: ReturnType<typeof setInterval> | undefined;

    const paint = () => {
      // Next may re-insert the <link> nodes (e.g. on navigation): pick up whichever exist now.
      const frame = still ? FAVICON_BUSY_STATIC_STEP : step++ % FAVICON_STEPS;
      const href = faviconFrameUrl(frame, dark.matches);
      for (const link of document.head.querySelectorAll<HTMLLinkElement>('link[rel~="icon"]')) {
        if (!saved.has(link)) {
          saved.set(link, { href: link.getAttribute("href"), type: link.getAttribute("type"), sizes: link.getAttribute("sizes") });
          link.setAttribute("type", "image/svg+xml");
          link.setAttribute("sizes", "any");
        }
        link.setAttribute("href", href);
      }
    };
    const restore = () => {
      const put = (link: HTMLLinkElement, name: string, value: string | null) =>
        value === null ? link.removeAttribute(name) : link.setAttribute(name, value);
      for (const [link, was] of saved) {
        if (!link.isConnected) continue;
        put(link, "href", was.href);
        put(link, "type", was.type);
        put(link, "sizes", was.sizes);
      }
      saved.clear();
    };
    const stop = () => {
      if (timer !== undefined) clearInterval(timer);
      timer = undefined;
    };
    const start = () => {
      paint();
      if (!still) timer = setInterval(paint, FRAME_MS);
    };
    const onVisibility = () => {
      if (document.hidden) { stop(); restore(); } else if (timer === undefined) start();
    };

    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stop();
      restore();
    };
  }, [busy]);
}
