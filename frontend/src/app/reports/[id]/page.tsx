"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, ArrowLeft } from "lucide-react";
import ReportViewer from "@/components/ReportViewer";
import { api } from "@/lib/api";

export default function ReportPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    sessionId: string;
    summary: Record<string, unknown>;
    excelFiles: import("@/lib/api").ExcelFileInfo[];
  } | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    (async () => {
      const res = await api.getResult(sessionId);
      setLoading(false);
      if (res.error) {
        setError(res.error);
      } else if (res.data) {
        setResult({
          sessionId: res.data.session_id,
          summary: res.data.summary,
          excelFiles: res.data.excel_files,
        });
      }
    })();
  }, [sessionId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
        <span className="ml-2 text-gray-400">加载处理结果...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto text-center py-20">
        <p className="text-red-500 mb-4">加载失败: {error}</p>
        <Link
          href="/history"
          className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          返回历史记录
        </Link>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="text-center py-20 text-gray-400">
        <p>未找到处理结果</p>
      </div>
    );
  }

  return (
    <div>
      <div className="max-w-2xl mx-auto mb-4">
        <Link
          href="/history"
          className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          返回历史记录
        </Link>
      </div>
      <ReportViewer
        sessionId={result.sessionId}
        summary={result.summary}
        excelFiles={result.excelFiles}
      />
    </div>
  );
}
