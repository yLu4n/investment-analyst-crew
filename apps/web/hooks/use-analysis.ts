"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createAnalysis, getAnalysisResult, getAnalysisStatus } from "@/lib/api";
import type { AnalysisRequest } from "@/types/analysis";

export function useCreateAnalysis() {
  return useMutation({
    mutationFn: (payload: AnalysisRequest) => createAnalysis(payload),
  });
}

export function useAnalysisStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["analysis-status", jobId],
    queryFn: () => getAnalysisStatus(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const step = query.state.data?.current_step;
      if (status === "completed" || status === "failed") {
        return false;
      }
      return step === "executing_analysis" ? 3000 : 5000;
    },
  });
}

export function useAnalysisResult(jobId: string | null, enabled: boolean) {
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: ["analysis-result", jobId],
    queryFn: async () => {
      const result = await getAnalysisResult(jobId as string);
      await queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      return result;
    },
    enabled: Boolean(jobId) && enabled,
  });
}
