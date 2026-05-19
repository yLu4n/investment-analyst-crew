"use client";

import { useRouter } from "next/navigation";
import { KeyRound, Loader2 } from "lucide-react";
import { useState } from "react";

import { useSessionState } from "@/components/session-provider";
import { Button, Card, Input, Label } from "@/components/ui";
import { createSupabaseBrowserClient } from "@/lib/supabase";

const MIN_PASSWORD_LENGTH = 8;

export function PasswordChangeForm() {
  const router = useRouter();
  const { user } = useSessionState();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const canChangePassword = hasPasswordIdentity(user);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (!canChangePassword) {
      setError("Troca de senha disponivel apenas para contas cadastradas com email e senha.");
      return;
    }

    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`A nova senha precisa ter pelo menos ${MIN_PASSWORD_LENGTH} caracteres.`);
      return;
    }

    if (password !== confirmPassword) {
      setError("A confirmacao de senha precisa ser igual a nova senha.");
      return;
    }

    const supabase = createSupabaseBrowserClient();
    if (!supabase) {
      setError("Autenticacao indisponivel no momento.");
      return;
    }

    setIsLoading(true);
    const { error: updateError } = await supabase.auth.updateUser({ password });
    setIsLoading(false);

    if (updateError) {
      setError(getSafeAuthErrorMessage(updateError.message));
      return;
    }

    setPassword("");
    setConfirmPassword("");
    setNotice("Senha alterada com sucesso.");
    router.refresh();
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-8">
      <Card className="w-full max-w-md">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md border border-border bg-muted">
            <KeyRound size={18} />
          </div>
          <div>
            <h1 className="text-2xl font-semibold">Alterar senha</h1>
            <p className="mt-1 text-sm text-muted-foreground">Atualize a senha da sua conta por email.</p>
          </div>
        </div>

        <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
          <div>
            <Label>Nova senha</Label>
            <Input
              autoComplete="new-password"
              disabled={!canChangePassword}
              minLength={MIN_PASSWORD_LENGTH}
              required
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <div>
            <Label>Confirmar nova senha</Label>
            <Input
              autoComplete="new-password"
              disabled={!canChangePassword}
              minLength={MIN_PASSWORD_LENGTH}
              required
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </div>

          {!canChangePassword && (
            <div className="rounded-lg border border-border bg-muted p-3 text-sm">
              Contas criadas somente com Google nao usam senha local neste sistema.
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

          <Button className="w-full" disabled={isLoading || !canChangePassword} type="submit">
            {isLoading && <Loader2 className="animate-spin" size={17} />}
            Salvar nova senha
          </Button>
        </form>
      </Card>
    </main>
  );
}

function hasPasswordIdentity(user: ReturnType<typeof useSessionState>["user"]) {
  if (!user) {
    return false;
  }

  const identities = user.identities ?? [];
  return identities.some((identity) => identity.provider === "email") || user.app_metadata?.provider === "email";
}

function getSafeAuthErrorMessage(message: string) {
  const normalizedMessage = message.toLowerCase();
  if (normalizedMessage.includes("password")) {
    return "A senha nao atende aos requisitos de seguranca.";
  }
  if (normalizedMessage.includes("session") || normalizedMessage.includes("jwt")) {
    return "Sessao expirada. Faca login novamente.";
  }
  return "Nao foi possivel alterar a senha agora. Tente novamente em instantes.";
}
