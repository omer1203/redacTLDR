import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export interface RequestAuth {
  token: string;
  userId: string;
  clerkEnabled: boolean;
  // Template name, not a secret. Long-lived client screens use it to mint fresh tokens.
  jwtTemplate: string | null;
}

export async function getRequestAuth(): Promise<RequestAuth> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  if (!clerkEnabled) {
    return {
      token: "",
      userId: process.env.NEXT_PUBLIC_DEMO_USER ?? "demo-user",
      clerkEnabled: false,
      jwtTemplate: null,
    };
  }

  const { userId, getToken } = await auth();
  if (!userId) {
    redirect("/");
  }
  const jwtTemplate = process.env.CLERK_JWT_TEMPLATE;
  if (!jwtTemplate) {
    throw new Error("Missing CLERK_JWT_TEMPLATE. Set it to enforce API audience-specific tokens.");
  }
  const token = await getToken({ template: jwtTemplate });
  if (!token) {
    throw new Error(
      `Signed in as ${userId}, but Clerk did not issue a "${jwtTemplate}" token. Check that JWT template in the Clerk dashboard, then open the dashboard again.`,
    );
  }
  return { token, userId, clerkEnabled: true, jwtTemplate };
}
