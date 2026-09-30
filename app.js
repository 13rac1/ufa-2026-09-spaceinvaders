import { DATA } from "./data.js";

const $ = (selector) => document.querySelector(selector);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const fmt = (n) => Math.round(n).toLocaleString("en-US");
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const COLOR = (player) =>
  player.startsWith("code") ? css("--code")
  : player.startsWith("jev") ? css("--jev")
  : player.startsWith("llm") ? css("--haiku")
  : player.startsWith("qwen") ? css("--qwen")
  : css("--floor");

const TERMS = {
  code: ["Code Autopilot", "A rule-based player with fixed rules: dodge a bullet, pick the target, aim ahead, fire. It sees the same screen as the models, plus what it saw a moment ago; nothing hidden. An AI coding agent (Claude) wrote and tuned the rules on practice seeds only. While it plays, no model runs; each decision takes under 0.1 ms."],
  jev: ["JEV", "TypeSafe's decision model, a \"System One\" model. It is built on a pretrained language model, but instead of writing an answer it reads the probability of every option in one pass (TypeSafe: it \"outputs all probabilities in parallel instead of autoregressively generating by token\"). It gets facts (JSON) and questions with fixed options and answers in about a tenth of a second. It does not write text or explain itself."],
  llm: ["LLM", "Large language model, like the ones behind chatbots. It reads a prompt and writes an answer word by word. Here: Claude Haiku 4.5 (Anthropic) and Qwen3.8 27B (open weights). It is slower than JEV because it generates its answer one token at a time, even when the answer is one word."],
  systemone: ["System One protocol and adapter", "The request format JEV uses: state + questions, answered with typed choices. The organizers' adapter lets an LLM answer the same request, so both get exactly the same question."],
  decoder: ["Decoder", "The part of the harness that turns the Atari screen (and, for objects that flicker, the Atari's memory) into facts: positions of the ship, aliens, bullets and shields. Every player uses the same decoder."],
  tier: ["Input tier", "How much the harness works out before the model decides. Tier 1: positions. Tier 2: the same facts with distances and timings computed. Tier 3: the code's own verdicts (safe moves, the target), a reference only."],
  seed: ["Seed", "A number that fixes the game's randomness, so a game can be played again exactly. Seeds 1-99 and 10000+ were for practice (tuning); seeds from 101 are the test (evaluation)."],
  modes: ["Turn mode and realtime mode", "In turn mode the game waits for every decision, so only the quality of decisions counts. In realtime mode the game keeps running while the player thinks, so speed counts too."],
  fallback: ["Fallback", "When a model gives no usable answer, the harness repeats the previous action. A model game counts only if fewer than 5% of its decisions fell back."],
  human: ["Human reference", "1,668.7 points: the standard human score for Atari Space Invaders that the organizers use to compare players."],
  sticky: ["Sticky actions", "A setting of the Atari environment: on each frame there is a 25% chance the previous action repeats. It keeps the game from being perfectly predictable, so nobody can replay a memorised sequence of buttons."],
  results: ["results.json", "The record of every evaluated game: score, steps, time per decision, tokens, cost. It is committed to the repository after every game, so its history shows every run."],
};

