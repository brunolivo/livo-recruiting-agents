export interface Candidate {
  name: string;
  role_type: string;
  source: string;
  profile_url?: string;
  headline?: string;
  location?: string;
  skills: string[];
  experience_years?: number;
  notable_work?: string;
  enriched_summary?: string;
  ai_expertise_depth?: string;
  recent_activity?: string;
  fit_score: number;
  technical_score: number;
  culture_score: number;
  scoring_rationale?: string;
  recommended: boolean;
  outreach_subject?: string;
  outreach_message?: string;
  outreach_channel?: string;
}

export interface PipelineStats {
  sourced: number;
  enriched: number;
  scored: number;
  recommended: number;
  outreached: number;
}

export interface InterviewInsights {
  candidate_name: string;
  key_strengths: string[];
  areas_of_concern: string[];
  technical_assessment?: string;
  cultural_fit_assessment?: string;
  recommendation?: string;
  next_steps: string[];
  summary?: string;
}
