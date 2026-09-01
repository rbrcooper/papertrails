import React from 'react';
import { X, BookOpen, ShieldCheck, Scale, AlertTriangle, FileCheck } from 'lucide-react';

interface MethodologyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MethodologyModal: React.FC<MethodologyModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
      <div
        className="bg-white rounded-lg border border-stone-200 shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        <div className="p-4 sm:p-5 border-b border-stone-200 flex items-center justify-between sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-amber-700" />
            <h2 className="text-xl font-bold text-stone-900 font-editorial">
              Regulatory Data Methodology & Standards
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-stone-400 hover:text-stone-700 p-1.5 rounded-md hover:bg-stone-100 transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 sm:p-6 space-y-4 text-xs text-stone-700 leading-relaxed font-sans">
          {/* Section 1 */}
          <div className="p-3.5 bg-stone-50 border border-stone-200 rounded-md">
            <div className="flex items-center gap-2 font-bold text-stone-900 text-sm mb-1.5 font-editorial">
              <FileCheck className="w-4 h-4 text-emerald-600" />
              <span>1. Data Provenance (ESMA Final Terms)</span>
            </div>
            <p>
              All debt issuance records are retrieved from official European Securities and Markets Authority (ESMA) prospectus filings under the Prospectus Regulation (EU) 2017/1129. Filings classified under <strong>FTWS</strong> (Final Terms Wholesale) disclose legally binding parameters of debt tranches issued by corporations active in fossil fuel extraction, refining, or transmission.
            </p>
          </div>

          {/* Section 2 */}
          <div className="p-3.5 bg-stone-50 border border-stone-200 rounded-md">
            <div className="flex items-center gap-2 font-bold text-stone-900 text-sm mb-1.5 font-editorial">
              <Scale className="w-4 h-4 text-amber-700" />
              <span>2. 1/n Equal Credit Allocation Rule</span>
            </div>
            <p>
              In European bond syndication, public Final Terms filings list the authorised syndicate dealers and managers without disclosing private internal underwriting fee splits or proprietary retention shares. To maintain rigorous investigative integrity without double-counting volume:
            </p>
            <ul className="list-disc list-inside mt-2 space-y-1 text-stone-800 font-mono text-[11px]">
              <li>Allocated Credit = Nominal Issued Tranche ÷ Total Syndicate Dealers (n)</li>
              <li>No bank is granted 100% full credit for multi-dealer syndicate tranches</li>
              <li>Cumulative market volume strictly equals the actual sum of issued tranches</li>
            </ul>
          </div>

          {/* Section 3 */}
          <div className="p-3.5 bg-stone-50 border border-stone-200 rounded-md">
            <div className="flex items-center gap-2 font-bold text-stone-900 text-sm mb-1.5 font-editorial">
              <ShieldCheck className="w-4 h-4 text-blue-600" />
              <span>3. Tranche Size vs. Programme Shelf Capacity</span>
            </div>
            <p>
              A fundamental distinction in debt capital markets is preserved throughout PaperTrails:
            </p>
            <ul className="list-disc list-inside mt-2 space-y-1 text-stone-800">
              <li>
                <strong>Issued Tranche (Big Headline Number):</strong> The actual fresh debt capital drawn down and underwritten on the issue date (e.g. €1.50B).
              </li>
              <li>
                <strong>Programme Size (Secondary Line):</strong> The total multi-year shelf facility umbrella established by the issuer (e.g. €40.0B). Programme headroom is never added into market volume totals. The same programme on multiple ISINs is not summed.
              </li>
              <li>
                <strong>No FX conversion:</strong> Tranches in different currencies (e.g. RON and EUR) are listed separately. They are never summed and labelled as euro.
              </li>
            </ul>
          </div>

          {/* Section 4 */}
          <div className="p-3.5 bg-amber-50/70 border border-amber-200 rounded-md">
            <div className="flex items-center gap-2 font-bold text-amber-950 text-sm mb-1.5 font-editorial">
              <AlertTriangle className="w-4 h-4 text-amber-700" />
              <span>4. Short-Term Upstream Expansion (STE mmboe)</span>
            </div>
            <p className="text-amber-900">
              The <strong>STE (Short-Term Expansion)</strong> metric measures fossil fuel companies' short-term expansion reserves in million barrels of oil equivalent (mmboe) currently in development or planned for capital allocation, tracking underwriting alignment with Paris Agreement 1.5°C carbon budgets.
            </p>
          </div>
        </div>

        <div className="p-4 border-t border-stone-200 bg-stone-50 flex justify-end mt-auto">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-white bg-stone-900 hover:bg-stone-800 rounded-md transition-colors cursor-pointer"
          >
            Understood
          </button>
        </div>
      </div>
    </div>
  );
};
