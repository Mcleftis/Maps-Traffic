/**
 * Relay αναφορών κίνησης μεταξύ συσκευών — Cloudflare Worker (δωρεάν πλάνο).
 *
 * Το κινητό ΜΕ Viber ("αποστολέας") ανεβάζει τις αναφορές που διάβασε από τις
 * ομάδες· τα υπόλοιπα κινητά ("παραλήπτες", ακόμα κι αν δεν έχουν Viber) τις
 * κατεβάζουν και τις δείχνουν στον χάρτη.
 *
 * API
 *   POST /   (header x-key: ΤΟ_ΚΛΕΙΔΙ_ΣΟΥ)  body: [{id,t,g,m,lat,lon,ico,label}]
 *   GET  /?key=ΤΟ_ΚΛΕΙΔΙ_ΣΟΥ               -> {items:[...]}
 *
 * Ρύθμιση στο Cloudflare (μία φορά):
 *   1) Workers & Pages -> Create -> Worker  (επικόλλησε αυτόν τον κώδικα)
 *   2) Storage & Databases -> KV -> Create namespace, π.χ. ALERTS
 *   3) Στον Worker: Settings -> Bindings -> KV namespace,
 *      Variable name: ALERTS  ->  διάλεξε το namespace
 *   4) Settings -> Variables -> Secret: SHARED_KEY = ένα δικό σου μυστικό
 */

const MAX_AGE_MS = 6 * 3600 * 1000;   // κρατά 6 ώρες ιστορικό
const MAX_ITEMS = 200;
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Content-Type, x-key",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    const url = new URL(request.url);
    const key = request.headers.get("x-key") || url.searchParams.get("key") || "";
    if (!env.SHARED_KEY || key !== env.SHARED_KEY) {
      return new Response(JSON.stringify({ error: "forbidden" }),
        { status: 403, headers: { ...CORS, "Content-Type": "application/json" } });
    }

    const now = Date.now();
    let items = [];
    try {
      items = JSON.parse((await env.ALERTS.get("items")) || "[]");
    } catch (e) {
      items = [];
    }
    // Πέτα ό,τι έχει παλιώσει.
    items = items.filter(a => a && typeof a.t === "number" && now - a.t <= MAX_AGE_MS);

    if (request.method === "POST") {
      let incoming = [];
      try { incoming = await request.json(); } catch (e) { incoming = []; }
      if (!Array.isArray(incoming)) incoming = [];

      const seen = new Set(items.map(a => a.id));
      let added = 0;
      for (const a of incoming) {
        if (!a || !a.id || seen.has(a.id)) continue;
        if (typeof a.lat !== "number" || typeof a.lon !== "number") continue;
        seen.add(a.id);
        items.push({
          id: String(a.id).slice(0, 120),
          t: typeof a.t === "number" ? a.t : now,
          g: String(a.g || "").slice(0, 80),
          m: String(a.m || "").slice(0, 300),
          lat: a.lat, lon: a.lon,
          ico: String(a.ico || "⚠️").slice(0, 8),
          label: String(a.label || "").slice(0, 40),
        });
        added++;
      }
      // Γράφουμε ΜΟΝΟ όταν όντως προστέθηκε κάτι (όριο δωρεάν πλάνου).
      if (added > 0) {
        items = items.slice(-MAX_ITEMS);
        await env.ALERTS.put("items", JSON.stringify(items));
      }
      return new Response(JSON.stringify({ ok: true, added, total: items.length }),
        { headers: { ...CORS, "Content-Type": "application/json" } });
    }

    return new Response(JSON.stringify({ items }),
      { headers: { ...CORS, "Content-Type": "application/json" } });
  },
};
