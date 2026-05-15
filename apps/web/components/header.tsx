"use client";

import Link from "next/link";
import { LogOut, Moon, Sun, UserPlus, WalletCards } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { useSessionState } from "@/components/session-provider";
import { Badge, Button } from "@/components/ui";

export function Header() {
  const { resolvedTheme, setTheme } = useTheme();
  const { plan, credits, signOut, user } = useSessionState();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold">Investment Analyst</h1>
          <p className="truncate text-sm text-muted-foreground">
            {user?.email ?? "Sessao local"} · plano {plan.toUpperCase()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className="gap-2">
            <WalletCards size={15} />
            {credits} creditos
          </Badge>
          {user ? (
            <Button variant="secondary" onClick={signOut}>
              <LogOut size={16} />
              Sair
            </Button>
          ) : (
            <>
              <Button asChild variant="secondary">
                <Link href="/login">Login</Link>
              </Button>
              <Button asChild>
                <Link href="/cadastro">
                  <UserPlus size={16} />
                  Cadastro
                </Link>
              </Button>
            </>
          )}
          <Button
            aria-label="Alternar tema"
            variant="secondary"
            className="w-10 px-0"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          >
            {mounted && resolvedTheme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </Button>
        </div>
      </div>
    </header>
  );
}
