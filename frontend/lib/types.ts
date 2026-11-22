export type Mode = "web" | "personal" | "ai";
export interface User { id: number; email: string; display_name: string; role: string }
export interface WebResult { title: string; url: string; snippet: string }
export interface PersonalResult {
  id: number; kind: string; title: string; url: string; snippet: string; tags: string[]; score: number; created_at: string;
}
export interface Citation {
  index: number; type: "personal" | "web"; title: string; url: string; item_id: number | null; snippet: string; cited: boolean;
}
export interface AIAnswer { answer: string; citations: Citation[]; warnings?: string[]; conversation_id?: number | null }
export interface Item {
  id: number; kind: "note" | "bookmark" | "document"; title: string; url: string; status: "pending" | "ready" | "failed";
  error: string; tags: string[]; collection_ids: number[]; original_name: string | null; snippet: string; created_at: string;
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Collection { id: number; name: string; description: string; item_count: number }
export interface HistoryEntry { id: number; mode: Mode; query: string; result_count: number; created_at: string }
export interface Conversation { id: number; title: string; updated_at: string }
export interface Message { id: number; role: "user" | "assistant"; content: string; citations: Citation[] }
export interface Settings {
  save_search_history: boolean; ai_memory_enabled: boolean; default_search_mode: Mode;
  ai_use_web: boolean; ai_use_personal: boolean; results_per_page: number;
}
export interface Insights {
  period_days: number; library: Record<string, number>; searches_by_mode: Record<string, number>;
  searches_per_day: { date: string; count: number }[]; top_queries: { query: string; count: number }[]; conversations: number;
}
