import React, { useState, useEffect } from 'react';
import { Search, X, ArrowDownUp, Flame, LayoutList, Trophy, PieChart, Download, FileText, ChevronDown } from 'lucide-react';
import { FilterState, Deal } from '../types/deal';
import { exportDealsToCSV, exportDealsToJSON } from '../utils/formatters';

interface FilterBarProps {
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  availableBanks: string[];
  availableIssuers: string[];
  availableYears: string[];
  totalDealsCount: number;
  filteredDealsCount: number;
  activeView: 'feed' | 'league' | 'issuers';
  onViewChange: (view: 'feed' | 'league' | 'issuers') => void;
  highlightedFilter?: string | null;
  filteredDeals: Deal[];
  updatedAt: string;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  filters,
  onFilterChange,
  availableBanks,
  availableIssuers,
  availableYears,
  totalDealsCount,
  filteredDealsCount,
  activeView,
  onViewChange,
  highlightedFilter,
  filteredDeals,
  updatedAt,
}) => {
  const [exportOpen, setExportOpen] = useState(false);
  const [chipHighlight, setChipHighlight] = useState<string | null>(null);

  // Animate the highlighted filter chip briefly
  useEffect(() => {
    if (highlightedFilter) {
      setChipHighlight(highlightedFilter);
      const timer = setTimeout(() => setChipHighlight(null), 1200);
      return () => clearTimeout(timer);
    }
  }, [highlightedFilter]);

  const hasActiveFilters =
    filters.search !== '' ||
    filters.selectedUnderwriter !== '' ||
    filters.selectedIssuer !== '' ||
    filters.expansionOnly ||
    filters.yearFilter !== '';

  const handleReset = () => {
    onFilterChange({
      search: '',
      selectedUnderwriter: '',
      selectedIssuer: '',
      expansionOnly: false,
      yearFilter: '',
      sortBy: 'date_desc',
    });
  };

  const chipAnimClass = (chipKey: string) =>
    chipHighlight === chipKey ? 'animate-pulse ring-2 ring-amber-400' : '';

  return (
    <div className="bg-white border-b border-stone-200 shadow-2xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3.5">
        {/* View Switcher Tabs & Search Row */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          {/* View Mode Buttons */}
          <div className="inline-flex p-1 bg-stone-100/90 rounded-lg border border-stone-200/80 self-start flex-wrap gap-1">
            <button
              id="view-feed-btn"
              onClick={() => onViewChange('feed')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                activeView === 'feed'
                  ? 'bg-white text-stone-900 shadow-xs border border-stone-200/60'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              <LayoutList className="w-3.5 h-3.5" />
              <span>Deal Feed ({filteredDealsCount})</span>
            </button>

            <button
              id="view-league-btn"
              onClick={() => onViewChange('league')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                activeView === 'league'
                  ? 'bg-white text-stone-900 shadow-xs border border-stone-200/60'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              <Trophy className="w-3.5 h-3.5 text-amber-600" />
              <span>Underwriter League</span>
            </button>

            <button
              id="view-issuers-btn"
              onClick={() => onViewChange('issuers')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                activeView === 'issuers'
                  ? 'bg-white text-stone-900 shadow-xs border border-stone-200/60'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              <PieChart className="w-3.5 h-3.5 text-stone-600" />
              <span>Issuer Profiles</span>
            </button>
          </div>

          {/* Quick Search + Export */}
          <div className="flex items-center gap-2 flex-1 max-w-lg">
            <div className="relative flex-1">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-stone-400">
                <Search className="w-4 h-4" />
              </div>
              <input
                id="search-input"
                type="text"
                value={filters.search}
                onChange={e => onFilterChange({ ...filters, search: e.target.value })}
                placeholder="Search issuer, ISIN, or underwriter..."
                className="w-full pl-9 pr-8 py-1.5 text-sm bg-stone-50 hover:bg-white focus:bg-white border border-stone-300 rounded-md focus:outline-hidden focus:ring-2 focus:ring-amber-500/20 focus:border-amber-600 transition-all font-sans text-stone-900 placeholder:text-stone-400"
              />
              {filters.search && (
                <button
                  onClick={() => onFilterChange({ ...filters, search: '' })}
                  className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-stone-400 hover:text-stone-600 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Export Dropdown */}
            <div className="relative">
              <button
                id="export-dropdown-btn"
                onClick={() => setExportOpen(!exportOpen)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold text-stone-700 bg-stone-50 hover:bg-stone-100 border border-stone-300 rounded-md transition-colors shadow-2xs cursor-pointer"
                title="Export data"
              >
                <Download className="w-3.5 h-3.5 text-stone-500" />
                <span>Export</span>
                <ChevronDown className="w-3 h-3 text-stone-400" />
              </button>
              {exportOpen && (
                <div className="absolute right-0 mt-1 w-48 bg-white border border-stone-200 rounded-md shadow-lg z-20">
                  <button
                    id="export-csv-btn"
                    onClick={() => { exportDealsToCSV(filteredDeals); setExportOpen(false); }}
                    className="w-full text-left px-3 py-2 text-xs font-medium text-stone-700 hover:bg-stone-50 flex items-center gap-2 cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5 text-stone-400" />
                    Export CSV ({filteredDeals.length} deals)
                  </button>
                  <button
                    id="export-json-btn"
                    onClick={() => { exportDealsToJSON(filteredDeals, updatedAt); setExportOpen(false); }}
                    className="w-full text-left px-3 py-2 text-xs font-medium text-stone-700 hover:bg-stone-50 flex items-center gap-2 border-t border-stone-100 cursor-pointer"
                  >
                    <FileText className="w-3.5 h-3.5 text-stone-400" />
                    Export JSON
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Filter Controls Row */}
        <div className="flex flex-wrap items-center gap-2.5 mt-3 pt-3 border-t border-stone-100">
          {/* Underwriter Bank Selector */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="filter-bank" className="text-xs font-medium text-stone-600 whitespace-nowrap">
              Bank:
            </label>
            <select
              id="filter-bank"
              value={filters.selectedUnderwriter}
              onChange={e => onFilterChange({ ...filters, selectedUnderwriter: e.target.value })}
              className="text-xs py-1.5 px-2 bg-stone-50 hover:bg-white border border-stone-300 rounded-md focus:ring-1 focus:ring-amber-500 focus:border-amber-500 text-stone-800 cursor-pointer max-w-[200px]"
            >
              <option value="">All Underwriting Banks ({availableBanks.length})</option>
              {availableBanks.map(bank => (
                <option key={bank} value={bank}>
                  {bank}
                </option>
              ))}
            </select>
          </div>

          {/* Issuer Selector */}
          <div className="flex items-center gap-1.5">
            <label htmlFor="filter-issuer" className="text-xs font-medium text-stone-600 whitespace-nowrap">
              Issuer:
            </label>
            <select
              id="filter-issuer"
              value={filters.selectedIssuer}
              onChange={e => onFilterChange({ ...filters, selectedIssuer: e.target.value })}
              className="text-xs py-1.5 px-2 bg-stone-50 hover:bg-white border border-stone-300 rounded-md focus:ring-1 focus:ring-amber-500 focus:border-amber-500 text-stone-800 cursor-pointer max-w-[180px]"
            >
              <option value="">All Issuers ({availableIssuers.length})</option>
              {availableIssuers.map(issuer => (
                <option key={issuer} value={issuer}>
                  {issuer}
                </option>
              ))}
            </select>
          </div>

          {/* Year Filter */}
          {availableYears.length > 1 && (
            <div className="flex items-center gap-1.5">
              <label htmlFor="filter-year" className="text-xs font-medium text-stone-600 whitespace-nowrap">
                Year:
              </label>
              <select
                id="filter-year"
                value={filters.yearFilter}
                onChange={e => onFilterChange({ ...filters, yearFilter: e.target.value })}
                className="text-xs py-1.5 px-2 bg-stone-50 hover:bg-white border border-stone-300 rounded-md focus:ring-1 focus:ring-amber-500 focus:border-amber-500 text-stone-800 cursor-pointer"
              >
                <option value="">All Years</option>
                {availableYears.map(year => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Upstream Fossil Expansion Toggle */}
          <button
            id="filter-expansion-toggle"
            type="button"
            onClick={() => onFilterChange({ ...filters, expansionOnly: !filters.expansionOnly })}
            className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-md border transition-colors cursor-pointer ${
              filters.expansionOnly
                ? 'bg-amber-100 text-amber-900 border-amber-300 font-semibold'
                : 'bg-stone-50 text-stone-700 border-stone-300 hover:bg-stone-100'
            }`}
          >
            <Flame className={`w-3.5 h-3.5 ${filters.expansionOnly ? 'text-amber-700' : 'text-stone-400'}`} />
            <span>Upstream Expansion (STE &gt; 0)</span>
          </button>

          {/* Sort By Dropdown */}
          <div className="flex items-center gap-1.5 ml-auto">
            <ArrowDownUp className="w-3.5 h-3.5 text-stone-500" />
            <select
              id="sort-select"
              value={filters.sortBy}
              onChange={e =>
                onFilterChange({ ...filters, sortBy: e.target.value as FilterState['sortBy'] })
              }
              className="text-xs py-1.5 px-2 bg-stone-50 hover:bg-white border border-stone-300 rounded-md focus:ring-1 focus:ring-amber-500 focus:border-amber-500 text-stone-800 cursor-pointer"
            >
              <option value="date_desc">Sort: Newest Issue Date</option>
              <option value="date_asc">Sort: Oldest Issue Date</option>
              <option value="amount_desc">Sort: Largest Tranche</option>
              <option value="amount_asc">Sort: Smallest Tranche</option>
              <option value="programme_desc">Sort: Largest Programme</option>
              <option value="ste_desc">Sort: Highest Upstream Expansion (STE)</option>
              <option value="underwriters_desc">Sort: Most Underwriters</option>
            </select>
          </div>

          {/* Reset Filters */}
          {hasActiveFilters && (
            <button
              onClick={handleReset}
              className="inline-flex items-center gap-1 text-xs text-amber-700 hover:text-amber-900 font-medium px-2 py-1 bg-amber-50 hover:bg-amber-100 rounded-md transition-colors cursor-pointer"
            >
              <X className="w-3 h-3" />
              <span>Reset</span>
            </button>
          )}
        </div>

        {/* Active Filter Chips */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-1.5 mt-2.5 pt-2 text-xs">
            <span className="text-stone-500">Active filters:</span>
            {filters.search && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 bg-stone-100 text-stone-800 rounded border border-stone-200 transition-all ${chipAnimClass('search')}`}>
                Keyword: "{filters.search}"
                <button
                  onClick={() => onFilterChange({ ...filters, search: '' })}
                  className="hover:text-red-600 cursor-pointer"
                >
                  ×
                </button>
              </span>
            )}
            {filters.selectedUnderwriter && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-900 rounded border border-amber-200 transition-all ${chipAnimClass('bank')}`}>
                Bank: {filters.selectedUnderwriter}
                <button
                  onClick={() => onFilterChange({ ...filters, selectedUnderwriter: '' })}
                  className="hover:text-red-600 cursor-pointer"
                >
                  ×
                </button>
              </span>
            )}
            {filters.selectedIssuer && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-900 rounded border border-blue-200 transition-all ${chipAnimClass('issuer')}`}>
                Issuer: {filters.selectedIssuer}
                <button
                  onClick={() => onFilterChange({ ...filters, selectedIssuer: '' })}
                  className="hover:text-red-600 cursor-pointer"
                >
                  ×
                </button>
              </span>
            )}
            {filters.yearFilter && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 bg-stone-100 text-stone-800 rounded border border-stone-200 transition-all ${chipAnimClass('year')}`}>
                Year: {filters.yearFilter}
                <button
                  onClick={() => onFilterChange({ ...filters, yearFilter: '' })}
                  className="hover:text-red-600 cursor-pointer"
                >
                  ×
                </button>
              </span>
            )}
            {filters.expansionOnly && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-900 rounded border border-amber-200 transition-all ${chipAnimClass('expansion')}`}>
                Upstream STE &gt; 0 only
                <button
                  onClick={() => onFilterChange({ ...filters, expansionOnly: false })}
                  className="hover:text-red-600 cursor-pointer"
                >
                  ×
                </button>
              </span>
            )}
            <span className="text-stone-400">
              ({filteredDealsCount} of {totalDealsCount} tranches matching)
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
