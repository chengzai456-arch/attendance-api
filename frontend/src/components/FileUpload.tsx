"use client";

import { useState, useCallback, useRef } from "react";
import { Upload, FileSpreadsheet, X, CheckCircle2, AlertCircle, Paperclip } from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";

const FILE_TYPES = [
  { key: "raw_data", label: "原始考勤数据", required: true, hint: "每日打卡工时推送模版" },
  { key: "leave", label: "离职流程", required: true, hint: "离职流程表" },
  { key: "roster", label: "花名册", required: true, hint: "花名册" },
  { key: "shift", label: "班次", required: true, hint: "班次字典" },
  { key: "resign", label: "补签管理", required: true, hint: "补签管理记录" },
  { key: "gus_whitelist", label: "GUS白名单", required: false, hint: "GUS需剔除人员" },
  { key: "sign_this_week", label: "本周签字报表", required: true, hint: "GUS+美区签字报表（无括号）" },
  { key: "sign_last_week", label: "上周签字报表", required: true, hint: "GUS+美区签字报表 (2)" },
  { key: "sign_biweek", label: "双周签字报表", required: true, hint: "GUS+美区签字报表 (1)" },
];

// 关键词匹配数组 — 与后端 EXPECTED_FILES 保持一致
const KEYWORD_MATCHERS: Record<string, string[]> = {
  raw_data: ["每日打卡", "工时推送", "原始数据"],
  leave: ["离职流程", "离职"],
  roster: ["花名册"],
  shift: ["班次"],
  resign: ["补签管理", "补签"],
  gus_whitelist: ["GUS需剔除", "GUS白名单", "白名单"],
  // 签字报表支持两种命名：中文关键词 或 GUS+美区签字报表+括号序号
  sign_this_week: ["本周加班", "本周", "签字报表"],
  sign_last_week: ["上周加班", "上周"],
  sign_biweek: ["双周累计", "双周"],
};

// 签字报表关键词（用于识别签字报表文件）
const SIGN_REPORT_KEYWORDS = ["签字报表", "美区签字", "GUS+美区"];

/** 从文件名中提取括号里的数字，如 "报表 (2).xlsx" → 2 */
function extractBracketNumber(filename: string): number | null {
  const m = filename.match(/\((\d+)\)/);
  return m ? parseInt(m[1]) : null;
}

/** 智能匹配签字报表三种（与后端 _match_sign_reports 保持一致） */
function matchSignReports(filenames: string[]): Record<string, string> {
  const result: Record<string, string> = {};

  // 先尝试中文关键词
  for (const fname of filenames) {
    if (["本周加班", "本周"].some((kw) => fname.includes(kw)) && !result.sign_this_week) {
      result.sign_this_week = fname;
    } else if (["上周加班", "上周"].some((kw) => fname.includes(kw)) && !result.sign_last_week) {
      result.sign_last_week = fname;
    } else if (["双周累计", "双周"].some((kw) => fname.includes(kw)) && !result.sign_biweek) {
      result.sign_biweek = fname;
    }
  }

  // 找出所有签字报表文件
  const signFiles = filenames.filter((f) => SIGN_REPORT_KEYWORDS.some((kw) => f.includes(kw)));
  const unmatched = signFiles.filter((f) => !Object.values(result).includes(f));
  if (unmatched.length === 0) return result;

  const noNum = unmatched.filter((f) => extractBracketNumber(f) === null);
  const num2 = unmatched.filter((f) => extractBracketNumber(f) === 2);
  const num1 = unmatched.filter((f) => extractBracketNumber(f) === 1);

  if (!result.sign_this_week && noNum.length > 0) result.sign_this_week = noNum[0];
  if (!result.sign_last_week && num2.length > 0) result.sign_last_week = num2[0];
  if (!result.sign_biweek && num1.length > 0) result.sign_biweek = num1[0];

  return result;
}

interface FileUploadProps {
  onUploaded: (sessionId: string) => void;
}

