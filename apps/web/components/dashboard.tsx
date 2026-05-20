"use client";

import { AlertCircle, FileUp, Loader2, Plus, RefreshCcw, Sparkles, X } from "lucide-react";
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
const TICKER_PATTERN = /^[A-Z0-9.]{1,20}$/;
const ASSET_TYPE_OPTIONS = [
  { value: "stock", label: "Acoes" },
  { value: "fii", label: "FIIs" },
  { value: "fixed_income", label: "Renda fixa" },
  { value: "fund", label: "Fundos" },
  { value: "crypto", label: "Cripto" },
  { value: "other", label: "Outros" },
];
const ASSET_TYPE_COLORS = ["#0f766e", "#2563eb", "#ca8a04", "#dc2626", "#7c3aed", "#475569", "#0891b2", "#16a34a"];
type AssetFormState = { ticker: string; quantity: string; average_price: string; asset_type: string };
type AssetModalState =
  | { mode: "add" }
  | { mode: "edit"; ticker: string }
  | null;
type AssetTypeSlice = {
  type: string;
  label: string;
  value: number;
  percentage: number;
  color: string;
};

const EMPTY_ASSET_FORM: AssetFormState = { ticker: "", quantity: "", average_price: "", asset_type: "stock" };

export function Dashboard() {
  const { credits, isPro, consumeCredit } = useSessionState();
  const [assets, setAssets] = useState<AssetInput[]>(DEFAULT_ASSETS);
  const [page, setPage] = useState(1);
  const [riskProfile, setRiskProfile] = useState<RiskProfile>("moderate");
  const [monthlyContribution, setMonthlyContribution] = useState(1000);
  const [jobId, setJobId] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [assetForm, setAssetForm] = useState<AssetFormState>(EMPTY_ASSET_FORM);
  const [assetFormError, setAssetFormError] = useState<string | null>(null);
  const [assetModal, setAssetModal] = useState<AssetModalState>(null);
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
  const assetTypeBreakdown = useMemo(() => getAssetTypeBreakdown(assets), [assets]);
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

  function submitAssetForm() {
    if (!assetModal) {
      return;
    }

    const ticker = assetForm.ticker.trim().toUpperCase();
    const quantity = Number(assetForm.quantity);
    const averagePrice = Number(assetForm.average_price);
    const assetType = normalizeAssetType(assetForm.asset_type);

    if (!TICKER_PATTERN.test(ticker)) {
      setAssetFormError("Ticker deve conter ate 20 caracteres alfanumericos.");
      return;
    }

    if (!Number.isFinite(quantity) || !Number.isFinite(averagePrice)) {
      setAssetFormError("Preencha ticker, quantidade e preco medio com valores validos.");
      return;
    }

    if (quantity <= 0 || averagePrice < 0) {
      setAssetFormError("Quantidade deve ser maior que zero e preco medio nao pode ser negativo.");
      return;
    }

    if (!assetType) {
      setAssetFormError("Selecione o tipo do ativo.");
      return;
    }

    setAssetFormError(null);
    const nextAsset = { ticker, quantity, average_price: averagePrice, asset_type: assetType };

    setAssets((current) => (assetModal.mode === "edit" ? updateAsset(current, nextAsset) : upsertAsset(current, nextAsset)));
    closeAssetModal();
  }

  function removeAsset(ticker: string) {
    setAssets((current) => {
      const next = current.filter((asset) => asset.ticker !== ticker);
      const pageCount = Math.max(1, Math.ceil(next.length / 10));
      setPage((currentPage) => Math.min(currentPage, pageCount));
      return next;
    });
  }

  function prepareAssetQuantityAddition(ticker: string) {
    const asset = assets.find((currentAsset) => currentAsset.ticker === ticker);
    setAssetForm({
      ticker,
      quantity: "",
      average_price: asset?.average_price.toString() ?? "",
      asset_type: asset?.asset_type ?? "stock",
    });
    setAssetModal({ mode: "add" });
    setAssetFormError(null);
    setImportError(null);
  }

  function openAssetCreation() {
    setAssetForm(EMPTY_ASSET_FORM);
    setAssetModal({ mode: "add" });
    setAssetFormError(null);
    setImportError(null);
  }

  function openAssetEdition(ticker: string) {
    const asset = assets.find((currentAsset) => currentAsset.ticker === ticker);
    if (!asset) {
      return;
    }

    setAssetForm({
      ticker: asset.ticker,
      quantity: asset.quantity.toString(),
      average_price: asset.average_price.toString(),
      asset_type: asset.asset_type ?? "stock",
    });
    setAssetModal({ mode: "edit", ticker: asset.ticker });
    setAssetFormError(null);
    setImportError(null);
  }

  function closeAssetModal() {
    setAssetModal(null);
    setAssetForm(EMPTY_ASSET_FORM);
    setAssetFormError(null);
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

            <div className="mt-4 flex justify-end">
              <Button variant="secondary" onClick={openAssetCreation}>
                <Plus size={16} />
                Adicionar ativo
              </Button>
            </div>

            <div className="mt-4">
              <PortfolioTable
                assets={assets}
                page={page}
                onAddQuantity={prepareAssetQuantityAddition}
                onEditAsset={openAssetEdition}
                onPageChange={setPage}
                onRemoveAsset={removeAsset}
              />
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

            <AssetTypeChart slices={assetTypeBreakdown} total={totalAllocated} />

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
      <AssetModal
        error={assetFormError}
        form={assetForm}
        mode={assetModal?.mode ?? null}
        onCancel={closeAssetModal}
        onChange={setAssetForm}
        onSubmit={submitAssetForm}
      />
      <UpsellModal open={showUpsell} onClose={() => setShowUpsell(false)} />
    </>
  );
}

