"use client";

import { ArrowLeft, Download, FileSpreadsheet, ExternalLink } from "lucide-react";
import Link from "next/link";
import { ExcelFileInfo } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function fmtSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

interface ReportViewerProps {
  sessionId: string;
  summary: Record<string, unknown>;
  excelFiles?: ExcelFileInfo[];
}

export default function ReportViewer({ sessionId, summary, excelFiles }: ReportViewerProps) {
  const summaryItems = [
    { label: "总人数", value: String(summary.total_people ?? "-") },
    { label: "排班率", value: String(summary.scheduled_rate ?? "-") },
    { label: "排班正确率", value: String(summary.correct_rate ?? "-") },
    { label: "日超8H", value: String(summary.over_8h_count ?? "-") },
  ];

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {summaryItems.map((item) => (
          <div key={item.label} className="bg-white border rounded-xl p-4 text-center">
            <div className="text-2xl font-bold text-primary-700">{item.value}</div>
            <div className="text-xs text-gray-500 mt-1">{item.label}</div>
          </div>
        ))}
      </div>

      {/* Excel Download Section */}
      <div className="bg-white border rounded-xl p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">下载处理结果</h3>
        {excelFiles && excelFiles.length > 0 ? (
          <div className="space-y-2">
            {excelFiles.map((f) => (
              <a
                key={f.filename}
                href={`${API_BASE}${f.download_url}`}
                download={f.filename}
                className="flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200
                           hover:bg-primary-50 hover:border-primary-300 transition-colors group"
              >
                <div className="w-9 h-9 rounded-lg bg-green-100 flex items-center justify-center
                                group-hover:bg-green-200 transition-colors">
                  <FileSpreadsheet className="w-5 h-5 text-green-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-800">{f.label}</div>
                  <div className="text-xs text-gray-400">
                    {f.filename} · {fmtSize(f.size_bytes)}
                  </div>
                </div>
                <Download className="w-4 h-4 text-gray-400 group-hover:text-primary-600 transition-colors shrink-0" />
              </a>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">暂无可下载的文件</p>
        )}
      </div>

      {/* Back */}
      <div className="mt-4 text-center">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-gray-400 hover:text-gray-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          重新上传
        </Link>
      </div>
    </div>
  );
}
