/**
 * Suppress ResizeObserver loop errors globally.
 * Registered as a Docusaurus client module so it runs before app hydration,
 * ensuring the handler is in place before webpack-dev-server's error overlay.
 */
const handler = (e: ErrorEvent) => {
  if (
    e.message?.includes("ResizeObserver loop") ||
    e.message?.includes("ResizeObserver")
  ) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
};

window.addEventListener("error", handler, true);
