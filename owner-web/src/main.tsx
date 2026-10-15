import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { SessionProvider } from "./lib/session";
import { ThemeProvider } from "./components/ThemeProvider";
import { router } from "./router";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider><SessionProvider><RouterProvider router={router} /></SessionProvider></ThemeProvider>
  </StrictMode>,
);
