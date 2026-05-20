"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Chrome, Loader2 } from "lucide-react";
import { useState } from "react";

import { Button, Card, Input, Label } from "@/components/ui";
import { createSupabaseBrowserClient } from "@/lib/supabase";

type AuthMode = "login" | "signup";
const MIN_PASSWORD_LENGTH = 8;

export function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isResetLoading, setIsResetLoading] = useState(false);
  const isSignup = mode === "signup";

  async function handlePasswordAuth(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setError("Autenticacao indisponivel no momento.");
      return;
    }

    if (isSignup && !isPasswordStrongEnough(password)) {
      setError(`A senha precisa ter pelo menos ${MIN_PASSWORD_LENGTH} caracteres.`);
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
            emailRedirectTo: `${window.location.origin}/auth/callback?next=/`,
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

  async function handlePasswordReset() {
    setError(null);
    setNotice(null);

    const normalizedEmail = email.trim();
    if (!normalizedEmail) {
      setError("Informe seu email para receber o link de troca de senha.");
      return;
    }

    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setError("Autenticacao indisponivel no momento.");
      return;
    }

    setIsResetLoading(true);
    const { error: resetError } = await supabase.auth.resetPasswordForEmail(normalizedEmail, {
      redirectTo: `${window.location.origin}/auth/callback?next=/alterar-senha`,
    });
    setIsResetLoading(false);

    if (resetError) {
      setError(getSafeAuthErrorMessage(resetError.message));
      return;
    }

    setNotice("Se o email estiver cadastrado, enviaremos um link para trocar a senha.");
  }

  async function handleGoogleAuth() {
    setError(null);
    setNotice(null);
    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setError("Autenticacao indisponivel no momento.");
      return;
    }

    const { error: googleError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback?next=/`,
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
              minLength={isSignup ? MIN_PASSWORD_LENGTH : undefined}
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
                minLength={MIN_PASSWORD_LENGTH}
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
          {notice && (
            <div className="rounded-lg border border-primary/40 bg-primary/10 p-3 text-sm">
              {notice}
            </div>
          )}

          <Button className="w-full" disabled={isLoading} type="submit">
            {isLoading && <Loader2 className="animate-spin" size={17} />}
            {isSignup ? "Cadastrar" : "Entrar"}
          </Button>
          {!isSignup && (
            <Button
              className="w-full"
              disabled={isResetLoading}
              type="button"
              variant="ghost"
              onClick={handlePasswordReset}
            >
              {isResetLoading && <Loader2 className="animate-spin" size={17} />}
              Esqueci minha senha
            </Button>
          )}
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

function isPasswordStrongEnough(password: string) {
  return password.length >= MIN_PASSWORD_LENGTH;
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