export default function FileUpload({ onUploaded }: FileUploadProps) {
  // 所有上传的原始文件
  const [files, setFiles] = useState<File[]>([]);
  // 文件类型 → 文件名 映射
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [matchMode, setMatchMode] = useState<"auto" | "manual">("auto");
  const inputRef = useRef<HTMLInputElement>(null);

  // ---- 自动匹配 ----
  const autoMatch = useCallback((allFiles: File[]) => {
    const newAssignments: Record<string, string> = {};
    const allFilenames = allFiles.map((f) => f.name);
    const remaining = new Set(allFilenames);

    // 非签字报表：按 FILE_TYPES 顺序匹配
    const signTypes = new Set(["sign_this_week", "sign_last_week", "sign_biweek"]);
    for (const ft of FILE_TYPES) {
      if (signTypes.has(ft.key)) continue;
      for (const fname of remaining) {
        if (KEYWORD_MATCHERS[ft.key]?.some((kw) => fname.includes(kw))) {
          newAssignments[ft.key] = fname;
          remaining.delete(fname);
          break;
        }
      }
    }

    // 签字报表：智能括号序号匹配
    const signMatched = matchSignReports(allFilenames);
    for (const [ftype, fname] of Object.entries(signMatched)) {
      newAssignments[ftype] = fname;
    }

    setAssignments((prev) => ({ ...prev, ...newAssignments }));
  }, []);

  // ---- 文件收集 ----
  const handleFiles = useCallback(
    (newFiles: FileList | File[]) => {
      const arr = Array.from(newFiles).filter(
        (f) => f.name.endsWith(".xlsx") || f.name.endsWith(".xls")
      );
      setFiles((prev) => {
        const existing = new Set(prev.map((f) => f.name));
        const merged = [...prev, ...arr.filter((f) => !existing.has(f.name))];
        // 全量自动匹配
        if (matchMode === "auto") {
          setTimeout(() => autoMatch(merged), 0);
        }
        return merged;
      });
      setError(null);
    },
    [matchMode, autoMatch]
  );

  // ---- 按类型指定（手动模式） ----
  const pickForType = (typeKey: string) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".xlsx,.xls";
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      // 加入文件列表
      setFiles((prev) => {
        const existing = new Set(prev.map((f) => f.name));
        const merged = existing.has(file.name) ? prev : [...prev, file];
        return merged;
      });
      setAssignments((prev) => ({ ...prev, [typeKey]: file.name }));
      setError(null);
    };
    input.click();
  };

  const removeFile = (name: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== name));
    setAssignments((prev) => {
      const next = { ...prev };
      for (const k of Object.keys(next)) {
        if (next[k] === name) delete next[k];
      }
      return next;
    });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  // ---- 上传 ----
  const handleUpload = async () => {
    if (files.length === 0) {
      setError("请先选择文件");
      return;
    }
    setUploading(true);
    setError(null);

    const res = await api.uploadFiles(files);
    if (res.error) {
      setError(res.error);
    } else if (res.data) {
      if (res.data.missing_files.length > 0) {
        setError(`缺少文件: ${res.data.missing_files.join(", ")}`);
      } else {
        onUploaded(res.data.session_id);
      }
    }
    setUploading(false);
  };

  // ---- 匹配到的文件列表（用于显示） ----
  const assignedFilenames = new Set(Object.values(assignments));
  const unassignedFiles = files.filter((f) => !assignedFilenames.has(f.name));

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* ---- 大批量拖拽区 ---- */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all",
          dragOver
            ? "border-primary-400 bg-primary-50"
            : "border-gray-300 hover:border-primary-300 hover:bg-gray-50"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".xlsx,.xls"
          className="hidden"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
        <Upload className="w-10 h-10 mx-auto mb-3 text-gray-400" />
        <p className="text-gray-600 font-medium">拖拽所有 Excel 文件到这里，自动匹配类型</p>
        <p className="text-sm text-gray-400 mt-1">支持 .xlsx / .xls，单次最多 50MB</p>
      </div>

      {/* ---- 匹配模式切换 ---- */}
      {files.length > 0 && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-gray-400">匹配模式：</span>
          {(["auto", "manual"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMatchMode(m)}
              className={clsx(
                "text-xs px-3 py-1 rounded-full border transition-colors",
                matchMode === m
                  ? "bg-primary-100 border-primary-300 text-primary-700"
                  : "bg-white border-gray-200 text-gray-500 hover:border-gray-300"
              )}
            >
              {m === "auto" ? "自动匹配" : "手动指派"}
            </button>
          ))}
        </div>
      )}

      {/* ---- 文件类型 → 文件 一一对应槽位 ---- */}
      <div className="mt-4 space-y-2">
        {FILE_TYPES.map((ft) => {
          const assignedName = assignments[ft.key];
          const isFilled = !!assignedName;
          // 尝试找一个匹配但还没分配的文件
          const hintFile = !isFilled
            ? files.find(
                (f) =>
                  !assignedFilenames.has(f.name) &&
                  KEYWORD_MATCHERS[ft.key]?.some((kw) => f.name.includes(kw))
              )
            : null;

          return (
            <div
              key={ft.key}
              className={clsx(
                "flex items-center gap-3 px-4 py-2.5 rounded-lg border transition-all",
                isFilled
                  ? "bg-green-50 border-green-200"
                  : "bg-white border-gray-200 hover:border-gray-300"
              )}
            >
              {/* 类型标签 */}
              <div className="w-36 shrink-0 flex items-center gap-1.5">
                {isFilled ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                ) : (
                  <div
                    className={clsx(
                      "w-4 h-4 rounded-full border-2",
                      ft.required ? "border-amber-300" : "border-gray-300"
                    )}
                  />
                )}
                <span className={clsx("text-sm font-medium", isFilled ? "text-green-800" : "text-gray-600")}>
                  {ft.label}
                </span>
                {!ft.required && (
                  <span className="text-[10px] text-gray-400">可选</span>
                )}
              </div>

              {/* 文件区域 */}
              {isFilled ? (
                <div className="flex-1 flex items-center gap-2 min-w-0">
                  <FileSpreadsheet className="w-4 h-4 text-green-600 shrink-0" />
                  <span className="text-sm text-green-700 truncate">{assignedName}</span>
                  <button
                    onClick={() => {
                      setAssignments((prev) => {
                        const next = { ...prev };
                        delete next[ft.key];
                        return next;
                      });
                    }}
                    className="ml-auto p-0.5 hover:bg-green-100 rounded shrink-0"
                  >
                    <X className="w-3.5 h-3.5 text-green-400" />
                  </button>
                </div>
              ) : matchMode === "manual" ? (
                <button
                  onClick={() => pickForType(ft.key)}
                  className="flex-1 flex items-center gap-1.5 text-sm text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded px-3 py-1.5 transition-colors"
                >
                  <Paperclip className="w-3.5 h-3.5" />
                  点击选择文件
                </button>
              ) : hintFile ? (
                <div className="flex-1 flex items-center gap-2 min-w-0">
                  <FileSpreadsheet className="w-4 h-4 text-amber-500 shrink-0" />
                  <span className="text-sm text-amber-700 truncate">{hintFile.name}</span>
                  <button
                    onClick={() => {
                      setAssignments((prev) => ({ ...prev, [ft.key]: hintFile.name }));
                    }}
                    className="ml-auto text-xs text-primary-600 hover:underline shrink-0"
                  >
                    确认匹配
                  </button>
                </div>
              ) : (
                <span className="flex-1 text-sm text-gray-300 truncate">
                  {ft.hint}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* ---- 未分配文件 ---- */}
      {unassignedFiles.length > 0 && (
        <div className="mt-4 space-y-1">
          <p className="text-xs text-gray-400">未匹配文件 ({unassignedFiles.length})</p>
          {unassignedFiles.map((f) => (
            <div
              key={f.name}
              className="flex items-center justify-between bg-white border border-dashed border-gray-300 rounded-lg px-4 py-2"
            >
              <div className="flex items-center gap-2 min-w-0">
                <FileSpreadsheet className="w-4 h-4 text-gray-400 shrink-0" />
                <span className="text-sm text-gray-500 truncate">{f.name}</span>
              </div>
              <button
                onClick={() => removeFile(f.name)}
                className="p-1 hover:bg-gray-100 rounded shrink-0"
              >
                <X className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-4 py-2.5">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Upload Button */}
      <div className="mt-6 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          已匹配 {Object.keys(assignments).length} / {FILE_TYPES.filter((t) => t.required).length} 类必填
        </span>
        <button
          onClick={handleUpload}
          disabled={uploading || files.length === 0}
          className={clsx(
            "px-8 py-2.5 rounded-lg font-medium text-white transition-all",
            uploading || files.length === 0
              ? "bg-gray-300 cursor-not-allowed"
              : "bg-primary-600 hover:bg-primary-700 active:scale-95"
          )}
        >
          {uploading ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full" />
              上传中...
            </span>
          ) : (
            "上传并处理"
          )}
        </button>
      </div>
    </div>
  );
}
