"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Chrome, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button, Card, Input, Label } from "@/components/ui";
import { createSupabaseBrowserClient } from "@/lib/supabase";

type AuthMode = "login" | "signup";

export function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const isSignup = mode === "signup";

  async function handlePasswordAuth(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setError("Autenticacao indisponivel no momento.");
      return;
    }

    if (isSignup && password !== confirmPassword) {
      setError("A confirmacao de senha precisa ser igual a senha.");
      return;
    }

    setIsLoading(true);
    const response = isSignup
      ? await supabase.auth.signUp({
          email,
          password,
          options: {
            data: {
              plan: "free",
              credits: 0,
            },
            emailRedirectTo: `${window.location.origin}/login`,
          },
        })
      : await supabase.auth.signInWithPassword({ email, password });

    setIsLoading(false);
    if (response.error) {
      setError(getSafeAuthErrorMessage(response.error.message));
      return;
    }

    router.push("/");
    router.refresh();
  }

  async function handleGoogleAuth() {
    setError(null);
    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setError("Autenticacao indisponivel no momento.");
      return;
    }

    const { error: googleError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin,
      },
    });

    if (googleError) {
      setError(getSafeAuthErrorMessage(googleError.message));
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-8">
      <Card className="w-full max-w-md">
        <div>
          <h1 className="text-2xl font-semibold">{isSignup ? "Criar conta" : "Login"}</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {isSignup
              ? "Use Google ou cadastre email e senha para iniciar no plano Free."
              : "Entre com email e senha ou use sua conta Google."}
          </p>
        </div>

        <Button className="mt-5 w-full" variant="secondary" onClick={handleGoogleAuth}>
          <Chrome size={17} />
          {isSignup ? "Cadastrar com Google" : "Entrar com Google"}
        </Button>

        <div className="my-5 h-px bg-border" />

        <form className="space-y-4" onSubmit={handlePasswordAuth}>
          <div>
            <Label>Email</Label>
            <Input
              autoComplete="email"
              inputMode="email"
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div>
            <Label>Senha</Label>
            <Input
              autoComplete={isSignup ? "new-password" : "current-password"}
              minLength={6}
              required
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          {isSignup && (
            <div>
              <Label>Confirmar senha</Label>
              <Input
                autoComplete="new-password"
                minLength={6}
                required
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
              />
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
              {error}
            </div>
          )}

          <Button className="w-full" disabled={isLoading} type="submit">
            {isLoading && <Loader2 className="animate-spin" size={17} />}
            {isSignup ? "Cadastrar" : "Entrar"}
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-muted-foreground">
          {isSignup ? "Ja tem conta?" : "Ainda nao tem conta?"}{" "}
          <Link className="font-medium text-foreground underline-offset-4 hover:underline" href={isSignup ? "/login" : "/cadastro"}>
            {isSignup ? "Fazer login" : "Criar cadastro"}
          </Link>
        </p>
      </Card>
    </main>
  );
}

function getSafeAuthErrorMessage(message: string) {
  const normalizedMessage = message.toLowerCase();
  if (normalizedMessage.includes("invalid") || normalizedMessage.includes("credentials")) {
    return "Email ou senha invalidos.";
  }
  if (normalizedMessage.includes("already") || normalizedMessage.includes("registered")) {
    return "Ja existe uma conta para este email.";
  }
  if (normalizedMessage.includes("password")) {
    return "A senha nao atende aos requisitos de seguranca.";
  }
  return "Nao foi possivel autenticar agora. Tente novamente em instantes.";
}
