"use client";

import { useState } from "react";
import FileUpload from "@/components/FileUpload";
import ProcessingStatus from "@/components/ProcessingStatus";
import ReportViewer from "@/components/ReportViewer";
import { ProcessResult } from "@/lib/api";

type Step = "upload" | "processing" | "result";

export default function HomePage() {
  const [step, setStep] = useState<Step>("upload");
  const [sessionId, setSessionId] = useState<string>("");
  const [result, setResult] = useState<ProcessResult | null>(null);

  const handleUploaded = (sid: string) => {
    setSessionId(sid);
    setStep("processing");
  };

  const handleComplete = (res: ProcessResult) => {
    setResult(res);
    setStep("result");
  };

  return (
    <div>
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold mb-2">考勤数据处理</h1>
        <p className="text-gray-500 text-sm">
          上传 Excel 文件，自动完成数据清洗、指标计算、透视分析和报告生成
        </p>
      </div>

      {step === "upload" && <FileUpload onUploaded={handleUploaded} />}
      {step === "processing" && (
        <ProcessingStatus sessionId={sessionId} onComplete={handleComplete} />
      )}
      {step === "result" && result && (
        <ReportViewer
          sessionId={sessionId}
          summary={result.summary}
          excelFiles={result.excel_files}
        />
      )}
    </div>
  );
}
