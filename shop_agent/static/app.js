/* Shopping Decision Agent — vanilla JS UI. No CDN, no fake product images. */
(function () {
  "use strict";

  var state = {
    owner: localStorage.getItem("sdagent_owner") || "local-demo",
    sessionId: null,
    revision: null,
    merchantVersion: null,
    data: null,
    outcome: null,
    timeline: [],
    imageOnline: false,
    imageBase64: null,
    imageName: "",
    busy: false
  };

  var STATUS_ZH = {
    PROPOSED: "待确认",
    NEEDS_REVIEW: "需重新研究",
    APPROVED: "已确认",
    REJECTED: "已拒绝",
    EXPIRED: "已过期",
    SUPERSEDED: "已被取代"
  };

  var AVAIL_ZH = { in_stock: "有货", out_of_stock: "缺货" };
  var RESV_ZH = { draft_reserved: "草稿预订" };

  var CASE_STEPS = {
    confirm: "载入查询后，由你手动点击“确认（创建本地草稿）”才会生成草稿；再次点击确认可看到幂等效果（不新增记录）。",
    reject: "载入查询后，由你手动点击“拒绝”；系统不会自动拒绝或预订。",
    no_feasible: "载入一个预算过低的查询；研究后应显示“无可行方案”和确定性协商选项，不会自动创建提案。",
    price_changed: "载入查询并研究后，由你手动点击“模拟涨价 +$5”，观察提案进入“需重新研究”；之后的确认会被拦截，必须重新研究。",
    expired: "说明提案有效期：每个提案都有有效期，超时后确认将被拒绝并要求重新研究，不会产生草稿。"
  };

  function $(id) { return document.getElementById(id); }

  function esc(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function catalogText(value) {
    return String(value || "").replace(/&quot;/g, '"').replace(/&#39;|&#x27;/gi, "'").replace(/&amp;/g, "&");
  }
  function money(value) {
    return (typeof value === "number" && isFinite(value)) ? "$" + value.toFixed(2) : "—";
  }

  function num(value, digits) {
    return (typeof value === "number" && isFinite(value)) ? value.toFixed(digits) : "—";
  }

  function statusLabel(value) { return STATUS_ZH[value] || value || "—"; }
  function availLabel(value) { return AVAIL_ZH[value] || value || "—"; }
  function resvLabel(value) { return RESV_ZH[value] || value || "—"; }

  function fmtTime(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    return isNaN(d.getTime()) ? String(iso) : d.toLocaleString();
  }

  function toast(message, isError) {
    var el = $("toast");
    el.textContent = message;
    el.className = "toast" + (isError ? " err" : "");
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.classList.add("hidden"); }, 5200);
  }

  async function api(path, opts) {
    opts = opts || {};
    var req = { method: opts.method || "GET", headers: {} };
    if (opts.body) { req.headers["Content-Type"] = "application/json"; req.body = JSON.stringify(opts.body); }
    var res = await fetch(path, req);
    var data;
    try { data = await res.json(); } catch (e) { data = { error: { code: "bad_response", message: res.statusText } }; }
    if (!res.ok) {
      var err = new Error((data.error && data.error.message) || "request failed");
      err.code = (data.error && data.error.code) || ("http_" + res.status);
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  function pushTimeline(kind, detail) {
    state.timeline.push({ kind: kind, detail: detail || "", at: new Date().toLocaleTimeString() });
  }

  // ---- renderers -----------------------------------------------------
  function renderBrief() {
    var data = state.data;
    if (!data) return;
    var b = data.brief || {}, s = data.session || {};
    var hard = b.hard_constraints || {}, price = hard.price || {};
    var prefs = (b.soft_preferences || []).map(function (p) {
      return '<span class="tag">' + esc(p.term) + " ×" + esc(p.weight) + "</span>";
    }).join("") || '<span class="muted">无</span>';
    var unresolved = (b.unresolved_tokens || []).map(function (t) {
      return '<span class="tag warn">' + esc(t) + "</span>";
    }).join("") || '<span class="muted">无</span>';
    $("briefBody").innerHTML =
      '<dl class="kv">' +
      "<dt>查询</dt><dd>" + esc(b.query) + "</dd>" +
      "<dt>解析器</dt><dd>" + "受限规则解析（非通用 LLM）" + "</dd>" +
      "<dt>预算</dt><dd>下限 " + money(price.lower) + " · 上限 " + money(price.upper) + "</dd>" +
      "<dt>必须包含</dt><dd>" + esc((hard.must_include || []).join(", ") || "无") + "</dd>" +
      "<dt>必须排除</dt><dd>" + esc((hard.must_exclude || []).join(", ") || "无") + "</dd>" +
      "<dt>软偏好</dt><dd>" + prefs + "</dd>" +
      "<dt>未解析词</dt><dd>" + unresolved + "</dd>" +
      "<dt>目录</dt><dd>" + esc((b.catalog || {}).label) + " · " + esc((b.catalog || {}).records) + " 条</dd>" +
      "<dt>策略</dt><dd>" + esc(b.policy) + "</dd>" +
      "</dl>" +
      '<details class="evidence"><summary>查看本轮编号</summary>' +
      '<pre class="evidence-pre">' + esc(JSON.stringify(
        { turn: s.turn, revision: s.revision, merchant_version: s.merchant_version }, null, 2)) +
      "</pre></details>";
  }

  function renderCandidates() {
    var data = state.data;
    if (!data) return;
    var list = data.candidates || [];
    if (!list.length) {
      var neg = data.negotiation || {};
      $("candidateBody").innerHTML = '<p class="muted">当前硬约束下没有可行候选。</p>' +
        (neg.needed ? '<p class="muted">可查看下方确定性协商选项（来自真实价格/词项统计）。</p>' : "");
      return;
    }
    var bestId = data.proposal && data.proposal.item_id;
    $("candidateBody").innerHTML = list.map(function (c) {
      var prefs = (c.matched_preferences || []).map(function (p) {
        return '<span class="tag">' + esc(p.term) + "</span>";
      }).join("");
      var meta = [esc(c.brand || "—")];
      if (typeof c.score === "number" && isFinite(c.score)) meta.push("匹配度 " + num(c.score, 3));
      if (c.hard_constraint_ok) meta.push("硬约束 OK");
      var raw = {
        item_id: c.item_id, score: c.score,
        visual_cosine: c.visual_cosine, reranker_logit: c.reranker_logit
      };
      return '<div class="cand' + (String(c.item_id) === String(bestId) ? " best" : "") + '">' +
        '<div class="cand-head"><span class="title">#' + esc(c.rank) + " " + esc(catalogText(c.title)) + "</span>" +
        '<span class="price">' + money(c.price_usd) + "</span></div>" +
        '<div class="meta">' + meta.join(" · ") + "</div>" +
        (prefs ? '<div class="meta">命中偏好 ' + prefs + "</div>" : "") +
        '<details class="evidence"><summary>查看排序依据</summary><pre class="evidence-pre">' +
        esc(JSON.stringify({ ranking: raw, evidence: c.evidence }, null, 2)) + "</pre></details></div>";
    }).join("");
  }

  function negotiationHtml() {
    var neg = (state.data && state.data.negotiation) || {};
    if (!neg.needed || !(neg.options || []).length) return "";
    var rows = neg.options.slice(0, 5).map(function (o) {
      return "<li>" + esc(o.minimal_action) + " → 可恢复 " + esc(o.minimal_recovered) + " 个候选</li>";
    }).join("");
    return '<div class="alert err"><strong>无可行方案</strong>：硬约束下没有商品满足。' +
      "确定性协商选项（仅展示，不会自动放宽约束）：<ul>" + rows + "</ul></div>";
  }

  function shareableResult() {
    var out = state.outcome;
    if (!out || out.verified !== true || !out.reservation) return "";
    var r = out.reservation;
    return [
      "Shopping Decision Agent · 已确认采购草稿",
      "商品：" + catalogText(r.title),
      "确认时目录价：" + money(r.price_usd) + " USD（不代表当前报价）",
      "结果：用户确认后已保存，并读回验证通过。",
      "来源：" + (state.realCatalog ? "历史商品目录" : "手写演示目录") + "；库存与报价变更为模拟。",
      "未向商户下单或扣款。"
    ].join("\n");
  }

  async function copyResult() {
    var text = shareableResult();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast("已复制。请回到聊天，审阅后自行粘贴发送。");
    } catch (err) {
      var field = $("shareResultText");
      if (field) {
        field.closest("details").open = true;
        field.focus(); field.select();
      }
      toast("浏览器未允许自动复制，请在展开的结果中手动复制。", true);
    }
  }

  function renderOutcome() {
    var out = state.outcome;
    var html = "";
    if (!out) return html;
    if (out.error) {
      html += '<div class="alert err"><strong>未能完成</strong>：' + esc(out.error.message) +
        '<br><span class="muted">' + esc(out.error.code) + "</span></div>";
    }
    if (out.reservation) {
      var ids = {
        reservation_id: out.reservation.reservation_id,
        proposal_id: out.reservation.proposal_id,
        checks: out.verification_checks
      };
      if (out.verified === true) {
        html += '<div class="alert ok"><strong>草稿已创建，回读校验通过</strong><br>' +
          esc(catalogText(out.reservation.title)) + " · " + money(out.reservation.price_usd) +
          " · " + esc(resvLabel(out.reservation.status)) +
          (out.idempotent ? " · <em>重复确认，未新增记录</em>" : "") +
          '<details class="evidence"><summary>查看草稿编号与回读明细</summary><pre class="evidence-pre">' +
          esc(JSON.stringify(ids, null, 2)) + "</pre></details>" +
          '<details class="evidence"><summary>查看可分享结果</summary>' +
          '<textarea id="shareResultText" class="share-result" rows="7" readonly aria-label="可分享的已确认结果">' +
          esc(shareableResult()) + '</textarea></details>' +
          '<button class="ghost small" data-act="copy-result">复制结果到聊天</button>' +
          '<p class="muted">仅复制文字，由你回到聊天审阅并发送。</p></div>';
      } else {
        html += '<div class="alert err"><strong>草稿已写入，但回读校验未通过（verified = false）</strong><br>' +
          esc(catalogText(out.reservation.title)) + " · " + money(out.reservation.price_usd) +
          " · 请勿据此认为已确认成功。" +
          '<details class="evidence"><summary>查看失败的回读明细</summary><pre class="evidence-pre">' +
          esc(JSON.stringify(ids, null, 2)) + "</pre></details></div>";
      }
    }
    if (out.note) html += '<div class="alert info">' + esc(out.note) + "</div>";
    return html;
  }

  function renderAction() {
    var data = state.data;
    var html = renderOutcome();
    if (!data) { $("actionBody").innerHTML = html || '<p class="muted">暂无提案。</p>'; return; }
    if (!data.proposal) {
      $("actionBody").innerHTML = html + negotiationHtml() ||
        '<p class="muted">本次没有可确认的提案。</p>';
      return;
    }
    var p = data.proposal;
    html += '<div class="proposal">' +
      '<div class="cand-head"><span class="title">' + esc(catalogText(p.title)) + "</span>" +
      '<span class="price">' + money(p.price_usd) + "</span></div>" +
      '<div class="meta">' + esc(p.brand || "—") + " · 状态 " +
      '<span class="status-pill status-' + esc(p.status) + '">' + esc(statusLabel(p.status)) + "</span>" +
      " · " + esc(availLabel(p.availability)) + " · 报价版本 v" + esc(p.merchant_version) + "</div>" +
      '<p class="rationale">' + esc(catalogText(p.rationale)) + "</p>" +
      '<div class="meta">有效期至 ' + esc(fmtTime(p.expires_at_iso)) + "</div>" +
      '<details class="evidence"><summary>查看提案依据与候选范围</summary><pre class="evidence-pre">' +
      esc(JSON.stringify({ proposal_id: p.proposal_id, eligible_item_ids: p.eligible_item_ids,
                           evidence: p.evidence }, null, 2)) +
      "</pre></details>" +
      '<div class="actions">' +
      '<button class="approve" data-act="approve">确认（创建本地草稿）</button>' +
      '<button class="danger" data-act="reject">拒绝</button>' +
      '<button class="ghost small" data-act="sim-price">模拟涨价 +$5</button>' +
      '<button class="ghost small" data-act="sim-down">模拟降价 -$3</button>' +
      '<button class="ghost small" data-act="sim-stock">模拟缺货</button>' +
      "</div></div>";
    $("actionBody").innerHTML = html;
  }

  function renderTimeline() {
    if (!state.timeline.length) { $("timelineBody").innerHTML = '<p class="muted">暂无事件。</p>'; return; }
    $("timelineBody").innerHTML = '<ul class="timeline">' + state.timeline.map(function (t) {
      return "<li><div class=\"t-kind\">" + esc(t.kind) + "</div>" +
        "<div class=\"t-meta\">" + esc(t.at) + " · " + esc(t.detail) + "</div></li>";
    }).join("") + "</ul>";
  }

  function renderTrace() {
    if (!state.data) { $("traceBody").textContent = ""; return; }
    $("traceBody").textContent = JSON.stringify(
      { trace: state.data.trace, recommendation: state.data.recommendation,
        limitations: state.data.limitations }, null, 2);
  }

  function renderAll() {
    renderBrief(); renderCandidates(); renderAction(); renderTimeline(); renderTrace();
    $("sourceLabel").textContent = "source: " + ((state.data && state.data.source_label) || "-");
    $("sessionLabel").textContent = "session: " + (state.sessionId || "-") +
      (state.revision ? " · revision " + state.revision : "");
  }

  // ---- image input ---------------------------------------------------
  function setBusy(busy, message) {
    state.busy = busy;
    var btn = $("researchSubmit");
    var status = $("researchStatus");
    if (btn) btn.disabled = busy;
    if (status) {
      if (busy) { status.textContent = message || "处理中…"; status.classList.remove("hidden"); }
      else { status.classList.add("hidden"); status.textContent = ""; }
    }
  }

  function applyImageAvailability() {
    var input = $("imageInput");
    var wrap = $("imageUploadWrap");
    var note = $("imageNote");
    if (!input || !note) return;
    if (state.imageOnline) {
      input.disabled = false;
      if (wrap) wrap.classList.remove("disabled");
      if (!state.imageBase64) {
        note.textContent = "可附加一张图片进行图片检索（与文字查询可选其一或同时使用）。";
        note.classList.remove("hidden");
      }
    } else {
      input.disabled = true;
      if (wrap) wrap.classList.add("disabled");
      state.imageBase64 = null;
      state.imageName = "";
      var preview = $("imagePreview");
      if (preview) preview.classList.add("hidden");
      note.textContent = "当前运行仅支持文字；图片检索未启用";
      note.classList.remove("hidden");
    }
  }

  async function initHealth() {
    try {
      var health = await api("/api/health");
      state.realCatalog = !!(health.agent && !health.agent.catalog_is_demo_fixture);
      if (state.realCatalog && $("queryInput").value === "wireless mouse under 30 dollars") {
        $("queryInput").value = "mouse pad under 15 dollars require rubber";
      }
      state.imageOnline = !!(health && health.capabilities && health.capabilities.image_query_online);
    } catch (err) {
      state.imageOnline = false;
    }
    applyImageAvailability();
  }

  function onImagePicked(event) {
    var file = event.target.files && event.target.files[0];
    if (!file) return;
    if (!state.imageOnline) { toast("当前运行仅支持文字；图片检索未启用", true); return; }
    var reader = new FileReader();
    reader.onload = function () {
      var dataUrl = String(reader.result || "");
      var comma = dataUrl.indexOf(",");
      state.imageBase64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
      state.imageName = file.name || "image";
      $("imagePreviewImg").src = dataUrl;
      $("imagePreview").classList.remove("hidden");
      $("imageNote").textContent = "已选图片：" + state.imageName + "（提交研究时随查询一起上传）";
      $("imageNote").classList.remove("hidden");
    };
    reader.onerror = function () { toast("读取图片失败，请重试", true); };
    reader.readAsDataURL(file);
  }

  function clearImage() {
    state.imageBase64 = null;
    state.imageName = "";
    var input = $("imageInput");
    if (input) input.value = "";
    var img = $("imagePreviewImg");
    if (img) img.removeAttribute("src");
    var preview = $("imagePreview");
    if (preview) preview.classList.add("hidden");
    applyImageAvailability();
  }

  // ---- actions -------------------------------------------------------
  async function doResearch(query) {
    var body = { owner: state.owner, query: query, top_k: 3 };
    if (state.imageBase64) body.image_base64 = state.imageBase64;
    setBusy(true, state.imageBase64 ? "正在对图片与查询进行检索，请稍候…" : "正在检索候选并生成决策，请稍候…");
    try {
      var data = await api("/api/research", { method: "POST", body: body });
      state.data = data;
      state.sessionId = data.session.session_id;
      state.revision = data.session.revision;
      state.merchantVersion = data.session.merchant_version;
      state.outcome = null;
      pushTimeline("research", "query=" + (query || "(仅图片)") + " → " +
        (data.feasible ? "提案 " + (data.proposal && data.proposal.item_id) : "无可行方案"));
      renderAll();
    } catch (err) { fail(err); }
    finally { setBusy(false); }
  }

  async function doRefine(utterance) {
    if (!state.sessionId) { toast("请先执行一次研究", true); return; }
    setBusy(true, "正在细化查询，请稍候…");
    try {
      var data = await api("/api/refine", { method: "POST",
        body: { owner: state.owner, session_id: state.sessionId, utterance: utterance } });
      state.data = data;
      state.revision = data.session.revision;
      state.merchantVersion = data.session.merchant_version;
      state.outcome = null;
      pushTimeline("refine", utterance + " → revision " + data.session.revision);
      renderAll();
    } catch (err) { fail(err); }
    finally { setBusy(false); }
  }

  async function doApprove() {
    var p = state.data && state.data.proposal;
    if (!p) return;
    try {
      var data = await api("/api/approve", { method: "POST",
        body: { owner: state.owner, session_id: state.sessionId, proposal_id: p.proposal_id } });
      state.outcome = data;
      pushTimeline("approve", "草稿 " + data.reservation.reservation_id +
        " · 回读校验 " + (data.verified ? "通过" : "未通过") + (data.idempotent ? "（幂等）" : ""));
      refreshProposalStatus(data.proposal);
      renderAll();
    } catch (err) { fail(err, "approve"); }
  }

  async function doReject() {
    var p = state.data && state.data.proposal;
    if (!p) return;
    try {
      var data = await api("/api/reject", { method: "POST",
        body: { owner: state.owner, session_id: state.sessionId, proposal_id: p.proposal_id } });
      state.outcome = { note: (data.outcome || {}).note || "已拒绝，没有任何本地预订。",
                        reservation: null, error: null };
      if (state.data) state.data.proposal = data.proposal;
      pushTimeline("reject", "已拒绝该提案（未产生草稿）");
      renderAll();
    } catch (err) { fail(err, "reject"); }
  }

  function refreshProposalStatus(proposal) {
    if (state.data && proposal) state.data.proposal = proposal;
  }

  async function doSimulate(mode) {
    var p = state.data && state.data.proposal;
    if (!p) { toast("当前没有提案可模拟", true); return; }
    var body = { owner: state.owner, session_id: state.sessionId, proposal_id: p.proposal_id };
    if (mode === "price") body.price_usd = Number(p.price_usd) + 5;
    else if (mode === "down") body.price_usd = Math.max(0.01, Number(p.price_usd) - 3);
    else body.availability = "out_of_stock";
    try {
      var data = await api("/api/simulate-quote", { method: "POST", body: body });
      if (state.data) state.data.proposal = data.proposal;
      state.merchantVersion = data.merchant_version;
      state.outcome = { note: data.note, reservation: null, error: null };
      pushTimeline("simulate-quote", "报价版本 v" + data.merchant_version + " → 需重新研究");
      renderAll();
    } catch (err) { fail(err); }
  }

  async function loadSession() {
    if (!state.sessionId) { toast("尚无会话", true); return; }
    try {
      var data = await api("/api/session/" + encodeURIComponent(state.sessionId) +
        "?owner=" + encodeURIComponent(state.owner));
      state.timeline = (data.events || []).slice().reverse().map(function (e) {
        return { kind: e.kind, detail: JSON.stringify(e.detail), at: new Date(e.created_at * 1000).toLocaleTimeString() };
      });
      renderAll();
      toast("已读取会话历史（重启后仍可读）");
    } catch (err) { fail(err); }
  }

  async function loadHistory() {
    try {
      var data = await api("/api/history?owner=" + encodeURIComponent(state.owner));
      var box = $("historyPanel");
      var rows = (data.reservations || []).map(function (r) {
        return "<li>" + esc(r.title) + " " + money(r.price_usd) +
          " · " + esc(resvLabel(r.status)) +
          ' <span class="muted">(' + esc(r.reservation_id) + ")</span></li>";
      }).join("");
      var props = (data.proposals || []).map(function (p) {
        return "<li>商品 " + esc(p.item_id) + " · " + esc(statusLabel(p.status)) +
          ' <span class="muted">(' + esc(p.proposal_id) + ")</span></li>";
      }).join("");
      $("historyBody").innerHTML =
        "<p class=\"muted\">会话 " + (data.sessions || []).length + " · 提案 " + (data.proposals || []).length +
        " · 草稿 " + (data.reservations || []).length + "</p>" +
        "<details class=\"evidence\"><summary>查看草稿预订明细</summary><ul>" +
        (rows || "<li class='muted'>无</li>") + "</ul></details>" +
        "<details class=\"evidence\"><summary>查看提案明细</summary><ul>" +
        (props || "<li class='muted'>无</li>") + "</ul></details>";
      box.classList.remove("hidden");
      box.scrollIntoView({ behavior: "smooth" });
    } catch (err) { fail(err); }
  }

  function fail(err, action) {
    var code = err && err.code ? err.code : "error";
    var message = err && err.message ? err.message : String(err);
    state.outcome = { error: { code: code, message: message }, reservation: null, note: null };
    pushTimeline((action || "error") + " refused", code + " — " + message);
    renderAll();
    toast(code + ": " + message, true);
  }

  function runCase(kind, query) {
    $("queryInput").value = query;
    var el = $("caseNote");
    el.textContent = CASE_STEPS[kind] || "已载入查询，请点击“研究 / Research”查看结果。";
    el.classList.remove("hidden");
    toast("已载入示例查询，请手动点击“研究”；系统不会自动确认或拒绝");
  }

  // ---- wiring --------------------------------------------------------
  function bind() {
    $("ownerInput").value = state.owner;
    $("ownerInput").addEventListener("change", function () {
      state.owner = this.value.trim() || "local-demo";
      localStorage.setItem("sdagent_owner", state.owner);
      toast("owner = " + state.owner);
    });
    $("researchForm").addEventListener("submit", function (e) {
      e.preventDefault();
      doResearch($("queryInput").value.trim());
    });
    $("refineForm").addEventListener("submit", function (e) {
      e.preventDefault();
      doRefine($("refineInput").value.trim());
    });
    $("imageInput").addEventListener("change", onImagePicked);
    $("imageClear").addEventListener("click", clearImage);
    $("historyBtn").addEventListener("click", loadHistory);
    $("actionBody").addEventListener("click", function (e) {
      var act = e.target.getAttribute && e.target.getAttribute("data-act");
      if (act === "approve") doApprove();
      else if (act === "reject") doReject();
      else if (act === "sim-price") doSimulate("price");
      else if (act === "sim-down") doSimulate("down");
      else if (act === "sim-stock") doSimulate("stock");
      else if (act === "copy-result") copyResult();
    });
    api("/api/cases").then(function (data) {
      var box = $("caseButtons");
      (data.cases || []).forEach(function (c) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "case-chip";
        btn.textContent = c.label_zh;
        btn.addEventListener("click", function () { runCase(c.kind, state.realCatalog ? (c.kind === "no_feasible" ? "mouse pad under 0.01 dollars require rubber" : "mouse pad under 15 dollars require rubber") : c.query); });
        box.appendChild(btn);
      });
      if (data.disclaimer_zh) $("disclaimer").textContent = data.disclaimer_zh;
    }).catch(function () { /* cases optional */ });
    initHealth();
    renderAll();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
