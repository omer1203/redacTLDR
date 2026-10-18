"use client";

import { createContext, useContext } from "react";
import { useRouter } from "next/navigation";

const InstantNavContext = createContext<(href: string) => void>(() => {});

export function InstantNavProvider({
  go,
  children,
}: {
  go: (href: string) => void;
  children: React.ReactNode;
}) {
  return <InstantNavContext.Provider value={go}>{children}</InstantNavContext.Provider>;
}

export function useScheduleNav() {
  return useContext(InstantNavContext);
}

export function useInstantNav() {
  const go = useScheduleNav();
  const router = useRouter();
  return (href: string) => {
    go(href);
    router.push(href);
  };
}
