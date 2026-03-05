import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { MARKETPLACE_REGION_MAP } from "../_shared/marketplace_config.ts";

const AMAZON_TOKEN_URL = "https://api.amazon.com/auth/o2/token";
const STREAMLIT_APP_URL = "https://saddl-adpulsev2.streamlit.app";

// Regional SP-API endpoints to probe for marketplace discovery, in priority order.
const REGION_ENDPOINTS = [
  "sellingpartnerapi-eu.amazon.com",
  "sellingpartnerapi-na.amazon.com",
  "sellingpartnerapi-fe.amazon.com",
];

serve(async (req) => {
  const url = new URL(req.url);
  const code = url.searchParams.get("spapi_oauth_code");
  const state = url.searchParams.get("state"); // this will be the client_id
  const error = url.searchParams.get("error");

  // Handle Amazon returning an error
  if (error) {
    return Response.redirect(`${STREAMLIT_APP_URL}?amazon_auth=failed&reason=${error}`);
  }

  if (!code || !state) {
    return new Response("Missing code or state parameter", { status: 400 });
  }

  // Exchange auth code for refresh token
  const tokenResponse = await fetch(AMAZON_TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code: code,
      redirect_uri: "https://wuakeiwxkjvhsnmkzywz.supabase.co/functions/v1/amazon-oauth-callback",
      client_id: Deno.env.get("LWA_CLIENT_ID")!,
      client_secret: Deno.env.get("LWA_CLIENT_SECRET")!,
    }),
  });

  if (!tokenResponse.ok) {
    const err = await tokenResponse.text();
    console.error("Token exchange failed:", err);
    return Response.redirect(`${STREAMLIT_APP_URL}?amazon_auth=failed&reason=token_exchange`);
  }

  const tokens = await tokenResponse.json();
  const refreshToken = tokens.refresh_token;
  const accessToken = tokens.access_token;

  // Discover which marketplace this seller authorized by calling
  // marketplaceParticipations. Try each regional endpoint in order
  // (EU first, then NA, then FE) and use the first successful response.
  let marketplaceId: string | null = null;
  let regionEndpoint: string | null = null;

  for (const endpoint of REGION_ENDPOINTS) {
    try {
      const mpResponse = await fetch(
        `https://${endpoint}/sellers/v1/marketplaceParticipations`,
        {
          headers: {
            "x-amz-access-token": accessToken,
            "Content-Type": "application/json",
          },
        }
      );

      if (mpResponse.ok) {
        const mpData = await mpResponse.json();
        const participations: any[] = mpData.payload || [];

        if (participations.length > 0) {
          marketplaceId = participations[0].marketplace.id;
          regionEndpoint = endpoint;

          console.log(
            "Marketplace participations discovered:",
            participations.map((p: any) => ({
              id: p.marketplace.id,
              name: p.marketplace.name,
              country: p.marketplace.countryCode,
            }))
          );
          break;
        }
      } else if (mpResponse.status === 403) {
        // Wrong region — try next
        console.log(`MarketplaceParticipations: 403 on ${endpoint}, trying next region`);
        continue;
      } else {
        console.error(
          `MarketplaceParticipations unexpected status ${mpResponse.status} on ${endpoint}`
        );
      }
    } catch (err) {
      console.error(`MarketplaceParticipations fetch failed on ${endpoint}:`, err);
    }
  }

  if (!marketplaceId) {
    console.warn(
      "MarketplaceParticipations: could not determine marketplace across all regions. " +
      "Storing token with status=needs_marketplace_config."
    );
  } else {
    // Validate discovered marketplace ID is in our known mapping
    if (!MARKETPLACE_REGION_MAP[marketplaceId]) {
      console.warn(
        `Discovered marketplace_id ${marketplaceId} is not in MARKETPLACE_REGION_MAP — ` +
        "storing it anyway but region lookup may fail."
      );
    }
  }

  // Store in Supabase
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  const { error: dbError } = await supabase
    .from("client_settings")
    .upsert({
      client_id: state,
      lwa_refresh_token: refreshToken,
      marketplace_id: marketplaceId,
      region_endpoint: regionEndpoint,
      onboarding_status: marketplaceId ? "connected" : "needs_marketplace_config",
      updated_at: new Date().toISOString(),
    }, { onConflict: "client_id" });

  if (dbError) {
    console.error("DB write failed:", dbError);
    return Response.redirect(`${STREAMLIT_APP_URL}?amazon_auth=failed&reason=db_error`);
  }

  // Success — send them back to Streamlit
  return Response.redirect(`${STREAMLIT_APP_URL}?amazon_auth=success&client_id=${state}`);
});
