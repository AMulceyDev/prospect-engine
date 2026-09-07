import type {
  AnalyzeResult,
  CompanyDetail,
  CompanyRead,
  EnrichResult,
  EnrichSirenResult,
  FilterResult,
  IngestResult,
  WebsiteDetectResult,
} from './types/index'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, text || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') p.set(k, String(v))
  }
  const s = p.toString()
  return s ? '?' + s : ''
}

export const api = {
  companies: {
    list: (params?: { skip?: number; limit?: number; code_postal?: string; with_domain?: boolean }) =>
      req<CompanyRead[]>(`/companies${qs(params ?? {})}`),
    get: (siren: string) =>
      req<CompanyDetail>(`/companies/${siren}`),
    clear: () =>
      req<{ deleted: number }>('/companies', { method: 'DELETE' }),
    deleteMany: (sirens: string[]) =>
      req<{ deleted: number }>(`/companies${qs({ sirens: sirens.join(',') })}`, { method: 'DELETE' }),
  },
  ingest: {
    run: (params: { days?: number; rows?: number; at_date?: string; active_only?: boolean; exclude_ei?: boolean }) =>
      req<IngestResult>(`/ingest/run${qs(params)}`, { method: 'POST' }),
    enrich: (params?: { limit?: number }) =>
      req<EnrichResult>(`/ingest/enrich${qs(params ?? {})}`, { method: 'POST' }),
    enrichOne: (siren: string) =>
      req<EnrichResult>(`/ingest/enrich/${siren}`, { method: 'POST' }),
    filter: () =>
      req<FilterResult>('/ingest/filter', { method: 'POST' }),
    websites: (params?: { limit?: number }) =>
      req<WebsiteDetectResult>(`/ingest/websites${qs(params ?? {})}`, { method: 'POST' }),
  },
  analyze: {
    run: (params?: { limit?: number; sirens?: string[] }) =>
      req<AnalyzeResult>(
        `/analyze/run${qs({ limit: params?.limit, sirens: params?.sirens?.join(',') })}`,
        { method: 'POST' },
      ),
  },
  enrich: (siren: string) =>
    req<EnrichSirenResult>(`/enrich/${siren}`, { method: 'POST' }),
  progress: () =>
    req<{ task: string; current: number; total: number }>('/progress'),
}