function upsertAsset(current: AssetInput[], incoming: AssetInput): AssetInput[] {
  const existingIndex = current.findIndex((asset) => asset.ticker === incoming.ticker);
  if (existingIndex === -1) {
    return [...current, incoming];
  }

  return current.map((asset, index) => {
    if (index !== existingIndex) {
      return asset;
    }

    const quantity = asset.quantity + incoming.quantity;
    const costBasis = asset.quantity * asset.average_price + incoming.quantity * incoming.average_price;

    return {
      ...asset,
      quantity,
      average_price: quantity > 0 ? costBasis / quantity : 0,
      asset_type: asset.asset_type ?? incoming.asset_type,
    };
  });
}

function updateAsset(current: AssetInput[], incoming: AssetInput): AssetInput[] {
  return current.map((asset) =>
    asset.ticker === incoming.ticker
      ? {
          ...asset,
          quantity: incoming.quantity,
          average_price: incoming.average_price,
          asset_type: incoming.asset_type,
        }
      : asset,
  );
}

function getAssetTypeBreakdown(assets: AssetInput[]): AssetTypeSlice[] {
  const totalsByType = assets.reduce<Record<string, number>>((totals, asset) => {
    const type = normalizeAssetType(asset.asset_type ?? "stock") || "other";
    const value = asset.quantity * asset.average_price;
    return { ...totals, [type]: (totals[type] ?? 0) + value };
  }, {});
  const total = Object.values(totalsByType).reduce((sum, value) => sum + value, 0);

  if (total <= 0) {
    return [];
  }

  return Object.entries(totalsByType)
    .sort(([, firstValue], [, secondValue]) => secondValue - firstValue)
    .map(([type, value]) => ({
      type,
      label: getAssetTypeLabel(type),
      value,
      percentage: value / total,
      color: getAssetTypeColor(type),
    }));
}

function normalizeAssetType(assetType: string) {
  return assetType.trim().toLowerCase().replace(/\s+/g, "_").slice(0, 64);
}

function getAssetTypeLabel(type: string) {
  return ASSET_TYPE_OPTIONS.find((option) => option.value === type)?.label ?? type.replace(/_/g, " ").toUpperCase();
}

