import React, { useState } from 'react';
import { Deal } from '../types/deal';
import { getBankClimateProfile } from '../data/referenceData';
import { FileText, Copy, Check, X, ShieldAlert, Share2 } from 'lucide-react';
import { safeHttpUrl } from '../utils/formatters';

interface StoryGeneratorModalProps {
  deal: Deal | null;
  onClose: () => void;
}

export const StoryGeneratorModal: React.FC<StoryGeneratorModalProps> = ({ deal, onClose }) => {
  const [copiedType, setCopiedType] = useState<string | null>(null);

  if (!deal) return null;

  const trancheNum = parseFloat(deal.amount) || 0;
  const progNum = parseFloat(deal.programme_size || '0') || 0;

  const formatMoney = (val: number, curr: string) => {
    if (val >= 1e9) return `${curr} ${(val / 1e9).toFixed(2)}B`;
    if (val >= 1e6) return `${curr} ${(val / 1e6).toFixed(1)}M`;
    return `${curr} ${val.toLocaleString()}`;
  };

  const trancheStr = formatMoney(trancheNum, deal.currency);
  const progStr = progNum > 0 ? formatMoney(progNum, deal.currency) : null;
  const nDealers = deal.underwriters.length || deal.n_underwriters || 1;
  const perDealerNum = deal.allocated_amount || trancheNum / nDealers;
  const perDealerStr = formatMoney(perDealerNum, deal.currency);

  const bankProfiles = deal.underwriters.map(u => ({
    underwriter: u,
    profile: getBankClimateProfile(u.raw_name),
  }));

  const nzbaBanks = bankProfiles.filter(bp => bp.profile?.nzbaMember);
  const hasExpansion = (deal.ste_mmboe ?? 0) > 0;

  // News Lead Hook
  const headline = `${deal.issuer} Issues ${trancheStr} Bond Underwritten by ${nDealers}-Bank Syndicate${
    hasExpansion ? ` Despite ${deal.ste_mmboe?.toFixed(0)} mmboe Upstream Expansion` : ''
  }`;

  const leadParagraph = `European fossil fuel issuer **${deal.issuer}** has closed a **${trancheStr}** debt offering (ISIN: \`${deal.isin}\`)${
    deal.issue_date ? ` dated ${deal.issue_date}` : ''
  }.${
    progStr ? ` The tranche forms part of the group's broader ${progStr} multi-currency Euro Medium Term Note (EMTN) programme.` : ''
  } The deal was underwritten across an equal-credit syndicate of ${nDealers} European and global institutions, granting each participating bank approximately **${perDealerStr}** in facilitated debt credit.`;

  const climateAngle = hasExpansion
    ? `### Climate Accountability & Policy Inconsistency
According to upstream industry registers, ${deal.issuer} currently holds **${deal.ste_mmboe?.toLocaleString()} mmboe** in short-term oil and gas expansion reserves${deal.watchlist_rank ? ` (ranked #${deal.watchlist_rank} on the European fossil debt monitor)` : ''}.
${
  nzbaBanks.length > 0
    ? `Notably, **${nzbaBanks.length} of the ${nDealers} syndicate underwriters** (${nzbaBanks
        .map(b => b.profile?.bankName || b.underwriter.raw_name)
        .join(', ')}) are signatories to the UN-convened **Net-Zero Banking Alliance (NZBA)**, despite facilitating general corporate refinancing for an active fossil expansionist.`
    : ''
}`
    : `### Corporate Debt Structure
The issuance provides liquidity under ESMA Final Terms Wholesale compliance. All participating syndicate dealers carried equal credit under standard 1/n allocation rules.`;

  const syndicateMarkdown = `| Underwriter Dealer | Syndicate Role | 1/n Allocation | NZBA Signatory | Policy Rating |
| :--- | :--- | :--- | :--- | :--- |
${bankProfiles
  .map(
    bp =>
      `| ${bp.underwriter.raw_name} | ${bp.underwriter.role || 'Dealer'} | ${perDealerStr} | ${
        bp.profile?.nzbaMember ? 'Yes (NZBA)' : 'No'
      } | ${bp.profile?.oilGasPolicyRating || 'Standard'} |`
  )
  .join('\n')}`;

  const citationUrl = safeHttpUrl(deal.source_url);
  const citationText = `Source: ESMA Final Terms Wholesale filing (${deal.isin})${
    citationUrl ? ` - Prospectus URL: ${citationUrl}` : ''
  }. Data processed via PaperTrails European Fossil Bond Monitor.`;

  const fullPitch = `# ${headline}

${leadParagraph}

${climateAngle}

### Syndicate Underwriting Breakdown
${syndicateMarkdown}

