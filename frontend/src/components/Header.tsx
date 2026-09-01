import React, { useState } from 'react';
import { FileText, Download, ShieldCheck, AlertTriangle, Building2, Landmark, HelpCircle, Layers } from 'lucide-react';
import {
  formatCurrencyTotals,
  formatDateTime,
  exportDealsToCSV,
  exportDealsToJSON,
  trancheTotalsByCurrency,
} from '../utils/formatters';
import { Deal } from '../types/deal';

interface HeaderProps {
  deals: Deal[];
  filteredDeals: Deal[];
  updatedAt: string;
  dataSource: 'snapshot' | 'api';
  onOpenMethodology: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  deals,
  filteredDeals,
  updatedAt,
  dataSource,
  onOpenMethodology,
}) => {
  const [copiedLink, setCopiedLink] = useState(false);

  const trancheTotals = trancheTotalsByCurrency(deals);

  const uniqueBanks = new Set<string>();
  const uniqueIssuers = new Set<string>();
  deals.forEach(d => {
    uniqueIssuers.add(d.issuer);
    d.underwriters.forEach(u => uniqueBanks.add(u.raw_name));
  });

  const totalSte = deals.reduce((acc, d) => acc + (d.ste_mmboe || 0), 0);

  const handleCopyShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const asOfLabel =
    dataSource === 'api'
      ? `As of ${formatDateTime(updatedAt)} · Flask /api/deals`
      : `Snapshot as of ${formatDateTime(updatedAt)}`;

  return (
    <header className="border-b border-stone-200 bg-white/90 backdrop-blur-xs sticky top-0 z-40">
      {/* Top Editorial Ribbon */}
      <div className="border-b border-stone-100 bg-stone-900 text-stone-300 text-xs py-1.5 px-4 sm:px-6">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-stone-500"></span>
            <span className="font-mono text-stone-200">ESMA Final Terms Registry</span>
            <span className="text-stone-500">•</span>
            <span>{asOfLabel}</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onOpenMethodology}
              className="hover:text-amber-300 transition-colors flex items-center gap-1 cursor-pointer"
              title="Read regulatory data methodology"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>Methodology & Equal Credit Rules</span>
            </button>
            <span className="text-stone-600">|</span>
            <span className="font-mono text-stone-400">
              v1.4 • {dataSource === 'api' ? 'Local API' : 'Embedded snapshot'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Brand & Action Header */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 text-[11px] font-semibold tracking-wider uppercase bg-amber-100 text-amber-900 border border-amber-200/80 rounded-sm">
                Financial Journalism Monitor
              </span>
              <span className="px-2 py-0.5 text-[11px] font-semibold tracking-wider uppercase bg-stone-100 text-stone-700 border border-stone-200 rounded-sm">
                EU Capital Markets
              </span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-stone-900 font-editorial">
              PaperTrails
            </h1>
            <p className="text-sm sm:text-base text-stone-600 mt-1 max-w-2xl font-sans">
              Monitoring European fossil fuel bond underwriting syndicates and debt issuances extracted directly from ESMA final terms regulatory filings.
            </p>
          </div>

          {/* Export & Action Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              id="export-csv-btn"
              onClick={() => exportDealsToCSV(filteredDeals)}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-stone-700 bg-stone-50 hover:bg-stone-100 border border-stone-300 rounded-md transition-colors shadow-2xs cursor-pointer"
              title="Download filtered tranches as CSV spreadsheet"
            >
              <Download className="w-3.5 h-3.5 text-stone-500" />
              <span>Export CSV ({filteredDeals.length})</span>
            </button>

            <button
              id="export-json-btn"
              onClick={() => exportDealsToJSON(filteredDeals, updatedAt)}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-stone-700 bg-stone-50 hover:bg-stone-100 border border-stone-300 rounded-md transition-colors shadow-2xs cursor-pointer"
              title="Download raw JSON dataset"
            >
              <FileText className="w-3.5 h-3.5 text-stone-500" />
              <span>JSON</span>
            </button>

            <button
              id="share-link-btn"
              onClick={handleCopyShare}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-amber-900 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-md transition-colors shadow-2xs cursor-pointer"
            >
              <Layers className="w-3.5 h-3.5 text-amber-700" />
              <span>{copiedLink ? 'Link Copied!' : 'Share Feed'}</span>
            </button>
          </div>
        </div>

        {/* Aggregate Metrics Ribbon */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-stone-100">
          <div className="bg-stone-50/80 border border-stone-200/80 p-2.5 rounded-md">
            <div className="flex items-center justify-between text-xs text-stone-500 mb-1">
              <span className="font-medium">Issued Tranches</span>
              <Landmark className="w-3.5 h-3.5 text-stone-400" />
            </div>
            <div className="text-xl font-bold text-stone-900 font-mono tracking-tight">
              {formatCurrencyTotals(trancheTotals)}
            </div>
            <div className="text-[11px] text-stone-500 mt-0.5">
              {deals.length} deals · native currency (no FX)
            </div>
          </div>

          <div className="bg-stone-50/80 border border-stone-200/80 p-2.5 rounded-md">
            <div className="flex items-center justify-between text-xs text-stone-500 mb-1">
              <span className="font-medium">Issuers</span>
              <Building2 className="w-3.5 h-3.5 text-stone-400" />
            </div>
            <div className="text-xl font-bold text-stone-900 font-mono tracking-tight">
              {uniqueIssuers.size}
            </div>
            <div className="text-[11px] text-stone-500 mt-0.5">
              Programme shelves not summed
            </div>
          </div>

          <div className="bg-stone-50/80 border border-stone-200/80 p-2.5 rounded-md">
            <div className="flex items-center justify-between text-xs text-stone-500 mb-1">
              <span className="font-medium">Active Syndicate Banks</span>
              <ShieldCheck className="w-3.5 h-3.5 text-stone-400" />
            </div>
            <div className="text-xl font-bold text-stone-900 font-mono tracking-tight">
              {uniqueBanks.size} Institutions
            </div>
            <div className="text-[11px] text-stone-500 mt-0.5">
              Equal credit 1/n allocated
            </div>
          </div>

          <div className="bg-amber-50/70 border border-amber-200/80 p-2.5 rounded-md">
            <div className="flex items-center justify-between text-xs text-amber-800 mb-1">
              <span className="font-medium">Upstream Expansion STE</span>
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            </div>
            <div className="text-xl font-bold text-amber-950 font-mono tracking-tight">
              {totalSte.toLocaleString('en-GB', { maximumFractionDigits: 0 })} <span className="text-xs font-normal">mmboe</span>
            </div>
            <div className="text-[11px] text-amber-700 mt-0.5">
              Short-term fossil reserve growth
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
