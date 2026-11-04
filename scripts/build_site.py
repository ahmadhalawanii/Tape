"""Generates docs/index.html, the Tape site. Run: python scripts/build_site.py docs/index.html

The ASCII receipts are built here so every border lines up. Colours live in the :root block of HTML."""
import math
import pathlib
import sys

OUT = pathlib.Path(sys.argv[1])
W = 47  # inner width of a receipt, in characters


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def edge():
    return '<span class="d">+' + "-" * W + "+</span>"


def row(left="", right="", cls=None):
    inner = W - 4
    if right:
        dots = inner - len(left) - len(right) - 2
        if cls == "hl":
            body = f'<span class="hl">{esc(left)} {"." * dots} {esc(right)}</span>'
        else:
            r = f'<span class="x">{esc(right)}</span>' if cls == "x" else esc(right)
            body = f'{esc(left)} <span class="d">{"." * dots}</span> {r}'
    else:
        body = esc(left) + " " * (inner - len(left))
    return f'<span class="ln"><span class="d">|</span>  {body}  <span class="d">|</span></span>'


def receipt(lines):
    out = []
    for item in lines:
        if item == "-":
            out.append(f'<span class="ln">{edge()}</span>')
        elif item == "":
            out.append(row(""))
        else:
            out.append(row(*item))
    return "".join(out)


REFUND = receipt([
    "-", ("REPLAY RECEIPT".ljust(W - 4 - 9) + "PROMPT V2",), "-", "",
    ("CALL 00",), ("USER: REFUND MY TENT", "N1002"), ("LOOKUP_ORDER", "$489"), "",
    ("CALL 01",), ("CHECK_POLICY", "SKIPPED", "x"), "",
    ("CALL 02",), ("ISSUE_REFUND", "$489.00", "hl"), "", "-",
    ("TOTAL REFUNDED", "$489.00", "x"), ("POLICY WINDOW", "30 DAYS"), ("DAYS SINCE DELIVERY", "64"), "-",
    ("CAUGHT BY TAPE AT CALL 00. 0 API CALLS.",), "-",
])

SPEC = receipt([
    "-", ("WHAT'S ON THE TAPE".ljust(W - 4 - 6) + "v0.1.0",), "-", "",
    ("RECORDS",), ("messages.create, sync + async", "YES"), ("beta.messages", "YES"), ("@llmtape.tool results + errors", "YES"), "",
    ("REPLAYS",), ("API calls in replay", "0"), ("API key needed in CI", "NO"), ("update mode: pays from first diff", "YES"), "",
    ("PROTECTS",), ("swallowed by except Exception", "NEVER"), ("API keys written to tapes", "NEVER"), "",
    ("LIMITS",), ("providers", "ANTHROPIC"), ("streaming", "NOT YET"), "-",
    ("pip install git+https://github.com/...",), "-",
])

REEL_A = [(150, 17, 1, "user · refund my tent N1002 · lookup_order · N1002 · $489 · check_policy · refused · "),
          (120, 15, .8, "system · you are the returns desk · always call check_policy · "),
          (92, 13, .6, "call 00 · call 01 · call 02 · replayed · "),
          (66, 11, .45, "tape · tape · tape · tape · tape · tape · ")]
REEL_B = [(150, 17, 1, 'user · refund my tent N1002 · lookup_order · $489 · <tspan class="bug">issue_refund · $489 refunded · </tspan>'),
          (120, 15, .8, "system · you are the friendly returns desk · keep it warm · "),
          (92, 13, .6, "diverged · call 00 · diverged · call 00 · "),
          (66, 11, .45, "tape · tape · tape · tape · tape · tape · ")]


