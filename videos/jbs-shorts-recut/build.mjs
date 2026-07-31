// Generator: builds public/cards/*.html and public/index.html from CARDS[] below.
// JBS brand: Deep Navy #1B2A3B canvas, Dark Slate #0F1C2B panels, Teal #4DD9C0 primary,
// Sky Blue #5BCFEA secondary, Blue-Purple #8B9FD4 tertiary. Nunito (display) / JetBrains Mono (data).
//
// v2 revisions from creator feedback:
//  - panel moved from bottom (TikTok caption/username zone) to top, below the
//    Following/For You safe zone
//  - every text reveal re-timed to the actual spoken moment (offsets below are
//    derived from transcript.json word timestamps, not fixed template beats)
//  - punch-in zooms on #video-wrap at emphasis words, kept to moments with no
//    competing card motion
import fs from "node:fs";
import path from "node:path";

const FPS = 30;
const W = 1080, H = 1920;
const DURATION = 270.14;

const ACCENTS = ["#4DD9C0", "#5BCFEA", "#8B9FD4"];

// TikTok safe zone (1080x1920): keep clear of the top ~180px (status bar +
// Following/For You tabs) and the bottom ~320px (caption/username/sound).
// Panel now anchors to the TOP, starting just below that exclusion band.
const SAFE_TOP = 210;

