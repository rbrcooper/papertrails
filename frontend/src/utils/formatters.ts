import { Deal, DealsData } from '../types/deal';

export type CurrencyTotals = Record<string, number>;

export function parseAmount(amount: string | number | null | undefined): number {
  if (amount === null || amount === undefined || amount === '') return 0;
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  return Number.isFinite(num) ? num : 0;
}

export function addToCurrencyTotals(
  totals: CurrencyTotals,
  amount: string | number | null | undefined,
  currency: string | null | undefined
): void {
  const num = parseAmount(amount);
  if (num === 0) return;
  const ccy = (currency || '').trim().toUpperCase() || 'UNKNOWN';
  totals[ccy] = (totals[ccy] || 0) + num;
}

export function currencyKeys(totals: CurrencyTotals): string[] {
  return Object.keys(totals)
    .filter(ccy => (totals[ccy] || 0) !== 0)
    .sort();
}

export function isMixedCurrency(totals: CurrencyTotals): boolean {
  return currencyKeys(totals).length > 1;
}

/**
 * Format totals grouped by ISO currency. Never converts FX; never labels a mixed
 * sum as EUR. Mixed books render as "€650.0M · RON 500.0M" (or "mixed — not summed").
 */
export function formatCurrencyTotals(
  totals: CurrencyTotals,
  options: { mixedLabel?: boolean } = {}
): string {
  const keys = currencyKeys(totals);
  if (keys.length === 0) return '—';
  if (options.mixedLabel && keys.length > 1) return 'mixed — not summed';
  return keys.map(ccy => formatAmount(totals[ccy], ccy)).join(' · ');
}

export function trancheTotalsByCurrency(
  deals: Array<Pick<Deal, 'amount' | 'currency'>>
): CurrencyTotals {
  const totals: CurrencyTotals = {};
  for (const deal of deals) {
    addToCurrencyTotals(totals, deal.amount, deal.currency);
  }
  return totals;
}

export function allocatedTotalsByCurrency(
  deals: Deal[],
  bankName?: string
): CurrencyTotals {
  const totals: CurrencyTotals = {};
  for (const deal of deals) {
    for (const u of deal.underwriters || []) {
      if (bankName && u.raw_name !== bankName) continue;
      addToCurrencyTotals(totals, u.allocated_amount, deal.currency);
    }
  }
  return totals;
}

/** Max programme_size per issuer per currency — same EMTN on many ISINs is not summed. */
export function maxProgrammeByIssuerCurrency(
  deals: Array<Pick<Deal, 'issuer' | 'programme_size' | 'currency'>>
): CurrencyTotals {
  const perIssuer: Record<string, CurrencyTotals> = {};
  for (const deal of deals) {
    const val = parseAmount(deal.programme_size);
    if (val <= 0) continue;
    const ccy = (deal.currency || '').trim().toUpperCase() || 'UNKNOWN';
    if (!perIssuer[deal.issuer]) perIssuer[deal.issuer] = {};
    perIssuer[deal.issuer][ccy] = Math.max(perIssuer[deal.issuer][ccy] || 0, val);
  }
  const totals: CurrencyTotals = {};
  for (const byCcy of Object.values(perIssuer)) {
    for (const [ccy, val] of Object.entries(byCcy)) {
      totals[ccy] = (totals[ccy] || 0) + val;
    }
  }
  return totals;
}

export function maxProgrammeByCurrency(
  deals: Array<Pick<Deal, 'programme_size' | 'currency'>>
): CurrencyTotals {
  const totals: CurrencyTotals = {};
  for (const deal of deals) {
    const val = parseAmount(deal.programme_size);
    if (val <= 0) continue;
    const ccy = (deal.currency || '').trim().toUpperCase() || 'UNKNOWN';
    totals[ccy] = Math.max(totals[ccy] || 0, val);
  }
  return totals;
}

/** Issuer-level STE is not bank-attributed. Bank STE is this value. */
export function steAllocated1n(
  deal: Pick<Deal, 'ste_mmboe' | 'n_underwriters' | 'underwriters'>
): number {
  const ste = deal.ste_mmboe ?? 0;
  if (ste <= 0) return 0;
  const n = deal.n_underwriters || deal.underwriters?.length || 1;
  return ste / (n || 1);
}

