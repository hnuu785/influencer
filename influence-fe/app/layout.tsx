import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "스토리로그 — 나의 하루가 콘텐츠가 됩니다",
  description: "일상의 기록을 나다운 퍼스널 브랜딩 콘텐츠로 바꾸는 AI 워크플로우",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