// archetype: "glass" (top text panel), "list" (stacked chips + punch),
// "hero" (full takeover data hit), "outro" (closing sting, video hidden)
// `*At` fields are seconds *relative to card.start* — set from transcript.json
// so a reveal never lands before the word is actually spoken.
const CARDS = [
  {
    id: "card-01", archetype: "glass", start: 0.04, end: 22.45, accent: 0,
    kicker: "HERE WE GO AGAIN",
    title: "“The water argument”",
    detail: "If your case against AI is data-center water use — do your homework. And get off social media.",
    kickerAt: 0.2, titleAt: 12.7, detailAt: 20.2,
  },
  {
    id: "card-02", archetype: "glass", start: 22.5, end: 31.28, accent: 1,
    kicker: "THE LOGIC GAP",
    title: "You can’t say both",
    detail: "“I’ll never use AI — the data centers waste too much water.”",
    kickerAt: 0.2, titleAt: 0.6, detailAt: 1.1,
  },
  {
    id: "card-03", archetype: "glass", start: 31.32, end: 37.72, accent: 1,
    kicker: "FACT",
    title: "Data centers aren’t new",
    detail: "Around for decades. They’re everywhere.",
    kickerAt: 0.1, titleAt: 1.0, detailAt: 1.6,
  },
  {
    id: "card-04", archetype: "list", start: 37.76, end: 55.2, accent: 0,
    kicker: "EVERYTHING RUNS ON ONE",
    items: ["FACEBOOK", "INSTAGRAM", "TIKTOK", "→ DATA CENTER"],
    punch: "Your point is moot.",
    kickerAt: 0.1, chipAts: [3.3, 6.0, 8.1, 9.2], punchAt: 14.0,
  },
  {
    id: "card-05", archetype: "glass", start: 55.24, end: 89.96, accent: 2,
    kicker: "A REAL EXAMPLE",
    title: "MLB deadline flyer",
    detail: "A buddy’s small business used AI to whip up a sale flyer before the MLB trading deadline. It saved him time — that’s the whole point.",
    kickerAt: 0.2, titleAt: 8.5, detailAt: 9.2,
  },
  {
    id: "card-06", archetype: "glass", start: 90.0, end: 108.48, accent: 0,
    kicker: "13 YEARS A DESIGNER",
    title: "AI didn’t replace him",
    detail: "The shirts, the hats, the designs — still all him. He just doesn’t use AI for that part.",
    kickerAt: 0.2, titleAt: 8.3, detailAt: 11.3,
  },
  {
    id: "card-07", archetype: "glass", start: 108.52, end: 117.8, accent: 0,
    kicker: "WHERE AI ACTUALLY HELPS",
    title: "The monotonous stuff",
    detail: "Take advantage of the busywork it removes — keep the creativity.",
    kickerAt: 0.2, titleAt: 2.2, detailAt: 4.0,
  },
  {
    id: "card-08", archetype: "glass", start: 117.84, end: 155.47, accent: 1,
    kicker: "FROM THE COMMENTS",
    title: "“How many bottles of water did you drink at Kinko’s?”",
    detail: "Before AI, flyers meant driving to Kinko’s to print. Nobody billed that water — but suddenly this counts?",
    kickerAt: 0.2, titleAt: 9.6, detailAt: 16.5,
  },
  {
    id: "card-09", archetype: "glass", start: 155.47, end: 169.26, accent: 2,
    kicker: "SAME THING, NEW NAME",
    title: "“The cloud” = a data center",
    detail: "Social media running on “the cloud” is the same infrastructure as AI. It's essentially identical.",
    kickerAt: 0.2, titleAt: 6.5, detailAt: 10.2,
  },
  {
    id: "card-10", archetype: "hero", start: 169.3, end: 189.84, accent: 0,
    kicker: "FACTUAL TRIVIA",
    number: "20", numberSuffix: "TRILLION",
    label: "gallons of water spent yearly on U.S. corn production",
    kickerAt: 2.4, numberAt: 13.6, suffixAt: 14.5, labelAt: 15.7,
    punchZoom: true,
  },
  {
    id: "card-11", archetype: "glass", start: 189.88, end: 198.56, accent: 0,
    kicker: "FAIR ENOUGH",
    title: "“Well — it's corn. We eat it.”",
    detail: "That's a valid use of the water. Unless…",
    kickerAt: 0.2, titleAt: 5.7, detailAt: 6.3,
  },
  {
    id: "card-12", archetype: "hero", start: 198.6, end: 212.96, accent: 1,
    kicker: "UNLESS…",
    number: "99%", numberSuffix: "→ ETHANOL",
    label: "Only ~1% of that corn water is actually consumed as food.",
    kickerAt: 0.1, numberAt: 10.7, suffixAt: 12.6, labelAt: 2.8,
    punchZoom: true,
  },
  {
    id: "card-13", archetype: "glass", start: 213.0, end: 232.96, accent: 2,
    kicker: "THE DOUBLE STANDARD",
    title: "Where's the corn outrage?",
    detail: "If AI's water use bothers you this much, go ask a golf course what its water bill looks like.",
    kickerAt: 0.2, titleAt: 0.5, detailAt: 15.0,
  },
  {
    id: "card-14", archetype: "glass", start: 233.0, end: 247.86, accent: 1,
    kicker: "STILL FRESH",
    title: "This argument isn't dying down",
    detail: "AI is still new — the takes will keep coming. Don't outsource your opinion to whoever sounds smart on TikTok. Even me.",
    kickerAt: 0.2, titleAt: 4.0, detailAt: 10.3,
  },
  {
    id: "card-15", archetype: "glass", start: 247.9, end: 261.53, accent: 0,
    kicker: "DO THE WORK",
    title: "Fact-check it yourself",
    detail: "Go verify the numbers — don't just take a confident TikTok voice at its word.",
    kickerAt: 0.2, titleAt: 2.3, detailAt: 5.0,
  },
  {
    id: "card-16", archetype: "glass", start: 261.53, end: 267.76, accent: 2,
    kicker: "THE REAL RISK",
    title: "A couple bad apples",
    detail: "Fast news is great — until misinformation from a few voices messes it up for everybody else.",
    kickerAt: 0.15, titleAt: 0.35, detailAt: 3.0,
    punchZoom: true,
  },
  {
    id: "card-17", archetype: "outro", start: 267.76, end: 270.14, accent: 0,
    kicker: "END RANT",
    title: "joeBuilds systems",
    detail: "Build the system. Every word counts.",
  },
];

// Extra punch-in zooms on the talking-head video itself, synced to emphasis
// words that land inside cards with no competing on-screen text motion at that
// instant (verified against each card's *At offsets above).
const PUNCHES = [
  { at: 53.5, hold: 0.6 },   // "Your point is moot." (card-04, after chips settle)
  { at: 130.3, hold: 0.7 },  // "...at Kinko's?" gut-punch (card-08)
  { at: 154.7, hold: 0.6 },  // "...hilarious" (card-09 lead-in)
  { at: 211.3, hold: 0.7 },  // "Ethanol." reveal (card-12, syncs with suffix)
];

