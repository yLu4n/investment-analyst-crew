"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui";

export function UpsellModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/55 p-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-5 shadow-lg">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">Analise Pro indisponivel</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              A analise por IA exige plano Pro e saldo de creditos. No Free, a carteira usa apenas
              indicadores deterministicos.
            </p>
          </div>
          <Button aria-label="Fechar" variant="ghost" className="h-8 w-8 px-0" onClick={onClose}>
            <X size={16} />
          </Button>
        </div>
        <div className="mt-5 flex justify-end">
          <Button onClick={onClose}>Entendi</Button>
        </div>
      </div>
    </div>
  );
}
