import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "考勤数据处理平台",
  description: "GUS 考勤排班数据分析全流程处理平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <header className="border-b bg-white sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
            <a href="/" className="flex items-center gap-2 font-semibold text-lg">
              <svg className="w-6 h-6 text-primary-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18M9 21V9" />
              </svg>
              考勤处理平台
            </a>
            <nav className="flex items-center gap-4 text-sm">
              <a href="/" className="hover:text-primary-600 transition-colors">上传处理</a>
              <a href="/history" className="hover:text-primary-600 transition-colors">历史记录</a>
            </nav>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