---
*${citationText}*`;

  const handleCopy = (text: string, type: string) => {
    navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 overflow-y-auto bg-stone-900/60 backdrop-blur-xs flex items-center justify-center p-4 sm:p-6"
    >
      <div className="bg-white border border-stone-300 rounded-xl max-w-3xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-stone-200 bg-stone-50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-amber-100 text-amber-800 rounded-md">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold font-editorial text-base text-stone-900">
                Newsroom Pitch Template
              </h3>
              <p className="text-xs text-stone-500">
                Filing-field template only — no generative AI.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-stone-400 hover:text-stone-700 rounded-md hover:bg-stone-200 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs sm:text-sm text-stone-800">
          {/* Quick Copy Action Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-amber-50/70 border border-amber-200 rounded-lg">
            <span className="text-xs font-semibold text-amber-950 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-amber-800" />
              Journalistic Pitch Template
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleCopy(leadParagraph, 'lead')}
                className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 bg-white border border-amber-300 hover:border-amber-400 text-amber-900 rounded shadow-2xs transition-colors cursor-pointer"
              >
                {copiedType === 'lead' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                <span>Copy Lead Paragraph</span>
              </button>
              <button
                onClick={() => handleCopy(fullPitch, 'full')}
                className="inline-flex items-center gap-1 text-xs font-semibold px-3 py-1.5 bg-amber-900 hover:bg-amber-950 text-amber-50 rounded shadow-xs transition-colors cursor-pointer"
              >
                {copiedType === 'full' ? <Check className="w-3 h-3 text-amber-200" /> : <Share2 className="w-3 h-3" />}
                <span>Copy Full Markdown Pitch</span>
              </button>
            </div>
          </div>

          {/* Section 1: Headline & Lead */}
          <div className="space-y-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-stone-500">
              Suggested Story Headline
            </span>
            <div className="p-3 bg-stone-50 border border-stone-200 rounded-md font-bold font-editorial text-base text-stone-900">
              {headline}
            </div>
          </div>

          <div className="space-y-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-stone-500">
              Lead Paragraph (Factual & Sourced)
            </span>
            <div className="p-3.5 bg-stone-50 border border-stone-200 rounded-md text-stone-800 leading-relaxed font-sans">
              {leadParagraph}
            </div>
          </div>

          {/* Section 2: Climate Policy / Inconsistency Angle */}
          <div className="space-y-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-stone-500 flex items-center gap-1">
              <ShieldAlert className="w-3 h-3 text-amber-700" />
              Policy Inconsistency & Accountability Angle
            </span>
            <div className="p-3.5 bg-amber-50/40 border border-amber-200/80 rounded-md text-stone-800 space-y-2">
              {hasExpansion ? (
                <>
                  <p>
                    <strong>Upstream Expansion:</strong> {deal.issuer} holds{' '}
                    <strong className="text-amber-900">{deal.ste_mmboe?.toLocaleString()} mmboe</strong> in short-term
                    expansion assets.
                  </p>
                  {nzbaBanks.length > 0 ? (
                    <p className="text-stone-700">
                      <strong>NZBA Signatories in Syndicate ({nzbaBanks.length}):</strong>{' '}
                      {nzbaBanks.map((b, i) => (
                        <span key={i} className="inline-block mr-1.5 font-medium text-stone-900">
                          {b.profile?.bankName || b.underwriter.raw_name}
                          <span className="text-stone-400 font-normal"> ({b.profile?.oilGasPolicyRating})</span>
                          {i < nzbaBanks.length - 1 ? ',' : ''}
                        </span>
                      ))}
                    </p>
                  ) : (
                    <p className="text-stone-600">No participating banks currently have active NZBA memberships mapped.</p>
                  )}
                </>
              ) : (
                <p className="text-stone-600">This issuer does not have flagged upstream short-term exploration reserves.</p>
              )}
            </div>
          </div>

          {/* Section 3: Syndicate Table */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-stone-500">
                Syndicate Underwriting Table (1/n Equal Split)
              </span>
              <button
                onClick={() => handleCopy(syndicateMarkdown, 'table')}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-stone-600 hover:text-stone-900 hover:underline cursor-pointer"
              >
                {copiedType === 'table' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                <span>Copy Table Markdown</span>
              </button>
            </div>
            <div className="border border-stone-200 rounded-md overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-stone-100 text-stone-700 font-semibold border-b border-stone-200">
                  <tr>
                    <th className="py-2 px-3">Underwriter Bank</th>
                    <th className="py-2 px-3">Role</th>
                    <th className="py-2 px-3 text-right">1/n Credit Allocation</th>
                    <th className="py-2 px-3 text-center">NZBA Member</th>
                    <th className="py-2 px-3">Fossil Policy Rating</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200 bg-white">
                  {bankProfiles.map((bp, i) => (
                    <tr key={i} className="hover:bg-stone-50">
                      <td className="py-2 px-3 font-medium text-stone-900">{bp.underwriter.raw_name}</td>
                      <td className="py-2 px-3 text-stone-500">{bp.underwriter.role || 'Dealer'}</td>
                      <td className="py-2 px-3 text-right font-mono font-medium text-stone-900">{perDealerStr}</td>
                      <td className="py-2 px-3 text-center">
                        {bp.profile?.nzbaMember ? (
                          <span className="inline-block px-1.5 py-0.5 text-[10px] font-bold bg-blue-100 text-blue-800 rounded">
                            NZBA
                          </span>
                        ) : (
                          <span className="text-stone-400">—</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-stone-600">
                        {bp.profile?.oilGasPolicyRating || (
                          <span className="text-stone-400 italic">Standard</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 bg-stone-50 border-t border-stone-200 flex items-center justify-between text-xs text-stone-500">
          <span>ESMA Final Terms Wholesale Verified</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-stone-200 hover:bg-stone-300 text-stone-800 font-semibold rounded-md transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