const WORK = path.resolve(new URL(".", import.meta.url).pathname);
const CARDS_DIR = path.join(WORK, "public", "cards");
fs.mkdirSync(CARDS_DIR, { recursive: true });

function esc(s) {
  return String(s);
}

function glassCardHtml(c) {
  const accent = ACCENTS[c.accent % ACCENTS.length];
  return `<div class="card" data-card-id="${c.id}">
  <style>
    .card[data-card-id="${c.id}"] .root {
      width: 100%; height: 100%;
      display: flex; align-items: flex-start; justify-content: center;
      padding: ${SAFE_TOP}px 32px 0;
      font-family: 'Nunito Sans', 'Inter', sans-serif;
      background: transparent;
    }
    .card[data-card-id="${c.id}"] .panel {
      width: 100%;
      max-width: 1016px;
      background: rgba(15,28,43,0.86);
      border: 1px solid rgba(77,217,192,0.35);
      border-radius: 16px;
      padding: 32px 32px 36px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.45);
      backdrop-filter: blur(10px);
    }
    .card[data-card-id="${c.id}"] .rule {
      width: 0; height: 4px; border-radius: 4px;
      background: linear-gradient(90deg, ${accent}, #8B9FD4);
      margin-bottom: 16px;
    }
    .card[data-card-id="${c.id}"] .kicker {
      font-family: 'JetBrains Mono', monospace;
      font-size: 20px; font-weight: 500; letter-spacing: 0.14em;
      color: ${accent}; text-transform: uppercase; margin-bottom: 14px;
    }
    .card[data-card-id="${c.id}"] .title {
      font-family: 'Nunito', sans-serif; font-weight: 900;
      font-size: 56px; line-height: 1.12; color: #FFFFFF; margin: 0 0 16px;
    }
    .card[data-card-id="${c.id}"] .detail {
      font-family: 'Nunito Sans', sans-serif; font-weight: 400;
      font-size: 32px; line-height: 1.45; color: #A8B8CC; margin: 0;
    }
  </style>
  <div class="root">
    <div class="panel">
      <div class="rule" id="${c.id}-rule" data-anim="grow-x" data-anim-at="0.15" data-anim-duration="0.45" data-anim-target-w="120"></div>
      <div class="kicker" id="${c.id}-kicker" data-anim="fade-in" data-anim-at="0.2" data-anim-duration="0.4">${esc(c.kicker)}</div>
      <h1 class="title" id="${c.id}-title" data-anim="slide-in" data-anim-at="0.3" data-anim-duration="0.5" data-anim-from="bottom" data-anim-distance="24">${esc(c.title)}</h1>
      <p class="detail" id="${c.id}-detail" data-anim="fade-in" data-anim-at="0.55" data-anim-duration="0.5">${esc(c.detail)}</p>
    </div>
  </div>
</div>`;
}

