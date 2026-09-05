/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useEffect } from 'react';
import dealsRawData from './data/deals.json';
import { Deal, DealsData, FilterState } from './types/deal';
import { Header } from './components/Header';
import { FilterBar } from './components/FilterBar';
import { DealCard } from './components/DealCard';
import { UnderwriterLeagueTable } from './components/UnderwriterLeagueTable';
import { IssuerMatrix } from './components/IssuerMatrix';
import { CompareView } from './components/CompareView';
import { DealDetailModal } from './components/DealDetailModal';
import { StoryGeneratorModal } from './components/StoryGeneratorModal';
import { MethodologyModal } from './components/MethodologyModal';
import { Filter, ArrowUp } from 'lucide-react';
import { sanitizeDealsPayload, compareByCurrencyThenAmount, compareByCurrencyThenProgramme } from './utils/formatters';

const embedded: DealsData = sanitizeDealsPayload(dealsRawData as DealsData);

export default function App() {
  const [deals, setDeals] = useState<Deal[]>(embedded.deals);
  const [updatedAt, setUpdatedAt] = useState(embedded.updated_at);
  const [dataSource, setDataSource] = useState<'snapshot' | 'api'>('snapshot');
  const [activeView, setActiveView] = useState<'feed' | 'league' | 'issuers' | 'compare'>('feed');
  const [inspectedDeal, setInspectedDeal] = useState<Deal | null>(null);
  const [pitchDeal, setPitchDeal] = useState<Deal | null>(null);
  const [isMethodologyOpen, setIsMethodologyOpen] = useState(false);

  const [filters, setFilters] = useState<FilterState>({
    search: '',
    selectedUnderwriter: '',
    selectedIssuer: '',
    expansionOnly: false,
    yearFilter: '',
    sortBy: 'date_desc',
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (pitchDeal) setPitchDeal(null);
      else if (inspectedDeal) setInspectedDeal(null);
      else if (isMethodologyOpen) setIsMethodologyOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [inspectedDeal, pitchDeal, isMethodologyOpen]);

  useEffect(() => {
    const ac = new AbortController();
    fetch('/api/deals', { signal: ac.signal })
      .then(res => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json() as Promise<DealsData>;
      })
      .then(payload => {
        const next = sanitizeDealsPayload(payload);
        setDeals(next.deals);
        if (next.updated_at) setUpdatedAt(next.updated_at);
        setDataSource('api');
      })
      .catch(err => {
        if (err?.name === 'AbortError') return;
      });
    return () => ac.abort();
  }, []);

  // Extract unique filter dropdown values
  const { availableBanks, availableIssuers, availableYears } = useMemo(() => {
    const banks = new Set<string>();
    const issuers = new Set<string>();
    const years = new Set<string>();

    deals.forEach(deal => {
      issuers.add(deal.issuer);
      deal.underwriters.forEach(u => banks.add(u.raw_name));
      if (deal.issue_date) {
        const y = deal.issue_date.slice(0, 4);
        if (y) years.add(y);
      }
    });

    return {
      availableBanks: Array.from(banks).sort(),
      availableIssuers: Array.from(issuers).sort(),
      availableYears: Array.from(years).sort().reverse(),
    };
  }, [deals]);

  // Filter and sort deals
  const filteredDeals = useMemo(() => {
    return deals
      .filter(deal => {
        // Search filter (issuer, ISIN, underwriter, doc_id)
        if (filters.search.trim()) {
          const q = filters.search.toLowerCase().trim();
          const matchIssuer = deal.issuer.toLowerCase().includes(q);
          const matchIsin = deal.isin.toLowerCase().includes(q);
          const matchDocId = deal.doc_id ? deal.doc_id.toLowerCase().includes(q) : false;
          const matchBank = deal.underwriters.some(u =>
            u.raw_name.toLowerCase().includes(q)
          );
          if (!matchIssuer && !matchIsin && !matchDocId && !matchBank) {
            return false;
          }
        }

        // Underwriter bank filter
        if (filters.selectedUnderwriter) {
          const hasBank = deal.underwriters.some(
            u => u.raw_name === filters.selectedUnderwriter
          );
          if (!hasBank) return false;
        }

        // Issuer filter
        if (filters.selectedIssuer && deal.issuer !== filters.selectedIssuer) {
          return false;
        }

        // Upstream Short-term Expansion only (STE > 0)
        if (filters.expansionOnly && (!deal.ste_mmboe || deal.ste_mmboe <= 0)) {
          return false;
        }

        // Year filter
        if (filters.yearFilter) {
          if (!deal.issue_date || !deal.issue_date.startsWith(filters.yearFilter)) {
            return false;
          }
        }

        return true;
      })
      .sort((a, b) => {
        switch (filters.sortBy) {
          case 'date_desc': {
            if (!a.issue_date) return 1;
            if (!b.issue_date) return -1;
            return b.issue_date.localeCompare(a.issue_date);
          }
          case 'date_asc': {
            if (!a.issue_date) return 1;
            if (!b.issue_date) return -1;
            return a.issue_date.localeCompare(b.issue_date);
          }
          case 'amount_desc':
            return compareByCurrencyThenAmount(a, b, 'desc');
          case 'amount_asc':
            return compareByCurrencyThenAmount(a, b, 'asc');
          case 'programme_desc':
            return compareByCurrencyThenProgramme(a, b, 'desc');
          case 'ste_desc': {
            const steA = a.ste_mmboe ?? 0;
            const steB = b.ste_mmboe ?? 0;
            return steB - steA;
          }
          case 'underwriters_desc': {
            return (b.n_underwriters || 0) - (a.n_underwriters || 0);
          }
          default:
            return 0;
        }
      });
  }, [deals, filters]);

  const handleSelectBank = (bankName: string) => {
    setFilters(prev => ({
      ...prev,
      selectedUnderwriter: bankName,
    }));
    setActiveView('feed');
  };

  const handleSelectIssuer = (issuerName: string) => {
    setFilters(prev => ({
      ...prev,
      selectedIssuer: issuerName,
    }));
    setActiveView('feed');
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-stone-900 flex flex-col font-sans">
      {/* Header */}
      <Header
        deals={deals}
        filteredDeals={filteredDeals}
        updatedAt={updatedAt}
        dataSource={dataSource}
        onOpenMethodology={() => setIsMethodologyOpen(true)}
      />

      {/* Filter & View Switcher */}
      <FilterBar
        filters={filters}
        onFilterChange={setFilters}
        availableBanks={availableBanks}
        availableIssuers={availableIssuers}
        availableYears={availableYears}
        totalDealsCount={deals.length}
        filteredDealsCount={filteredDeals.length}
        activeView={activeView}
        onViewChange={setActiveView}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {/* Deal Feed View */}
        {activeView === 'feed' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-stone-500 pb-1">
              <span className="font-semibold uppercase tracking-wider text-[11px] text-stone-700">
                Chronological Debt Feed ({filteredDeals.length} {filteredDeals.length === 1 ? 'deal' : 'deals'})
              </span>
              <span className="italic">
                {filters.sortBy === 'date_desc'
                  ? 'Showing newest issue dates first'
                  : `Sorted by ${filters.sortBy.replace('_', ' ')}`}
              </span>
            </div>

            {filteredDeals.length > 0 ? (
              <div className="space-y-3.5">
                {filteredDeals.map(deal => (
                  <DealCard
                    key={deal.id}
                    deal={deal}
                    onSelectBank={handleSelectBank}
                    onSelectIssuer={handleSelectIssuer}
                    onInspectDeal={deal => setInspectedDeal(deal)}
                    onGeneratePitch={deal => setPitchDeal(deal)}
                  />
                ))}
              </div>
            ) : (
              /* Quiet Empty State Rule */
              <div className="bg-white border border-stone-200 rounded-lg p-10 text-center">
                <p className="text-stone-600 text-sm font-medium">
                  No tranches match the selected filters or search terms.
                </p>
                <button
                  onClick={() =>
                    setFilters({
                      search: '',
                      selectedUnderwriter: '',
                      selectedIssuer: '',
                      expansionOnly: false,
                      yearFilter: '',
                      sortBy: 'date_desc',
                    })
                  }
                  className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-amber-800 hover:text-amber-950 bg-amber-50 hover:bg-amber-100 px-3 py-1.5 rounded-md transition-colors cursor-pointer"
                >
                  <Filter className="w-3 h-3" />
                  <span>Reset All Filters</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Underwriter Syndicate League Table View */}
        {activeView === 'league' && (
          <UnderwriterLeagueTable
            deals={filteredDeals}
            onSelectBank={handleSelectBank}
          />
        )}

        {/* Issuer Matrix View */}
        {activeView === 'issuers' && (
          <IssuerMatrix
            deals={filteredDeals}
            onSelectIssuer={handleSelectIssuer}
            onSelectBank={handleSelectBank}
          />
        )}

        {/* Side-by-Side Comparison Workspace */}
        {activeView === 'compare' && (
          <CompareView
            deals={filteredDeals}
            onSelectBank={handleSelectBank}
            onSelectIssuer={handleSelectIssuer}
          />
        )}
      </main>

      {/* Floating Scroll to Top */}
      <button
        onClick={scrollToTop}
        className="fixed bottom-5 right-5 p-2.5 bg-stone-900 text-stone-100 hover:bg-stone-800 rounded-full shadow-lg transition-all cursor-pointer hover:scale-105 z-30"
        title="Scroll to top"
        aria-label="Scroll to top"
      >
        <ArrowUp className="w-4 h-4" />
      </button>

      {/* Footer / Colophon */}
      <footer className="border-t border-stone-200 bg-white text-stone-600 text-xs py-8 px-4 sm:px-6 mt-12">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <div className="font-bold text-stone-900 font-editorial text-sm">
              PaperTrails
            </div>
            <p className="text-[11px] text-stone-500 mt-0.5">
              Financial journalism database monitoring EU fossil bond underwriting syndicates from ESMA Final Terms Wholesale (FTWS) filings.
            </p>
          </div>
          <div className="text-[11px] text-stone-500 flex flex-wrap items-center gap-3">
            <span>Equal credit rule: 1/n tranche allocation</span>
            <span>•</span>
            <button
              onClick={() => setIsMethodologyOpen(true)}
              className="hover:underline text-stone-700 cursor-pointer"
            >
              Methodology
            </button>
            <span>•</span>
            <span>British English editorial format</span>
          </div>
        </div>
      </footer>

      {/* Modals */}
      <DealDetailModal
        deal={inspectedDeal}
        onClose={() => setInspectedDeal(null)}
        onSelectBank={handleSelectBank}
        onGeneratePitch={deal => setPitchDeal(deal)}
      />

      <StoryGeneratorModal
        deal={pitchDeal}
        onClose={() => setPitchDeal(null)}
      />

      <MethodologyModal
        isOpen={isMethodologyOpen}
        onClose={() => setIsMethodologyOpen(false)}
      />
    </div>
  );
}

