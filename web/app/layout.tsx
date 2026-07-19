import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '기차 예약 매크로',
  description: 'SRT/KTX 예약 매크로 웹 버전',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