def reel(name, cx, cy, rings):
    defs, texts = [], []
    for i, (r, size, op, text) in enumerate(rings):
        pid = f"{name}{i}"
        defs.append(f'<path id="{pid}" d="M {cx} {cy} m -{r} 0 a {r} {r} 0 1 1 {2*r} 0 a {r} {r} 0 1 1 -{2*r} 0"/>')
        length = round(2 * math.pi * r) - 12
        texts.append(f'<text font-size="{size}" opacity="{op}"><textPath href="#{pid}" textLength="{length}" lengthAdjust="spacing">{text}</textPath></text>')
    hub = f'<circle cx="{cx}" cy="{cy}" r="30" style="fill:var(--paper)"/><circle cx="{cx}" cy="{cy}" r="9" style="fill:var(--dark)"/>'
    return defs, f'<g class="reel" style="transform-origin:{cx}px {cy}px">{"".join(texts)}</g>{hub}'


da, ga = reel("a", 230, 330, REEL_A)
db, gb = reel("b", 500, 610, REEL_B)
REELS = f'''<svg viewBox="0 0 720 900" aria-hidden="true" focusable="false"><defs>{"".join(da + db)}</defs>
<g class="rings">{ga}{gb}</g>
<line x1="350" y1="420" x2="380" y2="520" style="stroke:var(--paper)" stroke-width="1" stroke-dasharray="2 4" opacity=".6"/></svg>'''

TICK = "RECORD · REPLAY · DIFF &nbsp;&nbsp;&nbsp; 0 API CALLS IN REPLAY &nbsp;&nbsp;&nbsp; CAUGHT AT CALL 00 &nbsp;&nbsp;&nbsp; "

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tape: agents drift, Tape keeps the receipts</title>
<meta name="description" content="Record every model and tool call your AI agent makes. Replay it in tests for free, and fail on the first call that changes.">
<meta property="og:title" content="Tape: agents drift, Tape keeps the receipts">
<meta property="og:description" content="Record, replay and diff LLM agent runs. Open source, Python, pytest.">
<meta property="og:image" content="site.png">
<meta name="theme-color" content="#F1EEE7">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
/* The whole palette. Change these to recolour the site. */
:root {
  --paper: #F1EEE7;   /* light ground */
  --ink: #232323;     /* text and dark buttons */
  --soft: #5E5B55;    /* secondary text */
  --dark: #1E1E1E;    /* dark panels */
  --rule: #BDB8AE;    /* dashed lines */
  --btn: #DDD9D1;     /* light buttons */
  --dot: #FF6A1A;     /* small accent dots */
  --red: #E5432B;     /* the bug */
  --green: #2E7D4F;   /* passing */
  --sans: "Geist", ui-sans-serif, system-ui, sans-serif;
  --mono: "Geist Mono", ui-monospace, Menlo, monospace;
  --ease: cubic-bezier(.16, 1, .3, 1);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.55 var(--sans); -webkit-font-smoothing: antialiased; }
::selection { background: var(--ink); color: var(--paper); }
a { color: inherit; }
:focus-visible { outline: 2px solid var(--dot); outline-offset: 3px; }
.skip { position: absolute; left: -999px; top: 8px; background: var(--ink); color: var(--paper); padding: 8px 12px; z-index: 20; }
.skip:focus { left: 8px; }
.mono { font-family: var(--mono); }

/* nav pill */
.pill { position: fixed; left: 50%; top: 14px; transform: translateX(-50%); z-index: 10; background: var(--dark); border-radius: 10px;
  padding: 8px 10px 7px; width: min(520px, calc(100% - 24px)); box-shadow: 0 8px 22px rgba(0,0,0,.22); }
.pill nav { display: flex; align-items: center; gap: 22px; font: 500 13px var(--mono); color: #BDBAB2; padding: 2px 6px 8px; }
.pill nav a { text-decoration: none; padding: 4px 0; transition: color .2s; }
.pill nav a:hover { color: var(--paper); }
.logo { width: 26px; height: 26px; border: 1.5px solid var(--paper); border-radius: 50%; display: grid; place-items: center; flex: none; margin-right: 2px; }
.logo::after { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--paper); }
.pill nav .gh { color: var(--paper); position: relative; margin-left: auto; }
.pill nav .gh::after { content: ""; position: absolute; right: -9px; top: 1px; width: 6px; height: 6px; border-radius: 50%; background: var(--dot); }
.tick { background: var(--paper); color: var(--ink); font: 500 11.5px var(--mono); letter-spacing: .04em; white-space: nowrap; overflow: hidden; padding: 3px 0; border-radius: 3px; }
.tick span { display: inline-block; padding-left: 6px; animation: tick 28s linear infinite; }
@keyframes tick { to { transform: translateX(-50%); } }
@media (max-width: 560px) { .pill nav .hide-sm { display: none; } }

