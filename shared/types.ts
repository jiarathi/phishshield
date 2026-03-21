export type RiskLabel = "low" | "medium" | "high";

export interface AnalyzeRequest {
  text: string;
}

export interface IntentInfo {
  category: string;
  confidence: number; // 0..1
  signals: string[];
}

export interface ReputationInfo {
  provider: string;
  status: "clean" | "malicious" | "unknown" | "error";
  details: Record<string, unknown>;
}

export interface UrlFinding {
  url: string;
  final_url: string | null;
  domain: string | null;
  risk_label: RiskLabel;
  risk_score: number; // 0..1
  reasons: string[];
  reputation: ReputationInfo;
}

export interface ModelInfo {
  name: string;
  version: string;
  threshold: number;
}

export interface AnalyzeResponse {
  risk_label: RiskLabel;
  risk_score: number; // 0..1
  is_scam: boolean;
  summary: string;
  reasons: string[];
  actions: string[];
  intent: IntentInfo;
  url_findings: UrlFinding[];
  model: ModelInfo;
}