function listCardHtml(c) {
  const accent = ACCENTS[c.accent % ACCENTS.length];
  const chipRows = c.items.map((item, i) => {
    const isArrow = item.startsWith("→");
    return `<div class="chip${isArrow ? " chip-final" : ""}" id="${c.id}-chip-${i}" data-anim="slide-in" data-anim-at="${(0.15 + i * 0.28).toFixed(2)}" data-anim-duration="0.4" data-anim-from="left" data-anim-distance="40">${esc(item)}</div>`;
  }).join("\n      ");
  return `<div class="card" data-card-id="${c.id}">
  <style>
    .card[data-card-id="${c.id}"] .root {
      width: 100%; height: 100%;
      display: flex; align-items: flex-start; justify-content: center;
      padding: ${SAFE_TOP}px 32px 0;
      font-family: 'Nunito Sans', sans-serif;
      background: transparent;
    }
    .card[data-card-id="${c.id}"] .panel {
      width: 100%; max-width: 1016px;
      background: rgba(15,28,43,0.88);
      border: 1px solid rgba(77,217,192,0.35);
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.45);
      backdrop-filter: blur(10px);
    }
    .card[data-card-id="${c.id}"] .kicker {
      font-family: 'JetBrains Mono', monospace;
      font-size: 20px; font-weight: 500; letter-spacing: 0.14em;
      color: ${accent}; text-transform: uppercase; margin-bottom: 20px;
    }
    .card[data-card-id="${c.id}"] .chip {
      font-family: 'JetBrains Mono', monospace; font-weight: 500;
      font-size: 34px; color: #FFFFFF;
      border-left: 4px solid ${accent};
      padding: 8px 0 8px 18px; margin-bottom: 10px;
    }
    .card[data-card-id="${c.id}"] .chip-final {
      color: ${accent}; font-weight: 700;
    }
    .card[data-card-id="${c.id}"] .punch {
      font-family: 'Nunito', sans-serif; font-weight: 900;
      font-size: 48px; color: #FFFFFF; margin: 18px 0 0;
    }
  </style>
  <div class="root">
    <div class="panel">
      <div class="kicker" id="${c.id}-kicker" data-anim="fade-in" data-anim-at="0.1" data-anim-duration="0.4">${esc(c.kicker)}</div>
      ${chipRows}
      <p class="punch" id="${c.id}-punch" data-anim="scale-pop" data-anim-at="1.5" data-anim-duration="0.5">${esc(c.punch)}</p>
    </div>
  </div>
</div>`;
}

function heroCardHtml(c) {
  const accent = ACCENTS[c.accent % ACCENTS.length];
  const isNumeric = /^[0-9]+$/.test(c.number);
  return `<div class="card" data-card-id="${c.id}">
  <style>
    .card[data-card-id="${c.id}"] .root {
      width: 100%; height: 100%;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      text-align: center; padding: 0 48px;
      font-family: 'Nunito Sans', sans-serif;
      background: rgba(27,42,59,0.55);
    }
    .card[data-card-id="${c.id}"] .kicker {
      font-family: 'JetBrains Mono', monospace;
      font-size: 24px; font-weight: 500; letter-spacing: 0.18em;
      color: ${accent}; text-transform: uppercase; margin-bottom: 28px;
    }
    .card[data-card-id="${c.id}"] .number {
      font-family: 'Nunito', sans-serif; font-weight: 900;
      font-size: 200px; line-height: 1; color: #FFFFFF;
      text-shadow: 0 0 60px rgba(77,217,192,0.45);
    }
    .card[data-card-id="${c.id}"] .suffix {
      font-family: 'JetBrains Mono', monospace; font-weight: 700;
      font-size: 56px; letter-spacing: 0.08em; color: ${accent}; margin-top: 4px;
    }
    .card[data-card-id="${c.id}"] .label {
      font-family: 'Nunito Sans', sans-serif; font-weight: 400;
      font-size: 34px; line-height: 1.4; color: #A8B8CC;
      margin-top: 32px; max-width: 820px;
    }
    .card[data-card-id="${c.id}"] .rule {
      width: 0; height: 4px; border-radius: 4px;
      background: linear-gradient(90deg, ${accent}, #8B9FD4);
      margin-top: 32px;
    }
  </style>
  <div class="root">
    <div class="kicker" id="${c.id}-kicker" data-anim="fade-in" data-anim-at="0.1" data-anim-duration="0.4">${esc(c.kicker)}</div>
    ${isNumeric
      ? `<div class="number" id="${c.id}-number" data-anim="count-up" data-anim-at="0.3" data-anim-duration="1.1" data-anim-from="0" data-anim-to="${c.number}" data-anim-format=",d">0</div>`
      : `<div class="number" id="${c.id}-number" data-anim="scale-pop" data-anim-at="0.3" data-anim-duration="0.6">${esc(c.number)}</div>`}
    <div class="suffix" id="${c.id}-suffix" data-anim="fade-in" data-anim-at="0.9" data-anim-duration="0.4">${esc(c.numberSuffix)}</div>
    <p class="label" id="${c.id}-label" data-anim="fade-in" data-anim-at="1.2" data-anim-duration="0.5">${esc(c.label)}</p>
    <div class="rule" id="${c.id}-rule" data-anim="grow-x" data-anim-at="1.4" data-anim-duration="0.5" data-anim-target-w="140"></div>
  </div>
</div>`;
}

