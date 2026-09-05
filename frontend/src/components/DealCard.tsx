import React, { useState } from 'react';
import { ExternalLink, Copy, Check, Info, Flame, FileText, Sparkles } from 'lucide-react';
import { Deal } from '../types/deal';
import { formatAmount, formatExactAmount, formatDate, formatCouponRate, formatMaturity, displayUnderwriterRole, generateCitation, safeHttpUrl } from '../utils/formatters';

interface DealCardProps {
  deal: Deal;
  onSelectBank?: (bankName: string) => void;
  onSelectIssuer?: (issuerName: string) => void;
  onInspectDeal?: (deal: Deal) => void;
  onGeneratePitch?: (deal: Deal) => void;
}

export const DealCard: React.FC<DealCardProps> = ({
  deal,
  onSelectBank,
  onSelectIssuer,
  onInspectDeal,
  onGeneratePitch,
}) => {
  const [copiedIsin, setCopiedIsin] = useState(false);
  const [copiedCitation, setCopiedCitation] = useState(false);

  const formattedTranche = formatAmount(deal.amount, deal.currency);
  const exactTranche = formatExactAmount(deal.amount, deal.currency);
  const hasProgramme = deal.programme_size && deal.programme_size !== '0';
  const formattedProgramme = hasProgramme
    ? formatAmount(deal.programme_size, deal.currency)
    : null;
  const exactProgramme = hasProgramme
    ? formatExactAmount(deal.programme_size, deal.currency)
    : null;

  const handleCopyIsin = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(deal.isin);
    setCopiedIsin(true);
    setTimeout(() => setCopiedIsin(false), 2000);
  };

  const handleCopyCitation = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(generateCitation(deal));
    setCopiedCitation(true);
    setTimeout(() => setCopiedCitation(false), 2000);
  };

  const hasUpstreamExpansion = (deal.ste_mmboe ?? 0) > 0;
  const couponLabel = formatCouponRate(deal.coupon_rate, deal.coupon_type);
  const maturityLabel = formatMaturity(deal.maturity_date, deal.maturity_kind);

  return (
    <article
      id={`deal-card-${deal.id}`}
      className="bg-white border border-stone-200/90 rounded-lg p-4 sm:p-5 hover:border-stone-400/80 transition-all shadow-2xs hover:shadow-xs relative group"
    >
      {/* Top Header: Issuer, Watchlist Badge, ISIN, Date */}
      <div className="flex flex-wrap items-start justify-between gap-2 pb-3 border-b border-stone-100">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1">
            {deal.watchlist_rank && (
              <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold uppercase bg-stone-900 text-stone-100 rounded-xs">
                Watchlist #{deal.watchlist_rank}
              </span>
            )}
            {deal.doc_type_code && (
              <span
                className="px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase bg-stone-100 text-stone-700 border border-stone-200 rounded-xs"
                title="Document Type: Final Terms Wholesale"
              >
                {deal.doc_type_code}
              </span>
            )}
            {hasUpstreamExpansion && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold bg-amber-50 text-amber-900 border border-amber-300/80 rounded-xs">
                <Flame className="w-3 h-3 text-amber-600" />
                <span>Upstream Expansion: {deal.ste_mmboe?.toFixed(1)} mmboe</span>
              </span>
            )}
          </div>

          <h3 className="text-lg sm:text-xl font-bold text-stone-900 tracking-tight font-sans flex items-center gap-2">
            <button
              onClick={() => onSelectIssuer?.(deal.issuer)}
              className="text-left hover:text-amber-800 hover:underline transition-colors cursor-pointer"
            >
              {deal.issuer}
            </button>
          </h3>
        </div>

        {/* Issue Date & ISIN Code */}
        <div className="flex flex-col items-end text-xs">
          <time className="font-semibold text-stone-800 font-tabular text-sm">
            {formatDate(deal.issue_date)}
          </time>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="font-mono text-stone-600 bg-stone-100/90 px-1.5 py-0.5 rounded text-[11px] border border-stone-200/80">
              {deal.isin}
            </span>
            <button
              onClick={handleCopyIsin}
              className="text-stone-400 hover:text-stone-700 transition-colors p-0.5 cursor-pointer"
              title="Copy ISIN code"
            >
              {copiedIsin ? (
                <Check className="w-3.5 h-3.5 text-emerald-600" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Main Financial Figures Row: Tranche Headline + Programme Secondary */}
      <div className="my-4 py-3 px-3.5 bg-stone-50/90 border border-stone-200/70 rounded-md flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-0.5">
            Issued Tranche
          </div>
          <div
            className="text-2xl sm:text-3xl font-extrabold text-stone-950 font-mono tracking-tight"
            title={`Exact tranche: ${exactTranche}`}
          >
            {formattedTranche}
          </div>
          <div className="text-[11px] text-stone-500 font-tabular mt-0.5">
            Nominal tranche amount ({deal.currency})
            {(couponLabel || maturityLabel) && (
              <span className="text-stone-600">
                {' '}
                · {couponLabel && `Coupon ${couponLabel}`}
                {couponLabel && maturityLabel && ' · '}
                {maturityLabel && `Maturity ${maturityLabel}`}
              </span>
            )}
          </div>
        </div>

        {/* Secondary line: Programme Capacity */}
        <div className="sm:text-right border-t sm:border-t-0 pt-2 sm:pt-0 border-stone-200/60">
          <div className="text-[11px] font-medium text-stone-500">
            Programme Facility
          </div>
          {formattedProgramme ? (
            <div
              className="text-base sm:text-lg font-semibold text-stone-700 font-mono"
              title={`Exact programme facility capacity: ${exactProgramme}`}
            >
              Programme {formattedProgramme}
            </div>
          ) : (
            <div className="text-sm font-medium text-stone-400 italic">
              Programme capacity not specified in final terms
            </div>
          )}
          <div className="text-[10px] text-stone-500">
            Shelf capacity (not issued volume)
          </div>
        </div>
      </div>

      {/* Underwriters Syndicate Section */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-xs mb-2">
          <span className="font-semibold text-stone-700 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
            <span>Underwriting Syndicate</span>
            <span className="font-mono text-stone-500 font-normal">
              ({deal.n_underwriters} {deal.n_underwriters === 1 ? 'dealer' : 'dealers'} • 1/{deal.n_underwriters} equal split)
            </span>
          </span>
          <span className="text-[11px] text-stone-500 italic hidden sm:inline">
            Equal tranche credit allocation
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {deal.underwriters.map((underwriter, idx) => {
            const formattedAllocated = formatAmount(underwriter.allocated_amount, deal.currency);
            const exactAllocated = formatExactAmount(underwriter.allocated_amount, deal.currency);
            const roleLabel = displayUnderwriterRole(underwriter.role);

            return (
              <div
                key={idx}
                className="flex items-center justify-between gap-2 p-2 bg-stone-50 hover:bg-amber-50/50 border border-stone-200/70 hover:border-amber-300/80 rounded transition-colors text-xs group/bank"
              >
                <div className="flex flex-col min-w-0 truncate">
                  <button
                    onClick={() => onSelectBank?.(underwriter.raw_name)}
                    className="font-medium text-stone-900 group-hover/bank:text-amber-900 text-left truncate hover:underline cursor-pointer"
                    title={`Filter deals underwritten by ${underwriter.raw_name}`}
                  >
                    {underwriter.raw_name}
                  </button>
                  {roleLabel && (
                    <span className="text-[10px] text-stone-500 truncate">{roleLabel}</span>
                  )}
                </div>
                <div
                  className="font-mono font-semibold text-stone-700 whitespace-nowrap bg-white px-1.5 py-0.5 rounded border border-stone-200/80 text-[11px]"
                  title={`Exact equal credit: ${exactAllocated}`}
                >
                  {formattedAllocated}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Card Footer: Prospectus Link, Citation Tool, Pitch Generator, & Inspection Details */}
      <div className="mt-4 pt-3 border-t border-stone-100 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-3">
          {safeHttpUrl(deal.source_url) ? (
            <a
              href={safeHttpUrl(deal.source_url)!}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-semibold text-amber-800 hover:text-amber-950 hover:underline transition-colors cursor-pointer"
              title="Download verified ESMA Final Terms prospectus PDF in new tab"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Prospectus Filing</span>
              <ExternalLink className="w-3 h-3 ml-0.5" />
            </a>
          ) : (
            <span className="text-stone-400 text-[11px] italic">
              Prospectus link verified in ESMA registry
            </span>
          )}

          <button
            onClick={handleCopyCitation}
            className="inline-flex items-center gap-1 text-stone-600 hover:text-stone-900 transition-colors cursor-pointer"
            title="Copy journalistic reference citation for this deal"
          >
            {copiedCitation ? (
              <>
                <Check className="w-3 h-3 text-emerald-600" />
                <span className="text-emerald-700 font-medium">Citation Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3 text-stone-400" />
                <span>Copy Citation</span>
              </>
            )}
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* News Pitch Generator Trigger Button */}
          <button
            onClick={() => onGeneratePitch?.(deal)}
            className="inline-flex items-center gap-1 text-amber-900 bg-amber-100/90 hover:bg-amber-200/90 font-semibold px-2.5 py-1 rounded transition-colors cursor-pointer text-[11px] shadow-2xs"
            title="Generate ready-to-use newsroom story lead & pitch"
          >
            <Sparkles className="w-3 h-3 text-amber-800" />
            <span>Story Lead</span>
          </button>

          {deal.doc_id && (
            <span className="text-stone-600 text-[11px] font-mono hidden sm:inline">
              Doc ID: {deal.doc_id}
            </span>
          )}
          <button
            onClick={() => onInspectDeal?.(deal)}
            className="inline-flex items-center gap-1 text-stone-600 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 px-2 py-1 rounded transition-colors cursor-pointer text-[11px]"
            title="View complete ESMA regulatory record metadata"
          >
            <Info className="w-3 h-3" />
            <span>Inspect Filing</span>
          </button>
        </div>
      </div>
    </article>
  );
};