/** Only http(s) hrefs. Rejects javascript:, data:, and unparseable values. */
export function safeHttpUrl(url: string | null | undefined): string | null {
  if (!url || typeof url !== 'string') return null;
  const trimmed = url.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.href;
    }
  } catch {
    return null;
  }
  return null;
}

export function sanitizeDeal(deal: Deal): Deal {
  const copy = { ...deal } as Deal & { pdf_path?: unknown };
  delete copy.pdf_path;
  return copy;
}

export function sanitizeDealsPayload(payload: DealsData): DealsData {
  return {
    updated_at: payload?.updated_at,
    deals: (payload?.deals || []).map(sanitizeDeal),
  };
}

export function getCurrencySymbol(currency: string): string {
  switch (currency?.toUpperCase()) {
    case 'EUR':
      return '€';
    case 'GBP':
      return '£';
    case 'USD':
      return '$';
    case 'RON':
      return 'RON ';
    case 'NOK':
      return 'NOK ';
    case 'SEK':
      return 'SEK ';
    default:
      return `${currency} `;
  }
}

/**
 * Formats a currency amount into concise financial notation.
 * e.g. 1500000000 -> €1.50B
 *      650000000  -> €650.0M
 *      71428571.43 -> €71.4M
 */
export function formatAmount(
  amount: string | number | null | undefined,
  currency = 'EUR',
  options: { compact?: boolean; precision?: number } = {}
): string {
  if (amount === null || amount === undefined || amount === '') {
    return '—';
  }

  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '—';

  const symbol = getCurrencySymbol(currency);
  const compact = options.compact !== false;

  if (!compact) {
    return `${symbol}${num.toLocaleString('en-GB', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    })}`;
  }

  if (Math.abs(num) >= 1_000_000_000) {
    const val = num / 1_000_000_000;
    const formatted = val % 1 === 0 ? val.toFixed(0) : val.toFixed(2);
    return `${symbol}${formatted}B`;
  }

  if (Math.abs(num) >= 1_000_000) {
    const val = num / 1_000_000;
    const formatted = val % 1 === 0 ? val.toFixed(0) : val.toFixed(1);
    return `${symbol}${formatted}M`;
  }

  if (Math.abs(num) >= 1_000) {
    const val = num / 1_000;
    return `${symbol}${val.toFixed(1)}k`;
  }

  return `${symbol}${num.toLocaleString('en-GB')}`;
}

/**
 * Format exact currency for tooltips or detailed inspection
 */
