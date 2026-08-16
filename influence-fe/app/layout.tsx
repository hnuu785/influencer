import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Storylog — 나의 하루가 나다운 콘텐츠가 된다",
  description: "실제 경험을 근거가 보이는 스토리 카드와 채널별 콘텐츠로 바꾸는 개인 브랜딩 워크플로우",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" data-scroll-behavior="smooth">
      <body>{children}</body>
    </html>
  );
}
