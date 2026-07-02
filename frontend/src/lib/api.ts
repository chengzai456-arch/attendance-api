/**
 * API 客户端 - 与 FastAPI 后端通信
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ApiResponse<T = unknown> {
  data?: T;
  error?: string;
}

export interface SessionStatus {
  session_id: string;
  status: "uploaded" | "processing" | "completed" | "failed";
  current_step: string | null;
  progress: number;
  steps_completed: string[];
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ExcelFileInfo {
  filename: string;
  label: string;
  size_bytes: number;
  download_url: string;
}

export interface ProcessResult {
  session_id: string;
  summary: Record<string, unknown>;
  excel_files: ExcelFileInfo[];
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, options?: RequestInit): Promise<ApiResponse<T>> {
    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...options?.headers,
        },
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        return { error: err.detail || `HTTP ${res.status}` };
      }

      const contentType = res.headers.get("content-type") || "";

      // HTML 响应直接返回文本
      if (contentType.includes("text/html")) {
        const html = await res.text();
        return { data: html as unknown as T };
      }

      const data = await res.json();
      return { data };
    } catch (e) {
      return { error: e instanceof Error ? e.message : "网络错误" };
    }
  }

  /** 上传文件 */
  async uploadFiles(files: File[], sessionId?: string): Promise<ApiResponse<{ session_id: string; files_uploaded: string[]; missing_files: string[] }>> {
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    if (sessionId) formData.append("session_id", sessionId);

    try {
      const res = await fetch(`${this.baseUrl}/api/v1/files/upload?${sessionId ? `session_id=${sessionId}` : ""}`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      return res.ok ? { data } : { error: data.detail };
    } catch (e) {
      return { error: e instanceof Error ? e.message : "上传失败" };
    }
  }

  /** 开始处理 */
  async startProcessing(sessionId: string, date?: string, rosterIndex?: number): Promise<ApiResponse<SessionStatus>> {
    return this.request<SessionStatus>("/api/v1/process/start", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, date, roster_index: rosterIndex }),
    });
  }

  /** 轮询处理状态 */
  async getStatus(sessionId: string): Promise<ApiResponse<SessionStatus>> {
    return this.request<SessionStatus>(`/api/v1/process/${sessionId}/status`);
  }

  /** 获取处理结果摘要 */
  async getResult(sessionId: string): Promise<ApiResponse<ProcessResult>> {
    return this.request<ProcessResult>(`/api/v1/process/${sessionId}/result`);
  }

  /** 获取报告 HTML */
  async getReportHtml(sessionId: string): Promise<ApiResponse<string>> {
    return this.request<string>(`/api/v1/reports/${sessionId}/html`);
  }

  /** 获取报告 JSON */
  async getReportJson(sessionId: string): Promise<ApiResponse<unknown>> {
    return this.request<unknown>(`/api/v1/reports/${sessionId}/json`);
  }

  /** 获取历史记录 */
  async getHistory(limit = 20): Promise<ApiResponse<{ history: unknown[] }>> {
    return this.request<{ history: unknown[] }>(`/api/v1/reports/history?limit=${limit}`);
  }

  /** 检查后端健康 */
  async healthCheck(): Promise<ApiResponse<{ status: string }>> {
    return this.request<{ status: string }>("/api/health");
  }

  /** 获取会话文件信息 */
  async getSessionFiles(sessionId: string): Promise<ApiResponse<{ files: string[]; matched: Record<string, string>; missing: string[] }>> {
    return this.request(`/api/v1/files/${sessionId}/files`);
  }
}

export const api = new ApiClient(API_BASE);
