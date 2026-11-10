import type { ReactNode } from 'react';
import './globals.css';
export const dynamic = 'force-dynamic';
export const metadata = { title: 'Maaher LMS — Engineering Starter', description: 'Scaffold LMS pembelajaran coding' };
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="id"><body>{children}</body></html>;
}