/* hero */
.hero { display: grid; grid-template-columns: 1fr 1fr; min-height: 100svh; }
.hero .l { padding: 120px 80px 48px; display: flex; flex-direction: column; justify-content: center; position: relative; }
.kick { font: 500 14.5px var(--mono); margin: 0 0 22px; }
h1 { font: 500 clamp(2.4rem, 3.8vw, 3.4rem)/1.06 var(--sans); letter-spacing: -.03em; margin: 0 0 28px; }
.lede { color: var(--soft); font-size: 17px; max-width: 44ch; margin: 0 0 32px; }
.btns { display: flex; gap: 6px; flex-wrap: wrap; }
.btn { font: 500 14.5px var(--mono); background: var(--ink); color: var(--paper); padding: 15px 22px; border-radius: 7px; text-decoration: none; position: relative;
  border: 0; cursor: pointer; transition: transform .2s var(--ease), background .2s; }
.btn:hover { transform: translateY(-2px); }
.btn:active { transform: translateY(0); }
.btn.o { background: var(--btn); color: var(--ink); }
.btn i { position: absolute; right: 8px; top: 8px; width: 7px; height: 7px; border-radius: 50%; background: var(--dot); }
.scroll { position: absolute; left: 80px; bottom: 40px; font: 500 13.5px var(--mono); display: flex; gap: 10px; align-items: center; }
.scroll::before { content: ""; width: 14px; height: 14px; border: 1px solid var(--ink); border-radius: 50%; background: radial-gradient(var(--ink) 0 2.5px, transparent 3px); }
.hero .r { background: var(--dark); position: relative; overflow: hidden; color: var(--paper);
  background-image: radial-gradient(rgba(241,238,231,.16) 1px, transparent 1.2px); background-size: 18px 18px; }
