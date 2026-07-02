import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/**
 * 从 Supabase 直读历史记录（绕过 API，更快）
 */
export async function fetchHistoryFromSupabase(limit = 20) {
  const { data, error } = await supabase
    .from("processing_sessions")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);

  if (error) throw error;
  return data;
}

/**
 * 从 Supabase 直读报告数据
 */
export async function fetchReportFromSupabase(sessionId: string) {
  const { data, error } = await supabase
    .from("reports")
    .select("*")
    .eq("session_id", sessionId)
    .single();

  if (error) throw error;
  return data;
}
