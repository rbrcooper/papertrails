import React from 'react';
import { AlertTriangle, Landmark, HelpCircle } from 'lucide-react';
import {
  formatCurrencyTotals,
  formatDateTime,
  totalUniqueIssuerSte,
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
  updatedAt,
  dataSource,
  onOpenMethodology,
}) => {
  const trancheTotals = trancheTotalsByCurrency(deals);
  const totalSte = totalUniqueIssuerSte(deals);

  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
        {/* Brand + Status Row */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="px-2 py-0.5 text-[11px] font-semibold tracking-wider uppercase bg-amber-100 text-amber-900 border border-amber-200/80 rounded-sm">
                Financial Journalism Monitor
              </span>
              <span className="px-2 py-0.5 text-[11px] font-semibold tracking-wider uppercase bg-stone-100 text-stone-700 border border-stone-200 rounded-sm">
                EU Capital Markets (Tracked Feed)
              </span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-stone-900 font-editorial">
              PaperTrails
            </h1>
            <p className="text-sm text-stone-600 mt-1 max-w-2xl font-sans">
              European fossil fuel bond underwriting syndicates extracted from ESMA final terms filings for tracked GOGEL parent issuers.
            </p>
          </div>

          {/* Inline Status */}
          <div className="flex items-center gap-3 text-xs text-stone-500 shrink-0 pt-1">
            <div className="flex items-center gap-1.5">
              <span className={`inline-block w-2 h-2 rounded-full ${dataSource === 'api' ? 'bg-emerald-400 ring-2 ring-emerald-400/30 animate-pulse' : 'bg-stone-400'}`}></span>
              <span className="font-mono text-stone-600">
                {dataSource === 'api'
                  ? formatDateTime(updatedAt)
                  : `Snapshot ${formatDateTime(updatedAt)}`}
              </span>
            </div>
            <span className="text-stone-300">|</span>
            <button
              onClick={onOpenMethodology}
              className="hover:text-amber-800 transition-colors flex items-center gap-1 cursor-pointer text-stone-600"
              title="Read regulatory data methodology"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>Methodology</span>
            </button>
          </div>
        </div>

        {/* Two focused metric cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4 pt-4 border-t border-stone-100">
          <div className="bg-stone-50/90 border border-stone-200/90 p-3 rounded-lg shadow-2xs hover:shadow-xs transition-shadow">
            <div className="flex items-center justify-between text-xs text-stone-500 mb-1">
              <span className="font-semibold uppercase tracking-wider text-[10px]">Tracked Tranches</span>
              <Landmark className="w-3.5 h-3.5 text-stone-400" />
            </div>
            <div className="text-xl sm:text-2xl font-bold text-stone-950 font-mono tracking-tight">
              {formatCurrencyTotals(trancheTotals)}
            </div>
            <div className="text-[11px] text-stone-500 mt-0.5">
              {deals.length} tranches · native currency (no FX)
            </div>
          </div>

          <div className="bg-amber-50/80 border border-amber-200/90 p-3 rounded-lg shadow-2xs hover:shadow-xs transition-shadow">
            <div className="flex items-center justify-between text-xs text-amber-900 mb-1">
              <span className="font-semibold uppercase tracking-wider text-[10px]">Upstream Expansion STE</span>
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            </div>
            <div className="text-xl sm:text-2xl font-bold text-amber-950 font-mono tracking-tight">
              {totalSte.toLocaleString('en-GB', { maximumFractionDigits: 0 })} <span className="text-xs font-normal text-amber-800">mmboe</span>
            </div>
            <div className="text-[11px] text-amber-800/90 mt-0.5">
              Parent reserve (deduplicated across tranches)
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
