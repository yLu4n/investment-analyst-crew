import type {
  AnalysisCreatedResponse,
  AnalysisRequest,
  AnalysisResult,
  AnalysisStatus,
  AssetInput,
} from "@/types/analysis";
import { createSupabaseBrowserClient } from "@/lib/supabase";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const accessToken = await getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `Falha na API (${response.status}).`;
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail ?? message;
    } catch {
      // Keep the status-based fallback.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

async function getAccessToken() {
  const supabase = createSupabaseBrowserClient();
  if (!supabase) {
    return null;
  }

  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export function createAnalysis(payload: AnalysisRequest) {
  return request<AnalysisCreatedResponse>("/analysis", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAnalysisStatus(jobId: string) {
  return request<AnalysisStatus>(`/analysis/status/${jobId}`);
}

export function getAnalysisResult(jobId: string) {
  return request<AnalysisResult>(`/analysis/result/${jobId}`);
}

export function getPaginatedAssets(assets: AssetInput[], page: number, pageSize = 10) {
  const start = Math.max(0, (page - 1) * pageSize);
  return {
    rows: assets.slice(start, start + pageSize).map((asset, index) => ({
      ...asset,
      id: `${asset.ticker}-${start + index}`,
    })),
    total: assets.length,
    pageCount: Math.max(1, Math.ceil(assets.length / pageSize)),
  };
}