function outroCardHtml(c) {
  const accent = ACCENTS[c.accent % ACCENTS.length];
  return `<div class="card" data-card-id="${c.id}">
  <style>
    .card[data-card-id="${c.id}"] .root {
      width: 100%; height: 100%;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      text-align: center; background: #1B2A3B;
      font-family: 'Nunito Sans', sans-serif;
    }
    .card[data-card-id="${c.id}"] .kicker {
      font-family: 'JetBrains Mono', monospace;
      font-size: 22px; font-weight: 500; letter-spacing: 0.2em;
      color: ${accent}; text-transform: uppercase; margin-bottom: 20px;
    }
    .card[data-card-id="${c.id}"] .word {
      font-family: 'Nunito', sans-serif; font-weight: 900;
      font-size: 76px; color: #FFFFFF;
    }
    .card[data-card-id="${c.id}"] .word .accent { color: ${accent}; }
    .card[data-card-id="${c.id}"] .tagline {
      font-family: 'Nunito Sans', sans-serif; font-weight: 400;
      font-size: 28px; color: #A8B8CC; margin-top: 20px;
    }
    .card[data-card-id="${c.id}"] .rule {
      width: 0; height: 4px; border-radius: 4px;
      background: linear-gradient(90deg, ${accent}, #8B9FD4);
      margin-bottom: 24px;
    }
  </style>
  <div class="root">
    <div class="kicker" id="${c.id}-kicker" data-anim="fade-in" data-anim-at="0.05" data-anim-duration="0.3">${esc(c.kicker)}</div>
    <div class="rule" id="${c.id}-rule" data-anim="grow-x" data-anim-at="0.3" data-anim-duration="0.4" data-anim-target-w="100"></div>
    <div class="word" id="${c.id}-word" data-anim="scale-pop" data-anim-at="0.4" data-anim-duration="0.5">joe<span class="accent">Builds</span> systems</div>
    <div class="tagline" id="${c.id}-tag" data-anim="fade-in" data-anim-at="0.9" data-anim-duration="0.4">${esc(c.detail)}</div>
  </div>
</div>`;
}

const BUILDERS = { glass: glassCardHtml, list: listCardHtml, hero: heroCardHtml, outro: outroCardHtml };

const cardHtmlById = {};
for (const c of CARDS) {
  const html = BUILDERS[c.archetype](c);
  cardHtmlById[c.id] = html;
  fs.writeFileSync(path.join(CARDS_DIR, `${c.id}.html`), html, "utf8");
}
console.log(`Wrote ${CARDS.length} card fragments.`);

// ---- Compile GSAP statements per card (declarative data-anim -> tl calls) ----
function q(t) { return Math.round(t * FPS) / FPS; }

