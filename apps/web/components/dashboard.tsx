"use client";

import { AlertCircle, FileUp, Loader2, Plus, RefreshCcw, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { Header } from "@/components/header";
import { PortfolioTable } from "@/components/portfolio-table";
import { useSessionState } from "@/components/session-provider";
import { UpsellModal } from "@/components/upsell-modal";
import { Badge, Button, Card, Input, Label, Select, Skeleton } from "@/components/ui";
import { useAnalysisResult, useAnalysisStatus, useCreateAnalysis } from "@/hooks/use-analysis";
import { parseBrokerageFile } from "@/lib/import-parser";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { AssetInput, RiskProfile } from "@/types/analysis";

const DEFAULT_ASSETS: AssetInput[] = [
  { ticker: "PETR4", quantity: 100, average_price: 32.5, asset_type: "stock" },
  { ticker: "VALE3", quantity: 60, average_price: 68.1, asset_type: "stock" },
  { ticker: "ITSA4", quantity: 180, average_price: 10.2, asset_type: "stock" },
];

export function Dashboard() {
  const { credits, isPro, consumeCredit } = useSessionState();
  const [assets, setAssets] = useState<AssetInput[]>(DEFAULT_ASSETS);
  const [page, setPage] = useState(1);
  const [riskProfile, setRiskProfile] = useState<RiskProfile>("moderate");
  const [monthlyContribution, setMonthlyContribution] = useState(1000);
  const [jobId, setJobId] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [manualAsset, setManualAsset] = useState({ ticker: "", quantity: "", average_price: "" });
  const [showUpsell, setShowUpsell] = useState(false);

  const createAnalysisMutation = useCreateAnalysis();
  const statusQuery = useAnalysisStatus(jobId);
  const status = statusQuery.data;
  const resultQuery = useAnalysisResult(jobId, status?.status === "completed");

  const totalAllocated = useMemo(
    () => assets.reduce((total, asset) => total + asset.quantity * asset.average_price, 0),
    [assets],
  );
  const largestAssetWeight = useMemo(() => {
    if (totalAllocated <= 0) {
      return 0;
    }
    return Math.max(...assets.map((asset) => asset.quantity * asset.average_price)) / totalAllocated;
  }, [assets, totalAllocated]);
  const deterministicRisk = largestAssetWeight > 0.45 ? "Concentrada" : "Balanceada";
  const analysisBlocked = !isPro || credits === 0;

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      const parsed = await parseBrokerageFile(file);
      if (!parsed.ok) {
        setImportError(parsed.message);
        return;
      }

      setImportError(null);
      setAssets(parsed.assets);
      setPage(1);
    } catch {
      setImportError("Nao foi possivel importar o arquivo. Tente novamente ou preencha os ativos manualmente.");
    } finally {
      event.currentTarget.value = "";
    }
  }

  function addManualAsset() {
    const ticker = manualAsset.ticker.trim().toUpperCase();
    const quantity = Number(manualAsset.quantity);
    const averagePrice = Number(manualAsset.average_price);

    if (!ticker || Number.isNaN(quantity) || Number.isNaN(averagePrice)) {
      setImportError("Preencha ticker, quantidade e preco medio com valores validos.");
      return;
    }

    setImportError(null);
    setAssets((current) => [
      ...current,
      { ticker, quantity, average_price: averagePrice, asset_type: "stock" },
    ]);
    setManualAsset({ ticker: "", quantity: "", average_price: "" });
  }

  async function submitAiAnalysis() {
    if (analysisBlocked) {
      setShowUpsell(true);
      return;
    }

    const created = await createAnalysisMutation.mutateAsync({
      assets,
      risk_profile: riskProfile,
      monthly_contribution: monthlyContribution,
    });
    consumeCredit();
    setJobId(created.job_id);
  }

  return (
    <>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-6">
        <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="min-h-[340px]">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold">Carteira</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Importacao validada no cliente antes do envio para a API.
                </p>
              </div>
              <label className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium hover:bg-muted">
                <FileUp size={16} />
                Importar
                <input
                  className="sr-only"
                  type="file"
                  accept=".csv,.pdf,text/csv,application/pdf"
                  onChange={handleFileChange}
                />
              </label>
            </div>

            {importError && (
              <div className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
                <AlertCircle size={17} className="text-destructive" />
                <span className="flex-1">{importError}</span>
                <Button variant="secondary" onClick={() => setImportError(null)}>
                  Tentar novamente
                </Button>
              </div>
            )}

            <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_120px_140px_auto]">
              <div>
                <Label>Ticker</Label>
                <Input
                  value={manualAsset.ticker}
                  onChange={(event) => setManualAsset((asset) => ({ ...asset, ticker: event.target.value }))}
                  placeholder="BBDC4"
                />
              </div>
              <div>
                <Label>Quantidade</Label>
                <Input
                  inputMode="decimal"
                  value={manualAsset.quantity}
                  onChange={(event) => setManualAsset((asset) => ({ ...asset, quantity: event.target.value }))}
                  placeholder="100"
                />
              </div>
              <div>
                <Label>Preco medio</Label>
                <Input
                  inputMode="decimal"
                  value={manualAsset.average_price}
                  onChange={(event) =>
                    setManualAsset((asset) => ({ ...asset, average_price: event.target.value }))
                  }
                  placeholder="12.50"
                />
              </div>
              <div className="flex items-end">
                <Button className="w-full" variant="secondary" onClick={addManualAsset}>
                  <Plus size={16} />
                  Adicionar
                </Button>
              </div>
            </div>

            <div className="mt-4">
              <PortfolioTable assets={assets} page={page} onPageChange={setPage} />
            </div>
          </Card>

          <Card>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold">Analise</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Free usa diagnostico deterministico; Pro aciona agentes de IA.
                </p>
              </div>
              <Badge>{isPro ? "IA Pro" : "Free"}</Badge>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <Metric title="Patrimonio" value={formatCurrency(totalAllocated)} />
              <Metric title="Maior peso" value={formatPercent(largestAssetWeight)} />
              <Metric title="Risco" value={deterministicRisk} />
              <Metric title="Ativos" value={String(assets.length)} />
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div>
                <Label>Perfil</Label>
                <Select
                  value={riskProfile}
                  onChange={(event) => setRiskProfile(event.target.value as RiskProfile)}
                >
                  <option value="conservative">Conservador</option>
                  <option value="moderate">Moderado</option>
                  <option value="aggressive">Agressivo</option>
                </Select>
              </div>
              <div>
                <Label>Aporte mensal</Label>
                <Input
                  inputMode="decimal"
                  value={monthlyContribution}
                  onChange={(event) => setMonthlyContribution(Number(event.target.value))}
                />
              </div>
            </div>

            <Button
              className="mt-4 w-full"
              disabled={createAnalysisMutation.isPending || assets.length === 0}
              onClick={submitAiAnalysis}
            >
              {createAnalysisMutation.isPending ? <Loader2 className="animate-spin" size={17} /> : <Sparkles size={17} />}
              Analisar com IA
            </Button>

            <AnalysisPanel
              isLoading={statusQuery.isLoading || resultQuery.isLoading}
              error={createAnalysisMutation.error?.message ?? status?.error_message ?? resultQuery.error?.message}
              currentStep={status?.current_step}
              progress={status?.progress_percentage ?? 0}
              status={status?.status}
              report={resultQuery.data?.report_markdown}
            />
          </Card>
        </div>
      </main>
      <UpsellModal open={showUpsell} onClose={() => setShowUpsell(false)} />
    </>
  );
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <p className="text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 truncate text-lg font-semibold">{value}</p>
    </div>
  );
}

function AnalysisPanel({
  isLoading,
  error,
  currentStep,
  progress,
  status,
  report,
}: {
  isLoading: boolean;
  error?: string | null;
  currentStep?: string;
  progress: number;
  status?: string;
  report?: string;
}) {
  if (isLoading) {
    return (
      <div className="mt-4 space-y-3">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
        {error}
      </div>
    );
  }

  if (!status) {
    return (
      <div className="mt-4 rounded-lg border border-border bg-background p-3 text-sm text-muted-foreground">
        Aguardando envio para analise.
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-lg border border-border bg-background p-3">
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="font-medium">{currentStep}</span>
        <span className="text-muted-foreground">{progress}%</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
      </div>
      {status === "running" && (
        <p className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCcw className="animate-spin" size={15} />
          Polling ativo via TanStack Query.
        </p>
      )}
      {report && <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-sm">{report}</pre>}
    </div>
  );
}
