"use client";

import { useState, useEffect, useRef } from "react";
import { Loader2, CheckCircle2, XCircle, Clock, FileText } from "lucide-react";
import clsx from "clsx";
import { api, SessionStatus, ProcessResult } from "@/lib/api";

const STEP_LABELS: Record<string, string> = {
  clean: "数据清洗",
  metrics: "指标计算",
  pivot: "透视分析",
};

const STEP_ORDER = ["clean", "metrics", "pivot"];

interface ProcessingStatusProps {
  sessionId: string;
  onComplete: (result: ProcessResult) => void;
}

export default function ProcessingStatus({ sessionId, onComplete }: ProcessingStatusProps) {
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [resultLoading, setResultLoading] = useState(false);
  const [pollError, setPollError] = useState<string | null>(null);
  const [started, setStarted] = useState(false);
  const [starting, setStarting] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  // 自动启动处理
  const doStart = async () => {
    setStarting(true);
    setPollError(null);
    const res = await api.startProcessing(sessionId);
    setStarting(false);
    if (res.error) {
      setPollError(res.error);
    } else {
      setStarted(true);
    }
  };

  const poll = async () => {
    if (!mountedRef.current) return;
    const res = await api.getStatus(sessionId);
    if (!mountedRef.current) return;
    if (res.data) {
      setStatus(res.data);
      setPollError(null);

      if (res.data.status === "completed") {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setResultLoading(true);
        const result = await api.getResult(sessionId);
        setResultLoading(false);
        if (mountedRef.current && result.data) {
          onComplete(result.data);
        }
      } else if (res.data.status === "failed") {
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    } else if (res.error) {
      setPollError(res.error);
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    // 自动启动处理
    doStart();
    // 轮询状态
    setTimeout(() => poll(), 1000);
    intervalRef.current = setInterval(poll, 2000);
    return () => {
      mountedRef.current = false;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [sessionId]);

  const currentStepIdx = status?.current_step
    ? STEP_ORDER.indexOf(status.current_step)
    : -1;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="bg-white rounded-xl border p-6">
        <h3 className="text-lg font-semibold mb-2">处理进度</h3>
        <p className="text-sm text-gray-500 mb-4">
          会话: <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">{sessionId}</code>
        </p>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
          <div
            className={clsx(
              "h-2 rounded-full transition-all duration-500",
              status?.status === "failed" ? "bg-red-500" : "bg-primary-500"
            )}
            style={{ width: `${status?.progress || 0}%` }}
          />
        </div>

        {/* Steps */}
        <div className="space-y-3">
          {STEP_ORDER.map((step, idx) => {
            const completed = status?.steps_completed?.includes(step);
            const current = status?.current_step === step && status?.status === "processing";
            const failed = status?.status === "failed" && status.current_step === step;
            const pending = !completed && !current && !failed;

            return (
              <div key={step} className="flex items-center gap-3">
                {completed ? (
                  <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0" />
                ) : current ? (
                  <Loader2 className="w-5 h-5 text-primary-500 animate-spin shrink-0" />
                ) : failed ? (
                  <XCircle className="w-5 h-5 text-red-500 shrink-0" />
                ) : (
                  <Clock className="w-5 h-5 text-gray-300 shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span
                      className={clsx(
                        "text-sm font-medium",
                        completed && "text-green-700",
                        current && "text-primary-700",
                        failed && "text-red-700",
                        pending && "text-gray-400"
                      )}
                    >
                      {STEP_LABELS[step] || step}
                    </span>
                    {completed && <span className="text-xs text-green-500">完成</span>}
                    {current && <span className="text-xs text-primary-500">处理中...</span>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Poll Error */}
        {pollError && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <strong>错误:</strong> {pollError}
            <p className="mt-1 text-xs text-red-600">
              可能是会话已过期或处理未启动。请重新上传文件。
            </p>
            <div className="mt-2 flex gap-2">
              <button
                onClick={doStart}
                disabled={starting}
                className="text-xs px-3 py-1 bg-red-100 hover:bg-red-200 text-red-700 rounded transition-colors"
              >
                {starting ? "启动中..." : "重试启动"}
              </button>
              <a href="/" className="text-xs px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded transition-colors">
                重新上传
              </a>
            </div>
          </div>
        )}

        {/* Starting indicator */}
        {starting && (
          <div className="mt-4 flex items-center gap-2 text-sm text-gray-500">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在启动处理流程...
          </div>
        )}

        {/* Error */}
        {status?.error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <strong>错误:</strong> {status.error}
          </div>
        )}

        {/* Loading result */}
        {resultLoading && (
          <div className="mt-4 flex items-center gap-2 text-sm text-gray-500">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在获取处理结果...
          </div>
        )}
      </div>
    </div>
  );
}