function getAssetTypeColor(type: string) {
  const knownTypeIndex = ASSET_TYPE_OPTIONS.findIndex((option) => option.value === type);
  if (knownTypeIndex >= 0) {
    return ASSET_TYPE_COLORS[knownTypeIndex % ASSET_TYPE_COLORS.length];
  }

  const hash = Array.from(type).reduce((total, character) => total + character.charCodeAt(0), 0);
  return ASSET_TYPE_COLORS[hash % ASSET_TYPE_COLORS.length];
}

function getChartBackground(slices: AssetTypeSlice[]) {
  let currentPercentage = 0;
  const segments = slices.map((slice) => {
    const start = currentPercentage;
    currentPercentage += slice.percentage * 100;
    return `${slice.color} ${start}% ${currentPercentage}%`;
  });

  return `conic-gradient(${segments.join(", ")})`;
}

function AssetTypeChart({ slices, total }: { slices: AssetTypeSlice[]; total: number }) {
  const chartBackground = slices.length > 0 ? getChartBackground(slices) : "hsl(var(--muted))";

  return (
    <div className="mt-4 rounded-lg border border-border bg-background p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Tipos de ativos</h3>
          <p className="mt-1 text-xs text-muted-foreground">Distribuicao por valor investido</p>
        </div>
        <span className="text-sm font-medium">{formatCurrency(total)}</span>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-[132px_1fr] sm:items-center">
        <div className="relative mx-auto h-32 w-32 rounded-full" style={{ background: chartBackground }}>
          <div className="absolute inset-5 rounded-full bg-background" />
        </div>

        <div className="grid gap-2">
          {slices.length === 0 && <p className="text-sm text-muted-foreground">Nenhum ativo para exibir.</p>}
          {slices.map((slice) => (
            <div key={slice.type} className="grid grid-cols-[auto_1fr_auto] items-center gap-2 text-sm">
              <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: slice.color }} />
              <span className="truncate">{slice.label}</span>
              <span className="font-medium">{formatPercent(slice.percentage)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AssetModal({
  error,
  form,
  mode,
  onCancel,
  onChange,
  onSubmit,
}: {
  error: string | null;
  form: AssetFormState;
  mode: "add" | "edit" | null;
  onCancel: () => void;
  onChange: (form: AssetFormState) => void;
  onSubmit: () => void;
}) {
  if (!mode) {
    return null;
  }

  const isEdit = mode === "edit";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 px-4 py-6">
      <div
        aria-modal="true"
        role="dialog"
        className="w-full max-w-md rounded-lg border border-border bg-card p-4 text-card-foreground shadow-subtle"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">{isEdit ? "Editar ativo" : "Adicionar ativo"}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {isEdit ? "Ajuste os valores atuais da posicao." : "Informe os dados obrigatorios da compra."}
            </p>
          </div>
          <Button aria-label="Fechar modal" className="h-8 w-8 px-0" variant="ghost" onClick={onCancel}>
            <X size={17} />
          </Button>
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">
            <AlertCircle size={17} className="shrink-0 text-destructive" />
            <span>{error}</span>
          </div>
        )}

        <div className="mt-4 grid gap-3">
          <div>
            <Label>Ticker</Label>
            <Input
              disabled={isEdit}
              required
              value={form.ticker}
              onChange={(event) => onChange({ ...form, ticker: event.target.value })}
              placeholder="BBDC4"
            />
          </div>
          <div>
            <Label>Quantidade</Label>
            <Input
              autoFocus
              required
              inputMode="decimal"
              value={form.quantity}
              onChange={(event) => onChange({ ...form, quantity: event.target.value })}
              placeholder="100"
            />
          </div>
          <div>
            <Label>Preco medio</Label>
            <Input
              required
              inputMode="decimal"
              value={form.average_price}
              onChange={(event) => onChange({ ...form, average_price: event.target.value })}
              placeholder="12.50"
            />
          </div>
          <div>
            <Label>Tipo</Label>
            <Select
              required
              value={form.asset_type}
              onChange={(event) => onChange({ ...form, asset_type: event.target.value })}
            >
              {ASSET_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onCancel}>
            Cancelar
          </Button>
          <Button onClick={onSubmit}>{isEdit ? "Salvar" : "Adicionar"}</Button>
        </div>
      </div>
    </div>
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
