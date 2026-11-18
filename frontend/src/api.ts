import { BidCreatePayload, BidOut, RfqCreatePayload, RfqDetail, RfqSummary } from './types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let errMsg = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') {
        errMsg = data.detail;
      } else if (Array.isArray(data.detail)) {
        errMsg = data.detail.map((d: { msg?: string; loc?: string[] }) => `${(d.loc || []).join('.')}: ${d.msg}`).join('; ');
      }
    } catch {
      // ignore json parse failure
    }
    throw new Error(errMsg);
  }
  return res.json();
}

export const api = {
  listRfqs: () => request<RfqSummary[]>('/rfqs'),
  getRfq: (id: string) => request<RfqDetail>(`/rfqs/${id}`),
  createRfq: (payload: RfqCreatePayload) =>
    request<RfqSummary>('/rfqs', { method: 'POST', body: JSON.stringify(payload) }),
  deleteRfq: (id: string) =>
    request<{ message: string; id: string }>(`/rfqs/${id}`, { method: 'DELETE' }),
  submitBid: (rfqId: string, payload: BidCreatePayload) =>
    request<BidOut>(`/rfqs/${rfqId}/bids`, { method: 'POST', body: JSON.stringify(payload) }),
  deleteBid: (rfqId: string, bidId: string) =>
    request<{ message: string; id: string }>(`/rfqs/${rfqId}/bids/${bidId}`, { method: 'DELETE' }),
  seedDemo: () =>
    request<RfqSummary[]>('/rfqs/seed-demo', { method: 'POST' }),
};
