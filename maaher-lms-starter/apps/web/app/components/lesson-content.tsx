'use client';
import Markdown from 'react-markdown';
function safe(value: string | undefined) {
  if (!value || /[\s\\]/.test(value)) return false;
  try {
    if (new RegExp('[\\p{Cc}\\p{Cf}\\p{Cs}]','u').test(value + decodeURIComponent(value))) return false;
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password && !url.hostname.endsWith('.');
  } catch { return false; }
}
export default function LessonContent({ content, resources }: { content:string; resources:{label:string;url:string}[] }) {
  return <><Markdown skipHtml urlTransform={value => safe(value) ? value : ''} components={{
    a:({href,children}) => safe(href) ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>,
    img:({src,alt}) => typeof src === 'string' && safe(src) ? <a href={src} target="_blank" rel="noopener noreferrer">{alt || 'Buka gambar'}</a> : <span>{alt}</span>,
  }}>{content}</Markdown>{resources.length > 0 && <><h3>Materi tambahan</h3><ul>{resources.map((r,i) => <li key={i}>{safe(r.url) ? <a href={r.url} target="_blank" rel="noopener noreferrer">{r.label}</a> : r.label}</li>)}</ul></>}</>;
}
