export type UserPlan = "free" | "pro";

export type AssetInput = {
  ticker: string;
  quantity: number;
  average_price: number;
  asset_type?: string;
};

export type RiskProfile = "conservative" | "moderate" | "aggressive";

export type AnalysisRequest = {
  assets: AssetInput[];
  risk_profile: RiskProfile;
  monthly_contribution: number;
};

export type AnalysisCreatedResponse = {
  job_id: string;
};

export type AnalysisStatus = {
  status: "pending" | "running" | "completed" | "failed";
  current_step: string;
  progress_percentage: number;
  attempt_count: number;
  max_attempts: number;
  retry_backoff_seconds: number | null;
  next_retry_at: string | null;
  error_message: string | null;
};

export type AnalysisResult = {
  job_id: string;
  result_payload: Record<string, unknown>;
  report_markdown: string;
  pdf_path: string | null;
};

export type PortfolioRow = AssetInput & {
  id: string;
};

export type ImportParseResult =
  | { ok: true; assets: AssetInput[] }
  | { ok: false; message: string };