export function formatExactAmount(amount: string | number | null | undefined, currency = 'EUR'): string {
  if (amount === null || amount === undefined || amount === '') return '—';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '—';
  const symbol = getCurrencySymbol(currency);
  return `${symbol}${num.toLocaleString('en-GB', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Format date in British English style (e.g. 30 Jun 2026)
 */
export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return 'Undisclosed';
  
  // Handle ISO string or YYYY-MM-DD
  const date = new Date(dateString);
  if (isNaN(date.getTime())) {
    // If simple YYYY-MM-DD parsing
    const parts = dateString.split('-');
    if (parts.length === 3) {
      const year = parts[0];
      const monthIndex = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return `${day} ${months[monthIndex]} ${year}`;
    }
    return dateString;
  }

  return date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Format date with time for dataset timestamps
 */
export function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return dateString;

  return date.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  });
}

/** Coupon from FTWS form fields. */
export function formatCouponRate(
  rate?: number | null,
  couponType?: string | null
): string | null {
  if (rate == null || !Number.isFinite(rate)) return null;
  const pct = `${rate}%`;
  return couponType ? `${pct} (${couponType})` : pct;
}

/** Maturity from FTWS — date or kind (e.g. undated). */
export function formatMaturity(
  maturityDate?: string | null,
  maturityKind?: string | null
): string | null {
  if (maturityDate) return formatDate(maturityDate);
  if (maturityKind) return maturityKind;
  return null;
}

/** Show syndicate role when FTWS names a heading (not generic Dealer). */
export function displayUnderwriterRole(role?: string | null): string | null {
  if (!role || role === 'Dealer' || role === 'Unknown') return null;
  return role;
}

/** Sort by ISO currency then amount — no FX conversion. */
export function compareByCurrencyThenAmount(
  a: Pick<Deal, 'currency' | 'amount'>,
  b: Pick<Deal, 'currency' | 'amount'>,
  direction: 'asc' | 'desc'
): number {
  const ccyCmp = (a.currency || '').localeCompare(b.currency || '');
  if (ccyCmp !== 0) return ccyCmp;
  const amtA = parseAmount(a.amount);
  const amtB = parseAmount(b.amount);
  return direction === 'desc' ? amtB - amtA : amtA - amtB;
}

export function compareByCurrencyThenProgramme(
  a: Pick<Deal, 'currency' | 'programme_size'>,
  b: Pick<Deal, 'currency' | 'programme_size'>,
  direction: 'asc' | 'desc'
): number {
  const ccyCmp = (a.currency || '').localeCompare(b.currency || '');
  if (ccyCmp !== 0) return ccyCmp;
  const progA = parseAmount(a.programme_size);
  const progB = parseAmount(b.programme_size);
  return direction === 'desc' ? progB - progA : progA - progB;
}

/**
 * Generate investigative journalistic citation for reporting
 */
export function generateCitation(deal: Deal): string {
  const tranche = formatAmount(deal.amount, deal.currency);
  const prog = deal.programme_size ? ` (Programme: ${formatAmount(deal.programme_size, deal.currency)})` : '';
  const date = formatDate(deal.issue_date);
  const underwriters = deal.underwriters.map(u => u.raw_name).join(', ');
  const docInfo = deal.doc_id ? ` [ESMA Doc: ${deal.doc_id}]` : '';

  return `PaperTrails / ESMA Filing: ${deal.issuer} (${deal.isin}) — ${tranche} tranche issued ${date}${prog}. Underwriters (1/n equal split): ${underwriters}.${docInfo}`;
}

/**
 * Export deals to downloadable CSV format
 */
export function exportDealsToCSV(deals: Deal[]): void {
  const headers = [
    'ISIN',
    'Issuer',
    'Issue Date',
    'Currency',
    'Tranche Amount',
    'Formatted Tranche',
    'Programme Size',
    'Formatted Programme',
    'Underwriters Count',
    'Underwriters (Equal Split Credit)',
    'Short-Term Expansion (mmboe)',
    'Watchlist Rank',
    'Document Type',
    'ESMA Document ID',
    'Prospectus URL',
  ];

  const rows = deals.map(deal => {
    const underwritersAllocated = deal.underwriters
      .map(u => `${u.raw_name} (${formatAmount(u.allocated_amount, deal.currency)})`)
      .join('; ');

    return [
      `"${deal.isin}"`,
      `"${deal.issuer.replace(/"/g, '""')}"`,
      `"${deal.issue_date || 'N/A'}"`,
      `"${deal.currency}"`,
      `"${deal.amount}"`,
      `"${formatAmount(deal.amount, deal.currency)}"`,
      `"${deal.programme_size || ''}"`,
      `"${formatAmount(deal.programme_size, deal.currency)}"`,
      deal.n_underwriters,
      `"${underwritersAllocated.replace(/"/g, '""')}"`,
      deal.ste_mmboe ?? 0,
      deal.watchlist_rank ?? '',
      `"${deal.doc_type_code || ''}"`,
      `"${deal.doc_id || ''}"`,
      `"${deal.source_url || ''}"`,
    ].join(',');
  });

  const csvContent = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `papertrails_fossil_underwriting_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Export deals to downloadable JSON format
 */
export function exportDealsToJSON(deals: Deal[], updatedAt: string): void {
  const exportPayload = {
    metadata: {
      source: 'PaperTrails — EU Fossil Bond Underwriting Monitor',
      regulatory_source: 'ESMA Prospectus Register / Final Terms Wholesale (FTWS)',
      exported_at: new Date().toISOString(),
      dataset_updated_at: updatedAt,
      total_deals: deals.length,
      methodology: 'Equal credit allocation (1/n) across syndicate dealers on issued tranches',
    },
    deals: deals.map(sanitizeDeal),
  };

  const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `papertrails_deals_${new Date().toISOString().slice(0, 10)}.json`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
