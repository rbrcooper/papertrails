import React, { useState, useMemo } from 'react';
import { Deal } from '../types/deal';
import { getBankClimateProfile } from '../data/referenceData';
import { Scale, ArrowRightLeft, Building2, Flame, CheckCircle2 } from 'lucide-react';
import {
  addToCurrencyTotals,
  formatAmount,
  formatCurrencyTotals,
  maxProgrammeByCurrency,
  steAllocated1n,
  trancheTotalsByCurrency,
} from '../utils/formatters';

interface CompareViewProps {
  deals: Deal[];
  onSelectBank?: (bank: string) => void;
  onSelectIssuer?: (issuer: string) => void;
}

export const CompareView: React.FC<CompareViewProps> = ({ deals, onSelectBank, onSelectIssuer }) => {
  const [compareType, setCompareType] = useState<'banks' | 'issuers'>('banks');

  // Extract all unique banks and issuers
  const { allBanks, allIssuers } = useMemo(() => {
    const banks = new Set<string>();
    const issuers = new Set<string>();
    deals.forEach(d => {
      issuers.add(d.issuer);
      d.underwriters.forEach(u => banks.add(u.raw_name));
    });
    return {
      allBanks: Array.from(banks).sort(),
      allIssuers: Array.from(issuers).sort(),
    };
  }, [deals]);

  const [bankA, setBankA] = useState<string>(allBanks[0] || '');
  const [bankB, setBankB] = useState<string>(allBanks[1] || allBanks[0] || '');

  const [issuerA, setIssuerA] = useState<string>(allIssuers[0] || '');
  const [issuerB, setIssuerB] = useState<string>(allIssuers[1] || allIssuers[0] || '');

  const computeBankStats = (bankName: string) => {
    if (!bankName) return null;
    const profile = getBankClimateProfile(bankName);
    const allocatedByCurrency: Record<string, number> = {};
    let dealCount = 0;
    let totalSte = 0;
    const fundedIssuers = new Set<string>();
    const bankDeals: Deal[] = [];

    deals.forEach(d => {
      const u = d.underwriters.find(item => item.raw_name === bankName);
      if (u) {
        dealCount++;
        bankDeals.push(d);
        fundedIssuers.add(d.issuer);
        addToCurrencyTotals(allocatedByCurrency, u.allocated_amount, d.currency);
        totalSte += steAllocated1n(d);
      }
    });

    return {
      name: bankName,
      profile,
      allocatedByCurrency,
      dealCount,
      totalSte,
      issuersCount: fundedIssuers.size,
      issuers: Array.from(fundedIssuers),
      deals: bankDeals,
    };
  };

  const statsBankA = useMemo(() => computeBankStats(bankA), [bankA, deals]);
  const statsBankB = useMemo(() => computeBankStats(bankB), [bankB, deals]);

  // Find co-syndicated deals between Bank A and Bank B
  const coSyndicatedDeals = useMemo(() => {
    if (!bankA || !bankB || bankA === bankB) return [];
    return deals.filter(
      d =>
        d.underwriters.some(u => u.raw_name === bankA) &&
        d.underwriters.some(u => u.raw_name === bankB)
    );
  }, [bankA, bankB, deals]);

  const computeIssuerStats = (issuerName: string) => {
    if (!issuerName) return null;
    const issuerDeals: Deal[] = [];
    let ste = 0;
    let watchlistRank: number | null = null;
    const syndicateBanks = new Set<string>();

    deals.forEach(d => {
      if (d.issuer === issuerName) {
        issuerDeals.push(d);
        if ((d.ste_mmboe ?? 0) > ste) ste = d.ste_mmboe ?? 0;
        if (d.watchlist_rank) watchlistRank = d.watchlist_rank;
        d.underwriters.forEach(u => syndicateBanks.add(u.raw_name));
      }
    });

    return {
      name: issuerName,
      trancheByCurrency: trancheTotalsByCurrency(issuerDeals),
      programmeByCurrency: maxProgrammeByCurrency(issuerDeals),
      ste,
      watchlistRank,
      dealCount: issuerDeals.length,
      banksCount: syndicateBanks.size,
      banks: Array.from(syndicateBanks),
      deals: issuerDeals,
    };
  };

  const statsIssuerA = useMemo(() => computeIssuerStats(issuerA), [issuerA, deals]);
  const statsIssuerB = useMemo(() => computeIssuerStats(issuerB), [issuerB, deals]);

  // Overlapping underwriter banks for Issuer A & B
  const sharedBanks = useMemo(() => {
    if (!statsIssuerA || !statsIssuerB) return [];
    const setB = new Set(statsIssuerB.banks);
    return statsIssuerA.banks.filter(b => setB.has(b));
  }, [statsIssuerA, statsIssuerB]);

  return (
    <div className="space-y-6">
      {/* Top Banner / Mode Toggle */}
      <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-amber-100 text-amber-900 rounded-md">
                <Scale className="w-4 h-4" />
              </div>
              <h2 className="text-lg font-bold font-editorial text-stone-900">
                Syndicate & Issuer Side-by-Side Comparison Workspace
              </h2>
            </div>
            <p className="text-xs text-stone-500 mt-1">
              Cross-examine two institutions or corporate entities using the current feed filters. Mixed currencies are not converted. Bank STE is 1/n of deal STE.
            </p>
          </div>

          {/* Toggle Type */}
          <div className="inline-flex p-1 bg-stone-100 rounded-lg border border-stone-200 self-start">
            <button
              onClick={() => setCompareType('banks')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                compareType === 'banks'
                  ? 'bg-white text-stone-900 shadow-xs border border-stone-200/60'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              Underwriter Bank vs Bank
            </button>
            <button
              onClick={() => setCompareType('issuers')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                compareType === 'issuers'
                  ? 'bg-white text-stone-900 shadow-xs border border-stone-200/60'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              Corporate Issuer vs Issuer
            </button>
          </div>
        </div>
      </div>

      {/* BANK COMPARISON VIEW */}
      {compareType === 'banks' && (
        <div className="space-y-6">
          {/* Selectors Bar */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-2xs">
              <label className="block text-xs font-bold text-stone-700 uppercase tracking-wider mb-1.5">
                Primary Bank (Entity A)
              </label>
              <select
                value={bankA}
                onChange={e => setBankA(e.target.value)}
                className="w-full text-sm font-semibold p-2 bg-stone-50 border border-stone-300 rounded-lg text-stone-900 focus:ring-2 focus:ring-amber-500 cursor-pointer"
              >
                {allBanks.map(b => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>

            <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-2xs">
              <label className="block text-xs font-bold text-stone-700 uppercase tracking-wider mb-1.5">
                Comparative Bank (Entity B)
              </label>
              <select
                value={bankB}
                onChange={e => setBankB(e.target.value)}
                className="w-full text-sm font-semibold p-2 bg-stone-50 border border-stone-300 rounded-lg text-stone-900 focus:ring-2 focus:ring-amber-500 cursor-pointer"
              >
                {allBanks.map(b => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Comparison Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Card Bank A */}
            {statsBankA && (
              <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-2xs space-y-4">
                <div className="flex items-center justify-between border-b border-stone-100 pb-3">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400">Entity A</span>
                    <h3 className="text-base font-bold text-stone-900 font-editorial">{statsBankA.name}</h3>
                    <span className="text-xs text-stone-500">{statsBankA.issuersCount} issuers in current view</span>
                  </div>
                  {statsBankA.profile?.nzbaMember ? (
                    <span className="px-2 py-1 bg-blue-50 text-blue-800 border border-blue-200 text-xs font-semibold rounded-md">
                      NZBA Signatory ({statsBankA.profile.nzbaJoinedYear})
                    </span>
                  ) : (
                    <span className="px-2 py-1 bg-stone-100 text-stone-600 text-xs rounded-md">Non-NZBA</span>
                  )}
                </div>

                {/* Key Metrics */}
                <div className="grid grid-cols-3 gap-2 text-center py-2 bg-stone-50 rounded-lg border border-stone-100">
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">1/n Equal Credit</span>
                    <div className="text-sm font-bold font-mono text-stone-900">{formatCurrencyTotals(statsBankA.allocatedByCurrency)}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">Tranches</span>
                    <div className="text-sm font-bold font-mono text-stone-900">{statsBankA.dealCount}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">STE (1/n)</span>
                    <div className="text-sm font-bold font-mono text-stone-900">
                      {statsBankA.totalSte > 0
                        ? `${statsBankA.totalSte.toLocaleString('en-GB', { maximumFractionDigits: 1 })} mmboe`
                        : '—'}
                    </div>
                  </div>
                </div>

                {/* Policy Detail */}
                <div className="text-xs space-y-1.5 p-3 bg-amber-50/50 border border-amber-200/60 rounded-lg">
                  <div className="font-semibold text-stone-900 flex items-center justify-between">
                    <span>Fossil Policy Rating:</span>
                    <span className="text-amber-900 font-bold">{statsBankA.profile?.oilGasPolicyRating || 'Standard Wholesale Underwriting'}</span>
                  </div>
                  <p className="text-stone-600 text-[11px] leading-relaxed">
                    {statsBankA.profile?.expansionPolicyExemption ||
                      'Participates in wholesale debt syndications under ESMA prospectus rules.'}
                  </p>
                </div>

                {/* Issuers list */}
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-stone-500 block mb-2">
                    Financed Fossil Issuers:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {statsBankA.issuers.map(iss => (
                      <span key={iss} className="px-2 py-0.5 bg-stone-100 text-stone-800 rounded text-xs">
                        {iss}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Card Bank B */}
            {statsBankB && (
              <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-2xs space-y-4">
                <div className="flex items-center justify-between border-b border-stone-100 pb-3">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400">Entity B</span>
                    <h3 className="text-base font-bold text-stone-900 font-editorial">{statsBankB.name}</h3>
                    <span className="text-xs text-stone-500">{statsBankB.issuersCount} issuers in current view</span>
                  </div>
                  {statsBankB.profile?.nzbaMember ? (
                    <span className="px-2 py-1 bg-blue-50 text-blue-800 border border-blue-200 text-xs font-semibold rounded-md">
                      NZBA Signatory ({statsBankB.profile.nzbaJoinedYear})
                    </span>
                  ) : (
                    <span className="px-2 py-1 bg-stone-100 text-stone-600 text-xs rounded-md">Non-NZBA</span>
                  )}
                </div>

                {/* Key Metrics */}
                <div className="grid grid-cols-3 gap-2 text-center py-2 bg-stone-50 rounded-lg border border-stone-100">
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">1/n Equal Credit</span>
                    <div className="text-sm font-bold font-mono text-stone-900">{formatCurrencyTotals(statsBankB.allocatedByCurrency)}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">Tranches</span>
                    <div className="text-sm font-bold font-mono text-stone-900">{statsBankB.dealCount}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">STE (1/n)</span>
                    <div className="text-sm font-bold font-mono text-stone-900">
                      {statsBankB.totalSte > 0
                        ? `${statsBankB.totalSte.toLocaleString('en-GB', { maximumFractionDigits: 1 })} mmboe`
                        : '—'}
                    </div>
                  </div>
                </div>

                {/* Policy Detail */}
                <div className="text-xs space-y-1.5 p-3 bg-amber-50/50 border border-amber-200/60 rounded-lg">
                  <div className="font-semibold text-stone-900 flex items-center justify-between">
                    <span>Fossil Policy Rating:</span>
                    <span className="text-amber-900 font-bold">{statsBankB.profile?.oilGasPolicyRating || 'Standard Wholesale Underwriting'}</span>
                  </div>
                  <p className="text-stone-600 text-[11px] leading-relaxed">
                    {statsBankB.profile?.expansionPolicyExemption ||
                      'Participates in wholesale debt syndications under ESMA prospectus rules.'}
                  </p>
                </div>

                {/* Issuers list */}
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-stone-500 block mb-2">
                    Financed Fossil Issuers:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {statsBankB.issuers.map(iss => (
                      <span key={iss} className="px-2 py-0.5 bg-stone-100 text-stone-800 rounded text-xs">
                        {iss}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Co-Syndicated Alliances (Both Banks on Same Deal) */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ArrowRightLeft className="w-4 h-4 text-amber-700" />
                <h3 className="text-sm font-bold text-stone-900">
                  Joint Syndicate Co-Occurrences ({coSyndicatedDeals.length} shared {coSyndicatedDeals.length === 1 ? 'deal' : 'deals'})
                </h3>
              </div>
              <span className="text-xs text-stone-500">
                Where {bankA} & {bankB} underwrote in the same syndicate
              </span>
            </div>

            {coSyndicatedDeals.length > 0 ? (
              <div className="divide-y divide-stone-100 border border-stone-200 rounded-lg overflow-hidden">
                {coSyndicatedDeals.map(d => (
                  <div key={d.id} className="p-3 bg-stone-50 hover:bg-white flex items-center justify-between text-xs transition-colors">
                    <div>
                      <span className="font-bold text-stone-900">{d.issuer}</span>
                      <span className="text-stone-400 mx-2">•</span>
                      <span className="font-mono text-stone-600">{d.isin}</span>
                      {d.issue_date && <span className="text-stone-400 ml-2">({d.issue_date})</span>}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold text-stone-900">
                        {formatAmount(d.amount, d.currency)}
                      </span>
                      <span className="text-stone-500 text-[11px]">
                        ({d.underwriters.length} bank syndicate)
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-stone-500 italic p-3 bg-stone-50 rounded-lg">
                No shared debt tranches found between these two institutions in the current ESMA dataset.
              </p>
            )}
          </div>
        </div>
      )}

      {/* ISSUER COMPARISON VIEW */}
      {compareType === 'issuers' && (
        <div className="space-y-6">
          {/* Selectors Bar */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-2xs">
              <label className="block text-xs font-bold text-stone-700 uppercase tracking-wider mb-1.5">
                Primary Issuer (Company A)
              </label>
              <select
                value={issuerA}
                onChange={e => setIssuerA(e.target.value)}
                className="w-full text-sm font-semibold p-2 bg-stone-50 border border-stone-300 rounded-lg text-stone-900 focus:ring-2 focus:ring-amber-500 cursor-pointer"
              >
                {allIssuers.map(iss => (
                  <option key={iss} value={iss}>
                    {iss}
                  </option>
                ))}
              </select>
            </div>

            <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-2xs">
              <label className="block text-xs font-bold text-stone-700 uppercase tracking-wider mb-1.5">
                Comparative Issuer (Company B)
              </label>
              <select
                value={issuerB}
                onChange={e => setIssuerB(e.target.value)}
                className="w-full text-sm font-semibold p-2 bg-stone-50 border border-stone-300 rounded-lg text-stone-900 focus:ring-2 focus:ring-amber-500 cursor-pointer"
              >
                {allIssuers.map(iss => (
                  <option key={iss} value={iss}>
                    {iss}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Issuer A */}
            {statsIssuerA && (
              <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-2xs space-y-4">
                <div className="flex items-center justify-between border-b border-stone-100 pb-3">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400">Issuer A</span>
                    <h3 className="text-base font-bold text-stone-900 font-editorial">{statsIssuerA.name}</h3>
                    <span className="text-xs text-stone-500">{statsIssuerA.dealCount} tranche{statsIssuerA.dealCount === 1 ? '' : 's'} in current view</span>
                  </div>
                  {statsIssuerA.ste > 0 ? (
                    <span className="px-2 py-1 bg-amber-100 text-amber-900 border border-amber-200 text-xs font-bold rounded-md flex items-center gap-1">
                      <Flame className="w-3.5 h-3.5 text-amber-700" />
                      {statsIssuerA.ste.toLocaleString()} mmboe
                    </span>
                  ) : (
                    <span className="px-2 py-1 bg-stone-100 text-stone-600 text-xs rounded-md">Utility / Grid</span>
                  )}
                </div>

                {/* Metrics */}
                <div className="grid grid-cols-3 gap-2 text-center py-2 bg-stone-50 rounded-lg border border-stone-100">
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">Tranches Issued</span>
                    <div className="text-sm font-bold font-mono text-stone-900">{formatCurrencyTotals(statsIssuerA.trancheByCurrency)}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">Programme Shelf</span>
                    <div className="text-sm font-bold font-mono text-stone-900">
                      {formatCurrencyTotals(statsIssuerA.programmeByCurrency)}
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">Dealers in Syndicate</span>
                    <div className="text-sm font-bold font-mono text-stone-900">{statsIssuerA.banksCount}</div>
                  </div>
                </div>

              </div>
            )}

            {/* Issuer B */}
            {statsIssuerB && (
              <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-2xs space-y-4">
                <div className="flex items-center justify-between border-b border-stone-100 pb-3">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-stone-400">Issuer B</span>
                    <h3 className="text-base font-bold text-stone-900 font-editorial">{statsIssuerB.name}</h3>
                    <span className="text-xs text-stone-500">{statsIssuerB.dealCount} tranche{statsIssuerB.dealCount === 1 ? '' : 's'} in current view</span>
                  </div>
                  {statsIssuerB.ste > 0 ? (
                    <span className="px-2 py-1 bg-amber-100 text-amber-900 border border-amber-200 text-xs font-bold rounded-md flex items-center gap-1">
                      <Flame className="w-3.5 h-3.5 text-amber-700" />
                      {statsIssuerB.ste.toLocaleString()} mmboe
                    </span>
                  ) : (
                    <span className="px-2 py-1 bg-stone-100 text-stone-600 text-xs rounded-md">Utility / Grid</span>
                  )}
                </div>

                {/* Metrics */}
                <div className="grid grid-cols-3 gap-2 text-center py-2 bg-stone-50 rounded-lg border border-stone-100">
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">Tranches Issued</span>
                    <div className="text-sm font-bold font-mono text-stone-900">{formatCurrencyTotals(statsIssuerB.trancheByCurrency)}</div>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">Programme Shelf</span>
                    <div className="text-sm font-bold font-mono text-stone-900">
                      {formatCurrencyTotals(statsIssuerB.programmeByCurrency)}
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] text-stone-500 uppercase">Dealers in Syndicate</span>
                    <div className="text-sm font-bold font-mono text-stone-900">{statsIssuerB.banksCount}</div>
                  </div>
                </div>

              </div>
            )}
          </div>

          {/* Overlapping Dealer Syndicate Network */}
          <div className="bg-white border border-stone-200 rounded-xl p-5 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-amber-700" />
                <h3 className="text-sm font-bold text-stone-900">
                  Shared Underwriting Banking Syndicate ({sharedBanks.length} banks)
                </h3>
              </div>
              <span className="text-xs text-stone-500">
                Banks that underwrote debt for BOTH {issuerA} and {issuerB}
              </span>
            </div>

            {sharedBanks.length > 0 ? (
              <div className="flex flex-wrap gap-2 pt-1">
                {sharedBanks.map(bank => (
                  <span
                    key={bank}
                    className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-50 border border-amber-200 text-amber-900 font-medium text-xs rounded-md shadow-2xs"
                  >
                    <CheckCircle2 className="w-3 h-3 text-amber-700" />
                    {bank}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-stone-500 italic p-3 bg-stone-50 rounded-lg">
                No overlapping underwriter banks found between these two issuers.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