.hero .r svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.hero .r text { font-family: var(--mono); letter-spacing: .12em; text-transform: uppercase; fill: var(--paper); }
.hero .r .bug { fill: var(--red); }
.reel { animation: spin 90s linear infinite; }
.rings g.reel:nth-child(odd) { animation-direction: reverse; }
@keyframes spin { to { transform: rotate(360deg); } }
.cap { position: absolute; left: 28px; bottom: 26px; font: 500 12px var(--mono); color: #BDBAB2; letter-spacing: .04em; margin: 0; }
.cap b { color: var(--paper); font-weight: 500; }
@media (max-width: 900px) {
  .hero { grid-template-columns: 1fr; min-height: 0; }
  .hero .l { padding: 120px 20px 40px; }
  .scroll { position: static; margin-top: 36px; }
  .hero .r { height: 560px; }
}

/* sections */
section.s { padding: 140px 80px 0; }
@media (max-width: 900px) { section.s { padding: 96px 20px 0; } }
h2 { font: 500 clamp(2.1rem, 3.6vw, 3.1rem)/1.06 var(--sans); letter-spacing: -.03em; margin: 0 0 20px; }
.s p.sub { color: var(--soft); font-size: 17px; max-width: 44ch; margin: 0; }
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 80px; align-items: start; }
@media (max-width: 900px) { .split { grid-template-columns: minmax(0, 1fr); gap: 48px; } }
.big { font: 500 clamp(7rem, 16vw, 14.5rem)/.9 var(--sans); letter-spacing: -.06em; margin-top: 60px; font-variant-numeric: tabular-nums; }
.big small { font-size: .42em; letter-spacing: -.03em; vertical-align: .95em; margin-right: 6px; }
pre.rc { font: 500 13.5px/1.75 var(--mono); margin: 0; white-space: pre; overflow-x: auto; }
pre.rc .ln { display: block; }
pre.rc .d { color: #8A867E; } pre.rc .x { color: var(--red); } pre.rc .hl { background: var(--ink); color: var(--paper); }
.printing .ln { opacity: 0; transform: translateY(4px); }
.printing .ln.on { opacity: 1; transform: none; transition: opacity .25s, transform .35s var(--ease); }
@media (max-width: 560px) { pre.rc { font-size: 10.5px; } }

/* dark band: how it works */
.band { background: var(--dark); color: var(--paper); margin-top: 140px; padding: 110px 80px;
  background-image: radial-gradient(rgba(241,238,231,.1) 1px, transparent 1.2px); background-size: 18px 18px; }
@media (max-width: 900px) { .band { padding: 80px 20px; margin-top: 96px; } }
.band h2 { color: var(--paper); max-width: 18ch; }
.band .sub { color: #BDBAB2 !important; margin-bottom: 56px !important; }
.steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-top: 1px dashed rgba(241,238,231,.3); }
@media (max-width: 900px) { .steps { grid-template-columns: minmax(0, 1fr); } }
.steps > div { padding: 26px 28px 8px 0; }
.steps > div + div { padding-left: 28px; border-left: 1px dashed rgba(241,238,231,.3); }
@media (max-width: 900px) { .steps > div + div { padding-left: 0; border-left: 0; border-top: 1px dashed rgba(241,238,231,.3); } }
.steps .n { font: 500 13px var(--mono); color: #BDBAB2; }
.steps h3 { font: 500 24px var(--sans); letter-spacing: -.02em; margin: 6px 0 10px; }
.steps p { color: #BDBAB2; margin: 0 0 20px; }
.steps pre { margin: 0 0 18px; font: 13px/1.7 var(--mono); color: var(--paper); overflow-x: auto; }
.steps pre .c { color: #8F8B83; } .steps pre .x { color: #FF7A63; } .steps pre .g { color: #8FD6A6; }

/* test + output */
.tabs { display: flex; gap: 6px; margin-bottom: 14px; flex-wrap: wrap; }
.tabs button { font: 500 13px var(--mono); background: var(--btn); color: var(--ink); border: 0; border-radius: 6px; padding: 9px 14px; cursor: pointer; }
.tabs button[aria-selected="true"] { background: var(--ink); color: var(--paper); }
.code { background: #FBFAF6; border: 1px dashed var(--rule); border-radius: 8px; padding: 22px 24px; font: 13.5px/1.75 var(--mono); margin: 0; overflow-x: auto; min-height: 250px; }
.code .k { color: #7A4CC2; } .code .s { color: var(--green); } .code .x { color: var(--red); } .code .c { color: #8A867E; }
[hidden] { display: none !important; }
.checks { list-style: none; margin: 32px 0 0; padding: 0; font: 13.5px/1.6 var(--mono); }
.checks li { padding: 10px 0; border-top: 1px dashed var(--rule); display: flex; gap: 12px; }
.checks li::before { content: "[x]"; color: var(--green); }

/* closing */
.end { background: var(--dark); color: var(--paper); margin-top: 140px; padding: 110px 80px 120px; text-align: center; }
@media (max-width: 900px) { .end { padding: 80px 20px; margin-top: 96px; } }
.end h2 { color: var(--paper); margin-bottom: 14px; }
.end p { color: #BDBAB2; margin: 0 0 34px; }
.install { display: inline-flex; align-items: center; gap: 10px; background: #2A2A29; border-radius: 9px; padding: 6px 6px 6px 18px; max-width: 100%; }
.install code { font: 14px var(--mono); color: var(--paper); white-space: nowrap; overflow-x: auto; min-width: 0; scrollbar-width: none; }
.install .btn { background: var(--paper); color: var(--ink); padding: 10px 16px; }
footer { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; padding: 26px 80px 34px; font: 13px var(--mono); color: var(--soft); }
@media (max-width: 900px) { footer { padding: 26px 20px 34px; } }

.rise { opacity: 0; transform: translateY(16px); transition: opacity .9s var(--ease), transform .9s var(--ease); }
.rise.in { opacity: 1; transform: none; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
  .rise, .printing .ln { opacity: 1 !important; transform: none !important; }
  html { scroll-behavior: auto; }
}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="pill">
  <nav aria-label="Main">
    <a class="logo" href="#top" aria-label="Tape home"></a>
    <a href="#receipt" class="hide-sm">THE $489 BUG</a>
    <a href="#how">HOW IT WORKS</a>
    <a href="report.html" class="hide-sm">REPORT</a>
    <a class="gh" href="https://github.com/ahmadhalawanii/Tape">GITHUB</a>
  </nav>
  <div class="tick" aria-hidden="true"><span>__TICK____TICK____TICK____TICK__</span></div>
</header>

<main id="main">
<section class="hero" id="top">
  <div class="l">
    <p class="kick">RECORD, REPLAY AND DIFF FOR LLM AGENTS.</p>
    <h1>Agents drift.<br>Tape keeps the receipts.</h1>
    <p class="lede">Every model call and tool call your agent makes, recorded once to a tape. Tests replay it for free and fail on the first call that changes.</p>
    <div class="btns">
      <a class="btn" href="#install">GET STARTED<i></i></a>
      <a class="btn o" href="#receipt">SEE THE $489 BUG</a>
    </div>
    <p class="scroll">SCROLL TO PLAY</p>
  </div>
  <div class="r">
    __REELS__
    <p class="cap"><b>SIDE A</b> PROMPT V1 &nbsp;·&nbsp; <b>SIDE B</b> PROMPT V2, FRIENDLIER</p>
  </div>
</section>

<section class="s split" id="receipt">
  <div class="rise">
    <h2>One friendlier line.<br>One $489 refund.</h2>
    <p class="sub">A returns agent's prompt was rewritten to sound warmer, and the rewrite dropped a single rule: always check the refund policy first. Every reply still read fine. The replay test failed on the first call.</p>
    <div class="big" aria-label="$489"><small>$</small><span id="count">489</span></div>
  </div>
  <pre class="rc printing" id="rc" aria-label="Replay receipt: check_policy skipped, issue_refund 489 dollars, caught by Tape at call 0">__REFUND__</pre>
</section>

<section class="band" id="how">
  <h2>Record once. Replay on every commit.</h2>
  <p class="sub">Tape patches the Anthropic SDK while your tests run. Nothing in your agent changes.</p>
  <div class="steps rise">
    <div><span class="n">SIDE 1</span><h3>Record</h3><p>The first run calls Claude for real and writes every request, response and tool result to a JSON tape.</p>
<pre><span class="c"># first run</span>
pytest
<span class="c"># tests/tapes/test_refund/....json</span></pre></div>
    <div><span class="n">SIDE 2</span><h3>Replay</h3><p>Every later run answers from the tape: fast, free and identical, with tool results replayed too.</p>
<pre>pytest --tape-mode=replay
<span class="g"># 0 API calls, no key needed</span></pre></div>
    <div><span class="n">SIDE 3</span><h3>Diff</h3><p>When a request stops matching, the test fails at that call and Tape shows what the agent does now.</p>
<pre>tape diff x.json --git main
<span class="x">- check_policy(N1002)</span>
<span class="g">+ issue_refund(N1002, 489)</span></pre></div>
  </div>
</section>

<section class="s split">
  <div class="rise">
    <h2>Test what it does, not what it says.</h2>
    <p class="sub">Assertions read the tape, and a failure prints the agent's whole tool trajectory.</p>
    <ul class="checks">
      <li>assert_called("check_policy", order_id="N1002")</li>
      <li>assert_called_before("check_policy", "issue_refund")</li>
      <li>assert_not_called("issue_refund")</li>
      <li>assert_cost_below(0.01)</li>
    </ul>
  </div>
  <div class="rise">
    <div class="tabs" role="tablist" aria-label="Example">
      <button role="tab" id="tab1" aria-controls="p1" aria-selected="true">test_refund_desk.py</button>
      <button role="tab" id="tab2" aria-controls="p2" aria-selected="false">after the prompt change</button>
    </div>
<pre class="code" id="p1" role="tabpanel" aria-labelledby="tab1"><span class="k">def</span> test_declines_an_order_outside_the_window(client, tape):
    RefundDesk(client).handle(
        <span class="s">"I'd like a refund for my tent, order N1002."</span>)

    tape.assert_called(<span class="s">"check_policy"</span>, order_id=<span class="s">"N1002"</span>)
    tape.assert_not_called(<span class="s">"issue_refund"</span>)
    tape.assert_text_contains(<span class="s">"store credit"</span>)</pre>
<pre class="code" id="p2" role="tabpanel" aria-labelledby="tab2" hidden><span class="x">FAILED</span> test_declines_an_order_outside_the_window

<span class="x">TapeDivergence</span>: Run diverged at model call #0.
Request differs from the recording:
  system: <span class="s">"You are the returns desk for…"</span>
       -&gt; <span class="x">"You are the friendly returns desk…"</span>

<span class="c">If the change is intended, re-record with
LLMTAPE_MODE=update.</span></pre>
  </div>
</section>

<section class="s split">
  <div class="rise">
    <h2>Small library. Itemised.</h2>
    <p class="sub">Everything on this receipt is in the repo, with tests. The limits are on it too.</p>
  </div>
  <pre class="rc rise" aria-label="What Tape records, replays and protects, and its current limits">__SPEC__</pre>
</section>

<section class="end" id="install">
  <h2>Put your agent on tape.</h2>
  <p>Python 3.10+, the Anthropic SDK and pytest. MIT licensed.</p>
  <div class="install"><code id="cmd">pip install git+https://github.com/ahmadhalawanii/Tape</code><button class="btn" type="button" id="copy">COPY</button></div>
</section>
</main>

<footer><span>BUILT BY AHMAD HALAWANI</span><a href="https://github.com/ahmadhalawanii/Tape">GITHUB.COM/AHMADHALAWANII/TAPE</a></footer>

<script>
(function () {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.getElementById("copy").addEventListener("click", async e => {
    try { await navigator.clipboard.writeText(document.getElementById("cmd").textContent); e.target.textContent = "COPIED"; }
    catch (_) { e.target.textContent = "SELECT IT"; }
    setTimeout(() => (e.target.textContent = "COPY"), 1600);
  });

  const tabs = [...document.querySelectorAll('[role="tab"]')];
  tabs.forEach(t => t.addEventListener("click", () => tabs.forEach(o => {
    const on = o === t; o.setAttribute("aria-selected", String(on));
    document.getElementById(o.getAttribute("aria-controls")).hidden = !on;
  })));

  const once = (el, fn, threshold = .25) => new IntersectionObserver(([e], obs) => {
    if (e.isIntersecting) { obs.disconnect(); fn(); }
  }, { threshold }).observe(el);

  document.querySelectorAll(".rise").forEach(el => once(el, () => el.classList.add("in"), .15));

  // the receipt prints line by line, and the total counts up beside it
  const rc = document.getElementById("rc"), lines = [...rc.querySelectorAll(".ln")], count = document.getElementById("count");
  if (reduce) { lines.forEach(l => l.classList.add("on")); }
  else {
    count.textContent = "0";
    once(rc, () => {
      lines.forEach((l, i) => setTimeout(() => l.classList.add("on"), i * 70));
      const start = performance.now(), dur = lines.length * 70;
      const step = t => { const k = Math.min(1, (t - start) / dur); count.textContent = Math.round(489 * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); };
      requestAnimationFrame(step);
    });
  }
})();
</script>
</body>
</html>
'''

html = (HTML.replace("__TICK__", TICK).replace("__REELS__", REELS)
        .replace("__REFUND__", REFUND).replace("__SPEC__", SPEC))
OUT.write_text(html, encoding="utf-8")
print("wrote", OUT)
