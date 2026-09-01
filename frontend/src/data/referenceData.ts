export interface BankClimateProfile {
  bankName: string;
  matchedNames: string[];
  nzbaMember: boolean;
  nzbaJoinedYear?: number;
  oilGasPolicyRating: 'Strict Exclusion' | 'Phase-out Policy' | 'Partial Restrictions' | 'No Meaningful Restrictions';
  expansionPolicyExemption: string;
  headquarters: string;
}

export interface ParentEntityMapping {
  issuerName: string;
  parentName: string;
  ultimateBeneficialOwner: string;
  country: string;
  fossilSubsector: string;
  transitionScore?: string;
}

export const BANK_CLIMATE_REGISTRY: Record<string, BankClimateProfile> = {
  'barclays': {
    bankName: 'Barclays Bank',
    matchedNames: ['Barclays Bank Ireland PLC', 'Barclays Bank PLC', 'Barclays'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Restricts direct project finance for new oil/gas fields, but continues general corporate underwriting for pure-play expansionists.',
    headquarters: 'United Kingdom',
  },
  'bnp_paribas': {
    bankName: 'BNP Paribas',
    matchedNames: ['BNP Paribas', 'BNP Paribas Fortis'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'Committed to no dedicated oil/gas exploration finance, but syndicates general corporate debt for diversified energy majors.',
    headquarters: 'France',
  },
  'societe_generale': {
    bankName: 'Société Générale',
    matchedNames: ['Société Générale', 'Societe Generale', 'Société Générale S.A.'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Ends dedicated upstream exploration loans; general corporate bond syndication remains active for European utilities and majors.',
    headquarters: 'France',
  },
  'hsbc': {
    bankName: 'HSBC Continental Europe',
    matchedNames: ['HSBC Continental Europe', 'HSBC Bank plc', 'HSBC'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Excluded direct financing of new oil and gas fields in Dec 2022; corporate facilities and bond underwriting exempt.',
    headquarters: 'United Kingdom',
  },
  'unicredit': {
    bankName: 'UniCredit Bank',
    matchedNames: ['UniCredit Bank GmbH', 'UniCredit Bank AG', 'UniCredit'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Excludes Arctic and oil sands finance; standard corporate debt syndications permitted.',
    headquarters: 'Italy / Germany',
  },
  'deutsche_bank': {
    bankName: 'Deutsche Bank',
    matchedNames: ['Deutsche Bank Aktiengesellschaft', 'Deutsche Bank AG', 'Deutsche Bank'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Limits pure-play exploration advisory, but active in large-scale corporate bond underwriting.',
    headquarters: 'Germany',
  },
  'credit_agricole': {
    bankName: 'Crédit Agricole CIB',
    matchedNames: ['Crédit Agricole Corporate and Investment Bank', 'Credit Agricole'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'No direct financing of new extraction projects; continues syndicate dealer activity for European utilities.',
    headquarters: 'France',
  },
  'intesa_sanpaolo': {
    bankName: 'Intesa Sanpaolo',
    matchedNames: ['Intesa Sanpaolo', 'Intesa Sanpaolo S.p.A.'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Coal exit by 2025; ongoing corporate bond syndication for Mediterranean fossil gas & power entities.',
    headquarters: 'Italy',
  },
  'smbc': {
    bankName: 'SMBC Bank EU AG',
    matchedNames: ['SMBC Bank EU AG', 'SMBC Nikko', 'Sumitomo Mitsui Banking Corporation'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Restrictions apply to direct Arctic and oil sands; corporate syndicate underwriting permitted.',
    headquarters: 'Japan / EU',
  },
  'rabobank': {
    bankName: 'Rabobank',
    matchedNames: ['Coöperatieve Rabobank U.A.', 'Rabobank'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'Strict focus on agriculture & energy transition; active in national gas grid and utility syndication.',
    headquarters: 'Netherlands',
  },
  'natwest': {
    bankName: 'NatWest Markets',
    matchedNames: ['NatWest Markets N.V.', 'NatWest Markets Plc', 'NatWest'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'Ceasing reserve-based lending for new oil/gas; selective corporate underwriting for infrastructure.',
    headquarters: 'United Kingdom',
  },
  'ing': {
    bankName: 'ING Bank',
    matchedNames: ['ING Bank N.V.', 'ING'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'Ending upstream oil & gas financing by 2040; phasing down corporate underwriting portfolios.',
    headquarters: 'Netherlands',
  },
  'bofa': {
    bankName: 'BofA Securities',
    matchedNames: ['BofA Securities Europe SA', 'Bank of America'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'No Meaningful Restrictions',
    expansionPolicyExemption: 'Financing subject to client transition plans; active across global and European corporate debt tranches.',
    headquarters: 'United States',
  },
  'goldman_sachs': {
    bankName: 'Goldman Sachs',
    matchedNames: ['Goldman Sachs Bank Europe SE', 'Goldman Sachs'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'No Meaningful Restrictions',
    expansionPolicyExemption: 'Arctic and thermal coal direct exclusions; general corporate underwriting without upstream caps.',
    headquarters: 'United States',
  },
  'nordea': {
    bankName: 'Nordea Bank',
    matchedNames: ['Nordea Bank Abp', 'Nordea'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'Targeting 40-50% emissions reduction by 2030 across lending and underwriting books.',
    headquarters: 'Finland / Nordics',
  },
  'abn_amro': {
    bankName: 'ABN AMRO Bank',
    matchedNames: ['ABN AMRO Bank N.V.', 'ABN AMRO'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'Phasing out all fossil fuel exploration and production financing by 2030.',
    headquarters: 'Netherlands',
  },
  'erste_group': {
    bankName: 'Erste Group Bank',
    matchedNames: ['Erste Group Bank AG', 'Erste Group'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Thermal coal phase-out by 2030; Central & Eastern European sovereign/corporate debt leader.',
    headquarters: 'Austria',
  },
  'natixis': {
    bankName: 'Natixis',
    matchedNames: ['Natixis', 'Natixis Corporate & Investment Banking'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'Ends direct exploration funding; applies Green Weighting Factor to all corporate syndicated tranches.',
    headquarters: 'France',
  },
  'commerzbank': {
    bankName: 'Commerzbank',
    matchedNames: ['Commerzbank Aktiengesellschaft', 'Commerzbank AG', 'Commerzbank'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Coal and oil sands restrictions; ongoing European corporate syndicate participation.',
    headquarters: 'Germany',
  },
  'mufg': {
    bankName: 'MUFG Securities',
    matchedNames: ['MUFG Securities (Europe) N.V.', 'Mitsubishi UFJ Financial Group', 'MUFG'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Targets portfolio decarbonisation; active syndicate bookrunner across European corporate bonds.',
    headquarters: 'Japan / EU',
  },
  'santander': {
    bankName: 'Banco Santander',
    matchedNames: ['Banco Santander, S.A.', 'Banco Santander', 'Santander'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Ending financing for clients with >10% thermal coal revenue by 2030; corporate energy tranches active.',
    headquarters: 'Spain',
  },
  'cic': {
    bankName: 'Crédit Industriel et Commercial',
    matchedNames: ['Crédit Industriel et Commercial S.A.', 'CIC'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'Strict adherence to Crédit Mutuel Alliance Fédérale fossil exit framework.',
    headquarters: 'France',
  },
  'raiffeisen': {
    bankName: 'Raiffeisen Bank International',
    matchedNames: ['Raiffeisen Bank International AG', 'RBI'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Partial Restrictions',
    expansionPolicyExemption: 'Regional energy security commitments in CEE/SEE region with selective coal restrictions.',
    headquarters: 'Austria',
  },
  'seb': {
    bankName: 'SEB',
    matchedNames: ['Skandinaviska Enskilda Banken AB (publ)', 'SEB'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'Phase-out Policy',
    expansionPolicyExemption: 'Strict fossil sector policy capping credit exposure and ending exploration finance.',
    headquarters: 'Sweden',
  },
  'wells_fargo': {
    bankName: 'Wells Fargo',
    matchedNames: ['Wells Fargo Securities Europe S.A.', 'Wells Fargo'],
    nzbaMember: true,
    nzbaJoinedYear: 2021,
    oilGasPolicyRating: 'No Meaningful Restrictions',
    expansionPolicyExemption: 'No corporate bond underwriting restrictions on upstream oil and gas developers.',
    headquarters: 'United States',
  },
};

/**
 * Unofficial overlay — NOT the ESMA feed and NOT GOGEL. Invented parent/UBO
 * rows must not be shown as fact. UI hides this overlay.
 */
export const PARENT_ENTITY_REGISTRY: Record<string, ParentEntityMapping> = {
  'TotalEnergies SE': {
    issuerName: 'TotalEnergies SE',
    parentName: 'TotalEnergies SE',
    ultimateBeneficialOwner: 'Public / Institutional Shareholders (BlackRock, Amundi, Employees)',
    country: 'France',
    fossilSubsector: 'Integrated Supermajor (Upstream & LNG)',
  },
  'Eni SpA': {
    issuerName: 'Eni SpA',
    parentName: 'Eni S.p.A.',
    ultimateBeneficialOwner: 'Italian Ministry of Economy and Finance & Cassa Depositi e Prestiti (30.5%)',
    country: 'Italy',
    fossilSubsector: 'Integrated Oil & Gas (Upstream Expansion)',
  },
  'Aker BP ASA': {
    issuerName: 'Aker BP ASA',
    parentName: 'Aker ASA / BP plc Joint Venture',
    ultimateBeneficialOwner: 'Aker ASA (Kjell Inge Røkke) & BP p.l.c.',
    country: 'Norway',
    fossilSubsector: 'Pure-play Upstream Oil & Gas (North Sea / Barents)',
  },
  'ORLEN SA': {
    issuerName: 'ORLEN SA',
    parentName: 'ORLEN S.A.',
    ultimateBeneficialOwner: 'State Treasury of the Republic of Poland (49.9%)',
    country: 'Poland',
    fossilSubsector: 'Refining, Upstream Exploration & Petrochemicals',
  },
  'OMV AG': {
    issuerName: 'OMV AG',
    parentName: 'OMV Aktiengesellschaft',
    ultimateBeneficialOwner: 'ÖBAG (Austrian State 31.5%) & ADNOC/Mubadala (24.9%)',
    country: 'Austria',
    fossilSubsector: 'Oil, Gas & Chemicals (Neptun Deep Black Sea Gas)',
  },
  'EP Investment Sarl': {
    issuerName: 'EP Investment Sarl',
    parentName: 'Energetický a průmyslový holding, a.s. (EPH)',
    ultimateBeneficialOwner: 'Daniel Křetínský (EP Corporate Group)',
    country: 'Czech Republic / Luxembourg',
    fossilSubsector: 'Fossil Gas, Coal & Thermal Generation Fleet',
  },
  'Vier Gas Holdings Sarl': {
    issuerName: 'Vier Gas Holdings Sarl',
    parentName: 'Open Grid Europe (OGE) Holding Consortium',
    ultimateBeneficialOwner: 'Macquarie, Infinity Investments (ADIA), British Columbia IMC, MEAG',
    country: 'Germany / Luxembourg',
    fossilSubsector: 'Fossil Gas Transmission Network (Germany 12,000 km)',
  },
  'NV Nederlandse Gasunie': {
    issuerName: 'NV Nederlandse Gasunie',
    parentName: 'Gasunie',
    ultimateBeneficialOwner: 'State of the Netherlands (Ministry of Finance 100%)',
    country: 'Netherlands',
    fossilSubsector: 'Fossil Gas & Hydrogen Grid Infrastructure',
  },
  'Engie SA': {
    issuerName: 'Engie SA',
    parentName: 'Engie S.A.',
    ultimateBeneficialOwner: 'French Republic (23.6% voting power)',
    country: 'France',
    fossilSubsector: 'Fossil Gas Infrastructure, Thermal Generation & Renewables',
  },
  'Enel SpA': {
    issuerName: 'Enel SpA',
    parentName: 'Enel S.p.A.',
    ultimateBeneficialOwner: 'Italian Ministry of Economy and Finance (23.6%)',
    country: 'Italy',
    fossilSubsector: 'Electric Utility & Gas Distribution',
  },
  'Snam SpA': {
    issuerName: 'Snam SpA',
    parentName: 'Snam S.p.A.',
    ultimateBeneficialOwner: 'CDP Reti SpA (State-backed 31.4%) & State Grid Corporation of China',
    country: 'Italy',
    fossilSubsector: 'Fossil Gas Transmission & LNG Regasification Storage',
  },
  'CEZ a.s.': {
    issuerName: 'CEZ a.s.',
    parentName: 'ČEZ Group',
    ultimateBeneficialOwner: 'Ministry of Finance of the Czech Republic (69.8%)',
    country: 'Czech Republic',
    fossilSubsector: 'Power Generation (Gas, Coal & Nuclear)',
  },
  'SNGN Romgaz SA': {
    issuerName: 'SNGN Romgaz SA',
    parentName: 'S.N.G.N. Romgaz S.A.',
    ultimateBeneficialOwner: 'Romanian State via Ministry of Energy (70.0%)',
    country: 'Romania',
    fossilSubsector: 'Upstream Natural Gas Producer (Neptun Deep Partner)',
  },
  'Enagas SA': {
    issuerName: 'Enagas SA',
    parentName: 'Enagás S.A.',
    ultimateBeneficialOwner: 'Sociedad Estatal de Participaciones Industriales - SEPI (5%) & Free Float',
    country: 'Spain',
    fossilSubsector: 'Natural Gas Transmission System Operator (TSO)',
  },
  'Iren SpA': {
    issuerName: 'Iren SpA',
    parentName: 'Iren S.p.A.',
    ultimateBeneficialOwner: 'Italian Municipalities (Turin, Genoa, Reggio Emilia, Parma)',
    country: 'Italy',
    fossilSubsector: 'Multi-utility & Gas Distribution',
  },
  'RWE AG': {
    issuerName: 'RWE AG',
    parentName: 'RWE Aktiengesellschaft',
    ultimateBeneficialOwner: 'QIA (Qatar Investment Authority 9%) & Institutional Investors',
    country: 'Germany',
    fossilSubsector: 'Power Generation (Gas, Lignite & Renewables)',
  },
  'Veolia Environnement SA': {
    issuerName: 'Veolia Environnement SA',
    parentName: 'Veolia Environnement S.A.',
    ultimateBeneficialOwner: 'Institutional & Retail Investors (Caisse des Dépôts)',
    country: 'France',
    fossilSubsector: 'District Heating, Waste & Resource Management',
  },
  'Electricity Supply Board (ESB)': {
    issuerName: 'Electricity Supply Board (ESB)',
    parentName: 'Electricity Supply Board',
    ultimateBeneficialOwner: 'Government of Ireland (95%) & ESB Employee Share Trust (5%)',
    country: 'Ireland',
    fossilSubsector: 'Gas-fired Generation & Grid Infrastructure',
  },
};

/**
 * Match a raw bank name from ESMA filings to our Climate Profile Registry
 */
export function getBankClimateProfile(rawBankName: string): BankClimateProfile | null {
  const norm = rawBankName.toLowerCase().trim();
  for (const key in BANK_CLIMATE_REGISTRY) {
    const profile = BANK_CLIMATE_REGISTRY[key];
    if (profile.matchedNames.some(m => norm.includes(m.toLowerCase()) || m.toLowerCase().includes(norm))) {
      return profile;
    }
  }
  return null;
}

/**
 * Overlay is hidden. Do not print "subsidiary of" from this unofficial map.
 */
export function getParentEntityInfo(_issuerName: string): ParentEntityMapping | null {
  return null;
}