/* ---------- glossary cards ---------- */
function setupTerms() {
  const card = $("#term-card");
  const hide = () => { card.hidden = true; };
  document.querySelectorAll("dfn[data-term]").forEach((el) => {
    el.tabIndex = 0;
    const show = () => {
      const [title, text] = TERMS[el.dataset.term] || [el.textContent, ""];
      card.querySelector("h4").textContent = title;
      card.querySelector("p").textContent = text;
      card.hidden = false;
      const r = el.getBoundingClientRect();
      const width = Math.min(340, window.innerWidth - 32);
      card.style.width = width + "px";
      card.style.left = Math.max(16, Math.min(r.left, window.innerWidth - width - 16)) + "px";
      const below = r.bottom + 8;
      card.style.top = (below + 180 < window.innerHeight ? below : Math.max(8, r.top - 190)) + "px";
    };
    el.addEventListener("click", (e) => { e.stopPropagation(); show(); });
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(); } });
  });
  card.querySelector(".close").addEventListener("click", hide);
  document.addEventListener("click", (e) => { if (!card.contains(e.target)) hide(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
  window.addEventListener("scroll", hide, { passive: true });
  $("#glossary-list").innerHTML = Object.values(TERMS)
    .map(([t, d]) => `<dt>${esc(t)}</dt><dd>${esc(d)}</dd>`).join("");
}

/* ---------- small SVG helpers ---------- */
function barChart({ rows, max, width = 900, label, value, color, line, lineLabel, rowH = 34, left = 250 }) {
  const h = rows.length * rowH + 30;
  // room on the right for the longest value label (about 8 px per character)
  const right = Math.max(...rows.map((r) => String(value(r)).length)) * 8 + 16;
  const scale = (v) => (v / max) * (width - left - right);
  let s = `<svg viewBox="0 0 ${width} ${h}" role="img" aria-label="${esc(lineLabel || "bar chart")}">`;
  rows.forEach((r, i) => {
    const y = 10 + i * rowH;
    const w = Math.max(2, scale(Math.max(0, r._v)));
    s += `<text x="${left - 10}" y="${y + 20}" text-anchor="end">${esc(label(r))}</text>`;
    s += `<rect x="${left}" y="${y + 4}" width="${w}" height="${rowH - 12}" rx="3" fill="${color(r)}"/>`;
    s += `<text x="${left + w + 8}" y="${y + 20}">${esc(value(r))}</text>`;
  });
  if (line != null) {
    const x = left + scale(line);
    s += `<line x1="${x}" x2="${x}" y1="4" y2="${h - 22}" stroke="${css("--magenta")}" stroke-dasharray="5 4" stroke-width="2"/>`;
    s += `<text x="${x}" y="${h - 6}" text-anchor="middle" fill="${css("--magenta")}">${esc(lineLabel)}</text>`;
  }
  return s + "</svg>";
}

/* ---------- chapter 3 and 4: example frame and tiers ---------- */
const byPlayer = Object.fromEntries(DATA.entry.rows.map((r) => [r.player, r]));
const TIER_TEXT = {
  1: "Positions only. The model must work out where each alien will be when a shot arrives.",
  2: "The same facts with distances and timings worked out. The target is still the model's choice.",
  3: "The autopilot's own verdicts: what is safe, what to aim at. Here the autopilot decides and JEV agrees.",
};
const TIER_PLAYERS = { 1: ["jev-t1", "qwen-t1", "llm-t1"], 2: ["jev-t2", "qwen-t2", "llm-t2"], 3: ["jev-t3"] };

function setupTiers() {
  $("#example-frame").src = DATA.example.image;
  $("#example-request").textContent = JSON.stringify(DATA.example.tiers["1"].state, null, 1);
  const show = (tier) => {
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tier === tier)));
    $("#tier-text").textContent = TIER_TEXT[tier];
    $("#tier-scores").innerHTML = TIER_PLAYERS[tier].filter((p) => byPlayer[p]).map((p) => {
      const r = byPlayer[p];
      return `<span style="--c:${COLOR(p)}">${esc(r.name)}: ${fmt(r.score)}</span>`;
    }).join("") + `<span style="--c:${COLOR("code")}">Code: ${fmt(byPlayer.code.score)}</span>`;
    $("#tier-json").textContent = JSON.stringify(DATA.example.tiers[tier], null, 1);
  };
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.tier)));
  show("1");
}

