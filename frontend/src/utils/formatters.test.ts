import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Deal } from '../types/deal';
import {
  allocatedTotalsByCurrency,
  formatAmount,
  formatCurrencyTotals,
  isMixedCurrency,
  maxProgrammeByIssuerCurrency,
  safeHttpUrl,
  sanitizeDeal,
  steAllocated1n,
  trancheTotalsByCurrency,
} from './formatters.ts';

function deal(partial: Partial<Deal> & Pick<Deal, 'currency' | 'amount'>): Deal {
  return {
    id: partial.id || 'x',
    issuer: partial.issuer || 'Test',
    isin: partial.isin || 'XS1',
    issue_date: partial.issue_date ?? null,
    currency: partial.currency,
    amount: partial.amount,
    underwriters: partial.underwriters || [],
    source_url: partial.source_url ?? null,
    n_underwriters: partial.n_underwriters ?? (partial.underwriters?.length || 0),
    programme_size: partial.programme_size ?? null,
    ste_mmboe: partial.ste_mmboe ?? null,
  };
}

test('does not sum RON+EUR and label the total EUR', () => {
  const rweRon = deal({
    issuer: 'RWE AG',
    isin: 'XS2743711298',
    currency: 'RON',
    amount: '500000000',
  });
  const gasunieEur = deal({
    issuer: 'NV Nederlandse Gasunie',
    currency: 'EUR',
    amount: '650000000',
  });
  const totals = trancheTotalsByCurrency([rweRon, gasunieEur]);
  assert.equal(isMixedCurrency(totals), true);
  assert.equal(totals.RON, 500_000_000);
  assert.equal(totals.EUR, 650_000_000);

  const grouped = formatCurrencyTotals(totals);
  assert.equal(grouped, '€650M · RON 500M');
  assert.equal(formatCurrencyTotals(totals, { mixedLabel: true }), 'mixed — not summed');

  const fakeEurSum = formatAmount(totals.RON + totals.EUR, 'EUR');
  assert.notEqual(grouped, fakeEurSum);
  assert.ok(!grouped.startsWith('€1'));
});

test('RWE RON 500m is not formatted as euro', () => {
  const labeled = formatAmount('500000000', 'RON');
  assert.equal(labeled, 'RON 500M');
  assert.ok(!labeled.includes('€'));
  assert.notEqual(formatAmount('500000000', 'EUR'), labeled);
});

test('same-issuer programme shelves are maxed, not summed', () => {
  const a = deal({
    issuer: 'NV Nederlandse Gasunie',
    currency: 'EUR',
    amount: '650000000',
    programme_size: '7500000000',
  });
  const b = deal({
    issuer: 'NV Nederlandse Gasunie',
    currency: 'EUR',
    amount: '500000000',
    programme_size: '7500000000',
    isin: 'XS2',
  });
  const totals = maxProgrammeByIssuerCurrency([a, b]);
  assert.equal(totals.EUR, 7_500_000_000);
  assert.notEqual(totals.EUR, 15_000_000_000);
});

test('bank STE is 1/n of deal STE, not the full figure', () => {
  const d = deal({
    currency: 'EUR',
    amount: '1000000000',
    ste_mmboe: 100,
    n_underwriters: 4,
    underwriters: [
      { raw_name: 'A', role: 'Dealer', allocated_amount: 250000000 },
      { raw_name: 'B', role: 'Dealer', allocated_amount: 250000000 },
      { raw_name: 'C', role: 'Dealer', allocated_amount: 250000000 },
      { raw_name: 'D', role: 'Dealer', allocated_amount: 250000000 },
    ],
  });
  assert.equal(steAllocated1n(d), 25);
});

test('allocated totals stay in the deal currency', () => {
  const d = deal({
    currency: 'RON',
    amount: '500000000',
    n_underwriters: 1,
    underwriters: [{ raw_name: 'SMBC Bank EU AG', role: 'Dealer', allocated_amount: 500000000 }],
  });
  const totals = allocatedTotalsByCurrency([d], 'SMBC Bank EU AG');
  assert.equal(formatCurrencyTotals(totals), 'RON 500M');
  assert.ok(!formatCurrencyTotals(totals).includes('€'));
});

test('safeHttpUrl allows http(s) and rejects javascript/data', () => {
  assert.equal(
    safeHttpUrl('https://registers.esma.europa.eu/publication/downloadFile?fileId=1'),
    'https://registers.esma.europa.eu/publication/downloadFile?fileId=1'
  );
  assert.equal(safeHttpUrl('javascript:alert(1)'), null);
  assert.equal(safeHttpUrl('data:text/html,hi'), null);
  assert.equal(safeHttpUrl('/relative'), null);
  assert.equal(safeHttpUrl(null), null);
});

test('sanitizeDeal strips pdf_path', () => {
  const dirty = {
    ...deal({ currency: 'EUR', amount: '1' }),
    pdf_path: 'C:/Users/secret/filing.pdf',
  } as Deal & { pdf_path: string };
  const clean = sanitizeDeal(dirty);
  assert.equal('pdf_path' in clean, false);
});
