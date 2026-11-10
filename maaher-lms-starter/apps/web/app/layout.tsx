import type { ReactNode } from 'react';
import './globals.css';
export const dynamic = 'force-dynamic';
export const metadata = { title: 'Maaher LMS — Pembelajaran coding', description: 'Kelola kursus dan materi pembelajaran coding bersama organisasi Anda' };
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="id"><body>{children}</body></html>;
}
