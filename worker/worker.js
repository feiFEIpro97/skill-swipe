// SkillSwipe stats API — Cloudflare Worker + D1
// 部署: wrangler deploy
// 路由:
//   POST /swipe   {clientId, skillId, action:"like|skip"}  -> {ok:true}
//   GET  /stats                       -> {skillId:{like,skip}, ...}
//   GET  /stats?skillId=xxx           -> {like,skip}
//   GET  /me?clientId=xxx             -> [{skillId,action,ts}, ...]

const HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: HEADERS });
    }

    // 上报一次滑动
    if (url.pathname === "/swipe" && request.method === "POST") {
      try {
        const { clientId, skillId, action } = await request.json();
        if (!clientId || !skillId || !["like", "skip"].includes(action)) {
          return new Response(JSON.stringify({ error: "bad params" }), { status: 400, headers: HEADERS });
        }
        await env.DB.prepare(
          "INSERT INTO swipes (client_id, skill_id, action, ts) VALUES (?,?,?,?)"
        ).bind(clientId, skillId, action, Date.now()).run();
        return new Response(JSON.stringify({ ok: true }), { headers: HEADERS });
      } catch (e) {
        return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: HEADERS });
      }
    }

    // 聚合统计
    if (url.pathname === "/stats" && request.method === "GET") {
      try {
        const { results } = await env.DB.prepare(
          "SELECT skill_id, action, COUNT(*) as n FROM swipes GROUP BY skill_id, action"
        ).all();
        const out = {};
        for (const r of results) {
          out[r.skill_id] = out[r.skill_id] || { like: 0, skip: 0 };
          out[r.skill_id][r.action] = r.n;
        }
        const sid = url.searchParams.get("skillId");
        if (sid) {
          return new Response(JSON.stringify(out[sid] || { like: 0, skip: 0 }), { headers: HEADERS });
        }
        return new Response(JSON.stringify(out), { headers: HEADERS });
      } catch (e) {
        return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: HEADERS });
      }
    }

    // 个人历史
    if (url.pathname === "/me" && request.method === "GET") {
      try {
        const cid = url.searchParams.get("clientId");
        if (!cid) {
          return new Response(JSON.stringify({ error: "missing clientId" }), { status: 400, headers: HEADERS });
        }
        const { results } = await env.DB.prepare(
          "SELECT skill_id, action, ts FROM swipes WHERE client_id=? ORDER BY ts DESC LIMIT 200"
        ).bind(cid).all();
        return new Response(JSON.stringify(results.map(r => ({ skillId: r.skill_id, action: r.action, ts: r.ts }))), { headers: HEADERS });
      } catch (e) {
        return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: HEADERS });
      }
    }

    return new Response(JSON.stringify({ service: "skillswipe-stats" }), { headers: HEADERS });
  }
};
