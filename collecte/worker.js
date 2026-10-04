// Naim feedback collection server — Cloudflare Worker (free plan).
//
// Receives the rated tasks that Naim users chose to share, checks them, cleans them again, applies limits and stores
// them in a PRIVATE Hugging Face dataset (one commit per batch). The HF token is a Worker secret, never in the app.
//
// Bindings (wrangler.toml): KV namespace LIMITS (daily counters, duplicates) · secret HF_TOKEN · var DATASET_REPO
// · var DATA_DIR ("data" in production, "test" for tests: the curation script only reads "data").
//
// It also gives the Naim model to Naim installations: the model repo is private, this Worker holds a read token
// (secret HF_MODEL_TOKEN) and answers each request with a short-lived signed download link. An installation can be
// blocked (secret ADMIN_TOKEN for the /api/admin routes).

const LIMIT_INSTALL = 50;   // tasks per installation per day
const LIMIT_IP = 300;       // tasks per IP address per day
const MAX_ITEM = 300000;    // bytes per task
const MAX_BATCH = 20;
const HEX32 = /^[0-9a-f]{32}$/;
const SECRETS = [
  /\b(hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|glpat-[A-Za-z0-9_-]{20,})\b/g,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g,
  /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g,
];

const MODEL_FILES = new Set(["naim-Q4_K_M.gguf", "naim-mmproj-f16.gguf", "naim-Q8_0.gguf",
  "naim_prompts.json", "llama-server-naim"]);  // llama-server-naim: Naim's engine (reads the « naim » architecture)  // Naim's instructions and tool descriptions: private, delivered like the model
const LIMIT_DL_INSTALL = 20;  // model downloads per installation per day (resumed downloads included)
const LIMIT_DL_IP = 40;

const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status, headers: { "content-type": "application/json; charset=utf-8", "access-control-allow-origin": "*" },
});
const day = () => new Date().toISOString().slice(0, 10);

function clean(v) {  // second cleaning pass (the app already cleaned)
  if (typeof v === "string") return SECRETS.reduce((s, rx) => s.replace(rx, "[RETIRÉ]"), v);
  if (Array.isArray(v)) return v.map(clean);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, clean(x)]));
  return v;
}

function check(item, install) {
  if (!item || typeof item !== "object") return "format invalide";
  if (item.install !== install) return "identifiant d'installation incohérent";
  if (![1, 0, -1].includes(item.rating)) return "note manquante";  // Bon 1 · Correct 0 · Mauvais -1
  const msgs = item.messages;
  if (!Array.isArray(msgs) || msgs.length < 2 || msgs.length > 400) return "messages invalides";
  if (!msgs.some((m) => m && m.tool_calls && m.tool_calls.length)) return "tâche sans action (rien à apprendre)";
  if (JSON.stringify(item).length > MAX_ITEM) return "tâche trop volumineuse";
  if (!item.signals || typeof item.signals !== "object") return "signaux manquants";
  return null;
}

