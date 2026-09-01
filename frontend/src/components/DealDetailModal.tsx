import React, { useState } from 'react';
import { X, ExternalLink, Copy, Check, FileText, Flame, Sparkles } from 'lucide-react';
import { Deal } from '../types/deal';
import { formatAmount, formatExactAmount, formatDate, formatDateTime, generateCitation, sanitizeDeal, safeHttpUrl } from '../utils/formatters';
import { getBankClimateProfile } from '../data/referenceData';

interface DealDetailModalProps {
  deal: Deal | null;
  onClose: () => void;
  onSelectBank?: (bank: string) => void;
  onGeneratePitch?: (deal: Deal) => void;
}

export const DealDetailModal: React.FC<DealDetailModalProps> = ({
  deal,
  onClose,
  onSelectBank,
  onGeneratePitch,
}) => {
  const [copiedCitation, setCopiedCitation] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);

  if (!deal) return null;

  const prospectusUrl = safeHttpUrl(deal.source_url);

  const handleCopyCitation = () => {
    navigator.clipboard.writeText(generateCitation(deal));
    setCopiedCitation(true);
    setTimeout(() => setCopiedCitation(false), 2000);
  };

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(sanitizeDeal(deal), null, 2));
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div
        className="bg-white rounded-lg border border-stone-200 shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-stone-200 flex items-start justify-between gap-4 sticky top-0 bg-white z-10">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-mono font-bold uppercase bg-stone-900 text-stone-100 px-2 py-0.5 rounded-xs">
                {deal.doc_type_code || 'FTWS'}
              </span>
              {deal.watchlist_rank && (
                <span className="text-[11px] font-mono font-bold uppercase bg-amber-100 text-amber-900 border border-amber-300 px-2 py-0.5 rounded-xs">
                  Watchlist #{deal.watchlist_rank}
                </span>
              )}
              {deal.ste_mmboe && deal.ste_mmboe > 0 ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-800 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded-xs">
                  <Flame className="w-3 h-3 text-amber-600" />
                  STE: {deal.ste_mmboe.toFixed(2)} mmboe
                </span>
              ) : null}
            </div>
            <h2 className="text-xl font-bold text-stone-900 font-editorial">
              {deal.issuer}
            </h2>
            <div className="text-xs text-stone-500 font-mono mt-0.5">
              ISIN: {deal.isin}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-stone-400 hover:text-stone-700 p-1.5 rounded-md hover:bg-stone-100 transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-6 space-y-5 text-xs text-stone-700">
          {/* Main Financial Figures */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 bg-stone-50 border border-stone-200 rounded-md">
            <div>
              <div className="text-[11px] font-semibold uppercase text-stone-500">
                Issued Tranche
              </div>
              <div className="text-2xl font-bold font-mono text-stone-950 mt-0.5">
                {formatAmount(deal.amount, deal.currency)}
              </div>
              <div className="text-[11px] font-mono text-stone-500 mt-0.5">
                Exact: {formatExactAmount(deal.amount, deal.currency)}
              </div>
            </div>

            <div>
              <div className="text-[11px] font-semibold uppercase text-stone-500">
                Programme Capacity
              </div>
              <div className="text-xl font-bold font-mono text-stone-800 mt-0.5">
                {deal.programme_size
                  ? formatAmount(deal.programme_size, deal.currency)
                  : 'Not Specified'}
              </div>
              <div className="text-[11px] font-mono text-stone-500 mt-0.5">
                {deal.programme_size
                  ? `Exact: ${formatExactAmount(deal.programme_size, deal.currency)}`
                  : 'Shelf facility capacity'}
              </div>
            </div>
          </div>

          {/* Key Deal Metadata Table */}
          <div className="border border-stone-200 rounded-md overflow-hidden">
            <div className="bg-stone-100/80 px-3 py-2 border-b border-stone-200 font-semibold text-stone-800 uppercase tracking-wider text-[11px]">
              Filing & Extraction Details
            </div>
            <dl className="divide-y divide-stone-200">
              <div className="grid grid-cols-3 px-3 py-2">
                <dt className="text-stone-500 font-medium">Issue Date</dt>
                <dd className="col-span-2 font-mono font-semibold text-stone-900">
                  {formatDate(deal.issue_date)} ({deal.issue_date || 'N/A'})
                </dd>
              </div>
              <div className="grid grid-cols-3 px-3 py-2">
                <dt className="text-stone-500 font-medium">Currency</dt>
                <dd className="col-span-2 font-mono text-stone-900">{deal.currency}</dd>
              </div>
              <div className="grid grid-cols-3 px-3 py-2">
                <dt className="text-stone-500 font-medium">Amount Kind</dt>
                <dd className="col-span-2 font-mono text-stone-900">{deal.amount_kind || 'tranche'}</dd>
              </div>
              <div className="grid grid-cols-3 px-3 py-2">
                <dt className="text-stone-500 font-medium">ESMA Document ID</dt>
                <dd className="col-span-2 font-mono text-stone-900">{deal.doc_id || 'N/A'}</dd>
              </div>
              <div className="grid grid-cols-3 px-3 py-2">
                <dt className="text-stone-500 font-medium">Extraction Method</dt>
                <dd className="col-span-2 font-mono text-stone-900">{deal.extraction_method || 'dealer_table_regex'}</dd>
              </div>
              <div className="grid grid-cols-3 px-3 py-2">
                <dt className="text-stone-500 font-medium">Gate Status</dt>
                <dd className="col-span-2 font-mono text-stone-900">{deal.gate_status || 'published'}</dd>
              </div>
              <div className="grid grid-cols-3 px-3 py-2">
                <dt className="text-stone-500 font-medium">ESMA Publication Timestamp</dt>
                <dd className="col-span-2 font-mono text-stone-900">{formatDateTime(deal.published_at)}</dd>
              </div>
            </dl>
          </div>

          {/* Underwriters Syndicate Breakdown */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold uppercase tracking-wider text-[11px] text-stone-800">
                Underwriting Syndicate Equal Split Breakdown ({deal.n_underwriters} Dealers)
              </span>
              <span className="text-[11px] text-stone-500">
                1/{deal.n_underwriters} credit per dealer
              </span>
            </div>

            <div className="border border-stone-200 rounded-md overflow-hidden divide-y divide-stone-200">
              {deal.underwriters.map((u, i) => {
                const bankProfile = getBankClimateProfile(u.raw_name);
                return (
                  <div
                    key={i}
                    className="flex flex-col sm:flex-row sm:items-center justify-between p-2.5 bg-stone-50/50 hover:bg-stone-100 transition-colors gap-2"
                  >
                    <div>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => {
                            onClose();
                            onSelectBank?.(u.raw_name);
                          }}
                          className="font-semibold text-stone-900 hover:text-amber-800 hover:underline text-left cursor-pointer"
                        >
                          {u.raw_name}
                        </button>
                        {bankProfile?.nzbaMember && (
                          <span className="px-1.5 py-0.2 text-[10px] font-bold bg-blue-100 text-blue-800 rounded">
                            NZBA
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-stone-500">
                        <span>Role: {u.role || 'Dealer'}</span>
                        {bankProfile && (
                          <span className="text-stone-400 ml-2">
                            • Fossil Policy: <strong className="text-stone-600 font-medium">{bankProfile.oilGasPolicyRating}</strong>
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="sm:text-right">
                      <div className="font-mono font-bold text-stone-900">
                        {formatAmount(u.allocated_amount, deal.currency)}
                      </div>
                      <div className="text-[10px] font-mono text-stone-500">
                        Exact: {formatExactAmount(u.allocated_amount, deal.currency)}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Journalistic Citation Box */}
          <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-md">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-semibold text-amber-900 text-[11px] uppercase tracking-wider">
                Journalistic Citation Snippet
              </span>
              <button
                onClick={handleCopyCitation}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-900 hover:text-amber-950 bg-amber-100/80 px-2 py-0.5 rounded cursor-pointer"
              >
                {copiedCitation ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-600" />
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy Citation</span>
                  </>
                )}
              </button>
            </div>
            <p className="font-mono text-[11px] text-amber-950 leading-relaxed bg-white/80 p-2 rounded border border-amber-200/60 selection:bg-amber-200">
              {generateCitation(deal)}
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-stone-200 bg-stone-50 flex flex-wrap items-center justify-between gap-2 mt-auto">
          <div className="flex items-center gap-2">
            {prospectusUrl && (
              <a
                href={prospectusUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-stone-900 hover:bg-stone-800 rounded-md transition-colors shadow-2xs cursor-pointer"
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Prospectus PDF</span>
                <ExternalLink className="w-3.5 h-3.5 ml-0.5" />
              </a>
            )}

            {/* Story Lead Generator Trigger */}
            <button
              onClick={() => {
                onClose();
                onGeneratePitch?.(deal);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-amber-950 bg-amber-100 hover:bg-amber-200 border border-amber-300 rounded-md transition-colors cursor-pointer shadow-2xs"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-800" />
              <span>Generate News Pitch</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyJson}
              className="px-3 py-1.5 text-xs font-semibold text-stone-700 bg-white hover:bg-stone-100 border border-stone-300 rounded-md transition-colors cursor-pointer"
            >
              {copiedJson ? 'JSON Copied' : 'Copy Raw JSON'}
            </button>
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-semibold text-stone-700 bg-stone-200 hover:bg-stone-300 rounded-md transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

