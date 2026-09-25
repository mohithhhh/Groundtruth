import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { setWorkerUrl } from "maplibre-gl";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { SourceDrawerProvider } from "./components/SourceDrawer";
import { PrefsProvider } from "./lib/prefs";
import "./styles/global.css";

// Shipped by the groundtruth-maplibre-worker plugin in vite.config.ts.
setWorkerUrl(new URL("/maplibre/maplibre-gl-worker.mjs", window.location.origin).href);

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <PrefsProvider>
        <BrowserRouter>
          <SourceDrawerProvider>
            <App />
          </SourceDrawerProvider>
        </BrowserRouter>
      </PrefsProvider>
    </QueryClientProvider>
  </StrictMode>,
);
