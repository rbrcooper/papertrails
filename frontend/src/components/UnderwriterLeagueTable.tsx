import React, { useState } from 'react';
import { Trophy, ChevronRight, ShieldCheck, ArrowUpDown } from 'lucide-react';
import { Deal, BankExposure } from '../types/deal';
import {
  addToCurrencyTotals,
  allocatedTotalsByCurrency,
  formatCurrencyTotals,
  isMixedCurrency,
  steAllocated1n,
} from '../utils/formatters';
import { getBankClimateProfile } from '../data/referenceData';

interface UnderwriterLeagueTableProps {
  deals: Deal[];
  onSelectBank: (bankName: string) => void;
}

function maxCurrencyBucket(totals: Record<string, number>): number {
  const vals = Object.values(totals);
  return vals.length ? Math.max(...vals) : 0;
}

export const UnderwriterLeagueTable: React.FC<UnderwriterLeagueTableProps> = ({
  deals,
  onSelectBank,
}) => {
  const [sortField, setSortField] = useState<'amount' | 'deals' | 'ste' | 'name'>('amount');
  const [sortAsc, setSortAsc] = useState(false);

  const bankMap = new Map<string, BankExposure>();

  deals.forEach(deal => {
    deal.underwriters.forEach(u => {
      const name = u.raw_name;
      if (!bankMap.has(name)) {
        bankMap.set(name, {
          bankName: name,
          allocatedByCurrency: {},
          dealCount: 0,
          deals: [],
          issuers: new Set<string>(),
          totalSteSupported: 0,
        });
      }

      const entry = bankMap.get(name)!;
      addToCurrencyTotals(entry.allocatedByCurrency, u.allocated_amount, deal.currency);
      entry.dealCount += 1;
      entry.deals.push(deal);
      entry.issuers.add(deal.issuer);
      entry.totalSteSupported += steAllocated1n(deal);
    });
  });

  let rankings = Array.from(bankMap.values());

  rankings.sort((a, b) => {
    let diff = 0;
    if (sortField === 'amount') {
      diff = maxCurrencyBucket(b.allocatedByCurrency) - maxCurrencyBucket(a.allocatedByCurrency);
    } else if (sortField === 'deals') {
      diff = b.dealCount - a.dealCount;
    } else if (sortField === 'ste') {
      diff = b.totalSteSupported - a.totalSteSupported;
    } else {
      diff = a.bankName.localeCompare(b.bankName);
    }
    return sortAsc ? -diff : diff;
  });

  const marketTotals = allocatedTotalsByCurrency(deals);
  const mixedMarket = isMixedCurrency(marketTotals);

  const toggleSort = (field: 'amount' | 'deals' | 'ste' | 'name') => {
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
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Trophy className="w-4 h-4 text-amber-600" />
              <h2 className="text-lg font-bold text-stone-900 font-editorial">
                Underwriting Syndicate League Table
              </h2>
            </div>
            <p className="text-xs text-stone-600 max-w-3xl font-sans">
              Methodology notice: Volume is calculated strictly using <strong className="font-semibold text-stone-800">1/n equal credit allocation</strong> per issued tranche (tranche amount ÷ number of syndicate dealers) from verified ESMA final terms filings. Programme facility sizes are excluded. Mixed currencies are listed separately — they are not converted or summed as EUR.
            </p>
          </div>
          <div className="text-right whitespace-nowrap bg-white px-3 py-2 rounded-md border border-stone-200">
            <div className="text-[11px] text-stone-500 font-medium">Underwritten Tranches</div>
            <div className="text-base font-bold text-stone-900 font-mono">
              {formatCurrencyTotals(marketTotals)}
            </div>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-stone-100/80 border-b border-stone-200 text-stone-700 font-semibold uppercase tracking-wider text-[11px]">
            <tr>
              <th scope="col" className="py-3 px-3.5 text-center w-12">#</th>
              <th scope="col" className="py-3 px-3.5">
                <button
                  onClick={() => toggleSort('name')}
                  className="flex items-center gap-1 hover:text-stone-950 cursor-pointer"
                >
                  <span>Underwriting Institution</span>
                  <ArrowUpDown className="w-3 h-3 text-stone-400" />
                </button>
              </th>
              <th scope="col" className="py-3 px-3 text-center">Climate Pledge (NZBA)</th>
              <th scope="col" className="py-3 px-3.5 text-right">
                <button
                  onClick={() => toggleSort('amount')}
                  className="inline-flex items-center gap-1 hover:text-stone-950 ml-auto cursor-pointer"
                >
                  <span>Equal Credit Volume</span>
                  <ArrowUpDown className="w-3 h-3 text-stone-400" />
                </button>
              </th>
              <th scope="col" className="py-3 px-3.5 text-right">
                <span title="Share omitted when the book mixes currencies">Share</span>
              </th>
              <th scope="col" className="py-3 px-3.5 text-center">
                <button
                  onClick={() => toggleSort('deals')}
                  className="inline-flex items-center gap-1 hover:text-stone-950 mx-auto cursor-pointer"
                >
                  <span>Deals</span>
                  <ArrowUpDown className="w-3 h-3 text-stone-400" />
                </button>
              </th>
              <th scope="col" className="py-3 px-3.5">Issuers Financed</th>
              <th scope="col" className="py-3 px-3.5 text-right">
                <button
                  onClick={() => toggleSort('ste')}
                  className="inline-flex items-center gap-1 hover:text-stone-950 ml-auto cursor-pointer"
                  title="Short-term expansion attributed 1/n per syndicate (mmboe)"
                >
                  <span>Upstream Exp. (STE 1/n)</span>
                  <ArrowUpDown className="w-3 h-3 text-stone-400" />
                </button>
              </th>
              <th scope="col" className="py-3 px-3.5 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-200">
            {rankings.map((bank, index) => {
              const climateProfile = getBankClimateProfile(bank.bankName);
              const marketVolume = maxCurrencyBucket(marketTotals);
              const share =
                mixedMarket || marketVolume <= 0
                  ? '—'
                  : `${((maxCurrencyBucket(bank.allocatedByCurrency) / marketVolume) * 100).toFixed(1)}%`;

              return (
                <tr
                  key={bank.bankName}
                  className="hover:bg-amber-50/40 transition-colors group"
                >
                  <td className="py-3 px-3.5 text-center font-mono font-medium text-stone-500">
                    {index + 1}
                  </td>
                  <td className="py-3 px-3.5 font-semibold text-stone-900 font-sans">
                    <button
                      onClick={() => onSelectBank(bank.bankName)}
                      className="hover:text-amber-800 hover:underline text-left cursor-pointer"
                    >
                      {bank.bankName}
                    </button>
                    {climateProfile?.oilGasPolicyRating && (
                      <div className="text-[10px] text-stone-500 font-normal mt-0.5">
                        Policy: {climateProfile.oilGasPolicyRating}
                      </div>
                    )}
                  </td>
                  <td className="py-3 px-3 text-center">
                    {climateProfile?.nzbaMember ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-800 border border-blue-200">
                        <ShieldCheck className="w-3 h-3 text-blue-600" />
                        <span>Signatory</span>
                      </span>
                    ) : (
                      <span className="text-stone-400 text-[11px]">—</span>
                    )}
                  </td>
                  <td className="py-3 px-3.5 text-right font-mono font-bold text-stone-900 text-sm">
                    {formatCurrencyTotals(bank.allocatedByCurrency)}
                  </td>
                  <td className="py-3 px-3.5 text-right font-mono text-stone-600">
                    {share}
                  </td>
                  <td className="py-3 px-3.5 text-center font-mono">
                    <span className="bg-stone-100 text-stone-800 px-2 py-0.5 rounded font-semibold text-[11px] border border-stone-200">
                      {bank.dealCount}
                    </span>
                  </td>
                  <td className="py-3 px-3.5 text-stone-600 max-w-xs truncate">
                    <div className="flex flex-wrap gap-1">
                      {Array.from(bank.issuers).map(issuer => (
                        <span
                          key={issuer}
                          className="bg-stone-50 text-stone-700 border border-stone-200/80 px-1.5 py-0.5 rounded text-[10px]"
                        >
                          {issuer}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-3.5 text-right font-mono text-stone-700">
                    {bank.totalSteSupported > 0 ? (
                      <span className="text-amber-900 font-semibold bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded text-[11px]">
                        {bank.totalSteSupported.toLocaleString('en-GB', { maximumFractionDigits: 0 })} mmboe
                      </span>
                    ) : (
                      <span className="text-stone-400">—</span>
                    )}
                  </td>
                  <td className="py-3 px-3.5 text-center">
                    <button
                      onClick={() => onSelectBank(bank.bankName)}
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