function animStatements(c, absStart, nextStart) {
  const lines = [];
  const push = (s) => lines.push("          " + s);
  const enterDur = 0.4, exitDur = 0.35;

  push(`tl.set('.card-host[data-card-id="${c.id}"]', { visibility: "visible" }, ${q(absStart)});`);
  push(`tl.fromTo('.card-host[data-card-id="${c.id}"]', { opacity: 0 }, { opacity: 1, duration: ${enterDur}, ease: "power2.out" }, ${q(absStart)});`);

  const at = (offset) => q(absStart + offset);

  if (c.archetype === "glass") {
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-rule', { width: 0 }, { width: 120, duration: 0.45, ease: "power2.out" }, ${at(Math.max(0, c.kickerAt - 0.05))});`);
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-kicker', { opacity: 0 }, { opacity: 1, duration: 0.4, ease: "power2.out" }, ${at(c.kickerAt)});`);
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-title', { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }, ${at(c.titleAt)});`);
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-detail', { opacity: 0 }, { opacity: 1, duration: 0.5, ease: "power2.out" }, ${at(c.detailAt)});`);
  } else if (c.archetype === "list") {
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-kicker', { opacity: 0 }, { opacity: 1, duration: 0.4, ease: "power2.out" }, ${at(c.kickerAt)});`);
    c.items.forEach((_, i) => {
      const chipAt = at(c.chipAts[i]);
      push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-chip-${i}', { opacity: 0, x: -40 }, { opacity: 1, x: 0, duration: 0.4, ease: "power2.out" }, ${chipAt});`);
    });
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-punch', { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.6)" }, ${at(c.punchAt)});`);
  } else if (c.archetype === "hero") {
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-kicker', { opacity: 0 }, { opacity: 1, duration: 0.4, ease: "power2.out" }, ${at(c.kickerAt)});`);
    const isNumeric = /^[0-9]+$/.test(c.number);
    if (isNumeric) {
      push(`(function(){ const o = { v: 0 }; tl.to(o, { v: ${Number(c.number)}, duration: 1.1, ease: "power2.out", onUpdate: function(){ const node = document.querySelector('.card[data-card-id="${c.id}"] #${c.id}-number'); if (node) node.textContent = __fmt(o.v, ',d'); } }, ${at(c.numberAt)}); })();`);
    } else {
      push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-number', { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.6, ease: "back.out(1.6)" }, ${at(c.numberAt)});`);
    }
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-suffix', { opacity: 0 }, { opacity: 1, duration: 0.4, ease: "power2.out" }, ${at(c.suffixAt)});`);
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-label', { opacity: 0 }, { opacity: 1, duration: 0.5, ease: "power2.out" }, ${at(c.labelAt)});`);
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-rule', { width: 0 }, { width: 140, duration: 0.5, ease: "power2.out" }, ${at(Math.max(c.suffixAt, c.labelAt) + 0.2)});`);
  } else if (c.archetype === "outro") {
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-kicker', { opacity: 0 }, { opacity: 1, duration: 0.3, ease: "power2.out" }, ${at(0.05)});`);
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-rule', { width: 0 }, { width: 100, duration: 0.4, ease: "power2.out" }, ${at(0.3)});`);
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-word', { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.6)" }, ${at(0.4)});`);
    push(`tl.fromTo('.card[data-card-id="${c.id}"] #${c.id}-tag', { opacity: 0 }, { opacity: 1, duration: 0.4, ease: "power2.out" }, ${at(0.9)});`);
  }

  if (c.archetype !== "outro") {
    push(`tl.to('.card-host[data-card-id="${c.id}"]', { opacity: 0, duration: ${exitDur}, ease: "power2.in" }, ${q(c.end - exitDur)});`);
    push(`tl.set('.card-host[data-card-id="${c.id}"]', { opacity: 0 }, ${q(c.end)});`);
    push(`tl.set('.card-host[data-card-id="${c.id}"]', { visibility: "hidden" }, ${q(c.end)});`);
    if (nextStart != null && nextStart > c.end) {
      push(`tl.set('.card-host[data-card-id="${c.id}"]', { opacity: 0 }, ${q(nextStart)});`);
    }
  }

  return lines.join("\n");
}

const cardHostDivs = CARDS.map((c) => {
  const dur = q(c.end - c.start);
  return `      <div
        id="host-${c.id}"
        class="card-host clip"
        data-card-id="${c.id}"
        data-start="${q(c.start)}"
        data-duration="${dur}"
        data-track-index="2"
        style="left:0;top:0;width:${W}px;height:${H}px;visibility:hidden;opacity:0;"
      >
${cardHtmlById[c.id].split("\n").map((l) => "        " + l).join("\n")}
      </div>`;
}).join("\n\n");

// video hides during the outro card (pure-graphic moment)
const outro = CARDS[CARDS.length - 1];
const videoHideStatements = `          tl.to('#video-wrap', { opacity: 0, duration: 0.4, ease: "power2.in" }, ${q(outro.start)});`;

const animBlocks = CARDS.map((c, i) => {
  const next = CARDS[i + 1];
  return animStatements(c, c.start, next ? next.start : null);
}).join("\n\n");

const punchBlocks = PUNCHES.map((p, i) => {
  const inAt = q(p.at);
  const outAt = q(p.at + p.hold);
  return [
    `          tl.to('#video-wrap', { scale: 1.12, duration: 0.25, ease: "power2.out" }, ${inAt});`,
    `          tl.to('#video-wrap', { scale: 1.0, duration: 0.4, ease: "power2.inOut" }, ${outAt});`,
  ].join("\n");
}).join("\n\n");

