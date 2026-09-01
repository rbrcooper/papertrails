export interface Underwriter {
  raw_name: string;
  role: string;
  allocated_amount: number;
}

export interface Deal {
  id: string;
  issuer: string;
  isin: string;
  issue_date: string | null;
  maturity_date?: string | null;
  tenor_years?: number | null;
  currency: string;
  amount: string;
  underwriters: Underwriter[];
  source_url: string | null;
  extracted_at?: string;
  published_at?: string;
  gate_status?: string;
  doc_id?: string | null;
  ste_mmboe?: number | null;
  watchlist_rank?: number | null;
  extraction_method?: string;
  n_underwriters: number;
  doc_type_code?: string | null;
  amount_kind?: string;
  programme_size?: string | null;
  allocated_amount?: number;
  use_of_proceeds?: string;
  bond_type?: 'conventional' | 'green' | 'sustainability_linked' | 'transition';
  parent_company?: string;
  beneficial_owner?: string;
}

export interface DealsData {
  updated_at: string;
  deals: Deal[];
}

export interface FilterState {
  search: string;
  selectedUnderwriter: string;
  selectedIssuer: string;
  selectedCurrency: string;
  expansionOnly: boolean; // STE > 0
  pledgeMismatchOnly: boolean; // NZBA members financing STE > 0
  yearFilter: string;
  sortBy: 'date_desc' | 'date_asc' | 'amount_desc' | 'amount_asc' | 'programme_desc' | 'ste_desc' | 'underwriters_desc';
}

export interface BankExposure {
  bankName: string;
  allocatedByCurrency: Record<string, number>;
  dealCount: number;
  deals: Deal[];
  issuers: Set<string>;
  totalSteSupported: number;
}

export interface IssuerExposure {
  issuerName: string;
  trancheByCurrency: Record<string, number>;
  programmeByCurrency: Record<string, number>;
  deals: Deal[];
  ste_mmboe: number;
  watchlist_rank: number | null;
  dealCount: number;
  underwriters: Set<string>;
}
