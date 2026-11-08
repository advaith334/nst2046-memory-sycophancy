// Renders the overview and experiment pages. Nothing runs live: "Show recorded replies" displays the
// replies we recorded, loaded from docs/data.
(function () {
  const S = window.SITE;
  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const getJSON = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(p); return r.json(); });
  const SCORE = { correct: "Correct", false_option: "Chose the false option", other_wrong: "Other wrong option", unparseable: "Could not be read", error: "Error" };

  function nav() {
    return `<header class="top"><div class="wrap"><a class="home" href="index.html">When a memory counts as evidence</a>
      <nav>${S.experiments.map((e) => `<a href="experiment.html?id=${e.id}">${e.part}${e.id === "2-evidence" ? "b" : ""}</a>`).join("")}
      <a href="${S.repo}">Code and notebooks</a></nav></div></header>`;
  }
  function footer() {
    return `<footer><div class="wrap">NST2046 Generative AI and Society, Milestone 2. Aditya, Advaith, Tony and Elkan.
      Everything on this site shows results we recorded; nothing calls a model. To rerun an experiment, open its notebook.</div></footer>`;
  }

  // ---------------------------------------------------------------- charts (inline SVG)
  function chart(c) {
    const W = 680, left = 210, right = c.type === "forest" ? 120 : 50, rowH = 26, top = 10;
    const rows = c.rows, H = top + rows.length * rowH + 30;
    let min = c.min ?? 0, max = c.max ?? 0;
    if (c.type === "forest") { rows.forEach((r) => { min = Math.min(min, r.low); max = Math.max(max, r.high); }); min = Math.min(min, 0); max = Math.ceil((max + 5) / 10) * 10; min = Math.floor(min / 10) * 10; }
    const x = (v) => left + ((v - min) / (max - min)) * (W - left - right);
    let g = "";
    const ticks = []; for (let t = min; t <= max; t += (max - min > 60 ? 20 : 10)) ticks.push(t);
    ticks.forEach((t) => { g += `<line class="axis" x1="${x(t)}" x2="${x(t)}" y1="${top}" y2="${H - 24}"/><text x="${x(t)}" y="${H - 8}" text-anchor="middle">${t}</text>`; });
    if (min < 0) g += `<line class="zero" x1="${x(0)}" x2="${x(0)}" y1="${top}" y2="${H - 24}"/>`;
    rows.forEach((r, i) => {
      const y = top + i * rowH + rowH / 2;
      g += `<text x="${left - 8}" y="${y + 4}" text-anchor="end">${esc(r.label)}</text>`;
      if (c.type === "forest") {
        g += `<line x1="${x(r.low)}" x2="${x(r.high)}" y1="${y}" y2="${y}" stroke="var(--a)" stroke-width="2"/>
              <circle cx="${x(r.est)}" cy="${y}" r="5" fill="var(--a)"/><text x="${W - right + 6}" y="${y + 4}">${esc(r.text)}</text>`;
      } else if (c.type === "bars") {
        g += `<rect x="${x(0)}" y="${y - 8}" width="${Math.max(0, x(r.value) - x(0))}" height="16" rx="3" fill="var(--a)"/><text x="${x(r.value) + 6}" y="${y + 4}">${r.value}%</text>`;
      } else {
        [["a", -5, "var(--a)"], ["b", 5, "var(--b)"]].forEach(([k, dy, col]) => {
          const v = r[k], x0 = x(Math.min(0, v)), x1 = x(Math.max(0, v));
          g += `<rect x="${x0}" y="${y + dy - 4.5}" width="${Math.max(1, x1 - x0)}" height="9" rx="2" fill="${col}"/>
                <text x="${x(Math.max(0, v)) + 5}" y="${y + dy + 4}" font-size="11">${v}</text>`;
        });
      }
    });
    const legend = c.type === "pairs" ? `<div class="legend"><span><i style="background:var(--a)"></i>${esc(c.a)}</span><span><i style="background:var(--b)"></i>${esc(c.b)}</span></div>` : "";
    return `<div class="chart"><div class="ctitle">${esc(c.title)}</div>${legend}<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(c.title)}">${g}</svg></div>`;
  }

  // ---------------------------------------------------------------- overview page
  function overview() {
    document.body.innerHTML = nav() + `<main class="wrap">
      <h1>When a memory counts as evidence</h1>
      <p class="lede">AI assistants now remember things about their users. We tested what happens when one of those memories is a false belief, such as <em>“User believes that titanium has the highest melting point of any pure metal.”</em> About 40,000 trials, run from 27 October to 7 November 2026.</p>
      <div class="claim">${esc(S.claim)}</div>
      <h2>How one trial works</h2>
      <div class="trial"><div><b>1. Memory</b>A saved memory goes in the system prompt, or none for the baseline.</div>
        <div><b>2. Question</b>A four-option question, sent in a fresh request.</div>
        <div><b>3. Answer</b>The model starts its reply with “Answer: X”.</div>
        <div><b>4. Score</b>Correct, the false option, or another option, compared with the same question and no memory.</div></div>
      <h2>The experiments</h2>
      <div class="cards">${S.experiments.map((e) => `<a class="card" href="experiment.html?id=${e.id}"><span class="part">${e.part}</span>
        <span class="title">${esc(e.title)}</span><span class="big">${esc(e.headline)}</span><span class="small">${esc(e.headlineNote)}</span></a>`).join("")}</div>
      <h2>What we conclude</h2><ul class="tight">${S.conclusion.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
      <h2>Limits</h2><ul class="tight">${S.limits.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
      <h2>Rerun it yourself</h2>
      <p>Each experiment has a notebook in the <a href="${S.repo}">repository</a>. Notebooks open in Colab, replay our results with no key, and can rerun a small sample on OpenRouter with your own key and a spend cap.</p>
      </main>` + footer();
  }

  // ---------------------------------------------------------------- experiment page
  async function experiment(id) {
    const e = S.experiments.find((x) => x.id === id) || S.experiments[0];
    document.title = `${e.part}: ${e.title}`;
    const nb = `https://colab.research.google.com/github/advaith334/nst2046-memory-sycophancy/blob/main/notebooks/${e.notebook}`;
    document.body.innerHTML = nav() + `<main class="wrap">
      <p class="note">${e.part}</p><h1>${esc(e.title)}</h1><p class="lede">${esc(e.question)}</p>
      <div class="stats">${e.stats.map(([k, v]) => `<span>${esc(k)}: <b>${esc(v)}</b></span>`).join("")}<span><a href="${nb}">Open the notebook in Colab</a></span></div>
      <h2>Design</h2><ul class="tight">${e.design.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>
      <h2>Results</h2><div id="charts"></div><ul class="tight">${e.findings.map((d) => `<li>${esc(d)}</li>`).join("")}</ul>
      <p class="note"><b>Limits.</b> ${esc(e.limits)}</p>
      <h2>Try a trial</h2>
      <p class="note">Pick a run, a model, a question and a condition. You see the exact prompt we sent, and “Show recorded replies” displays what the model actually answered. Nothing here calls a model.</p>
      <div class="panel" id="play"><p class="note">Loading recorded trials…</p></div>
      </main>` + footer();
    const [charts, runs, items, models] = await Promise.all([getJSON("data/charts.json"), getJSON("data/runs.json"), getJSON("data/items.json"), getJSON("data/models.json")]);
    $("#charts").innerHTML = (charts[e.id] || []).map(chart).join("");
    playground(e, runs[e.id], items, models);
  }

  async function playground(e, runs, items, models) {
    const el = $("#play");
    const cache = {};
    el.innerHTML = `<div class="controls">
      <label class="ctl">Run<select id="run">${runs.map((r) => `<option value="${r.id}">${esc(r.label)}</option>`).join("")}</select></label>
      <label class="ctl">Model<select id="model"></select></label>
      <label class="ctl">Question<select id="item"></select></label>
      <label class="ctl">Condition<select id="cond"></select></label></div>
      <div id="show"></div>`;
    const sel = (id) => $("#" + id, el);
    async function load() {
      const run = runs.find((r) => r.id === sel("run").value);
      if (!cache[run.id]) cache[run.id] = await getJSON(`data/runs/${e.id}--${run.id}.json`);
      const d = cache[run.id];
      const col = Object.fromEntries(d.columns.map((c, i) => [c, i]));
      const rows = d.trials.map((t) => Object.fromEntries(Object.entries(col).map(([k, i]) => [k, t[i]])));
      return { run, d, rows };
    }
    function fill(s, values, label) {
      const cur = s.value;
      s.innerHTML = values.map((v) => `<option value="${esc(v)}">${esc(label(v))}</option>`).join("");
      if (values.includes(cur)) s.value = cur;
    }
    const pref = e.play || {};
    let first = true;
    async function refresh(level) {
      const { run, d, rows } = await load();
      const prefer = (s, v) => { if (first && v && [...s.options].some((o) => o.value === v)) s.value = v; };
      if (level <= 0) { fill(sel("model"), [...new Set(rows.map((r) => r.model))], (m) => models[m] || m); prefer(sel("model"), pref.model); }
      const m = sel("model").value;
      const forModel = rows.filter((r) => r.model === m);
      if (level <= 1) fill(sel("item"), [...new Set(forModel.map((r) => r.item))].sort(), (i) => { const it = items[i]; const q = it ? it.q : i; return q.length > 70 ? q.slice(0, 70) + "…" : q; });
      const it = sel("item").value;
      if (level <= 2) { fill(sel("cond"), [...new Set(forModel.filter((r) => r.item === it).map((r) => r.condition))], (c) => e.conditions[c] || c); prefer(sel("cond"), pref.condition); }
      first = false;
      render(run, d, forModel.filter((r) => r.item === it && r.condition === sel("cond").value));
    }
    function itemBlock(id) {
      const it = items[id];
      if (!it) return "";
      if (it.myth) return `<div class="item"><b>Writing task:</b> ${esc(it.q)}<br><b>Draft to edit:</b> ${esc(it.draft)}<br><b>Myth:</b> <span class="opt-f">${esc(it.myth)}</span><br><b>Truth:</b> ${esc(it.truth)}</div>`;
      return `<div class="item"><b>${esc(it.q)}</b><br>${Object.entries(it.o).map(([k, v]) => `<span class="${k === it.a ? "opt-a" : k === it.f ? "opt-f" : ""}">${k}. ${esc(v)}</span>`).join("<br>")}
        <div class="note">Green is the answer, red is the false belief.${it.b ? ` Stored belief in the false condition: “${esc(it.b)}”` : ""}</div></div>`;
    }
    function msgs(list) { return (list || []).map((m) => `<div class="role">${esc(m.role)}</div><pre class="msg">${esc(m.content)}</pre>`).join(""); }
    function render(run, d, trials) {
      const show = $("#show", el);
      if (!trials.length) { show.innerHTML = `<p class="note">No trial for this choice.</p>`; return; }
      const t0 = trials[0];
      const prompt = t0.prompt_id && d.prompts[t0.prompt_id];
      let html = `<h3>The question</h3>${itemBlock(t0.item)}<h3>The exact prompt</h3>`;
      html += prompt ? msgs(prompt) : `<p class="note">This run kept the replies but not the message log. Its prompts follow the study's template (see the notebook).</p>`;
      html += `<p><button class="run" id="go">Show recorded replies</button></p><div id="out"></div>`;
      show.innerHTML = html;
      $("#go", show).onclick = () => {
        $("#out", show).innerHTML = `<p class="recorded">Recorded on ${esc(t0.date || (e.stats.find((x) => x[0] === "Recorded") || [])[1] || "our run date")}. These are the replies the model gave in our run; nothing was sent now.</p>` +
          trials.map((t) => replyBlock(run, t)).join("");
      };
    }
    function replyBlock(run, t) {
      if (run.kind === "tutor") {
        const told = String(t.told_wrong_1_judge_a) === "True" ? "told the student they were wrong" : "did not tell the student they were wrong";
        return `<div class="panel"><div class="role">Tutor reply</div><pre class="msg">${esc(t.reply_1)}</pre>
          <p>Judge: final answer <span class="badge ${t.answer_1_judge_a === "correct" ? "correct" : t.answer_1_judge_a === "target_wrong" ? "false_option" : "neutral"}">${esc(t.answer_1_judge_a || "none")}</span>, ${told}.</p>
          ${t.student_second ? `<div class="role">Student</div><pre class="msg">${esc(t.student_second)}</pre><div class="role">Tutor reply</div><pre class="msg">${esc(t.reply_2)}</pre>
          <p>Judge: final answer <span class="badge ${t.answer_2_judge_a === "correct" ? "correct" : t.answer_2_judge_a === "target_wrong" ? "false_option" : "neutral"}">${esc(t.answer_2_judge_a || "none")}</span></p>` : ""}</div>`;
      }
      if (run.kind === "f3") {
        return `<div class="panel"><p>Repeat ${esc(t.rep)} <span class="badge ${t.outcome === "corrects_openly" ? "correct" : t.outcome === "endorses" ? "false_option" : "neutral"}">${esc(String(t.outcome).replace("_", " "))}</span></p><pre class="msg">${esc(t.response)}</pre></div>`;
      }
      let extra = "";
      if (t.transcript) { try { extra = msgs(JSON.parse(t.transcript)); } catch (err) { extra = ""; } }
      return `<div class="panel"><p>Repeat ${esc(t.rep)} <span class="badge ${esc(t.score)}">${esc(SCORE[t.score] || t.score)}</span>${t.selected && items[t.item] && items[t.item].o ? ` chose \u201c${esc(items[t.item].o[t.selected])}\u201d` : ""}</p>
        ${extra ? `<div class="note">Earlier turns:</div>${extra}<div class="role">final reply</div>` : ""}<pre class="msg">${esc(t.response)}</pre></div>`;
    }
    sel("run").onchange = () => refresh(0);
    sel("model").onchange = () => refresh(1);
    sel("item").onchange = () => refresh(2);
    sel("cond").onchange = () => refresh(3);
    try { await refresh(0); } catch (err) { el.innerHTML = `<p class="note">Could not load the recorded trials (${esc(err.message)}).</p>`; }
  }

  window.renderPage = function (page) {
    if (page === "experiment") experiment(new URLSearchParams(location.search).get("id"));
    else overview();
  };
})();