/* ---------- chapter 5: quiz ---------- */
function setupQuiz() {
  const box = $("#quiz-box");
  let i = 0, right = 0;
  const render = () => {
    if (i >= DATA.quiz.length) {
      const share = `I matched the autopilot on ${right} of ${DATA.quiz.length} Space Invaders frames. `
        + `Holding FIRE beat the AI: ${location.href.split("#")[0]}`;
      box.innerHTML = `<div><p class="progress">DONE</p></div><div><h3>You matched the autopilot on ${right} of ${DATA.quiz.length}.</h3>
        <p>JEV, given the same frames as numbers, fires whenever its gun is ready, lined up or not.</p>
        <button class="next" id="share">Copy a line to share</button> <button class="next" id="again">Play again</button>
        <p class="small" id="shared" aria-live="polite"></p></div>`;
      $("#again").addEventListener("click", () => { i = 0; right = 0; render(); });
      $("#share").addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(share); $("#shared").textContent = "Copied."; }
        catch { $("#shared").textContent = share; }
      });
      return;
    }
    const q = DATA.quiz[i];
    box.innerHTML = `<div><p class="progress">FRAME ${i + 1}/${DATA.quiz.length} · SCORE ${right}</p>
        <img src="${q.image}" width="240" height="315" alt="Game frame ${i + 1}"></div>
      <div><p>What should the ship do now?</p>
        <div class="actions">${DATA.actions.map((a) => `<button data-a="${a}">${a}</button>`).join("")}</div>
        <p class="verdict" aria-live="polite"></p>
        <details><summary>What a model sees (Tier 1)</summary><pre class="json">${esc(JSON.stringify(q.tier1, null, 1))}</pre></details>
        <p class="small">Seed ${q.seed}, a practice (tuning) seed. <span class="tag tuning">tuning seeds</span></p></div>`;
    box.querySelectorAll(".actions button").forEach((b) => b.addEventListener("click", () => {
      const ok = q.right.includes(b.dataset.a);
      if (ok) right++;
      box.querySelectorAll(".actions button").forEach((x) => {
        x.disabled = true;
        if (q.right.includes(x.dataset.a)) x.classList.add("right");
        if (x.dataset.a === q.code_action) x.classList.add("code");
      });
      if (!ok) b.classList.add("wrong");
      box.querySelector(".verdict").innerHTML = `<strong>${ok ? "Good call." : "Not quite."}</strong> The code chose <code>${q.code_action}</code>. ${esc(q.reason)}
        <br><button class="next">${i + 1 < DATA.quiz.length ? "Next frame" : "See result"}</button>`;
      box.querySelector(".next").addEventListener("click", () => { i++; render(); });
    }));
  };
  render();
}

