import React, { useState } from 'react';
import { Building2, Flame, ArrowUpDown, ChevronRight } from 'lucide-react';
import { Deal, IssuerExposure } from '../types/deal';
import { addToCurrencyTotals, formatCurrencyTotals } from '../utils/formatters';

interface IssuerMatrixProps {
  deals: Deal[];
  onSelectIssuer: (issuerName: string) => void;
  onSelectBank: (bankName: string) => void;
}

function maxCurrencyBucket(totals: Record<string, number>): number {
  const vals = Object.values(totals);
  return vals.length ? Math.max(...vals) : 0;
}

export const IssuerMatrix: React.FC<IssuerMatrixProps> = ({
  deals,
  onSelectIssuer,
  onSelectBank,
}) => {
  const [sortField, setSortField] = useState<'ste' | 'tranche' | 'programme' | 'deals' | 'name'>('ste');
  const [sortAsc, setSortAsc] = useState(false);

  const issuerMap = new Map<string, IssuerExposure>();

  deals.forEach(deal => {
    const name = deal.issuer;
    if (!issuerMap.has(name)) {
      issuerMap.set(name, {
        issuerName: name,
        trancheByCurrency: {},
        programmeByCurrency: {},
        deals: [],
        ste_mmboe: deal.ste_mmboe ?? 0,
        watchlist_rank: deal.watchlist_rank ?? null,
        dealCount: 0,
        underwriters: new Set<string>(),
      });
    }

    const entry = issuerMap.get(name)!;
    addToCurrencyTotals(entry.trancheByCurrency, deal.amount, deal.currency);
    if (deal.programme_size) {
      const prog = parseFloat(deal.programme_size) || 0;
      const ccy = (deal.currency || '').toUpperCase() || 'UNKNOWN';
      entry.programmeByCurrency[ccy] = Math.max(entry.programmeByCurrency[ccy] || 0, prog);
    }
    if ((deal.ste_mmboe ?? 0) > entry.ste_mmboe) {
      entry.ste_mmboe = deal.ste_mmboe ?? 0;
    }
    if (deal.watchlist_rank && (!entry.watchlist_rank || deal.watchlist_rank < entry.watchlist_rank)) {
      entry.watchlist_rank = deal.watchlist_rank;
    }
    entry.dealCount += 1;
    entry.deals.push(deal);
    deal.underwriters.forEach(u => entry.underwriters.add(u.raw_name));
  });

  const issuersList = Array.from(issuerMap.values());

  issuersList.sort((a, b) => {
    let diff = 0;
    if (sortField === 'ste') {
      diff = b.ste_mmboe - a.ste_mmboe;
    } else if (sortField === 'tranche') {
      diff = maxCurrencyBucket(b.trancheByCurrency) - maxCurrencyBucket(a.trancheByCurrency);
    } else if (sortField === 'programme') {
      diff = maxCurrencyBucket(b.programmeByCurrency) - maxCurrencyBucket(a.programmeByCurrency);
    } else if (sortField === 'deals') {
      diff = b.dealCount - a.dealCount;
    } else {
      diff = a.issuerName.localeCompare(b.issuerName);
    }
    return sortAsc ? -diff : diff;
  });

  const toggleSort = (field: 'ste' | 'tranche' | 'programme' | 'deals' | 'name') => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <div className="bg-white border border-stone-200 rounded-lg overflow-hidden shadow-2xs">
      <div className="p-4 sm:p-5 border-b border-stone-200 bg-stone-50/70">
        <div className="flex items-center gap-2 mb-1">
          <Building2 className="w-4 h-4 text-stone-700" />
          <h2 className="text-lg font-bold text-stone-900 font-editorial">
            Issuer Profiles & Fossil Exposure Matrix
          </h2>
        </div>
        <p className="text-xs text-stone-600 max-w-3xl font-sans">
          Overview of bond issuing corporate entities, their short-term upstream expansion reserves (<strong className="font-semibold text-stone-800">STE mmboe</strong>), cumulative nominal tranches issued in native currency (not FX-converted), and syndicate dealer networks. Programme shelf is the max per issuer per currency — not summed across ISINs.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-stone-100/80 border-b border-stone-200 text-stone-700 font-semibold uppercase tracking-wider text-[11px]">
            <tr>
              <th scope="col" className="py-3 px-3.5 w-12 text-center">Rank</th>
              <th scope="col" className="py-3 px-3.5">
                <button
                  onClick={() => toggleSort('name')}
                  className="flex items-center gap-1 hover:text-stone-950 cursor-pointer"
                >
                  <span>Issuer Corporate Entity</span>
                  <ArrowUpDown className="w-3 h-3 text-stone-400" />
                </button>
              </th>
              <th scope="col" className="py-3 px-3.5 text-right">
                <button
                  onClick={() => toggleSort('ste')}
                  className="inline-flex items-center gap-1 hover:text-stone-950 ml-auto cursor-pointer"
                  title="Short-term upstream expansion reserve growth (million barrels of oil equivalent)"
                >
                  <span>Upstream STE (mmboe)</span>
                  <ArrowUpDown className="w-3 h-3 text-stone-400" />
                </button>
              </th>
              <th scope="col" className="py-3 px-3.5 text-right">
                <button
                  onClick={() => toggleSort('tranche')}
                  className="inline-flex items-center gap-1 hover:text-stone-950 ml-auto cursor-pointer"
                >
                  <span>Issued Tranches</span>
                  <ArrowUpDown className="w-3 h-3 text-stone-400" />
                </button>
              </th>
              <th scope="col" className="py-3 px-3.5 text-right">
                <button
                  onClick={() => toggleSort('programme')}
                  className="inline-flex items-center gap-1 hover:text-stone-950 ml-auto cursor-pointer"
                  title="Maximum active programme capacity per currency"
                >
                  <span>Programme Shelf</span>
                  <ArrowUpDown className="w-3 h-3 text-stone-400" />
                </button>
              </th>
              <th scope="col" className="py-3 px-3.5 text-center">
                <button
                  onClick={() => toggleSort('deals')}
                  className="inline-flex items-center gap-1 hover:text-stone-950 mx-auto cursor-pointer"
                >
                  <span>Tranches</span>
                  <ArrowUpDown className="w-3 h-3 text-stone-400" />
                </button>
              </th>
              <th scope="col" className="py-3 px-3.5">Syndicate Underwriters</th>
              <th scope="col" className="py-3 px-3.5 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-200">
            {issuersList.map((issuer, idx) => {
              const hasSte = issuer.ste_mmboe > 0;

              return (
                <tr
                  key={issuer.issuerName}
                  className={`hover:bg-stone-50/80 transition-colors ${
                    hasSte ? 'bg-amber-50/20' : ''
                  }`}
                >
                  <td className="py-3 px-3.5 text-center font-mono font-medium text-stone-500">
                    {issuer.watchlist_rank ? `#${issuer.watchlist_rank}` : idx + 1}
                  </td>
                  <td className="py-3 px-3.5 font-semibold text-stone-900">
                    <button
                      onClick={() => onSelectIssuer(issuer.issuerName)}
                      className="hover:text-amber-800 hover:underline text-left cursor-pointer flex items-center gap-1.5"
                    >
                      <span>{issuer.issuerName}</span>
                      {hasSte && (
                        <Flame className="w-3.5 h-3.5 text-amber-600 shrink-0" title="Active upstream fossil reserve expansion" />
                      )}
                    </button>
                  </td>
                  <td className="py-3 px-3.5 text-right font-mono">
                    {hasSte ? (
                      <span className="font-bold text-amber-950 bg-amber-100/80 border border-amber-300 px-2 py-0.5 rounded text-[11px]">
                        {issuer.ste_mmboe.toLocaleString('en-GB', { maximumFractionDigits: 2 })} mmboe
                      </span>
                    ) : (
                      <span className="text-stone-400 font-normal">0.00</span>
                    )}
                  </td>
                  <td className="py-3 px-3.5 text-right font-mono font-bold text-stone-900 text-sm">
                    {formatCurrencyTotals(issuer.trancheByCurrency)}
                  </td>
                  <td className="py-3 px-3.5 text-right font-mono text-stone-700">
                    {formatCurrencyTotals(issuer.programmeByCurrency)}
                  </td>
                  <td className="py-3 px-3.5 text-center font-mono font-semibold">
                    <span className="bg-stone-100 text-stone-800 px-2 py-0.5 rounded border border-stone-200">
                      {issuer.dealCount}
                    </span>
                  </td>
                  <td className="py-3 px-3.5 text-stone-600 max-w-xs">
                    <div className="flex flex-wrap gap-1">
                      {Array.from(issuer.underwriters).map(bank => (
                        <button
                          key={bank}
                          onClick={() => onSelectBank(bank)}
                          className="bg-stone-50 hover:bg-amber-100 text-stone-700 hover:text-amber-900 border border-stone-200 px-1.5 py-0.5 rounded text-[10px] transition-colors cursor-pointer"
                          title={`Filter deals underwritten by ${bank}`}
                        >
                          {bank}
                        </button>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-3.5 text-center">
                    <button
                      onClick={() => onSelectIssuer(issuer.issuerName)}
                      className="inline-flex items-center gap-1 px-2 py-1 bg-stone-100 hover:bg-stone-200 text-stone-800 rounded text-[11px] font-medium transition-colors cursor-pointer"
                    >
                      <span>Filter</span>
                      <ChevronRight className="w-3 h-3 text-stone-500" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
