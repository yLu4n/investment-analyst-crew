"use client";

import { ChevronLeft, ChevronRight, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui";
import { getPaginatedAssets } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import type { AssetInput } from "@/types/analysis";

export function PortfolioTable({
  assets,
  page,
  onAddQuantity,
  onPageChange,
  onRemoveAsset,
}: {
  assets: AssetInput[];
  page: number;
  onAddQuantity: (ticker: string) => void;
  onPageChange: (page: number) => void;
  onRemoveAsset: (ticker: string) => void;
}) {
  const pageSize = 10;
  const { rows, total, pageCount } = getPaginatedAssets(assets, page, pageSize);

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-muted text-left text-muted-foreground">
          <tr>
            <th className="px-3 py-3 font-medium">Ticker</th>
            <th className="px-3 py-3 font-medium">Quantidade</th>
            <th className="px-3 py-3 font-medium">Preco medio</th>
            <th className="px-3 py-3 font-medium">Valor</th>
            <th className="px-3 py-3 text-right font-medium">Acoes</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((asset) => (
            <tr key={asset.id} className="border-t border-border">
              <td className="px-3 py-3 font-medium">{asset.ticker}</td>
              <td className="px-3 py-3">{asset.quantity}</td>
              <td className="px-3 py-3">{formatCurrency(asset.average_price)}</td>
              <td className="px-3 py-3">{formatCurrency(asset.quantity * asset.average_price)}</td>
              <td className="px-3 py-3">
                <div className="flex justify-end gap-2">
                  <Button
                    aria-label={`Adicionar quantidade em ${asset.ticker}`}
                    title="Adicionar quantidade"
                    variant="secondary"
                    className="h-8 w-8 px-0"
                    onClick={() => onAddQuantity(asset.ticker)}
                  >
                    <Plus size={15} />
                  </Button>
                  <Button
                    aria-label={`Remover ${asset.ticker}`}
                    title="Remover ativo"
                    variant="danger"
                    className="h-8 w-8 px-0"
                    onClick={() => onRemoveAsset(asset.ticker)}
                  >
                    <Trash2 size={15} />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="px-3 py-8 text-center text-muted-foreground" colSpan={5}>
                Nenhum ativo carregado.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div className="flex items-center justify-between border-t border-border px-3 py-2 text-sm text-muted-foreground">
        <span>
          {total} ativos · pagina {page} de {pageCount}
        </span>
        <div className="flex gap-2">
          <Button
            aria-label="Pagina anterior"
            variant="secondary"
            className="h-8 w-8 px-0"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft size={16} />
          </Button>
          <Button
            aria-label="Proxima pagina"
            variant="secondary"
            className="h-8 w-8 px-0"
            disabled={page >= pageCount}
            onClick={() => onPageChange(page + 1)}
          >
            <ChevronRight size={16} />
          </Button>
        </div>
      </div>
    </div>
  );
}
