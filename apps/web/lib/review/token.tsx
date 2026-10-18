"use client";

import { useAuth } from "@clerk/nextjs";
import { createContext, useCallback, useContext, type ReactNode } from "react";

import { ApiError } from "@/lib/api/client";

/**
 * API token source for long-lived client screens.
 *
 * Server pages mint one Clerk token per request, and template tokens expire in
 * about a minute. The review screen stays open far longer, so every request
 * asks Clerk for a token at call time (Clerk caches and refreshes it). Without
 * Clerk, the empty token makes `apiFetch` send the local `x-demo-user` header.
 */

export type GetToken = () => Promise<string>;

const TokenContext = createContext<GetToken | null>(null);

const demoToken: GetToken = async () => "";

function ClerkTokenProvider({ template, children }: { template: string; children: ReactNode }) {
  const { getToken } = useAuth();
  const getFreshToken = useCallback(async () => {
    const token = await getToken({ template });
    if (!token) {
      throw new ApiError(401, "Your session ended. Sign in again to keep reviewing.");
    }
    return token;
  }, [getToken, template]);
  return <TokenContext.Provider value={getFreshToken}>{children}</TokenContext.Provider>;
}

export function ApiTokenProvider({
  clerkEnabled,
  jwtTemplate,
  children,
}: {
  clerkEnabled: boolean;
  jwtTemplate: string | null;
  children: ReactNode;
}) {
  // `useAuth` throws outside ClerkProvider, so the Clerk branch is its own component.
  if (clerkEnabled && jwtTemplate) {
    return <ClerkTokenProvider template={jwtTemplate}>{children}</ClerkTokenProvider>;
  }
  return <TokenContext.Provider value={demoToken}>{children}</TokenContext.Provider>;
}

export function useApiToken(): GetToken {
  const getToken = useContext(TokenContext);
  if (!getToken) {
    throw new Error("useApiToken must be used inside ApiTokenProvider");
  }
  return getToken;
}