/* ---------- chapter 6: scoreboard ---------- */
function setupScores() {
  const rows = DATA.entry.rows;
  const draw = (metric) => {
    document.querySelectorAll(".toggle button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.metric === metric)));
    let data, max, value, line = null, lineLabel = "";
    if (metric === "score") {
      data = rows.map((r) => ({ ...r, _v: r.score }));
      max = Math.max(...data.map((r) => r._v), DATA.entry.human);
      value = (r) => fmt(r.score);
      line = DATA.entry.human; lineLabel = `human reference ${DATA.entry.human.toLocaleString("en-US")}`;
    } else if (metric === "latency_ms") {
      // log scale from 0.01 ms: code and the floors take far under 0.1 ms
      data = rows.map((r) => ({ ...r, _v: Math.log10(Math.max(r.latency_ms, 0.01)) + 2 }));
      max = Math.max(...data.map((r) => r._v));
      value = (r) => (r.latency_ms < 0.1 ? "< 0.1 ms" : `${fmt(r.latency_ms)} ms`);
      lineLabel = "log scale";
    } else {
      data = rows.map((r) => ({ ...r, _v: r.cost }));
      max = Math.max(...data.map((r) => r._v));
      value = (r) => (r.player.startsWith("qwen") ? "self-hosted, not counted"
        : r.cost === 0 ? "$0" : `$${r.cost.toFixed(5)}`);
    }
    data.sort((a, b) => b._v - a._v);
    $("#score-chart").innerHTML = barChart({
      rows: data, max, line, lineLabel,
      label: (r) => `${r.name} · ${r.input.replace(": code verdicts (reference)", " (ref)")}`,
      value, color: (r) => COLOR(r.player),
    });
  };
  document.querySelectorAll(".toggle button").forEach((b) => b.addEventListener("click", () => draw(b.dataset.metric)));
  draw("score");
  const jev = byPlayer["jev-t1"], haiku = byPlayer["llm-t1"];
  $("#score-summary").textContent = `JEV beats both LLMs at the same tier, ${Math.round(haiku.latency_ms / jev.latency_ms)}x faster and `
    + `${Math.round(haiku.cost / jev.cost)}x cheaper than Haiku. Evaluation seeds 101-105, turn mode.`;
}

/* ---------- chapter 7: speed ---------- */
function setupSpeed() {
  const players = ["code", "jev-t1", "llm-t1", "qwen-t1"].map((p) => byPlayer[p]);
  const data = players.map((r) => ({ ...r, _v: (r.latency_ms * 60) / 1000 }));
  $("#frames-chart").innerHTML = barChart({
    rows: data, max: Math.max(...data.map((r) => r._v)),
    label: (r) => r.name, color: (r) => COLOR(r.player),
    value: (r) => (r._v < 0.01 ? "0 frames" : `${r._v.toFixed(r._v < 10 ? 1 : 0)} frames`),
    lineLabel: "frames that pass while deciding",
  });
  const [jevTurn, jevReal] = DATA.entry.realtime.jev;
  const [codeTurn, codeReal] = DATA.entry.realtime.code;
  $("#speed-summary").innerHTML = `A bullet falls 1 px per frame. In realtime JEV keeps ${Math.round((100 * jevReal) / jevTurn)}% of its score;
    the autopilot loses nothing (${fmt(codeReal)}).`;
}

/* ---------- chapter 8: waves ---------- */
function setupWaves() {
  const W = 900, H = 340, top = 30, y0 = 100, y1 = 175;
  const Y = (y) => top + ((y - y0) / (y1 - y0)) * (H - top - 60);
  const colW = (W - 120) / DATA.after.waves.length;
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Where each wave starts relative to the landing line">`;
  const lineY = Y(160);
  s += `<line x1="100" x2="${W - 10}" y1="${lineY}" y2="${lineY}" stroke="${css("--orange")}" stroke-width="3" stroke-dasharray="8 5"/>`;
  s += `<text x="92" y="${lineY + 5}" text-anchor="end" fill="${css("--orange")}">landing line</text>`;
  DATA.after.waves.forEach((w, i) => {
    const x = 110 + i * colW, base = Y(w.start_y);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 6; c++) {
      s += `<rect x="${x + 12 + c * 20}" y="${base - r * 16 - 8}" width="12" height="9" fill="${css("--olive")}"/>`;
    }
    s += `<text x="${x + 70}" y="${H - 46}" text-anchor="middle">wave ${w.wave}</text>`;
    s += `<text x="${x + 70}" y="${H - 28}" text-anchor="middle" class="muted">${w.cleared} cleared</text>`;
    s += `<text x="${x + 70}" y="${H - 10}" text-anchor="middle" class="muted">${w.invaded} landed</text>`;
  });
  $("#waves-chart").innerHTML = s + "</svg>";
}

