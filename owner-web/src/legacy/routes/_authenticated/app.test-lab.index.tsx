// @ts-nocheck
import { redirect } from "@tanstack/react-router";
import { createFileRoute, createLazyFileRoute } from "@/shims/file-route";

export const Route = createFileRoute("/_authenticated/app/test-lab/")({
  beforeLoad: () => {
    throw redirect({ to: "/app/test-lab/real" });
  },
});
