export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
export async function api(path: string, tenant = '', body?: object) {
  const response = await fetch(path, { method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store',
    headers: { 'content-type':'application/json', ...(tenant ? { 'x-tenant-id':tenant } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const data = await response.json();
  if (!response.ok) throw new ApiError(typeof data.detail === 'string' ? data.detail : 'Periksa data yang diisi', response.status);
  return data;
}
export type Membership = { tenant_id:string; name:string; role:string };