const indexHtml = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <style>
      @font-face { font-family: "Nunito"; src: url("fonts/Nunito-400.ttf") format("truetype"); font-weight: 400; font-display: block; }
      @font-face { font-family: "Nunito"; src: url("fonts/Nunito-700.ttf") format("truetype"); font-weight: 700; font-display: block; }
      @font-face { font-family: "Nunito"; src: url("fonts/Nunito-800.ttf") format("truetype"); font-weight: 800; font-display: block; }
      @font-face { font-family: "Nunito"; src: url("fonts/Nunito-900.ttf") format("truetype"); font-weight: 900; font-display: block; }
      @font-face { font-family: "Nunito Sans"; src: url("fonts/Nunito-400.ttf") format("truetype"); font-weight: 400; font-display: block; }
      @font-face { font-family: "Nunito Sans"; src: url("fonts/Nunito-700.ttf") format("truetype"); font-weight: 700; font-display: block; }
      @font-face { font-family: "JetBrains Mono"; src: url("fonts/JetBrainsMono-400.ttf") format("truetype"); font-weight: 400; font-display: block; }
      @font-face { font-family: "JetBrains Mono"; src: url("fonts/JetBrainsMono-500.ttf") format("truetype"); font-weight: 500; font-display: block; }
      @font-face { font-family: "JetBrains Mono"; src: url("fonts/JetBrainsMono-700.ttf") format("truetype"); font-weight: 700; font-display: block; }

      :root {
        --bg: #1B2A3B;
        --text: #F1F5F9;
        --accent-0: #4DD9C0;
        --accent-1: #5BCFEA;
        --accent-2: #8B9FD4;
      }
      * { box-sizing: border-box; }
      html, body {
        margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden;
        background: #000;
        font-family: 'Nunito', 'Nunito Sans', 'JetBrains Mono', ui-sans-serif, system-ui, sans-serif;
      }
      #stage { position: relative; width: 100%; height: 100%; overflow: hidden; }
      .video-wrapper {
        position: absolute; left: 0; top: 0; width: ${W}px; height: ${H}px; overflow: hidden;
        transform-origin: 50% 38%;
      }
      .video-wrapper video { width: 100%; height: 100%; object-fit: cover; }
      .card-host { position: absolute; pointer-events: none; overflow: hidden; }
      .card-host .card { position: relative; width: 100%; height: 100%; overflow: hidden; }
    </style>
  </head>
  <body>
    <div
      id="stage"
      data-composition-id="talking-head-recut"
      data-start="0"
      data-duration="${DURATION}"
      data-fps="${FPS}"
      data-width="${W}"
      data-height="${H}"
    >
      <div class="video-wrapper" id="video-wrap">
        <video
          id="bg-video"
          src="input-video.mp4"
          muted
          playsinline
          style="opacity:1"
          data-start="0"
          data-duration="${DURATION}"
          data-track-index="1"
        ></video>
      </div>
      <audio
        id="source-audio"
        src="input-video.mp4"
        data-start="0"
        data-duration="${DURATION}"
        data-track-index="10"
        data-volume="1"
      ></audio>

${cardHostDivs}

      <script src="vendor/gsap.min.js"></script>
      <script>
        (function () {
          window.__fmt = function (v, fmt) {
            if (typeof fmt === "string" && /^\\.[0-9]+f$/.test(fmt)) {
              return Number(v).toFixed(Number(fmt.slice(1, -1)));
            }
            if (fmt === ",d") return Math.round(v).toLocaleString();
            return String(Math.round(v));
          };

          const tl = window.gsap.timeline({ paused: true });

          tl.set('#video-wrap', { scale: 1.0 }, 0);

${animBlocks}

${videoHideStatements}

${punchBlocks}

          window.__timelines = window.__timelines || {};
          window.__timelines["talking-head-recut"] = tl;
        })();
      </script>
    </div>
  </body>
</html>
`;

fs.writeFileSync(path.join(WORK, "public", "index.html"), indexHtml, "utf8");
console.log("Wrote public/index.html");
