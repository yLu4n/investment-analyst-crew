"use client";

import type { User } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { createSupabaseBrowserClient } from "@/lib/supabase";
import type { UserPlan } from "@/types/analysis";

type SessionState = {
  user: User | null;
  plan: UserPlan;
  credits: number;
  isPro: boolean;
  isLoading: boolean;
  consumeCredit: () => void;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [plan, setPlan] = useState<UserPlan>("free");
  const [credits, setCredits] = useState(0);

  useEffect(() => {
    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setIsLoading(false);
      return;
    }

    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user ?? null);
      setPlan(resolvePlan(data.user));
      setCredits(resolveCredits(data.user));
      setIsLoading(false);
    });

    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setPlan(resolvePlan(session?.user ?? null));
      setCredits(resolveCredits(session?.user ?? null));
    });

    return () => data.subscription.unsubscribe();
  }, []);

  const state = useMemo<SessionState>(
    () => ({
      user,
      plan,
      credits,
      isPro: plan === "pro",
      isLoading,
      consumeCredit: () => setCredits((current) => Math.max(0, current - 1)),
      signOut: async () => {
        const supabase = createSupabaseBrowserClient();
        await supabase?.auth.signOut();
        setUser(null);
        setPlan("free");
        setCredits(0);
      },
    }),
    [credits, isLoading, plan, user],
  );

  return <SessionContext.Provider value={state}>{children}</SessionContext.Provider>;
}

function resolvePlan(user: User | null): UserPlan {
  const metadata = (user?.app_metadata as Record<string, unknown> | undefined) ?? {};
  const subscriptionStatus = String(metadata.subscription_status ?? "").toLowerCase();
  const hasActiveSubscription = ["active", "trialing"].includes(subscriptionStatus);
  return metadata.plan === "pro" && hasActiveSubscription ? "pro" : "free";
}

function resolveCredits(user: User | null): number {
  const metadata = (user?.app_metadata as Record<string, unknown> | undefined) ?? {};
  return typeof metadata.credits === "number" ? metadata.credits : 0;
}

export function useSessionState() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSessionState must be used inside SessionProvider");
  }
  return context;
}