/* ---------- chapter 9: after the deadline ---------- */
function setupAfter() {
  const versions = DATA.code_versions.map((v) => ({ ...v, name: `Code ${v.version}`, player: "code", _v: v.score }));
  $("#versions-chart").innerHTML = barChart({
    rows: versions, max: Math.max(...versions.map((r) => r._v)),
    label: (r) => `${r.name} (${r.games} games)`, value: (r) => fmt(r.score), color: () => css("--code"),
    line: DATA.entry.human, lineLabel: "human reference",
  }) + `<p class="small">Evaluation seeds 101-120. Before these: v1 scored 891 and v2 1,562. Each version took thousands of practice games; v5's best rule, the lowest row first in the last drop, came from the operator watching the video.</p>`;
  $("#rules").innerHTML = DATA.after.code_steps.map((s) =>
    `<li><span class="v">${s.version}</span>${esc(s.rule)} <span class="small">(${esc(s.tuning)})</span></li>`).join("");
  $("#failed").innerHTML = DATA.after.failed.map(([idea, d]) => `<li>Failed: ${esc(idea)} (${esc(d)} per game)</li>`).join("");

  const st = DATA.after.strategy;
  const models = [["JEV", "jev", "jev-t1"], ["Haiku", "haiku", "llm-t1"], ["Qwen", "qwen", "qwen-t1"]];
  const W = 900, rowH = 20, groupH = rowH * 2 * st.labels.length + 32;
  let s = `<svg viewBox="0 0 ${W} ${groupH * models.length}" role="img" aria-label="Right answers without and with the strategy">`;
  models.forEach(([name, key, player], m) => {
    const gy = m * groupH;
    s += `<text x="0" y="${gy + 18}" style="font-weight:600" fill="${COLOR(player)}">${name}</text>`;
    st.labels.forEach((lab, k) => {
      [0, 1].forEach((j) => {
        const y = gy + 28 + (k * 2 + j) * rowH, v = st[key][k][j], w = v * (W - 360);
        s += `<text x="250" y="${y + 15}" text-anchor="end" class="${j ? "" : "muted"}">${j ? "with strategy" : lab}</text>`;
        s += `<rect x="260" y="${y + 4}" width="${Math.max(2, w)}" height="${rowH - 6}" rx="3" fill="${COLOR(player)}" opacity="${j ? 1 : 0.4}"/>`;
        s += `<text x="${266 + w}" y="${y + 15}">${Math.round(v * 100)}%</text>`;
      });
    });
  });
  $("#strategy-chart").innerHTML = s + "</svg>";
  $("#strategy-summary").innerHTML = `Right answers on 300 frames, without and with the autopilot's strategy in the question.
    JEV moves more, but in real games it scored ${st.jev_games}: <strong>knowing what to do is not doing it.</strong>`;

  const nq = DATA.narrow;
  $("#narrow-table").innerHTML = `<table class="data"><thead><tr><th>Question</th><th>JEV right</th>
    <th>Always guessing the most common answer</th></tr></thead><tbody>${nq.questions.map((q) =>
    `<tr><td>${esc(q.question)}</td><td>${Math.round(q.right * 100)}%</td><td>${Math.round(q.guess * 100)}%</td></tr>`).join("")}
    </tbody></table>`;
  const [fl, nl] = [nq.fired.lined_up, nq.fired.not_lined_up];
  $("#narrow-summary").innerHTML = `No better than a constant guess. And it fires whenever the gun is ready:
    ${Math.round((100 * fl[0]) / fl[1])}% when lined up, ${Math.round((100 * nl[0]) / nl[1])}% when not. So it plays like holding FIRE.`;

}

function setupHero() {
  const order = ["code", "always-fire", "jev-t1", "random", "qwen-t1", "llm-t1"];
  const names = { code: "Code Autopilot", "always-fire": "Hold FIRE", "jev-t1": "JEV", random: "Random", "qwen-t1": "Qwen", "llm-t1": "Haiku" };
  // HTML bars, not SVG: the text keeps its size on a phone.
  const max = Math.max(...order.flatMap((p) => byPlayer[p].scores)) * 1.03;
  const pct = (v) => `${(100 * v) / max}%`;
  $("#hero-chart").innerHTML = `<div class="hbars" role="img" aria-label="${order.map((p) => `${names[p]} ${byPlayer[p].score}`).join(", ")}">
    ${order.map((p) => `<div class="hrow"><span class="hname">${names[p]}</span><div class="htrack">
      <div class="hbar" style="width:${pct(byPlayer[p].score)};background:${COLOR(p)}"></div>
      ${byPlayer[p].scores.map((v) => `<i class="hdot" style="left:${pct(v)};border-color:${COLOR(p)}" title="${fmt(v)}"></i>`).join("")}
      </div><span class="hval">${fmt(byPlayer[p].score)}</span></div>`).join("")}
    <div class="hguide"><div class="hhuman" style="left:${pct(DATA.entry.human)}"><span>human ${fmt(DATA.entry.human)}</span></div></div></div>`;
}

setupHero();
setupTerms();
setupTiers();
setupQuiz();
setupScores();
setupSpeed();
setupWaves();
setupAfter();
