import type { ReactNode } from 'react';
export const metadata = { title: 'Maaher LMS — Engineering Starter', description: 'Scaffold LMS pembelajaran coding' };
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="id"><body style={{fontFamily:'system-ui, sans-serif',margin:'2rem auto',maxWidth:760,padding:'0 1rem'}}>{children}</body></html>;
}
