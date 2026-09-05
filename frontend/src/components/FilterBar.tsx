import React from 'react';
import { Search, X, SlidersHorizontal, ArrowDownUp, Flame, LayoutList, Trophy, PieChart, Scale } from 'lucide-react';
import { FilterState } from '../types/deal';

interface FilterBarProps {
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  availableBanks: string[];
  availableIssuers: string[];
  availableYears: string[];
  totalDealsCount: number;
  filteredDealsCount: number;
  activeView: 'feed' | 'league' | 'issuers' | 'compare';
  onViewChange: (view: 'feed' | 'league' | 'issuers' | 'compare') => void;
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
}) => {
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

            <button
              id="view-compare-btn"
              onClick={() => onViewChange('compare')}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                activeView === 'compare'
                  ? 'bg-white text-stone-900 shadow-xs border border-stone-200/60'
                  : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              <Scale className="w-3.5 h-3.5 text-amber-700" />
              <span>Side-by-Side Compare</span>
            </button>
          </div>

          {/* Quick Search */}
          <div className="relative flex-1 max-w-md">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-stone-400">
              <Search className="w-4 h-4" />
            </div>
            <input
              id="search-input"
              type="text"
              value={filters.search}
              onChange={e => onFilterChange({ ...filters, search: e.target.value })}
              placeholder="Search issuer, ISIN (e.g. XS3305...), or underwriter bank..."
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
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-stone-100 text-stone-800 rounded border border-stone-200">
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
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-900 rounded border border-amber-200">
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
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-900 rounded border border-blue-200">
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
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-stone-100 text-stone-800 rounded border border-stone-200">
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
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-900 rounded border border-amber-200">
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
