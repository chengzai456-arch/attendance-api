"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Clock, CheckCircle2, XCircle, Loader2, ChevronRight, FileText, Trash2 } from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface HistoryItem {
  id: number;
  session_id: string;
  date: string | null;
  status: string;
  files_uploaded: string[];
  summary: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="w-5 h-5 text-green-500" />,
  failed: <XCircle className="w-5 h-5 text-red-500" />,
  processing: <Loader2 className="w-5 h-5 text-primary-500 animate-spin" />,
  uploaded: <Clock className="w-5 h-5 text-gray-400" />,
};

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    const res = await api.getHistory(50);
    if (res.error) {
      setError(res.error);
    } else if (res.data) {
      setItems(res.data.history as HistoryItem[]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleDelete = async (sessionId: string) => {
    if (!confirm(`确定删除会话 ${sessionId.slice(0, 19)} 吗？\n此操作将删除数据库记录、Storage 文件和本地文件。`)) return;
    setDeleting(sessionId);
    try {
      const res = await fetch(`${API_BASE}/api/v1/process/${sessionId}/cancel`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        alert(`删除失败: ${err.detail || res.statusText}`);
      }
    } catch (e) {
      alert(`删除失败: ${e instanceof Error ? e.message : "网络错误"}`);
    } finally {
      setDeleting(null);
      loadHistory();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
        <span className="ml-2 text-gray-400">加载中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-20">
        <p className="text-red-500">加载失败: {error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">处理历史</h1>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>暂无处理记录</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div
              key={item.session_id}
              className="bg-white border rounded-xl p-4 hover:shadow-md transition-all group"
            >
              <div className="flex items-center justify-between">
                <Link
                  href={
                    item.status === "completed"
                      ? `/reports/${item.session_id}`
                      : "#"
                  }
                  className={clsx(
                    "flex-1 min-w-0 flex items-center gap-3",
                    item.status === "completed" ? "cursor-pointer" : ""
                  )}
                >
                  <span className="shrink-0">
                    {STATUS_ICONS[item.status] || <Clock className="w-5 h-5 text-gray-400" />}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm truncate">
                        {item.session_id.slice(0, 19)}
                      </span>
                      <span
                        className={clsx(
                          "text-xs px-2 py-0.5 rounded-full",
                          item.status === "completed" && "bg-green-100 text-green-700",
                          item.status === "failed" && "bg-red-100 text-red-700",
                          item.status === "processing" && "bg-primary-100 text-primary-700",
                          item.status === "uploaded" && "bg-gray-100 text-gray-600",
                        )}
                      >
                        {item.status === "completed" ? "完成" :
                         item.status === "failed" ? "失败" :
                         item.status === "processing" ? "处理中" : "已上传"}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {item.date || "-"} · {item.files_uploaded?.length || 0} 个文件
                      {item.summary && ` · ${item.summary.total_people || "?"} 人`}
                    </div>
                  </div>
                </Link>
                <div className="flex items-center gap-2 ml-2 shrink-0">
                  {item.status === "completed" && (
                    <ChevronRight className="w-5 h-5 text-gray-300" />
                  )}
                  <button
                    onClick={() => handleDelete(item.session_id)}
                    disabled={deleting === item.session_id}
                    className="opacity-40 group-hover:opacity-100 transition-opacity p-1.5
                               rounded-lg hover:bg-red-50 hover:text-red-600 disabled:opacity-50
                               disabled:cursor-not-allowed"
                    title="删除此记录"
                  >
                    {deleting === item.session_id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
              {item.error && (
                <div className="mt-2 text-xs text-red-500 bg-red-50 rounded px-3 py-1.5">
                  {item.error}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