async function sha(text) {
  const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(h)].slice(0, 8).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function b64(text) {
  const bytes = new TextEncoder().encode(text);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

async function commit(env, path, content, summary) {
  // Hugging Face commit API (NDJSON): one header line, one file line
  const body = [
    JSON.stringify({ key: "header", value: { summary } }),
    JSON.stringify({ key: "file", value: { path, content: b64(content), encoding: "base64" } }),
  ].join("\n");
  const r = await fetch(`https://huggingface.co/api/datasets/${env.DATASET_REPO}/commit/main`, {
    method: "POST", headers: { authorization: `Bearer ${env.HF_TOKEN}`, "content-type": "application/x-ndjson" }, body,
  });
  if (!r.ok) throw new Error(`Hugging Face ${r.status}: ${(await r.text()).slice(0, 200)}`);
}

async function counter(env, key) { return parseInt((await env.LIMITS.get(key)) || "0", 10); }

async function submit(request, env) {
  let body;
  try { body = await request.json(); } catch { return json({ error: "JSON invalide" }, 400); }
  const install = String(body.install || "");
  const items = body.items;
  if (!HEX32.test(install) || !Array.isArray(items) || items.length > MAX_BATCH) return json({ error: "requête invalide" }, 400);
  const ip = request.headers.get("cf-connecting-ip") || "?";
  const d = day(), ipKey = `ip:${d}:${await sha(ip + d)}`, inKey = `in:${d}:${install}`;
  let nInstall = await counter(env, inKey), nIp = await counter(env, ipKey);
  const accepted = [], rejected = [], lines = [];
  let error = null;
  for (const item of items) {
    const id = String((item && item.id) || "").slice(0, 64);
    if (nInstall >= LIMIT_INSTALL || nIp >= LIMIT_IP) { error = "limite quotidienne atteinte, réessaie demain"; break; }
    if (await env.LIMITS.get(`seen:${id}`)) { accepted.push(id); continue; }  // already stored: no duplicate
    const why = check(item, install);
    if (why) { rejected.push({ id, reason: why }); continue; }
    lines.push(JSON.stringify({ ...clean(item), received: new Date().toISOString(), ip_hash: await sha(ip + d) }));
    accepted.push(id); nInstall++; nIp++;
  }
  if (lines.length) {
    try {
      await commit(env, `${env.DATA_DIR || "data"}/submissions-${d}-${crypto.randomUUID()}.jsonl`, lines.join("\n") + "\n",
        `${lines.length} tâche(s) partagée(s)`);
    } catch (e) {
      return json({ accepted: [], rejected, error: "stockage indisponible, réessaie plus tard" }, 503);
    }
    const ttl = { expirationTtl: 60 * 60 * 48 };
    await env.LIMITS.put(inKey, String(nInstall), ttl);
    await env.LIMITS.put(ipKey, String(nIp), ttl);
    for (const id of accepted) await env.LIMITS.put(`seen:${id}`, "1", { expirationTtl: 60 * 60 * 24 * 30 });
  }
  return json({ accepted, rejected, error });
}

async function model(request, env, url) {
  // GET /api/model/<file>?install=<id> -> 302 to a short-lived signed link of the private model repo
  const name = decodeURIComponent(url.pathname.slice("/api/model/".length));
  const install = url.searchParams.get("install") || "";
  if (!MODEL_FILES.has(name)) return json({ error: "fichier inconnu" }, 404);
  if (!HEX32.test(install)) return json({ error: "installation Naim non reconnue" }, 403);
  if (!(request.headers.get("user-agent") || "").startsWith("Naim")) return json({ error: "réservé à l'application Naim" }, 403);
  if (await env.LIMITS.get(`block:${install}`)) return json({ error: "accès au modèle bloqué pour cette installation" }, 403);
  const ip = request.headers.get("cf-connecting-ip") || "?";
  const d = day(), inKey = `dl:${d}:${install}`, ipKey = `dlip:${d}:${await sha(ip + d)}`;
  const nIn = await counter(env, inKey), nIp = await counter(env, ipKey);
  if (nIn >= LIMIT_DL_INSTALL || nIp >= LIMIT_DL_IP) return json({ error: "trop de téléchargements aujourd'hui, réessaie demain" }, 429);
  const r = await fetch(`https://huggingface.co/${env.MODEL_REPO}/resolve/main/${encodeURIComponent(name)}`, {
    method: "HEAD", redirect: "manual", headers: { authorization: `Bearer ${env.HF_MODEL_TOKEN}` },
  });
  const loc = r.headers.get("location");
  let small = null;  // a small file (Naim's instructions) is served by Hugging Face directly, without a redirect
  if (r.status === 200) {
    const g = await fetch(`https://huggingface.co/${env.MODEL_REPO}/resolve/main/${encodeURIComponent(name)}`, {
      headers: { authorization: `Bearer ${env.HF_MODEL_TOKEN}` } });
    if (g.ok) small = g; else return json({ error: `fichier indisponible (${g.status})` }, 502);
  }
  if (!small && (r.status < 300 || r.status >= 400 || !loc)) return json({ error: `modèle indisponible (${r.status})` }, 502);
  const ttl = { expirationTtl: 60 * 60 * 48 };
  await env.LIMITS.put(inKey, String(nIn + 1), ttl);
  await env.LIMITS.put(ipKey, String(nIp + 1), ttl);
  const known = await env.LIMITS.getWithMetadata(`inst:${install}`);
  await env.LIMITS.put(`inst:${install}`, "1", { metadata: { first: known.metadata?.first || new Date().toISOString(), last: new Date().toISOString(), n: (known.metadata?.n || 0) + 1 } });
  if (small) return new Response(small.body, { status: 200, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
  return new Response(null, { status: 302, headers: { location: loc, "cache-control": "no-store" } });
}

async function modelVersion(env) {
  // GET /api/model-version -> the version currently given to the users ({name: "v3", date, ...}); v2 before versioning
  const r = await fetch(`https://huggingface.co/${env.MODEL_REPO}/resolve/main/naim_version.json`, {
    headers: { authorization: `Bearer ${env.HF_MODEL_TOKEN}` },
  });
  if (r.status === 404) return json({ name: "v2", version: 2 });
  if (!r.ok) return json({ error: `version indisponible (${r.status})` }, 502);
  const v = await r.json().catch(() => ({}));
  return json({ name: v.name || `v${v.version || 2}`, version: v.version || 2, date: v.date || null });
}

async function admin(request, env, url) {
  // owner only: list installations, block / unblock one
  if (!env.ADMIN_TOKEN || request.headers.get("authorization") !== `Bearer ${env.ADMIN_TOKEN}`) return json({ error: "non autorisé" }, 401);
  if (url.pathname === "/api/admin/installs") {
    const list = await env.LIMITS.list({ prefix: "inst:" });
    const out = [];
    for (const k of list.keys) {
      const id = k.name.slice(5);
      out.push({ install: id, ...(k.metadata || {}), blocked: !!(await env.LIMITS.get(`block:${id}`)) });
    }
    return json({ installs: out });
  }
  if (url.pathname === "/api/admin/block" && request.method === "POST") {
    const b = await request.json().catch(() => ({}));
    if (!HEX32.test(b.install || "")) return json({ error: "identifiant invalide" }, 400);
    if (b.blocked === false) await env.LIMITS.delete(`block:${b.install}`);
    else await env.LIMITS.put(`block:${b.install}`, new Date().toISOString());
    return json({ ok: true, install: b.install, blocked: b.blocked !== false });
  }
  return json({ error: "inconnu" }, 404);
}

async function remove(request, env) {
  let body;
  try { body = await request.json(); } catch { return json({ error: "JSON invalide" }, 400); }
  const install = String(body.install || "");
  if (!HEX32.test(install)) return json({ error: "identifiant invalide" }, 400);
  // recorded here, applied by the curation script before every training: the data is never used afterwards
  await commit(env, `${env.DATA_DIR || "data"}/deletions-${crypto.randomUUID()}.jsonl`,
    JSON.stringify({ install, time: new Date().toISOString() }) + "\n", "Demande de suppression");
  return json({ ok: true });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "content-type" } });
    if (request.method === "POST" && url.pathname === "/api/submit") return submit(request, env);
    if (request.method === "POST" && url.pathname === "/api/delete") return remove(request, env);
    if (request.method === "GET" && url.pathname === "/api/model-version") return modelVersion(env);
    if (request.method === "GET" && url.pathname.startsWith("/api/model/")) return model(request, env, url);
    if (url.pathname.startsWith("/api/admin/")) return admin(request, env, url);
    return new Response("Naim — serveur de collecte des tâches partagées (volontaires, nettoyées, anonymes). POST /api/submit, /api/delete\n",
      { headers: { "content-type": "text/plain; charset=utf-8" } });
  },
};
