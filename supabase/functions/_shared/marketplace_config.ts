// Amazon SP-API marketplace IDs → regional endpoint hostnames.
// Source: https://developer-docs.amazon.com/sp-api/docs/marketplace-ids

export const MARKETPLACE_REGION_MAP: Record<string, string> = {
  // North America
  "ATVPDKIKX0DER":  "sellingpartnerapi-na.amazon.com",   // US
  "A2EUQ1WTGCTBG2": "sellingpartnerapi-na.amazon.com",   // CA
  "A1AM78C64UM0Y8": "sellingpartnerapi-na.amazon.com",   // MX
  "A2Q3Y263D00KWC": "sellingpartnerapi-na.amazon.com",   // BR

  // Europe / Middle East / Africa
  "A1F83G8C2ARO7P": "sellingpartnerapi-eu.amazon.com",   // UK
  "A1PA6795UKMFR9": "sellingpartnerapi-eu.amazon.com",   // DE
  "A13V1IB3VIYZZH": "sellingpartnerapi-eu.amazon.com",   // FR
  "APJ6JRA9NG5V4":  "sellingpartnerapi-eu.amazon.com",   // IT
  "A1RKKUPIHCS9HS": "sellingpartnerapi-eu.amazon.com",   // ES
  "A1805IZSGTT6HS": "sellingpartnerapi-eu.amazon.com",   // NL
  "A2NODRKZP88ZB9": "sellingpartnerapi-eu.amazon.com",   // SE
  "A1C3SOZRARQ6R3": "sellingpartnerapi-eu.amazon.com",   // PL
  "ARBP9OOSHTCHU":  "sellingpartnerapi-eu.amazon.com",   // EG
  "A33AVAJ2PDY3EV": "sellingpartnerapi-eu.amazon.com",   // TR
  "A17E79C6D8DWNP": "sellingpartnerapi-eu.amazon.com",   // KSA
  "A2VIGQ35RCS4UG": "sellingpartnerapi-eu.amazon.com",   // UAE
  "A21TJRUUN4KGV":  "sellingpartnerapi-eu.amazon.com",   // IN
  "AMEN7PMS3EDWL":  "sellingpartnerapi-eu.amazon.com",   // BE
  "AE08WJ6YKNBMC":  "sellingpartnerapi-eu.amazon.com",   // ZA

  // Far East
  "A1VC38T7YXB528": "sellingpartnerapi-fe.amazon.com",   // JP
  "A39IBJ37TRP1C6": "sellingpartnerapi-fe.amazon.com",   // AU
  "A19VAU5U5O7RUS": "sellingpartnerapi-fe.amazon.com",   // SG
};

export function getRegionEndpoint(marketplaceId: string): string {
  const endpoint = MARKETPLACE_REGION_MAP[marketplaceId];
  if (!endpoint) {
    throw new Error(
      `Unknown marketplace_id: ${marketplaceId}. ` +
      `Known marketplaces: ${Object.keys(MARKETPLACE_REGION_MAP).join(", ")}`
    );
  }
  return endpoint;
}
