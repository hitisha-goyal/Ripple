/* Ripple - the whole front end, in one file.
 *
 * WHAT HAPPENED HERE. This file was written in two halves, in two windows that
 * could not see each other, and neither half could see index.html. The second
 * half assumed x() escaped a string and that every screen returned HTML; the
 * first half had written x() as the lookup for a data-x handle and built real
 * elements. Nothing tied either half to the page: the first half looked for a
 * container called "view" that index.html does not have, and for templates
 * called tpl-step-1 when the page calls them t-step1. So render() stopped on
 * its second line and the main pane stayed blank on every screen while the
 * sidebar, which is static markup, drew perfectly.
 *
 * It is now one file, written against the page and the service that actually
 * exist:
 *   - the screen is [data-x="screen"], the steps are t-step1 .. t-step7, and
 *     every data-x handle in index.html is filled in by name rather than by a
 *     second structure built over the top of it,
 *   - every address called is one ripple/api.py really serves,
 *   - the class names are the ones styles.css defines, including the
 *     information button, which is .iwrap/.ifact/button.i/.ipanel and NOT
 *     .why - .why is the amber tag that rides on a matched line of code.
 *
 * Three rules the copy is written to, because breaking any of them is how a
 * screen starts telling somebody a comfortable lie:
 *   - every number drawn here was counted by the service; where a count was
 *     not reported the screen says so rather than printing a nought,
 *   - a clean sentence is only printed when it was earned, and when part of the
 *     folder went unread the screen says so next to the count that would
 *     otherwise read as full coverage,
 *   - the fact stays on the page and only the reasoning goes behind the
 *     information button.
 */

/* ---------------------------------------------------------------- constants */

const POLL_MS = 500;

/* Three weeks. Inside that, the effective date badge turns amber, because a
 * change that lands next month and a change that lands on Friday need
 * different amounts of attention from whoever is reading. */
const AMBER_DAYS = 21;

/* At most twenty table cards, forty branches, forty file-type chips. Nothing is
 * dropped at any of those limits: what is not drawn is counted out loud. */
const MAX_TABLE_CARDS = 20;
const MAX_BRANCHES = 40;
const MAX_TYPE_CHIPS = 40;

/* The deeper-scan button never asks for more than this. lineage owns the real
 * ceiling; this only decides what the button offers. */
const HOP_CEILING = 25;

/* The five kinds of change the scan understands. Anything else read out of an
 * email is left unset rather than mapped onto the nearest one: a wrong kind
 * quietly changes what the scan looks for. */
const CHANGE_KINDS = [
  { value: 'renamed', label: 'Renamed - the attribute keeps its meaning under a new name' },
  { value: 'retyped', label: 'Type changed - the same name, a different type' },
  { value: 'dropped', label: 'Removed - the attribute goes away' },
  { value: 'values', label: 'Values changing - the same name and type, different contents' },
  { value: 'added', label: 'New attribute - something arrives that was not there before' }
];

/* Deliberately loose on the local part and strict on the dot in the domain, so
 * a whole Outlook To line - display names, semicolons, angle brackets - yields
 * the addresses and nothing else. */
const EMAIL_RE = /[A-Za-z0-9._%+'\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+/g;

/* --------------------------------------------------------------- the state */

const S = {
  step: 1,
  maxStep: 1,
  screen: '',
  mode: 'email',
  health: null,
  catalogue: null,
  vals: null,
  emailPreview: null,
  chosenFile: null,
  scan: null,
  summary: null,
  reply: null,
  replyEdits: null,
  savedAs: '',
  saveError: '',
  past: null,
  pastError: '',
  pastSaid: '',
  manRows: [{ table: '', attrs: '' }],
  man: {
    sourceSystem: '',
    changeType: '',
    effectiveDate: '',
    whatChanges: '',
    contactName: '',
    contactTeam: '',
    contactRaw: '',
    contactEmails: []
  },
  busy: false,
  busyWhat: '',
  mapTab: 0,
  productionText: null,
  productionRead: null,
  productionSaid: '',
  folderSaid: '',
  copySaid: '',
  /* Which panels are open, keyed by label, so a re-render does not slam shut
   * something somebody is halfway through reading. */
  why: new Set(),
  openGroups: new Set(),
  openRows: new Set(),
  groupsDefaulted: false
};

let liveLine = '';
let progressTimer = null;
let lastError = '';
let healthAsked = false;
let catalogueAsked = false;
let productionTimer = null;
let navWired = false;
let aiStatusRow = null;

const STEP_TITLES = {
  1: 'Notification',
  2: 'Review fields',
  3: 'Repository',
  4: 'Impact analysis',
  5: 'Dependency map',
  6: 'Summary',
  7: 'Reply'
};

/* --------------------------------------------------------------- the tools */

function $(sel, root) {
  return (root || document).querySelector(sel);
}

function $$(sel, root) {
  return Array.prototype.slice.call((root || document).querySelectorAll(sel));
}

function x(root, name) {
  return (root || document).querySelector('[data-x="' + name + '"]');
}

function el(tag, props, ...children) {
  const node = document.createElement(tag);
  const p = props || {};
  Object.keys(p).forEach(function (key) {
    const v = p[key];
    /* hidden is read first: false is a real instruction here - show it - and
     * everywhere else false means "not this attribute at all". */
    if (key === 'hidden') { node.hidden = Boolean(v); return; }
    if (v === null || v === undefined || v === false) return;
    if (key === 'class') { node.className = v; return; }
    if (key === 'for') { node.htmlFor = v; return; }
    if (key === 'text') { node.textContent = String(v); return; }
    if (key.length > 2 && key.slice(0, 2) === 'on' && typeof v === 'function') {
      /* Listeners are attached here rather than written into the markup: this
       * page has no inline event handlers anywhere. */
      node.addEventListener(key.slice(2).toLowerCase(), v);
      return;
    }
    if (key in node) { node[key] = v; return; }
    node.setAttribute(key, String(v));
  });
  addKids(node, children);
  return node;
}

function addKids(node, kids) {
  kids.forEach(function (k) {
    if (k === null || k === undefined || k === false || k === '') return;
    if (Array.isArray(k)) { addKids(node, k); return; }
    node.appendChild(typeof k === 'object' ? k : document.createTextNode(String(k)));
  });
}

/* Fill one data-x handle. Returns null when the page has no such handle, so a
 * missing one shows up as nothing drawn there rather than as a thrown error
 * that stops the whole screen. */
function fill(root, name, ...kids) {
  const node = x(root, name);
  if (!node) return null;
  node.textContent = '';
  addKids(node, kids);
  return node;
}

function setText(root, name, text) {
  const node = x(root, name);
  if (node) node.textContent = str(text);
  return node;
}

function onClick(root, name, fn, disabled) {
  const node = x(root, name);
  if (!node) return null;
  node.disabled = Boolean(disabled);
  node.addEventListener('click', fn);
  return node;
}

function show(node, on) {
  if (node) node.hidden = !on;
  return node;
}

/* The service and the scan spell the same fact differently in places, so read
 * every spelling a value might arrive under rather than drawing a blank where a
 * real count exists. */
function pick(obj, ...names) {
  if (!obj) return undefined;
  for (let i = 0; i < names.length; i += 1) {
    const v = obj[names[i]];
    if (v !== undefined && v !== null) return v;
  }
  return undefined;
}

function str(v) {
  return v === undefined || v === null ? '' : String(v);
}

function listOf(v) {
  return Array.isArray(v) ? v : [];
}

function numberOr(v, fallback) {
  return typeof v === 'number' && isFinite(v) ? v : fallback;
}

/* A count, or null when nothing counted it. Null is drawn as "not reported",
 * never as nought: a nought nobody counted is an invented number. */
function count(v) {
  return typeof v === 'number' && isFinite(v) ? v : null;
}

function num(n) {
  return typeof n === 'number' && isFinite(n) ? n.toLocaleString('en-GB') : '';
}

function mb(bytes) {
  return (bytes / (1024 * 1024)).toFixed(1);
}

function plural(n, one, many) {
  return n === 1 ? '1 ' + one : num(n) + ' ' + many;
}

/* Written out for one and for many. Printed plural-only these read "1 findings
 * are on a line", which is how a careful tool sounds careless on the one screen
 * where care is the thing being sold. */
function oneOrMany(n, singular, many) {
  return numberOr(n, 0) === 1 ? singular : many;
}

/* Entries in the under-specified lists arrive either as bare strings or as
 * small objects. This is the ONE place that copes with both, so a shape that
 * turns out to be wrong shows up here and not as sixty blank chips. */
function fieldOf(entry, ...names) {
  if (typeof entry === 'string') return entry;
  if (!entry || typeof entry !== 'object') return '';
  for (let i = 0; i < names.length; i += 1) {
    const v = entry[names[i]];
    if (v !== undefined && v !== null && v !== '') return String(v);
  }
  return '';
}

function joinNames(values, sep) {
  const out = [];
  listOf(values).forEach(function (item) {
    const t = fieldOf(item, 'table', 'name', 'value', 'folder', 'ext');
    if (t) out.push(t);
  });
  return out.join(sep || ', ');
}

/* Counted things arrive either as {".ipynb": 12} from a Python counter or as a
 * list of small objects. Both are read; neither is invented. */
function countList(v) {
  if (!v) return [];
  let out = [];
  if (Array.isArray(v)) {
    out = v.map(function (item) {
      if (typeof item === 'string') return { ext: item, count: null };
      return {
        ext: fieldOf(item, 'ext', 'lang', 'name', 'type'),
        count: count(pick(item, 'files', 'count', 'n'))
      };
    });
  } else if (typeof v === 'object') {
    out = Object.keys(v).map(function (k) {
      return { ext: k, count: count(Number(v[k])) };
    });
  }
  out.sort(function (a, b) {
    const ac = numberOr(a.count, -1);
    const bc = numberOr(b.count, -1);
    if (bc !== ac) return bc - ac;
    return a.ext.localeCompare(b.ext);
  });
  return out;
}

function totalOf(rows) {
  let total = 0;
  let sawOne = false;
  rows.forEach(function (r) {
    if (typeof r.count === 'number') { total += r.count; sawOne = true; }
  });
  return sawOne ? total : null;
}

/* ------------------------------------------------------------- the service */

async function api(path, opts) {
  const res = await fetch(path, opts || {});
  const raw = await res.text();
  let body = null;
  if (raw) {
    try { body = JSON.parse(raw); } catch (err) { body = null; }
  }
  if (!res.ok) {
    /* The service writes its own plain-English message. Replacing it with one
     * of ours would hide the only sentence that says what went wrong. */
    let msg = '';
    if (body && typeof body === 'object') {
      const detail = pick(body, 'detail', 'error', 'message');
      if (Array.isArray(detail)) {
        msg = detail.map(function (d) {
          return d && d.msg ? String(d.msg) : String(d);
        }).join('; ');
      } else if (detail !== undefined) {
        msg = String(detail);
      }
    }
    if (!msg) msg = raw ? raw.slice(0, 400) : res.status + ' ' + res.statusText;
    throw new Error(msg);
  }
  return body;
}

function sendJson(path, method, body) {
  return api(path, {
    method: method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
}

function postJson(path, body) { return sendJson(path, 'POST', body); }
function patchJson(path, body) { return sendJson(path, 'PATCH', body); }

function errorText(err) {
  if (!err) return 'no reason was given';
  if (typeof err === 'string') return err;
  if (err.message) return String(err.message);
  return String(err);
}

/* --------------------------------------------------------------- ui atoms */

function badge(text, tone) {
  return el('span', { class: 'badge ' + (tone || 'grey'), text: text });
}

function chip(text, extra) {
  return el('span', { class: 'chip' + (extra ? ' ' + extra : ''), text: text });
}

function note(tone, ...kids) {
  return el('div', { class: 'note' + (tone ? ' ' + tone : '') }, kids);
}

function kv(label, value) {
  return el('div', { class: 'factrow' },
    el('div', { text: label }),
    el('div', { text: value }));
}

function buttonEl(label, cls, onClickFn, disabled) {
  const b = el('button', { type: 'button', class: cls, text: label, disabled: Boolean(disabled) });
  b.addEventListener('click', onClickFn);
  return b;
}

/* The information button. The fact stays on the page; only the reasoning goes
 * inside. No count, no table name and no warning is ever hidden in one.
 * .iwrap/.ifact/button.i/.ipanel are the class names styles.css defines for it;
 * .why is a different thing entirely in that file. */
function why(fact, label, ...explanation) {
  const open = S.why.has(label);
  const panel = el('div', { class: 'ipanel', hidden: !open });
  explanation.forEach(function (line) {
    panel.appendChild(typeof line === 'object' ? line : el('p', { text: String(line) }));
  });
  const btn = el('button', {
    type: 'button',
    class: 'i',
    'aria-label': label,
    'aria-expanded': open ? 'true' : 'false',
    text: 'i'
  });
  btn.addEventListener('click', function () {
    const nowOpen = panel.hidden;
    panel.hidden = !nowOpen;
    btn.setAttribute('aria-expanded', nowOpen ? 'true' : 'false');
    if (nowOpen) S.why.add(label); else S.why.delete(label);
  });
  return el('div', { class: 'iwrap' },
    el('div', { class: 'ifact' },
      el('div', {}, typeof fact === 'object' ? fact : el('span', { text: String(fact) })),
      btn),
    panel);
}

/* One counted card. There is deliberately nowhere in here to put a percentage
 * or a bar. A count that was never reported says so. */
function statCard(label, value, sub, tone) {
  const n = count(value);
  return el('div', { class: 'stat' + (tone ? ' ' + tone : '') },
    el('div', { class: 'lbl', text: label }),
    n === null
      ? el('div', { class: 'big small muted', text: 'not reported' })
      : el('div', { class: 'big', text: num(n) }),
    sub ? el('div', { class: 'small muted', text: sub }) : null);
}

function statsRow(title, cards, ...extra) {
  if (!cards.length && !extra.length) return null;
  return el('div', {},
    title ? el('h3', { text: title }) : null,
    el('div', { class: 'stats' }, cards),
    extra);
}

function scrollBox(...kids) {
  return el('div', { class: 'scrollbox' }, kids);
}

/* ------------------------------------------------- slow work and progress */

async function run(fn, what) {
  S.busy = true;
  S.busyWhat = what;
  liveLine = '';
  lastError = '';
  render();
  startProgressPoll();
  try {
    return await fn();
  } catch (err) {
    lastError = errorText(err);
    return null;
  } finally {
    stopProgressPoll();
    S.busy = false;
    S.busyWhat = '';
    liveLine = '';
    render();
  }
}

function startProgressPoll() {
  if (progressTimer !== null) return;
  progressTimer = window.setInterval(function () {
    api('/api/progress').then(function (p) {
      const line = progressText(p, S.busyWhat);
      /* Redraw only when the line actually changes. Redrawing twice a second
       * moves the page under the reader and makes a stalled engine look busy. */
      if (line !== liveLine) {
        liveLine = line;
        render();
      }
    }, function () {
      /* If progress cannot be read, stop asking rather than hammering the
       * service. The fixed sentence stays, which is honest, and the work
       * itself carries on. */
      stopProgressPoll();
    });
  }, POLL_MS);
}

function stopProgressPoll() {
  if (progressTimer === null) return;
  window.clearInterval(progressTimer);
  progressTimer = null;
}

/* The counted line when there is one, the fixed sentence until there is. Where
 * the engine reports a count and no total, the count is shown on its own: a
 * fraction with an invented denominator is worse than no fraction. */
function progressText(p, fallback) {
  if (!p) return fallback;
  const head = str(pick(p, 'label', 'step', 'what', 'line', 'stage', 'name', 'message'));
  const done = count(pick(p, 'done', 'count', 'n'));
  const total = count(pick(p, 'total', 'of'));
  if (!head && done === null) return fallback;
  const words = head || fallback;
  if (done !== null && total !== null && total > 0) {
    return words + ' · ' + num(done) + ' of ' + num(total);
  }
  if (done !== null) return words + ' · ' + num(done);
  return words;
}

/* ------------------------------------------------------------- the health */

function repoOf() {
  const h = S.health;
  return h && h.repo ? h.repo : {};
}

function limitsOf() {
  const h = S.health;
  return h && h.limits ? h.limits : {};
}

function aiOf() {
  const h = S.health;
  return h && h.ai ? h.ai : {};
}

function aiAvailable() {
  return Boolean(pick(aiOf(), 'available', 'on', 'enabled'));
}

function repoName() {
  const repo = repoOf();
  return fieldOf(repo, 'label') || fieldOf(repo, 'path') || 'this repository';
}

function ensureHealth() {
  if (healthAsked || S.health) return;
  healthAsked = true;
  api('/api/health').then(function (h) {
    S.health = h;
    render();
  }, function (err) {
    lastError = errorText(err);
    render();
  });
}

function ensureCatalogue() {
  if (catalogueAsked || S.catalogue) return;
  catalogueAsked = true;
  api('/api/catalog').then(function (c) {
    S.catalogue = c;
    render();
  }, function (err) {
    /* Stored rather than swallowed: a card that stays quiet reads as a card
     * with nothing to report. */
    S.catalogue = { failed: errorText(err) };
    render();
  });
}

/* ------------------------------------------------------------- the render */

function screenRoot() {
  return x(document, 'screen');
}

/* Hand entry removes step 2 from the wizard. Greying it out, or skipping it
 * while the sidebar still names it, both leave the reader looking for a screen
 * that is never coming. */
function stepOrder() {
  const all = [1, 2, 3, 4, 5, 6, 7];
  return S.mode === 'manual' ? all.filter(function (n) { return n !== 2; }) : all;
}

function goStep(n) {
  S.step = n;
  S.screen = '';
  const order = stepOrder();
  if (order.indexOf(n) > order.indexOf(S.maxStep)) S.maxStep = n;
  lastError = '';
  render();
}

function goScreen(name) {
  S.screen = name;
  lastError = '';
  render();
}

function render() {
  const root = screenRoot();
  if (!root) return;
  renderNav();
  renderStatus();
  renderHeader();
  root.textContent = '';
  if (lastError) root.appendChild(errorCard(lastError));

  if (S.screen === 'past') { pastScreen(root); return; }
  if (S.screen === 'settings') { settingsScreen(root); return; }

  const body = cloneStep(S.step);
  root.appendChild(body);
  const draw = {
    1: stepNotification,
    2: stepReview,
    3: stepRepository,
    4: stepFindings,
    5: stepMap,
    6: stepSummary,
    7: stepReply
  }[S.step];
  if (draw) draw(body);
}

/* Each step has a <template> in index.html, named t-step1 .. t-step7. If a
 * build has none for a step, the step is still drawn into an empty section and
 * says so: a blank screen would hide the fact that the page itself is
 * working. */
function cloneStep(n) {
  const holder = el('div', {});
  const tpl = document.getElementById('t-step' + n);
  if (tpl && tpl.content) {
    holder.appendChild(tpl.content.cloneNode(true));
  } else {
    holder.appendChild(note('bad',
      el('p', { text: 'This build of the page has no skeleton for step ' + n + ', so there is nothing to fill in.' })));
  }
  return holder;
}

function errorCard(message) {
  return el('section', { class: 'card clip' },
    el('div', { class: 'chead' }, el('h2', { text: 'That did not work' })),
    el('div', { class: 'pad' },
      el('p', { class: 'prose', text: message }),
      el('p', { class: 'small muted', text: 'Nothing was changed by the attempt.' })));
}

function renderHeader() {
  const title = S.screen === 'past' ? 'Past analyses'
    : S.screen === 'settings' ? 'Settings and checks'
      : (STEP_TITLES[S.step] || 'Step ' + S.step);
  setText(document, 'stepTitle', title);

  const slot = fill(document, 'progress');
  if (!slot) return;
  if (S.busy) {
    slot.appendChild(el('span', { class: 'spin', 'aria-hidden': 'true' }));
    slot.appendChild(el('span', { text: liveLine || S.busyWhat }));
  }
}

/* The sidebar is the step rail. It is static markup, so its buttons are wired
 * once and only their state is repainted. */
function renderNav() {
  wireNav();
  const order = stepOrder();
  const here = order.indexOf(S.step);
  const furthest = Math.max(order.indexOf(S.maxStep), here);
  for (let n = 1; n <= 7; n += 1) {
    const btn = x(document, 'nav' + n);
    if (!btn) continue;
    const item = btn.closest ? btn.closest('li') : null;
    const inWizard = order.indexOf(n) >= 0;
    if (item) item.hidden = !inWizard;
    if (!inWizard) { btn.disabled = true; btn.className = 'navitem'; continue; }
    const at = order.indexOf(n);
    const reachable = at <= furthest;
    const isHere = S.screen === '' && n === S.step;
    btn.className = 'navitem' + (isHere ? ' on' : '') + (at < furthest ? ' done' : '');
    btn.disabled = !reachable;
    if (isHere) btn.setAttribute('aria-current', 'step');
    else btn.removeAttribute('aria-current');
  }
  const past = x(document, 'navPast');
  if (past) past.className = 'navitem' + (S.screen === 'past' ? ' on' : '');
  const settings = x(document, 'navSettings');
  if (settings) settings.className = 'navitem' + (S.screen === 'settings' ? ' on' : '');
}

function wireNav() {
  if (navWired) return;
  navWired = true;
  for (let n = 1; n <= 7; n += 1) {
    const btn = x(document, 'nav' + n);
    if (!btn) continue;
    btn.addEventListener('click', function () { goStep(n); });
  }
  const past = x(document, 'navPast');
  if (past) past.addEventListener('click', function () { goScreen('past'); });
  const settings = x(document, 'navSettings');
  if (settings) settings.addEventListener('click', function () { goScreen('settings'); });
}

/* The status block. Nothing here goes green on a guess: until the service has
 * answered, every row says so. The third row is added by this file because
 * index.html carries two, and whether the fields were read by a model or found
 * by matching the catalogue is the third thing that decides what an answer on
 * this screen is worth. */
function renderStatus() {
  const repoDot = x(document, 'repoDot');
  const repoVal = x(document, 'repoStatus');
  const dialectDot = x(document, 'dialectDot');
  const dialectVal = x(document, 'dialectStatus');

  if (!S.health) {
    if (repoDot) repoDot.className = 'dot';
    if (repoVal) repoVal.textContent = 'Not checked yet';
    if (dialectDot) dialectDot.className = 'dot';
    if (dialectVal) dialectVal.textContent = 'Not checked yet';
    paintAiRow(null);
    return;
  }

  const repo = repoOf();
  const files = count(pick(repo, 'files', 'filesIndexed', 'filesScanned'));
  if (repoDot) repoDot.className = 'dot ' + (files && files > 0 ? 'good' : 'bad');
  if (repoVal) {
    repoVal.textContent = files && files > 0
      ? (fieldOf(repo, 'label') || fieldOf(repo, 'path')) + ' · ' + num(files) + ' files indexed'
      : 'No files indexed';
  }

  const dialect = str(pick(S.health, 'sqlDialect', 'dialect'));
  if (dialectDot) dialectDot.className = 'dot ' + (dialect ? 'good' : 'warn');
  if (dialectVal) dialectVal.textContent = dialect || 'Not reported';
  paintAiRow(aiAvailable());
}

function paintAiRow(state) {
  const anchor = x(document, 'repoDot');
  const block = anchor && anchor.closest ? anchor.closest('.status') : null;
  if (!block) return;
  if (!aiStatusRow) {
    aiStatusRow = el('div', { class: 'statusrow' },
      el('span', { class: 'dot' }),
      el('span', { class: 'statuslbl', text: 'Reading' }),
      el('span', { class: 'statusval' }));
    block.appendChild(aiStatusRow);
  }
  const dot = aiStatusRow.firstChild;
  const value = aiStatusRow.lastChild;
  if (state === null) {
    dot.className = 'dot';
    value.textContent = 'Not checked yet';
    return;
  }
  dot.className = 'dot ' + (state ? 'good' : 'warn');
  value.textContent = state
    ? 'AI on · ' + (fieldOf(aiOf(), 'modelLabel', 'model') || 'model not named')
    : 'AI off - rules only';
}

/* ------------------------------------------------ step 1 - the notification */

/* index.html offers two tabs here. The service has no route that takes typed-in
 * email text - api.py says so and says why - so a "paste the email" box would
 * be a control with nothing behind it. The two tabs are therefore the two ways
 * a change really can be entered: from a saved message, or by hand. */
function stepNotification(root) {
  ensureHealth();

  const emailMode = S.mode === 'email';
  const fileTab = x(root, 'srcFile');
  const handTab = x(root, 'srcPaste');
  if (fileTab) {
    fileTab.textContent = 'From an email';
    fileTab.className = 'pill tab' + (emailMode ? ' on' : '');
    fileTab.addEventListener('click', function () { setMode('email'); });
  }
  if (handTab) {
    handTab.textContent = 'Entered by hand';
    handTab.className = 'pill tab' + (emailMode ? '' : ' on');
    handTab.addEventListener('click', function () { setMode('manual'); });
  }
  show(x(root, 'filePane'), emailMode);
  show(x(root, 'pastePane'), !emailMode);

  if (emailMode) emailPane(root); else manualPane(root);
}

function setMode(mode) {
  if (S.mode === mode) return;
  S.mode = mode;
  /* Hand entry takes step 2 out of the wizard, so anybody standing on it has to
   * be moved rather than left on a screen that no longer exists. */
  if (mode === 'manual' && S.step === 2) S.step = 1;
  if (mode === 'manual' && S.maxStep === 2) S.maxStep = 1;
  render();
}

function uploadCeiling() {
  return count(pick(limitsOf(), 'maxUploadBytes', 'max_upload_bytes'));
}

function emailPane(root) {
  const pane = x(root, 'filePane');
  const input = x(root, 'emailFile');
  const chosen = el('p', { class: 'small muted' });

  const drop = el('div', {
    class: 'drop',
    tabindex: '0',
    role: 'button',
    'aria-label': 'Choose the notification email'
  },
    el('div', { text: 'Drop the saved message here, or press this box to choose a file.' }),
    el('div', { class: 'faint', text: 'Outlook .msg, .eml and plain text are read.' }));

  drop.addEventListener('dragover', function (ev) { ev.preventDefault(); });
  drop.addEventListener('drop', function (ev) {
    ev.preventDefault();
    const dt = ev.dataTransfer;
    chooseFile(dt && dt.files && dt.files.length ? dt.files[0] : null, chosen, root);
  });
  drop.addEventListener('click', function () { if (input) input.click(); });
  drop.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' || ev.key === ' ') {
      ev.preventDefault();
      if (input) input.click();
    }
  });
  if (input) {
    input.addEventListener('change', function (ev) {
      const f = ev.target.files && ev.target.files.length ? ev.target.files[0] : null;
      chooseFile(f, chosen, root);
    });
  }
  if (pane && input) pane.insertBefore(drop, input);
  if (pane) pane.appendChild(chosen);
  chosen.textContent = S.chosenFile
    ? S.chosenFile.name + ' · ' + mb(S.chosenFile.size) + ' MB chosen. Nothing has been sent yet.'
    : 'No file chosen yet.';

  const ceiling = uploadCeiling();
  const sizeLine = ceiling === null
    ? 'The service did not report a size limit to this page, so the file is only checked when it is sent.'
    : 'The largest file this build accepts is ' + mb(ceiling) + ' MB. The size is checked here and again on the service.';

  const readingLine = !S.health
    ? 'Still asking the service how the fields will be read.'
    : (aiAvailable()
      ? 'AI is on - the email is read by ' + (fieldOf(aiOf(), 'modelLabel', 'model') || 'the configured model')
      : 'AI is off - fields are found by matching the repository catalogue');

  fill(root, 'readNote',
    el('p', { class: 'prose', text: readingLine }),
    !aiAvailable() && fieldOf(aiOf(), 'reason')
      ? el('p', { class: 'small muted', text: fieldOf(aiOf(), 'reason') })
      : null,
    el('p', { class: 'small muted', text: sizeLine }),
    why(
      el('span', { text: 'Nothing is scanned when the file is read. Ripple shows you what it read, you correct it, and the scan runs only after you confirm.' }),
      'Why the email is not scanned as soon as it is read',
      'An email says what somebody meant to change, in the words their team uses. The words for the same attribute in our SQL are often different ones.',
      'Confirming the fields first is what stops a scan running against a name that appears nowhere in the repository and coming back clean.'),
    note('info',
      el('p', { text: 'No file to hand. Type the change in yourself instead - nothing is lost, because Ripple searches for exactly what is on the screen either way.' }),
      el('div', { class: 'foot' },
        buttonEl('Enter it by hand', 'ghost sm', function () { setMode('manual'); }))));

  drawReadBack(root);

  const readBtn = onClick(root, 'doRead', function () {
    if (!S.chosenFile) return;
    sendChosenFile(S.chosenFile);
  }, S.busy || !S.chosenFile);
  if (readBtn) readBtn.hidden = false;

  const ready = Boolean(S.vals);
  const next = onClick(root, 'next1', function () { goStep(2); }, S.busy || !ready);
  if (next) next.textContent = 'Review the fields';
}

function chooseFile(file, chosen, root) {
  if (!file) return;
  const ceiling = uploadCeiling();
  if (ceiling !== null && file.size > ceiling) {
    S.chosenFile = null;
    chosen.textContent = file.name + ' is ' + mb(file.size) + ' MB. The largest this build accepts is '
      + mb(ceiling) + ' MB, so it was not sent.';
    const btn = x(root, 'doRead');
    if (btn) btn.disabled = true;
    return;
  }
  S.chosenFile = file;
  render();
}

function sendChosenFile(file) {
  const form = new FormData();
  form.append('file', file, file.name);
  run(function () { return readNotification(form); }, 'Reading the message');
}

async function readNotification(form) {
  const data = await api('/api/read-email', { method: 'POST', body: form });
  if (!data) return;
  S.emailPreview = data;
  S.vals = valsFromRead(data);
  S.step = 2;
  if (S.maxStep < 2) S.maxStep = 2;
}

/* The read-back panel. Every row is something the service sent; where it sent
 * nothing the row says the file did not carry it, rather than staying blank. */
function drawReadBack(root) {
  const panel = x(root, 'readBack');
  if (!panel) return;
  const data = S.emailPreview;
  panel.hidden = !data;
  if (!data) return;
  const preview = data.emailPreview || {};
  const v = S.vals || {};

  const from = [fieldOf(preview, 'fromName'), fieldOf(preview, 'fromEmail')]
    .filter(function (t) { return t; }).join(' · ');
  setText(root, 'nFrom', from || 'The file carried no sender.');
  setText(root, 'nReceived', str(pick(data, 'received', 'sent', 'date')) || 'The file carried no received date.');
  setText(root, 'nSubject', fieldOf(preview, 'subject') || 'The file carried no subject.');
  setText(root, 'nTable', listOf(v.tables).map(function (r) { return r.table; })
    .filter(function (t) { return t; }).join(', ') || 'No upstream table was read.');

  const fields = fill(root, 'nFields');
  if (fields) {
    const all = [];
    listOf(v.tables).forEach(function (r) { attrList(r.attrs).forEach(function (a) { all.push(a); }); });
    if (!all.length) fields.appendChild(el('span', { class: 'small muted', text: 'No attribute was read.' }));
    all.forEach(function (a) { fields.appendChild(chip(a, 'mono')); });
  }

  setText(root, 'nDate', v.effectiveDate ? dateInWords(v.effectiveDate) : 'No date of change was read.');

  const warnings = listOf(pick(data, 'warnings', 'notes', 'notUnderstood'));
  const unread = fill(root, 'nUnread');
  if (unread) {
    if (pick(data, 'warnings', 'notes', 'notUnderstood') === undefined) {
      unread.appendChild(el('span', {
        class: 'small muted',
        text: 'The service did not report what it could not understand, so this row says nothing either way.'
      }));
    } else if (!warnings.length) {
      unread.appendChild(el('span', { text: 'Nothing in the message was left unread.' }));
    } else {
      const list = el('div', { class: 'chips' });
      warnings.forEach(function (w) {
        list.appendChild(chip(typeof w === 'string' ? w : fieldOf(w, 'text', 'message', 'why')));
      });
      unread.appendChild(list);
    }
  }
}

/* ------------------------------------------- step 1 - entered by hand */

function manualPane(root) {
  const pane = x(root, 'pastePane');
  if (!pane) return;

  /* The textarea window 9 wrote here was labelled "the email as it arrived".
   * There is no route that reads pasted email text, so it is used for the one
   * free-text field this mode really needs. */
  const label = $('label[for="i-email"]', pane);
  if (label) label.textContent = 'What is changing, in their words if you have them';
  const box = x(root, 'emailText');
  if (box) {
    box.rows = 4;
    box.value = str(S.man.whatChanges);
    box.addEventListener('input', function (ev) { S.man.whatChanges = ev.target.value; });
  }

  const rowsBox = el('div', {});
  const countLine = el('p', { class: 'small muted', text: countText(S.manRows) });
  drawRowsEditor(rowsBox, S.manRows, function () { countLine.textContent = countText(S.manRows); });

  const block = el('div', {},
    el('p', { class: 'prose', text: 'Type what the upstream team is changing. Ripple searches for exactly what is on this screen.' }),
    el('div', { class: 'lbl', text: 'The upstream tables and attributes' }),
    rowsBox,
    countLine,
    el('div', { class: 'lbl', text: 'The details' }),
    textField('Source system', S.man, 'sourceSystem', 'The team or platform the table comes from'),
    kindField(S.man),
    dateField(S.man));
  pane.insertBefore(block, pane.firstChild);

  pane.appendChild(el('div', {},
    textField('Contact name', S.man, 'contactName', ''),
    contactBox(S.man),
    textField('Contact team', S.man, 'contactTeam', '')));

  fill(root, 'readNote',
    el('p', { class: 'prose', text: 'You typed this in, so there is no "check what Ripple read" step. You would only be checking your own typing.' }),
    el('p', { class: 'small muted', text: 'Nothing is scanned until you press on to the repository and start the analysis.' }));

  show(x(root, 'readBack'), false);
  const readBtn = x(root, 'doRead');
  if (readBtn) readBtn.hidden = true;

  const next = onClick(root, 'next1', function () {
    S.vals = valsFromManual();
    goStep(3);
  }, S.busy);
  if (next) next.textContent = 'Choose the repository';
}

function drawRowsEditor(box, rows, onChange) {
  box.textContent = '';
  const redraw = function () { drawRowsEditor(box, rows, onChange); if (onChange) onChange(); };
  rows.forEach(function (row, i) {
    const tableInput = el('input', { type: 'text', value: str(row.table), placeholder: 'CUSTOMER_DEMOGRAPHICS' });
    tableInput.addEventListener('input', function (ev) {
      row.table = ev.target.value;
      /* Only the count is touched. A full redraw here would rebuild this input
       * and the caret would jump to the end on every keystroke. */
      if (onChange) onChange();
    });
    const attrInput = el('input', { type: 'text', value: str(row.attrs), placeholder: 'MARKET_CODE, REGION_CODE' });
    attrInput.addEventListener('input', function (ev) {
      row.attrs = ev.target.value;
      if (onChange) onChange();
    });
    box.appendChild(el('div', { class: 'grid2 even' },
      el('div', {}, el('label', { class: 'faint', text: 'Upstream table' }), tableInput),
      el('div', {}, el('label', { class: 'faint', text: 'Attributes, separated by commas' }), attrInput)));
    box.appendChild(el('div', { class: 'foot' },
      buttonEl('Remove this table', 'ghost sm', function () {
        rows.splice(i, 1);
        redraw();
      }, rows.length < 2)));
  });
  box.appendChild(el('div', { class: 'foot' },
    buttonEl('Add another table', 'ghost sm', function () {
      rows.push({ table: '', attrs: '' });
      redraw();
    })));
}

/* Kept exactly as it was typed and only split when it is sent. Reformatting
 * somebody's list under their cursor is how a screen loses a name they were
 * halfway through writing. */
function attrList(s) {
  return str(s).split(',').map(function (t) { return t.trim(); })
    .filter(function (t) { return t.length > 0; });
}

function countText(rows) {
  const tables = listOf(rows).filter(function (r) { return str(r.table).trim().length > 0; }).length;
  let attrs = 0;
  listOf(rows).forEach(function (r) { attrs += attrList(r.attrs).length; });
  return plural(tables, 'table', 'tables') + ' · ' + plural(attrs, 'attribute', 'attributes');
}

function textField(label, target, key, hint) {
  const input = el('input', { type: 'text', value: str(target[key]), placeholder: hint || '' });
  input.addEventListener('input', function (ev) { target[key] = ev.target.value; });
  return el('div', {}, el('label', { class: 'faint', text: label }), input);
}

function textAreaField(label, target, key, hint) {
  const input = el('textarea', { rows: 4, value: str(target[key]), placeholder: hint || '' });
  input.addEventListener('input', function (ev) { target[key] = ev.target.value; });
  return el('div', {}, el('label', { class: 'faint', text: label }), input);
}

function fillKindSelect(sel, target) {
  sel.textContent = '';
  sel.appendChild(el('option', { value: '', text: 'Not chosen yet' }));
  CHANGE_KINDS.forEach(function (k) {
    sel.appendChild(el('option', { value: k.value, text: k.label }));
  });
  sel.value = kindValue(target.changeType);
  sel.addEventListener('change', function (ev) { target.changeType = ev.target.value; });
}

function kindField(target) {
  const sel = el('select', { class: 'drop' });
  fillKindSelect(sel, target);
  return el('div', {},
    el('label', { class: 'faint', text: 'Change type' }),
    sel,
    why(
      el('span', { class: 'small muted', text: 'These five are what the scan can act on.' }),
      'Why the change type is a list and not a box',
      'The scan behaves differently for each of these five, so a kind it does not recognise would be quietly ignored.',
      'Leaving it unchosen is better than choosing the nearest one: the scan then tells you it does not know, instead of searching for the wrong thing.'));
}

function kindValue(v) {
  const wanted = str(v).toLowerCase();
  const found = CHANGE_KINDS.filter(function (k) { return k.value === wanted; });
  return found.length ? found[0].value : '';
}

function dateField(target) {
  const words = el('p', { class: 'small muted', text: dateInWords(target.effectiveDate) });
  const badgeHolder = el('span', {}, dateBadge(target.effectiveDate));
  const input = el('input', { type: 'date', class: 'drop', value: str(target.effectiveDate) });
  input.addEventListener('input', function (ev) {
    target.effectiveDate = ev.target.value;
    /* The date written out in words sits under the picker so a slip of a digit
     * is visible as a wrong weekday rather than hiding in a number. */
    words.textContent = dateInWords(target.effectiveDate);
    badgeHolder.textContent = '';
    badgeHolder.appendChild(dateBadge(target.effectiveDate));
  });
  return el('div', {},
    el('label', { class: 'faint' }, 'Effective date ', badgeHolder),
    input,
    words);
}

function dateInWords(value) {
  if (!value) return 'No date set.';
  /* Parsed with a time attached so the browser reads it as local midnight. A
   * bare date string is read as UTC and lands on the day before for anybody
   * west of Greenwich. */
  const d = new Date(str(value) + 'T00:00:00');
  if (isNaN(d.getTime())) return 'That date could not be read.';
  return d.toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  });
}

function daysLeftOf(value) {
  if (!value) return null;
  const d = new Date(str(value) + 'T00:00:00');
  if (isNaN(d.getTime())) return null;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  /* Rounded, not floored: a clock change makes one of these days 23 or 25 hours
   * long and a floor would drop a whole day. */
  return Math.round((d.getTime() - today.getTime()) / 86400000);
}

function dateBadge(value) {
  const n = daysLeftOf(value);
  if (n === null) return badge('No date set', 'grey');
  if (n < 0) {
    const gone = Math.abs(n);
    return badge(gone === 1 ? '1 day ago' : gone + ' days ago', 'amber');
  }
  if (n === 0) return badge('Today', 'amber');
  return badge(n === 1 ? '1 day left' : n + ' days left', n <= AMBER_DAYS ? 'amber' : 'grey');
}

function addresses(text) {
  const found = str(text).match(EMAIL_RE) || [];
  const seen = Object.create(null);
  const out = [];
  found.forEach(function (a) {
    const key = a.toLowerCase();
    /* An Outlook To line carries the same address twice often enough that two
     * chips for one person would read as two people. */
    if (seen[key]) return;
    seen[key] = true;
    out.push(a);
  });
  return out;
}

function contactBox(target) {
  const chips = el('div', { class: 'chips' });
  const drawChips = function () {
    chips.textContent = '';
    if (!target.contactEmails.length) {
      chips.appendChild(el('span', { class: 'small muted', text: 'No address recognised yet.' }));
      return;
    }
    target.contactEmails.forEach(function (addr) { chips.appendChild(chip(addr, 'mono')); });
    chips.appendChild(el('span', {
      class: 'small muted',
      text: plural(target.contactEmails.length, 'address', 'addresses') + ' understood'
    }));
  };
  const input = el('input', {
    type: 'text',
    value: str(target.contactRaw),
    placeholder: 'Paste the whole To line if that is easier'
  });
  input.addEventListener('input', function (ev) {
    target.contactRaw = ev.target.value;
    target.contactEmails = addresses(ev.target.value);
    /* Only the chips are redrawn. Re-rendering the page here would rebuild this
     * input and throw the cursor out of the box on every keystroke. */
    drawChips();
  });
  drawChips();
  return el('div', {},
    el('label', { class: 'faint', text: 'Contact email addresses' }),
    input,
    chips,
    why(
      el('span', { class: 'small muted', text: 'Any number of addresses, in any shape.' }),
      'Why the addresses are shown back as chips',
      'Whatever is pasted here is picked over for addresses, so a whole To line with display names and semicolons works.',
      'They are shown back one by one so what was understood is obvious before the reply is drafted to them.'));
}

function valsFromManual() {
  const m = S.man;
  return {
    subject: '',
    description: m.whatChanges,
    sourceSystem: m.sourceSystem,
    changeType: kindValue(m.changeType),
    effectiveDate: m.effectiveDate,
    contactName: m.contactName,
    contactTeam: m.contactTeam,
    contactRaw: m.contactRaw,
    contactEmails: m.contactEmails.slice(),
    tables: S.manRows.map(function (r) { return { table: r.table, attrs: r.attrs }; }),
    filledBy: 'you'
  };
}

function valsFromRead(data) {
  const tables = [];
  const read = pick(data, 'upstream', 'tables', 'upstreamTables', 'upstream_tables');
  listOf(read).forEach(function (t) {
    if (typeof t === 'string') { tables.push({ table: t, attrs: '' }); return; }
    const attrs = pick(t, 'attrs', 'attributes', 'columns', 'fields');
    tables.push({
      table: fieldOf(t, 'table', 'name'),
      attrs: Array.isArray(attrs) ? attrs.join(', ') : str(attrs)
    });
  });
  if (!tables.length) {
    const one = str(pick(data, 'table', 'upstreamTable', 'upstream_table'));
    const attrs = pick(data, 'attributes', 'attrs', 'columns', 'fields');
    if (one || attrs) {
      tables.push({ table: one, attrs: Array.isArray(attrs) ? attrs.join(', ') : str(attrs) });
    }
  }
  if (!tables.length) tables.push({ table: '', attrs: '' });

  const preview = data.emailPreview || {};
  const emails = pick(data, 'contactEmails', 'contact_emails', 'contacts');
  const raw = str(pick(data, 'contactRaw', 'contact_raw', 'contact'))
    || (Array.isArray(emails) ? emails.join('; ') : '')
    || fieldOf(preview, 'fromEmail');
  return {
    subject: str(pick(data, 'subject')) || fieldOf(preview, 'subject'),
    description: str(pick(data, 'description', 'whatChanges', 'what_changes')) || fieldOf(preview, 'body'),
    sourceSystem: str(pick(data, 'sourceSystem', 'source_system', 'system')),
    changeType: kindValue(pick(data, 'changeKind', 'changeType', 'change_type', 'kind')),
    effectiveDate: str(pick(data, 'effectiveDate', 'effective_date', 'date')),
    contactName: str(pick(data, 'contactName', 'contact_name')) || fieldOf(preview, 'fromName'),
    contactTeam: str(pick(data, 'contactTeam', 'contact_team', 'team')),
    contactRaw: raw,
    contactEmails: Array.isArray(emails) ? emails.slice() : addresses(raw),
    tables: tables,
    filledBy: filledByOf(data)
  };
}

function filledByOf(data) {
  const said = str(pick(data, 'filledBy', 'filled_by', 'readBy', 'read_by', 'foundBy')).toLowerCase();
  if (said === 'ai' || said === 'catalogue' || said === 'catalog' || said === 'you') {
    return said === 'catalog' ? 'catalogue' : said;
  }
  /* The service did not say, so fall back to the one thing this page knows: a
   * reader that is on means the email went to a model, a reader that is off
   * means the fields came from matching the catalogue. Printing the two as one
   * would hide which of them you actually got, and they are different amounts
   * of trust. */
  return aiAvailable() ? 'ai' : 'catalogue';
}

function trustLabel(filledBy) {
  if (filledBy === 'you') return 'Entered by you - no AI used';
  if (filledBy === 'ai') return 'Read by AI - check it';
  return 'Found by matching the catalogue - check it';
}

/* --------------------------------------------- step 2 - what Ripple read */

function stepReview(root) {
  const v = S.vals;
  if (!v) {
    fill(root, 'fieldNote', note('warn',
      el('p', { text: 'No message has been read, so there is nothing here to check. Go back and choose the file.' })));
    onClick(root, 'back2', function () { goStep(1); });
    onClick(root, 'next2', function () { goStep(1); }, true);
    return;
  }
  if (!v.tables.length) v.tables.push({ table: '', attrs: '' });
  const first = v.tables[0];

  const card = $('.card', root) || root;
  const chead = $('.chead', root);

  /* Warnings first, above everything editable. A warning under the fold is a
   * warning nobody acted on. */
  const warnings = listOf(pick(S.emailPreview, 'warnings', 'notes', 'notUnderstood'));
  const top = el('div', { class: 'pad' });
  if (warnings.length) {
    const list = el('div', {});
    warnings.forEach(function (w) {
      list.appendChild(el('p', { text: typeof w === 'string' ? w : fieldOf(w, 'text', 'message', 'why') }));
    });
    top.appendChild(note('warn', el('h3', { text: 'Read this before you confirm' }), list));
  }
  top.appendChild(el('div', { class: 'chips' }, badge(trustLabel(v.filledBy), v.filledBy === 'you' ? 'green' : 'amber')));
  top.appendChild(why(
    el('span', { text: 'The scan uses exactly what is on this screen, not the email. Anything you change here is what Ripple searches for.' }),
    'Why this screen and not the email',
    'The email is read once and then set aside. From here on, the fields on this screen are the whole of what the scan is given.',
    'A wrong name corrected here is corrected everywhere, and a name left wrong here is searched for exactly as it stands.'));
  if (chead && chead.parentNode) chead.parentNode.insertBefore(top, chead.nextSibling);
  else card.insertBefore(top, card.firstChild);

  /* The fields of the first upstream table go in the handles window 9 wrote.
   * Any further tables are drawn underneath in the same shape. */
  const countLine = el('p', { class: 'small muted' });
  const repaintFields = function () {
    const box = fill(root, 'fieldList');
    if (!box) return;
    const attrs = attrList(first.attrs);
    if (!attrs.length) {
      box.appendChild(el('span', { class: 'small muted', text: 'No attribute is listed for this table yet.' }));
    }
    attrs.forEach(function (a, i) {
      const holder = el('span', { class: 'chip mono' }, a);
      holder.appendChild(buttonEl('remove', 'link', function () {
        const kept = attrList(first.attrs);
        kept.splice(i, 1);
        first.attrs = kept.join(', ');
        repaintFields();
      }));
      box.appendChild(holder);
    });
    countLine.textContent = countText(v.tables) + ' will be searched for.';
  };

  const fieldInput = x(root, 'fieldInput');
  onClick(root, 'addField', function () {
    if (!fieldInput) return;
    const wanted = str(fieldInput.value).trim();
    if (!wanted) return;
    const kept = attrList(first.attrs);
    kept.push(wanted);
    first.attrs = kept.join(', ');
    fieldInput.value = '';
    repaintFields();
  });
  if (fieldInput) {
    fieldInput.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Enter') return;
      ev.preventDefault();
      const btn = x(root, 'addField');
      if (btn) btn.click();
    });
  }

  const tableInput = x(root, 'tableInput');
  if (tableInput) {
    tableInput.value = str(first.table);
    tableInput.addEventListener('input', function (ev) {
      first.table = ev.target.value;
      countLine.textContent = countText(v.tables) + ' will be searched for.';
    });
  }

  const kindSelect = x(root, 'changeKind');
  if (kindSelect) fillKindSelect(kindSelect, v);

  fill(root, 'fieldNote',
    countLine,
    el('p', {
      class: 'small muted',
      text: 'These are the names the scan is given. Say plainly what they are called in the upstream table, not what you hope they are called here.'
    }));
  repaintFields();

  /* Everything index.html has no handle for, in one pad of its own, in the
   * order the reader needs it. */
  const extra = el('div', { class: 'pad' },
    el('div', { class: 'grid2 even' },
      el('div', {}, textField('Source system', v, 'sourceSystem', '')),
      el('div', {}, dateField(v))),
    el('div', { class: 'grid2 even' },
      el('div', {}, textField('Contact name', v, 'contactName', '')),
      el('div', {}, textField('Contact team', v, 'contactTeam', ''))),
    contactBox(v),
    el('div', { class: 'grid2 even' },
      el('div', {}, textField('Subject', v, 'subject', '')),
      el('div', {}, textAreaField('Description', v, 'description', ''))));

  const more = el('div', {});
  drawExtraTables(more, v, countLine);
  extra.appendChild(el('div', { class: 'lbl', text: 'Any other upstream table in the same change' }));
  extra.appendChild(more);

  const foot = $('.foot', root);
  if (foot && foot.parentNode) foot.parentNode.insertBefore(extra, foot);
  else root.appendChild(extra);

  onClick(root, 'back2', function () { goStep(1); });
  onClick(root, 'next2', function () { goStep(3); }, S.busy);
}

function drawExtraTables(box, v, countLine) {
  box.textContent = '';
  const redraw = function () {
    drawExtraTables(box, v, countLine);
    countLine.textContent = countText(v.tables) + ' will be searched for.';
  };
  for (let i = 1; i < v.tables.length; i += 1) {
    const row = v.tables[i];
    const tableInput = el('input', { type: 'text', value: str(row.table), placeholder: 'ANOTHER_UPSTREAM_TABLE' });
    tableInput.addEventListener('input', function (ev) {
      row.table = ev.target.value;
      countLine.textContent = countText(v.tables) + ' will be searched for.';
    });
    const attrInput = el('input', { type: 'text', value: str(row.attrs), placeholder: 'MARKET_CODE, REGION_CODE' });
    attrInput.addEventListener('input', function (ev) {
      row.attrs = ev.target.value;
      countLine.textContent = countText(v.tables) + ' will be searched for.';
    });
    box.appendChild(el('div', { class: 'grid2 even' },
      el('div', {}, el('label', { class: 'faint', text: 'Upstream table' }), tableInput),
      el('div', {}, el('label', { class: 'faint', text: 'Attributes, separated by commas' }), attrInput)));
    box.appendChild(el('div', { class: 'foot' },
      buttonEl('Remove this table', 'ghost sm', function () {
        v.tables.splice(i, 1);
        redraw();
      })));
  }
  box.appendChild(el('div', { class: 'foot' },
    buttonEl('Add another table', 'ghost sm', function () {
      v.tables.push({ table: '', attrs: '' });
      redraw();
    })));
}

/* ---------------------------------------------- step 3 - the repository */

function stepRepository(root) {
  ensureHealth();

  const folderTab = x(root, 'srcFolder');
  const netTab = x(root, 'srcGithub');
  if (folderTab) folderTab.className = 'pill tab on';
  if (netTab) {
    /* There is no route in this build for reading a repository over the
     * network, so the tab is switched off with the reason beside it rather than
     * left as a control with nothing behind it. */
    netTab.className = 'pill tab';
    netTab.disabled = true;
  }
  show(x(root, 'folderPane'), true);
  const netPane = x(root, 'githubPane');
  show(netPane, false);
  ['ghUrl', 'ghBranch', 'ghToken'].forEach(function (name) {
    const node = x(root, name);
    if (node) node.disabled = true;
  });
  /* Belt and braces on a pane that must not accept anything: every control in
   * it is switched off, not only the three with handles. Guarded, because
   * without the guard a missing pane would fall back to the whole document and
   * switch off every control on the page. */
  if (netPane) {
    $$('input, select, textarea, button', netPane).forEach(function (node) { node.disabled = true; });
  }
  fill(root, 'githubNote', note('warn',
    el('p', { text: 'This build has no route for reading a repository over the network, so these boxes are switched off.' })));

  if (!S.health) {
    fill(root, 'dialectNote', el('p', {
      class: 'small muted',
      text: 'Asking the service which folder is connected and how much of it was read.'
    }));
    onClick(root, 'back3', function () { goStep(S.mode === 'manual' ? 1 : 2); });
    onClick(root, 'checkRepo', function () {}, true);
    onClick(root, 'startScan', function () {}, true);
    return;
  }

  const repo = repoOf();
  const box = x(root, 'repoPath');
  if (box) {
    box.value = fieldOf(repo, 'path');
    box.placeholder = 'C:\\work\\pipelines';
  }

  const folderPane = x(root, 'folderPane');
  if (folderPane) {
    /* The reason the other tab is switched off has to be on the pane somebody
     * is actually looking at. Inside the hidden pane it would never be read. */
    folderPane.appendChild(el('p', {
      class: 'small muted',
      text: 'Ripple reads a folder on this machine. This build has no route for reading a repository over the '
        + 'network, which is why that tab is switched off rather than offered.'
    }));
    folderPane.appendChild(el('p', {
      class: 'small muted',
      text: 'The choice is held only while Ripple is running - RIPPLE_REPO is what keeps it, and there is nowhere for this build to write it down.'
    }));
    folderPane.appendChild(el('p', {
      class: 'small',
      id: 'folder-said',
      text: str(S.folderSaid)
    }));
  }

  /* The dialect is reported by the service and there is no route in this build
   * that changes it, so the control shows the one in force and says so rather
   * than offering a choice that goes nowhere. */
  const dialect = str(pick(S.health, 'sqlDialect', 'dialect'));
  const sel = x(root, 'dialect');
  if (sel) {
    sel.textContent = '';
    sel.appendChild(el('option', { value: dialect, text: dialect || 'not reported' }));
    sel.value = dialect;
    sel.disabled = true;
  }
  fill(root, 'dialectNote', el('p', {
    class: 'small muted',
    text: dialect
      ? 'Set on the service. There is no route in this build to change it from this page, and it decides how every statement is read.'
      : 'The service did not report a dialect, so nothing on this page can say which one the SQL was read as.'
  }));

  /* The published-tables control, from the one function the whole app uses. */
  const prodBox = x(root, 'prodList');
  if (prodBox) {
    const readHost = el('div', {});
    const saidHost = el('p', { class: 'small' });
    prodBox.parentNode.appendChild(readHost);
    prodBox.parentNode.appendChild(saidHost);
    prodBox.parentNode.appendChild(el('p', {
      class: 'small muted',
      text: 'This one setting decides whether "no production table is impacted" is a result or an accident.'
    }));
    productionControl(prodBox, readHost, saidHost);
  }

  /* The facts about what was read. index.html has no handle for these, so they
   * go in one pad of their own, above the progress pane. */
  const facts = el('div', { class: 'pad' },
    el('div', { class: 'grid2 even' },
      el('div', {}, connectedBlock(repo)),
      el('div', {}, indexBlock(repo))));
  const scanPane = x(root, 'scanPane');
  if (scanPane && scanPane.parentNode) scanPane.parentNode.insertBefore(facts, scanPane);
  else root.appendChild(facts);

  drawScanPane(root);

  const files = count(pick(repo, 'files', 'filesIndexed'));
  const statements = count(pick(repo, 'statements'));
  const ready = Boolean(S.vals) && upstreamForScan().length > 0;

  const foot = $('.foot', root);
  const reread = buttonEl('Re-read the repository', 'ghost', function () {
    run(reindex, 'Re-reading the repository');
  }, S.busy);
  const checkBtn = x(root, 'checkRepo');
  if (foot && checkBtn) foot.insertBefore(reread, checkBtn);
  else if (foot) foot.appendChild(reread);

  if (checkBtn) checkBtn.textContent = 'Read this folder';
  onClick(root, 'checkRepo', function () {
    const wanted = box ? box.value : '';
    run(function () { return readFolder(wanted); }, 'Reading that folder');
  }, S.busy);

  onClick(root, 'startScan', function () { startScanNow(null); },
    S.busy || !ready || !(files !== null && files > 0));

  if (foot) {
    /* Future tense, always. A hint that reads as though the scan is already
     * under way is how a program that has not started gets reported as hung. */
    foot.appendChild(el('p', { class: 'small muted', text: scanHint(files, statements, ready) }));
  }

  onClick(root, 'back3', function () { goStep(S.mode === 'manual' ? 1 : 2); });
}

function scanHint(files, statements, ready) {
  if (files === null) return 'The service did not report how many files are indexed, so there is nothing to say about what a scan would search.';
  if (files === 0) return 'Nothing is indexed yet, so there is nothing for a scan to search.';
  if (!ready) return 'No upstream table and attribute have been confirmed yet, so there is nothing for the scan to follow.';
  if (statements === null) {
    return 'The scan will search the ' + num(files) + ' files in the index for your attributes.';
  }
  return 'The scan will search the ' + num(files) + ' files in the index and follow your attributes through the '
    + num(statements) + ' statements read from them.';
}

function connectedBlock(repo) {
  const files = count(pick(repo, 'files', 'filesIndexed'));
  const statements = count(pick(repo, 'statements'));
  const unreadable = count(pick(repo, 'unreadable'));
  const held = count(pick(repo, 'heldOnline'));
  const tooLong = count(pick(repo, 'pathTooLong'));
  const skipped = count(pick(repo, 'inSkippedDirs'));
  const skippedNames = listOf(pick(repo, 'skippedDirNames', 'skippedFolderNames'));
  const runsSqlFrom = count(pick(repo, 'runsSqlFrom'));

  const box = el('div', {},
    el('h3', { text: 'What is connected' }),
    kv('Folder', fieldOf(repo, 'path') || 'No folder is connected'),
    kv('Label', fieldOf(repo, 'label') || 'Not named'),
    kv('Branch', fieldOf(repo, 'branch') || 'None recorded - this is a folder rather than a checkout'),
    kv('Files indexed', files === null ? 'Not reported' : num(files)),
    kv('Statements understood', statements === null ? 'Not reported' : num(statements)));

  if (repo.exists === false) {
    box.appendChild(note('bad', el('p', {
      text: 'There is no folder at that path any more, so every count above is from the last time it could be read.'
    })));
  }

  /* Files indexed is the number somebody reads to decide the whole folder was
   * covered. When it was not, the rows saying so sit directly underneath it -
   * never on another card and never further down the page. */
  if (held) {
    box.appendChild(why(
      kv('Files not on this machine', num(held)),
      'Why a file is not on this machine',
      'The name is in the folder but the contents are held elsewhere and were never fetched, so nothing inside was read and nothing inside was searched.',
      'They are counted apart from files that were opened and refused to parse, because the two have different fixes.'));
  }
  if (tooLong) {
    box.appendChild(why(
      kv('Paths too long to open', num(tooLong)),
      'Why a path can be too long',
      'Windows refuses a path past a certain length, so the file could not be opened at all.',
      'Nothing in those files was read, so nothing in them was searched.'));
  }
  if (unreadable) {
    box.appendChild(why(
      kv('Statements that would not parse', num(unreadable)),
      'Why a statement will not parse',
      'The file was opened and read, but the SQL inside it was a shape the parser refused.',
      'Each one is listed with its file and its line after a scan, rather than being dropped.'));
  }
  if (skipped) {
    box.appendChild(why(
      kv('Files in folders Ripple skips', num(skipped)),
      'Why some folders are skipped',
      'Build output, dependencies and version-control folders are stepped over, because a copy of a query in a build folder is not a place anything is published from.',
      'The folder names are listed beside this count so a folder that should have been read is visible.'));
    if (skippedNames.length) {
      box.appendChild(el('p', { class: 'small muted', text: 'Skipped: ' + joinNames(skippedNames, ', ') }));
    }
  }
  if (runsSqlFrom) {
    box.appendChild(why(
      el('span', {
        text: num(runsSqlFrom) + ' of these files run SQL that is kept in a separate .sql file rather than '
          + 'written inside them. Those .sql files were read on their own account, and any that name a file '
          + 'which is not in this repository are listed as gaps after a scan.'
      }),
      'Why files that hold no SQL still matter',
      'A job that runs a query kept somewhere else holds no SQL of its own. Without this line a row counting those files reads as a pile of files Ripple learned nothing from.',
      'The query they point at was read separately, so the work in them is not lost - unless the file they name is outside this folder, and then it is named as a gap.'));
  }
  return box;
}

function indexBlock(repo) {
  const files = count(pick(repo, 'files', 'filesIndexed'));
  const branch = fieldOf(repo, 'branch');
  const kinds = countList(pick(repo, 'kinds', 'fileTypes'));
  const unknownRaw = pick(repo, 'unknownExt', 'unknown_ext');
  const unknown = countList(unknownRaw);
  const box = el('div', {}, el('h3', { text: 'What is in the index' }));

  if (kinds.length) {
    const list = el('div', { class: 'chips' });
    kinds.forEach(function (k) {
      list.appendChild(chip(k.ext + ' · ' + (k.count === null ? 'not counted' : num(k.count))));
    });
    box.appendChild(list);
  } else {
    box.appendChild(el('p', { class: 'small muted', text: 'The kinds of file in the index were not reported.' }));
  }

  box.appendChild(el('h4', { text: 'File types Ripple does not open' }));
  if (unknownRaw === undefined) {
    box.appendChild(el('p', {
      class: 'small muted',
      text: 'This build did not report the file types it stepped over, so nothing is known about them.'
    }));
  } else if (!unknown.length) {
    box.appendChild(el('p', { class: 'prose', text: 'No file type in this folder was one Ripple steps over.' }));
  } else {
    const list = el('div', { class: 'chips' });
    unknown.forEach(function (u) {
      list.appendChild(chip((u.ext || 'no extension') + ' · ' + (u.count === null ? 'not counted' : num(u.count))));
    });
    box.appendChild(why(
      list,
      'Why the unopened file types are listed one by one',
      'A repository whose pipeline is written in a file type Ripple does not open looks exactly like a repository with no pipeline in it.',
      'Listing each type by name is what makes the next unlisted one visible instead of silent. The service sends the types it recorded, so treat this as what it reported rather than as a complete inventory.'));
    box.appendChild(el('p', {
      class: 'small muted',
      text: 'Nothing inside those files was read, so nothing inside them was searched. Adding those types to the ones Ripple opens and re-reading the repository is what fixes it.'
    }));
  }

  if (files !== null) {
    box.appendChild(el('p', {
      class: 'prose',
      text: branch
        ? 'Ripple indexed ' + num(files) + ' files from branch ' + branch + '.'
        : 'Ripple indexed ' + num(files) + ' files. No branch was recorded, so this is a folder on this machine rather than a checkout.'
    }));
  }

  box.appendChild(catalogueBlock(repo));
  return box;
}

function neverOpenedTotal(repo) {
  const held = numberOr(count(pick(repo, 'heldOnline')), 0);
  const tooLong = numberOr(count(pick(repo, 'pathTooLong')), 0);
  const skipped = numberOr(count(pick(repo, 'inSkippedDirs')), 0);
  const types = numberOr(totalOf(countList(pick(repo, 'unknownExt', 'unknown_ext'))), 0);
  return held + tooLong + skipped + types;
}

/* The catalogue card has four answers and three of them are not "all clear". */
function catalogueBlock(repo) {
  const box = el('div', {}, el('h4', { text: 'The catalogue' }));
  const c = S.catalogue;
  if (!c) {
    ensureCatalogue();
    box.appendChild(el('p', {
      class: 'small muted',
      text: 'Waiting for the catalogue counts - the tables and columns Ripple learned from the CREATE statements in this folder.'
    }));
    return box;
  }
  if (c.failed) {
    box.appendChild(note('bad', el('p', {
      text: 'The catalogue counts could not be read, so nothing is known about the tables in this folder: ' + c.failed
    })));
    return box;
  }

  const tables = count(pick(c, 'tableCount', 'tables'));
  const columns = count(pick(c, 'columnCount', 'columns'));
  const gaps = listOf(c.gaps);
  const unopened = neverOpenedTotal(repo);

  box.appendChild(kv('Tables learned from CREATE statements', tables === null ? 'Not reported' : num(tables)));
  box.appendChild(kv('Columns written down across them', columns === null ? 'Not reported' : num(columns)));

  if (tables === 0) {
    /* "Every table definition was readable" is technically true of nothing at
     * all, and reads as a clean bill of health for a folder that was never
     * read. */
    box.appendChild(note('bad', el('p', {
      text: 'No table definitions were read, so there is no catalogue to check.'
    })));
    return box;
  }

  if (gaps.length) {
    box.appendChild(why(
      el('span', { text: num(gaps.length) + ' tables here have no column list written down.' }),
      'Why a table has no column list',
      'A table built by copying another one, or built from a SELECT that names no columns, has nowhere in the code that writes its columns down.',
      'Marked as worked out is not the same as guessed: the hop really happened, the column list for it is simply not written anywhere in this repository.'));
    box.appendChild(el('p', {
      class: 'prose',
      text: 'A scan still follows your attribute through these, because a SELECT * carries every column, so the '
        + 'trail does not stop here. What Ripple cannot do is name the columns inside them, so every step past one '
        + 'is marked on the result as worked out rather than read. This is a fact about how the code is written, '
        + 'not a gap in the scan.'
    }));
    const list = scrollBox();
    gaps.forEach(function (g) {
      const table = fieldOf(g, 'table', 'name');
      const reason = fieldOf(g, 'reason', 'why', 'how', 'note');
      list.appendChild(chip(reason ? table + ' - ' + reason : table, 'mono'));
    });
    box.appendChild(list);
    if (unopened > 0) {
      box.appendChild(el('p', {
        class: 'small muted',
        text: 'Files that were never opened are not counted above, so there may be tables in ' + repoName()
          + ' that this card knows nothing about.'
      }));
    }
    return box;
  }

  if (unopened > 0) {
    /* Green directly under a warning that part of the folder went unread is how
     * a partial scan gets reported as a clean one, so this names the repository
     * it is talking about. */
    box.appendChild(note('warn', el('p', {
      text: 'Every table definition in the files that could be opened in ' + repoName()
        + ' was readable. The files above were not opened, so nothing is known about them.'
    })));
    return box;
  }

  box.appendChild(note('good', el('p', { text: 'Every table definition was readable.' })));
  return box;
}

function drawScanPane(root) {
  const pane = x(root, 'scanPane');
  if (!pane) return;
  pane.hidden = !S.busy;
  const spin = x(root, 'scanSpin');
  if (spin) spin.hidden = !S.busy;
  setText(root, 'scanStage', S.busy ? (liveLine || S.busyWhat) : '');
  fill(root, 'scanCounts');
  fill(root, 'scanNote', S.busy
    ? el('p', {
      class: 'small muted',
      text: 'This line does not move on a timer. It changes when the engine reports something new, and reading a real repository takes minutes rather than seconds.'
    })
    : null);
}

async function reindex() {
  const h = await api('/api/reindex', { method: 'POST' });
  S.health = h;
  /* The catalogue was learned from the index that has just been thrown away, so
   * it has to be asked for again rather than shown against new counts. */
  S.catalogue = null;
  catalogueAsked = false;
}

/* On success, CLEAR ANY RESULT ON SCREEN. A finding left up after the folder
 * changes looks entirely right and is about a repository nobody is reading any
 * more. On failure change nothing else: the folder in force must still be the
 * one that was working. */
async function readFolder(wanted) {
  try {
    const h = await postJson('/api/repo/folder', { path: wanted });
    S.health = h;
    S.catalogue = null;
    catalogueAsked = false;
    S.scan = null;
    S.summary = null;
    S.reply = null;
    S.replyEdits = null;
    S.savedAs = '';
    S.productionText = null;
    S.productionRead = null;
    const read = count(pick(repoOf(), 'files'));
    S.folderSaid = (read === null ? 'The service did not report a file count' : num(read) + ' '
      + oneOrMany(read, 'file was', 'files were') + ' read from that folder')
      + '. Any result that was on screen has been cleared, because it was about the folder Ripple was reading before.';
    if (S.maxStep > 3) S.maxStep = 3;
    if (S.step > 3) S.step = 3;
  } catch (err) {
    /* The reason goes where the button is, and nothing else changes. The folder
     * in force must still be the one that was working. */
    S.folderSaid = 'That folder was not read, and nothing was changed: ' + errorText(err);
  }
}

/* ------------------------------------------------- the published-tables box */

function currentProductionText() {
  if (typeof S.productionText === 'string') return S.productionText;
  const rule = S.health ? S.health.productionRule : null;
  S.productionText = str(rule ? rule.text : '');
  return S.productionText;
}

/* ONE function, used by the repository screen and by settings. The list is
 * checked as it is typed, with a 600ms pause, and the answer is painted into
 * its own node - never through render(), or the cursor leaves the box. */
function productionControl(box, readHost, saidHost) {
  box.value = currentProductionText();
  box.classList.add('mono');
  const repaint = function () {
    readHost.textContent = '';
    addKids(readHost, [productionReadBlock(S.productionRead)]);
  };
  repaint();

  box.addEventListener('input', function (ev) {
    S.productionText = ev.target.value;
    if (productionTimer) window.clearTimeout(productionTimer);
    productionTimer = window.setTimeout(function () {
      readProductionList(S.productionText, readHost);
    }, 600);
  });

  /* Check the list already in force the moment the screen opens, rather than
   * waiting for somebody to touch the box. A rule that matches nothing is worth
   * knowing about before it is edited, not after. */
  if (!S.productionRead) {
    window.setTimeout(function () { readProductionList(currentProductionText(), readHost); }, 0);
  }

  const foot = el('div', { class: 'foot' },
    buttonEl('Save this list', 'pri sm', function () {
      saveProductionList(box.value, saidHost);
    }));
  readHost.parentNode.insertBefore(foot, saidHost);
  saidHost.textContent = str(S.productionSaid);
  const storage = el('p', { class: 'small muted', text: productionStorageLine() });
  saidHost.parentNode.insertBefore(storage, saidHost.nextSibling);
}

function productionStorageLine() {
  const from = str(pick(S.health, 'productionFrom'));
  if (from === 'entered') {
    return 'This list was typed in during this run of Ripple. It is held in memory only, so a restart loses it - RIPPLE_PROD_TABLES is what keeps it.';
  }
  if (from === 'environment') {
    return 'This list came from RIPPLE_PROD_TABLES, so it comes back the same way every time Ripple starts.';
  }
  if (from === 'default') {
    return 'Nothing has been set, so the list in force is Ripple\u2019s own guess at how published tables are named.';
  }
  return 'The service did not say where this list is kept, so treat it as held only while Ripple is running.';
}

function readProductionList(text, readHost) {
  postJson('/api/production/read', { text: text }).then(function (res) {
    S.productionRead = res;
    readHost.textContent = '';
    addKids(readHost, [productionReadBlock(res)]);
  }, function (err) {
    S.productionRead = { failed: errorText(err) };
    readHost.textContent = '';
    addKids(readHost, [productionReadBlock(S.productionRead)]);
  });
}

function saveProductionList(text, saidHost) {
  postJson('/api/production', { text: text }).then(function (h) {
    S.health = h;
    S.productionText = text;
    S.productionSaid = 'Saved. ' + productionStorageLine();
    render();
  }, function (err) {
    S.productionSaid = 'Not saved: ' + errorText(err);
    saidHost.textContent = S.productionSaid;
  });
}

function productionReadBlock(res) {
  const box = el('div', {});
  if (!res) {
    box.appendChild(el('p', { class: 'small muted', text: 'The list has not been checked yet.' }));
    return box;
  }
  if (res.failed) {
    box.appendChild(note('bad', el('p', { text: 'The list could not be checked: ' + res.failed })));
    return box;
  }

  const entries = listOf(res.entries);
  const names = count(pick(res, 'nameCount')) !== null
    ? count(pick(res, 'nameCount'))
    : listOf(res.names).length;
  const patterns = count(pick(res, 'patternCount')) !== null
    ? count(pick(res, 'patternCount'))
    : listOf(res.patterns).length;

  box.appendChild(el('p', {
    class: 'prose',
    text: plural(names, 'table name', 'table names') + ' and ' + plural(patterns, 'pattern', 'patterns')
      + ' were read from this list.'
  }));

  if (entries.length) {
    const chips = scrollBox();
    entries.forEach(function (e) {
      const isPattern = fieldOf(e, 'kind') !== 'exact';
      chips.appendChild(chip(fieldOf(e, 'raw', 'match', 'value', 'name'), isPattern ? 'pattern' : 'mono'));
    });
    box.appendChild(chips);
    box.appendChild(el('p', { class: 'small muted', text: 'The amber chips are patterns. The rest are table names.' }));
  }

  if (names === 0 && patterns === 0) {
    box.appendChild(note('bad', el('p', {
      text: 'Nothing in this paste was read as a table name. Ripple falls back to its own guess - names ending '
        + '_PROD, _PRD or _PUBLISHED - which is almost certainly not how your tables are named. Paste the list '
        + 'again, one table per line.'
    })));
  }

  const notes = listOf(res.notes);
  if (notes.length) {
    const list = el('div', {});
    notes.forEach(function (n) { list.appendChild(el('p', { text: typeof n === 'string' ? n : fieldOf(n, 'text', 'why', 'reason') })); });
    box.appendChild(el('h4', { text: 'What was left out of the paste, and why' }));
    box.appendChild(list);
  }

  const column = fieldOf(res, 'column');
  if (column) box.appendChild(kv('Column used', column));

  box.appendChild(productionCheckBlock(res, names));
  return box;
}

/* check comes from production.check_against_repo, and this page could not see
 * that file. Every key below is read under several spellings and, where none of
 * them is there, the screen says the check was not reported rather than showing
 * a nought. A missing-table count of zero because nothing was checked reads
 * exactly like a list that all matched. */
function productionCheckBlock(res, names) {
  const check = res.check && typeof res.check === 'object' ? res.check : null;
  const box = el('div', {});
  const filesRead = numberOr(count(pick(repoOf(), 'files')), 0);

  if (filesRead === 0) {
    box.appendChild(note('warn', el('p', {
      text: 'Nothing has been read from a repository yet, so this list has not been checked against one and Ripple '
        + 'cannot say whether these tables exist. Choose the repository first.'
    })));
    return box;
  }
  if (!check) {
    box.appendChild(note('warn', el('p', {
      text: 'The service did not send a check of this list against the repository, so nothing here says whether '
        + 'these tables exist in it.'
    })));
    return box;
  }

  const missing = check.missing && typeof check.missing === 'object' ? check.missing : check;
  const notWritten = listOf(pick(missing, 'notWritten', 'not_written', 'notInRepo', 'unknown'));
  const noBuilder = listOf(pick(missing, 'noBuilder', 'no_builder', 'notBuilt', 'noWriter'));
  const couldBe = listOf(pick(check, 'couldBePattern', 'could_be_pattern', 'maybePatterns'));
  const matches = listOf(pick(check, 'patternMatches', 'pattern_matches', 'patterns'));
  const knownShape = pick(missing, 'notWritten', 'not_written', 'notInRepo', 'unknown') !== undefined
    || pick(missing, 'noBuilder', 'no_builder', 'notBuilt', 'noWriter') !== undefined;

  if (!knownShape) {
    box.appendChild(note('warn', el('p', {
      text: 'The service answered with a shape this page does not recognise, so the missing-table check is not '
        + 'shown. Do not read that as every table on the list being present.'
    })));
  } else {
    const total = notWritten.length + noBuilder.length;
    if (total > 0) {
      box.appendChild(note('bad',
        el('p', {
          text: total + ' of the ' + names + ' ' + oneOrMany(names, 'table', 'tables')
            + ' on this list ' + oneOrMany(total, 'is', 'are') + ' not in this repository. Either the name is '
            + 'spelled differently here, or the table is built somewhere Ripple could not read. Until that is '
            + 'settled, a clean result for those tables means nothing.'
        })));
      if (notWritten.length) {
        box.appendChild(el('h4', { text: 'Not written anywhere in this repository' }));
        const a = scrollBox();
        notWritten.forEach(function (n) { a.appendChild(chip(fieldOf(n, 'name', 'table', 'value', 'raw'), 'mono')); });
        box.appendChild(a);
      }
      if (noBuilder.length) {
        box.appendChild(el('h4', { text: 'The name is here, but nothing readable builds it' }));
        const b = scrollBox();
        noBuilder.forEach(function (n) { b.appendChild(chip(fieldOf(n, 'name', 'table', 'value', 'raw'), 'mono')); });
        box.appendChild(b);
      }
    } else {
      box.appendChild(note('good', el('p', {
        text: 'Every table name on this list was found in this repository.'
      })));
    }
  }

  if (couldBe.length) {
    box.appendChild(el('h4', { text: 'Was one of these meant as a pattern' }));
    couldBe.forEach(function (cb) {
      const ends = count(pick(cb, 'endsWith', 'ends_with', 'matched'));
      box.appendChild(el('p', {
        class: 'prose',
        text: fieldOf(cb, 'name', 'value', 'raw') + ' matches no table by name'
          + (ends === null ? ', but some tables here end with it.' : ', but ' + plural(ends, 'table here ends', 'tables here end') + ' with it.')
          + (fieldOf(cb, 'suggestion') ? ' Written as ' + fieldOf(cb, 'suggestion') + ' it would match them.' : '')
      }));
    });
    box.appendChild(el('p', { class: 'small muted', text: 'Ripple has not decided this either way.' }));
  }

  if (matches.length) {
    box.appendChild(el('h4', { text: 'What each pattern matches here' }));
    matches.forEach(function (pm) {
      const n = count(pick(pm, 'matched', 'count', 'tables'));
      const line = fieldOf(pm, 'pattern', 'raw', 'name') + ' - '
        + (n === null ? 'the service did not say how many tables it matches'
          : plural(n, 'table', 'tables'))
        + (n === 0 ? ' - this pattern is doing nothing at all' : '');
      box.appendChild(n === 0 ? note('warn', el('p', { text: line })) : el('p', { class: 'prose', text: line }));
    });
  }
  return box;
}

/* --------------------------------------------------------------- the scan */

function upstreamForScan() {
  const v = S.vals;
  if (!v) return [];
  const out = [];
  listOf(v.tables).forEach(function (row) {
    const table = str(row.table).trim();
    const attrs = attrList(row.attrs);
    if (table && attrs.length) out.push({ table: table, attrs: attrs });
  });
  return out;
}

function startScanNow(hops) {
  const upstream = upstreamForScan();
  if (!upstream.length) {
    lastError = 'No table and attribute have been confirmed, so there is nothing for the scan to follow.';
    render();
    return;
  }
  const body = { upstream: upstream, changeKind: str(S.vals.changeType) };
  if (hops) body.maxHops = hops;
  run(async function () {
    const res = await postJson('/api/scan', body);
    S.scan = res;
    S.summary = null;
    S.reply = null;
    S.replyEdits = null;
    S.savedAs = '';
    S.saveError = '';
    S.mapTab = 0;
    S.openGroups = new Set();
    S.openRows = new Set();
    S.groupsDefaulted = false;
    S.step = 4;
    if (stepOrder().indexOf(4) > stepOrder().indexOf(S.maxStep)) S.maxStep = 4;
  }, hops ? 'Following the trails ' + hops + ' renames deep' : 'Following your attributes through the repository');
}

/* ====================================================================
   STEP 4 - the findings
   ==================================================================== */

function statsOf() {
  const scan = S.scan;
  return scan && scan.stats ? scan.stats : {};
}

function stepFindings(root) {
  const scan = S.scan;
  if (!scan) {
    fill(root, 'headline', note('warn',
      el('h3', { text: 'No scan on this screen' }),
      el('p', { text: 'No scan has been run in this session, so there is nothing to show. Nothing was scanned.' }),
      el('div', { class: 'foot' }, buttonEl('Go to the repository', 'pri sm', function () { goStep(3); }))));
    onClick(root, 'back4', function () { goStep(3); });
    onClick(root, 'next4', function () { goStep(5); }, true);
    return;
  }

  drawHeadline(root, scan);
  drawStatRows(root, scan);
  drawCoverage(root, scan);
  drawQualifiers(root, scan);
  drawGroups(root, scan);
  drawHowToCheck(root, scan);

  onClick(root, 'back4', function () { goStep(3); });
  onClick(root, 'next4', function () { goStep(5); }, S.busy);
}

/* The headline badge replaces the risk word twice, and the coverage badge is
 * not drawn at all when no files were read or when the column was never met:
 * "whole trail seen" reads as a reassurance over a scan that followed no trail
 * at all. */
function headlineBadges(scan) {
  const wrap = el('div', { class: 'chips' });
  const files = count(scan.filesScanned);
  if (files === 0) {
    wrap.appendChild(badge('Nothing was scanned', 'amber'));
  } else if (scan.lookupFailed) {
    wrap.appendChild(badge('Column not found - nothing was checked', 'amber'));
  } else {
    const risk = fieldOf(scan, 'risk') || 'unknown';
    const tone = risk === 'high' ? 'red'
      : risk === 'medium' ? 'amber'
        : (risk === 'none' || risk === 'low') ? 'green' : 'grey';
    wrap.appendChild(badge(risk + ' risk', tone));
  }
  if (files !== null && files > 0 && !scan.lookupFailed) {
    const cov = scan.coverage || {};
    if (cov.complete) wrap.appendChild(badge('whole trail seen', 'green'));
    else {
      const gaps = listOf(cov.gaps).length;
      wrap.appendChild(badge(gaps + ' ' + oneOrMany(gaps, 'gap', 'gaps') + ' in what Ripple could see', 'amber'));
    }
  }
  return wrap;
}

/* The line under the title has to be true of the screen under it. */
function findingsLede(scan) {
  if (scan.lookupFailed) {
    return 'Ripple never met these column names. Check the spelling before reading anything below.';
  }
  if (listOf(scan.groups).length > 0) {
    return 'Every finding grouped under the published table it puts at risk.';
  }
  if (listOf(scan.reached).length > 0) {
    return 'Nothing matched your published-table rule. Every table the change does reach is below.';
  }
  return 'Nothing matched your published-table rule, and the change reached no other table either.';
}

function drawHeadline(root, scan) {
  const repo = repoOf();
  const read = count(scan.filesScanned);
  const matched = count(scan.filesMatched);
  const folder = fieldOf(pick(scan, 'repo') || {}, 'label') || fieldOf(repo, 'path');

  const counts = read === null
    ? 'The service did not report how many files were read.'
    : num(read) + ' ' + oneOrMany(read, 'file read', 'files read') + ' · '
      + (matched === null ? 'no count of how many mention the names you confirmed'
        : num(matched) + ' ' + oneOrMany(matched, 'mentions', 'mention') + ' the names you confirmed');

  fill(root, 'headline',
    el('section', { class: 'card clip' },
      el('div', { class: 'chead' },
        el('span', { class: 'tag', text: 'Step 4' }),
        el('h2', { text: 'What the change reaches' }),
        el('span', { class: 'spacer' }),
        headlineBadges(scan)),
      el('div', { class: 'pad' },
        el('p', { class: 'prose', text: findingsLede(scan) }),
        el('p', { class: 'mono', text: folder || 'Ripple did not report which folder it read.' }),
        el('p', { class: 'prose', text: counts }),
        /* This sentence qualifies every other sentence on the screen and is
         * printed on every scan, clean or not. It is the commonest way to be
         * wrong with this tool. */
        note('info', el('p', {
          text: 'Ripple read ' + (read === null ? 'these files' : num(read) + ' ' + oneOrMany(read, 'file', 'files'))
            + ' and nothing else, so "no impact" means "nothing in this repository", not "nothing anywhere". '
            + 'A job in another repository, a scheduled query, or a dashboard built straight on the table is '
            + 'outside what it can see.'
        })))));
}

/* Both rows use the SAME grid, so a card is the same size wherever it sits and
 * a short row leaves the rest of the row empty. */
function drawStatRows(root, scan) {
  const st = statsOf();
  const repo = repoOf();

  const reach = [];
  reach.push(statCard('Production tables at risk', st.productionTables, 'On your published list', 'red'));
  if (numberOr(count(st.productionStopsLoading), 0) > 0) {
    reach.push(statCard('Published tables that stop refreshing', st.productionStopsLoading,
      'Their columns do not change - their data stops', 'red'));
  }
  if (numberOr(count(st.feedsBroken), 0) > 0) {
    reach.push(statCard('Deliveries out of the warehouse', st.feedsBroken,
      'Files another team reads - tell them', 'red'));
  }
  reach.push(statCard('Other tables reached', st.tablesReached, 'Not on your published list'));
  reach.push(statCard('Attributes impacted', st.attributesImpacted, 'Of those you confirmed'));
  reach.push(statCard('Files to change', st.filesWithImpact));
  reach.push(statCard('Breaking usages', st.breakingUsages));

  const skippedDirs = count(pick(repo, 'inSkippedDirs'));
  const skippedNames = joinNames(pick(repo, 'skippedDirNames', 'skippedFolderNames'), ', ');
  const types = countList(scan.fileTypesUnopened);
  const typeTotal = totalOf(types);

  const gapCards = [];
  gapCards.push(statCard('To check by hand', st.couldNotRead, 'Ripple could not follow these'));
  /* A count that was not reported is drawn saying so. Only an actual nought
   * takes a card off this row - a trail Ripple gave up on is not a trail that
   * ended, and leaving either off makes a result built on half a picture look,
   * number for number, exactly like one built on the whole picture. */
  if (count(st.trailsCutShort) !== 0) {
    gapCards.push(statCard('Trails cut short', st.trailsCutShort,
      'Stopped at ' + (count(scan.maxHops) === null ? 'the hop limit' : num(scan.maxHops) + ' renames deep'), 'red'));
  }
  if (count(st.tablesNotVisible) !== 0) {
    gapCards.push(statCard('Tables not fully readable', st.tablesNotVisible, starTablesSubLine(scan)));
  }
  if (count(st.neverOpened) !== 0) {
    gapCards.push(statCard('Never opened', st.neverOpened, 'Not on this machine, or path too long', 'red'));
  }
  if (skippedDirs !== 0) {
    gapCards.push(statCard('In folders Ripple skips', skippedDirs, skippedNames || 'folder names not reported'));
  }
  if (typeTotal !== 0) {
    gapCards.push(statCard('Types Ripple does not open', typeTotal,
      types.map(function (t) { return t.ext || 'no extension'; }).join(', ')));
  }

  /* Every one of these is named in the condition itself. A clean bill of health
   * printed directly above a card saying a notebook was never looked inside is
   * the tool contradicting itself on one screen, and the reader believes the
   * green one. A count that was never reported is not a nought, so it does not
   * earn the note either. */
  const clean = numberOr(count(scan.filesScanned), 0) > 0
    && count(st.couldNotRead) === 0
    && count(st.trailsCutShort) === 0
    && count(st.tablesNotVisible) === 0
    && count(st.neverOpened) === 0
    && skippedDirs === 0
    && typeTotal === 0;

  fill(root, 'stats',
    statsRow('What the change reaches', reach),
    statsRow('What this result does not cover', gapCards,
      clean
        ? note('good', el('p', {
          text: 'Every file was opened and read - nothing was skipped, and nothing was left for a person to follow by hand.'
        }))
        : null));
}

/* The sub-line names which kind of unreadable, read off starTables[].how, so
 * the card never describes a statement the file does not contain. */
function starTablesSubLine(scan) {
  let stars = 0;
  let copies = 0;
  listOf(scan.starTables).forEach(function (t) {
    const how = fieldOf(t, 'how');
    if (!how || how === 'star' || how === 'placeholder') stars += 1;
    else copies += 1;
  });
  if (stars > 0 && copies > 0) return 'Copied whole, or SELECT * - no column list';
  if (copies > 0) return 'Copied or renamed whole - no column list';
  return 'Built with SELECT * - no column list';
}

/* The never-opened card sits above the findings and directly under the counts,
 * because it is the card that decides whether every number above it can be
 * believed, and the bottom of a long page is where a caveat goes to be
 * missed. */
function drawCoverage(root, scan) {
  const host = fill(root, 'coverage');
  if (!host) return;

  const held = listOf(scan.heldOnline);
  const tooLong = listOf(scan.pathTooLong);
  if (held.length || tooLong.length) {
    const body = el('div', {},
      el('p', {
        class: 'prose',
        text: 'These files are named in the repository and Ripple could not open them, so nothing in them was read and nothing in them was counted.'
      }));
    if (held.length) {
      body.appendChild(el('h4', {
        text: held.length + ' ' + oneOrMany(held.length, 'file is', 'files are') + ' not on this machine'
      }));
      const a = scrollBox();
      held.forEach(function (f) { a.appendChild(chip(fieldOf(f, 'path', 'file', 'name'), 'mono')); });
      body.appendChild(a);
    }
    if (tooLong.length) {
      body.appendChild(el('h4', {
        text: tooLong.length + ' ' + oneOrMany(tooLong.length, 'path was', 'paths were') + ' too long to open'
      }));
      const b = scrollBox();
      tooLong.forEach(function (f) { b.appendChild(chip(fieldOf(f, 'path', 'file', 'name'), 'mono')); });
      body.appendChild(b);
    }
    host.appendChild(note('bad', el('h3', { text: 'Files that were never opened' }), body));
  }

  /* Not drawn at all when the column was never met: "every step of every trail
   * was read" over a trail that does not exist is reassuring nonsense in longer
   * words. */
  if (scan.lookupFailed) return;
  const cov = scan.coverage || {};
  const files = count(pick(cov, 'filesMatched')) !== null ? count(cov.filesMatched) : count(scan.filesMatched);

  if (cov.complete) {
    host.appendChild(note('good',
      el('h3', { text: 'Where Ripple could not see through' }),
      el('p', {
        text: 'Every step of every trail above was read out of the SQL. No file that mentions these names went '
          + 'unread. No table on the way was built with a SELECT *. No trail was still going when Ripple stopped. '
          + 'Nothing below is worked out rather than read.'
      }),
      el('p', {
        text: files === null
          ? 'That is true of the files listed above and of nothing outside them.'
          : 'That is true of these ' + num(files) + ' ' + oneOrMany(files, 'file', 'files') + ' and of nothing outside them.'
      })));
    return;
  }

  const gaps = listOf(cov.gaps);
  const body = el('div', {},
    el('p', {
      class: 'prose',
      text: 'The answer above rests on these. Each is a place Ripple could not see through. They are listed as '
        + 'counts rather than as a score, because there is no honest way to say what share of the whole trail they are.'
    }));
  if (!gaps.length) {
    body.appendChild(el('p', { class: 'small muted', text: 'The service did not list which gaps they are.' }));
  }
  gaps.forEach(function (g) {
    const n = count(pick(g, 'count'));
    body.appendChild(el('p', { class: 'prose' },
      el('strong', { text: n === null ? 'some' : num(n) }),
      ' ' + fieldOf(g, 'what', 'text', 'why')));
  });
  const unread = count(pick(cov, 'filesUnread'));
  if (unread !== null && unread > 0) {
    body.appendChild(el('p', {
      class: 'small muted',
      text: num(unread) + ' ' + oneOrMany(unread, 'file was', 'files were') + ' not read.'
    }));
  }
  host.appendChild(note('warn', el('h3', { text: 'Where Ripple could not see through' }), body));
}

/* ---- the cards that qualify the answer, beside the answer they qualify ---- */

function drawQualifiers(root, scan) {
  const host = fill(root, 'gaps');
  if (!host) return;
  const cards = [
    qualifyCutShort(scan),
    qualifyStarTables(scan),
    qualifyMergedNames(scan),
    qualifyWildcardNames(scan),
    qualifyTwoDefinitions(scan),
    qualifySkippedInFolders(scan),
    qualifyNamedByFile(scan),
    qualifyFileTypes(scan)
  ].filter(function (c) { return c; });
  if (!cards.length) return;
  host.appendChild(el('h3', { text: 'Each place Ripple could not read' }));
  cards.forEach(function (c) { host.appendChild(c); });
}

/* This one comes first, before all the others. */
function qualifyCutShort(scan) {
  const cut = listOf(scan.cutShort);
  if (!cut.length) return null;
  const hops = count(scan.maxHops);
  const body = el('div', {},
    el('p', {
      class: 'prose',
      text: cut.length + ' ' + oneOrMany(cut.length, 'trail stopped', 'trails stopped')
        + ' because of a setting rather than because the code ran out. Ripple follows a column through '
        + (hops === null ? 'a set number of' : num(hops)) + ' renames and then stops, and a trail that was '
        + 'still going when it stopped has not ended.'
    }));
  const chips = scrollBox();
  cut.forEach(function (c) {
    chips.appendChild(chip(fieldOf(c, 'table', 'name') + ' · ' + fieldOf(c, 'attr', 'column'), 'mono'));
  });
  body.appendChild(chips);
  body.appendChild(el('p', {
    class: 'prose',
    text: '"Does not reach a published table" is not something this result can tell you about '
      + oneOrMany(cut.length, 'it', 'them') + '.'
  }));
  if (hops !== null && hops < HOP_CEILING) {
    const deeper = Math.min(hops * 2, HOP_CEILING);
    body.appendChild(el('div', { class: 'foot' },
      buttonEl('Follow these ' + deeper + ' renames deep instead', 'pri sm', function () {
        startScanNow(deeper);
      }, S.busy)));
    body.appendChild(el('p', {
      class: 'small muted',
      text: 'No files are read a second time, and it changes nothing on the settings screen - it applies to this one scan only.'
    }));
  }
  return note('bad', el('h3', { text: 'Trails cut short by the hop limit' }), body);
}

function qualifyStarTables(scan) {
  const tables = listOf(scan.starTables);
  if (!tables.length) return null;
  const body = el('div', {},
    el('p', {
      class: 'prose',
      text: 'Ripple could not read a column list for ' + oneOrMany(tables.length, 'this table', 'these tables')
        + ', so anything past ' + oneOrMany(tables.length, 'it', 'them') + ' is worked out rather than read.'
    }));
  const list = scrollBox();
  tables.forEach(function (t) {
    const how = fieldOf(t, 'how');
    let says;
    if (!how || how === 'star') says = 'built with SELECT *';
    else if (how === 'placeholder') {
      const written = fieldOf(t, 'note', 'starNote', 'star_note');
      says = 'a placeholder the job fills in at run time' + (written ? ' - the file writes ' + written : '');
    } else says = 'the whole table copied or renamed with ' + how;
    list.appendChild(chip(fieldOf(t, 'table', 'name') + ' - ' + says, 'mono'));
  });
  body.appendChild(list);
  return note('warn', el('h3', { text: 'Tables whose column list is not readable' }), body);
}

function qualifyMergedNames(scan) {
  const merged = listOf(scan.mergedNames);
  if (!merged.length) return null;
  let anyCapitals = false;
  const list = scrollBox();
  merged.forEach(function (m) {
    if (fieldOf(m, 'reason') === 'capitals') {
      anyCapitals = true;
      list.appendChild(chip(fieldOf(m, 'a', 'spellingA', 'first') + '  vs  '
        + fieldOf(m, 'b', 'spellingB', 'second') + ' - same name, different capitals', 'mono'));
    } else {
      list.appendChild(chip(fieldOf(m, 'table', 'name') + ' - in '
        + (joinNames(m.datasets, ', ') || fieldOf(m, 'datasets')), 'mono'));
    }
  });
  const body = el('div', {}, list);
  if (anyCapitals) {
    body.appendChild(el('p', {
      class: 'prose',
      text: 'BigQuery treats capitals as significant, so two names differing only by case really are two tables '
        + 'there. Ripple cannot tell whether that is what your code means or just how it was typed.'
    }));
  }
  body.appendChild(el('p', {
    class: 'prose',
    text: 'Ripple followed all of them, because missing a chain is worse than showing a row you can dismiss by '
      + 'opening the file. Findings under these names may be about either table, so check before acting on one.'
  }));
  return note('warn', el('h3', { text: 'One name standing for more than one table' }), body);
}

function qualifyWildcardNames(scan) {
  const wild = listOf(scan.wildcardNames);
  if (!wild.length) return null;
  let familyOnly = false;
  const list = scrollBox();
  wild.forEach(function (w) {
    if (w && w.familyOnly) familyOnly = true;
    list.appendChild(chip(fieldOf(w, 'pattern', 'table', 'name'), 'mono'));
  });
  const body = el('div', {},
    el('p', {
      class: 'prose',
      text: oneOrMany(wild.length, 'This table was', 'These tables were')
        + ' read through a wildcard rather than by name, so which tables the statement really covers depends on '
        + 'what exists when the job runs.'
    }),
    list);
  if (familyOnly) {
    body.appendChild(note('warn', el('p', {
      text: 'At least one pattern matched only the family name without its separator. BigQuery would match nothing '
        + 'there, so every row from it is marked "table not stated".'
    })));
  }
  return note('warn', el('h3', { text: 'Tables read through a wildcard rather than by name' }), body);
}

function qualifyTwoDefinitions(scan) {
  const two = listOf(scan.twoDefinitions);
  if (!two.length) return null;
  const list = scrollBox();
  two.forEach(function (t) {
    list.appendChild(chip(fieldOf(t, 'table', 'name') + ' - '
      + (listOf(t.files).join(', ') || fieldOf(t, 'files')), 'mono'));
  });
  return note('warn',
    el('h3', { text: 'Tables built from scratch in more than one file' }),
    el('p', {
      class: 'prose',
      text: 'Only one of them can be the one that runs, and nothing in the code says which. Check your scheduler '
        + 'before acting on a finding under these names.'
    }),
    list);
}

function qualifySkippedInFolders(scan) {
  const skipped = listOf(scan.skippedInFolders);
  const folders = listOf(scan.skippedFolderNames);
  const counted = count(scan.skippedInFolders) !== null ? count(scan.skippedInFolders) : skipped.length;
  if (!skipped.length && !folders.length) return null;
  const list = scrollBox();
  folders.forEach(function (f) { list.appendChild(chip(fieldOf(f, 'name', 'folder', 'path'), 'mono')); });
  return note('warn',
    el('h3', { text: 'Code files not read because of the folder they are in' }),
    el('p', {
      class: 'prose',
      text: counted + ' code ' + oneOrMany(counted, 'file was', 'files were') + ' not read because of the folder '
        + oneOrMany(counted, 'it is', 'they are') + ' in.'
    }),
    folders.length ? list : null,
    /* No promise of a control that is not there. This build has no route that
     * changes the skip list, so the screen says where it really lives. */
    el('p', {
      class: 'prose',
      text: 'If the pipeline really runs from one of those folders, that skip list is set on the service. There is '
        + 'no route in this build to change it from this page.'
    }));
}

function qualifyNamedByFile(scan) {
  const named = listOf(scan.namedByFile);
  if (!named.length) return null;
  const list = scrollBox();
  named.forEach(function (t) {
    list.appendChild(chip(fieldOf(t, 'table', 'name') + ' - named by '
      + (fieldOf(t, 'tool', 'namedBy', 'named_by') || 'the file') + ' · ' + fieldOf(t, 'file'), 'mono'));
  });
  return note('warn',
    el('h3', { text: 'Tables named after their file rather than by the SQL' }),
    el('p', {
      class: 'prose',
      text: 'The SQL in these files does not name the table it builds. The name comes from the file, so opening the '
        + 'file will show the query and not the name.'
    }),
    list);
}

/* The repository screen already counts these; the ANSWER has to as well. A
 * caveat may never live on a different screen from the answer it qualifies. */
function qualifyFileTypes(scan) {
  const types = countList(scan.fileTypesUnopened);
  if (!types.length) return null;
  const total = totalOf(types);
  const list = scrollBox();
  const shown = types.slice(0, MAX_TYPE_CHIPS);
  shown.forEach(function (t) {
    list.appendChild(chip((t.ext || 'no extension') + ' - ' + (t.count === null ? 'not counted' : num(t.count))));
  });
  const body = el('div', {},
    el('p', {
      class: 'prose',
      text: (total === null ? 'Some files are' : num(total) + ' ' + oneOrMany(total, 'file is', 'files are'))
        + ' of a type Ripple does not open. Ripple opens SQL and the file types that normally hold SQL, so if the '
        + 'chain passes through a notebook or a Terraform file the answer stops there. Notebooks and Terraform '
        + 'files are the usual ones to check.'
    }),
    list);
  if (types.length > shown.length) {
    body.appendChild(el('p', {
      class: 'small muted',
      text: (types.length - shown.length) + ' more '
        + oneOrMany(types.length - shown.length, 'type is', 'types are') + ' not listed here.'
    }));
  }
  return note('warn', el('h3', { text: 'File types Ripple does not open' }), body);
}

/* ------------------------------- the findings themselves ----------------- */

function productionRuleText() {
  const one = str(pick(S.health, 'production'));
  if (one) return one;
  const rule = S.health ? S.health.productionRule : null;
  return rule ? str(rule.oneLine) : '';
}

function breakingCount(rows) {
  let n = 0;
  listOf(rows).forEach(function (r) { if (r && r.breaking) n += 1; });
  return n;
}

/* Worst first: most breaking usages, then most rows. */
function worstFirst(cards) {
  return cards.slice().sort(function (a, b) {
    const ab = breakingCount(a.rows);
    const bb = breakingCount(b.rows);
    if (ab !== bb) return bb - ab;
    return listOf(b.rows).length - listOf(a.rows).length;
  });
}

function cardsFrom(list, kind) {
  return listOf(list).map(function (g) {
    return {
      kind: kind,
      table: fieldOf(g, 'prod', 'table', 'name'),
      note: fieldOf(g, 'note'),
      rows: listOf(g.rows)
    };
  });
}

function drawGroups(root, scan) {
  const groups = cardsFrom(scan.groups, 'prod');
  const reached = cardsFrom(scan.reached, 'reached');
  const other = listOf(scan.other);
  const files = count(scan.filesScanned);

  const notes = fill(root, 'groupsNote');
  const groupHost = fill(root, 'groups');
  const reachedNote = fill(root, 'reachedNote');
  const reachedHost = fill(root, 'reached');
  const otherNote = fill(root, 'otherNote');
  const otherHost = fill(root, 'other');
  if (!notes || !groupHost) return;

  if (files === 0) {
    /* Not a tick, and not "no impact". Nothing was scanned. */
    notes.appendChild(note('bad',
      el('h3', { text: 'Nothing was scanned' }),
      el('p', {
        text: 'No file was read, so this result says nothing about your pipeline. Choose a repository and run the '
          + 'scan again.'
      }),
      el('div', { class: 'foot' }, buttonEl('Open settings', 'ghost sm', function () { goScreen('settings'); }))));
    return;
  }

  /* Drawn before the clean result, not after it. A guessed naming rule matters
   * most on the screen that says nothing was found. */
  if (str(pick(S.health, 'productionFrom')) === 'default') {
    notes.appendChild(note('warn', el('p', {
      text: 'Nobody has said which tables this team publishes, so the rule in force is Ripple’s own guess at '
        + 'how they are named. Every published-table count on this screen is being judged against that guess.'
    })));
  }

  if (!groups.length && !reached.length && !other.length) {
    /* A green tick only when there is genuinely nothing anywhere. */
    notes.appendChild(note('good',
      el('h3', { text: 'Nothing in this repository is impacted' }),
      el('p', {
        text: 'Ripple read ' + (files === null ? 'the files in the index' : num(files) + ' ' + oneOrMany(files, 'file', 'files'))
          + ' and found no published table, no other table and no loose usage anywhere.'
      })));
    return;
  }

  if (!groups.length && (reached.length || other.length)) {
    const rule = productionRuleText();
    notes.appendChild(note('warn',
      el('h3', { text: 'Nothing matched your published-table rule' }),
      el('p', {
        text: 'The change reaches tables in this repository, and not one of them matched the rule that says which '
          + 'tables your team publishes.'
      }),
      el('p', { class: 'mono', text: rule || 'Ripple did not report the rule that is in force.' }),
      el('p', { text: 'Until that list is right, "no production table is impacted" is an accident rather than a result.' }),
      el('div', { class: 'foot' },
        buttonEl('Check the published-tables list', 'pri sm', function () { goScreen('settings'); }))));
  }

  /* The two kinds of impact that are not "a column of this table changes". They
   * sit here, above the findings, with their own words. */
  const stops = stopsLoadingBlock(scan);
  if (stops) notes.appendChild(stops);
  const feeds = feedsBlock(scan);
  if (feeds) notes.appendChild(feeds);

  const orderedProd = worstFirst(groups);
  const orderedReached = worstFirst(reached);
  const ordered = orderedProd.concat(orderedReached);
  const drawn = ordered.slice(0, MAX_TABLE_CARDS);
  const rest = ordered.slice(MAX_TABLE_CARDS);

  if (drawn.length) {
    notes.appendChild(el('p', {
      class: 'small muted',
      text: 'Sorted worst first - most breaking usages, then most findings. The first card is open; the rest are '
        + 'closed so the page can be read.'
    }));
  }

  let firstOpened = false;
  drawn.forEach(function (c, i) {
    const openByDefault = !firstOpened;
    firstOpened = true;
    const card = groupCard(c, i, openByDefault);
    (c.kind === 'prod' ? groupHost : (reachedHost || groupHost)).appendChild(card);
  });

  if (reachedNote) {
    const shownReached = drawn.filter(function (c) { return c.kind === 'reached'; }).length;
    if (!reached.length) {
      reachedNote.appendChild(el('p', {
        class: 'small muted',
        text: 'The chain ended at no table outside your published list.'
      }));
    } else {
      reachedNote.appendChild(el('p', {
        class: 'prose',
        text: 'These are not thrown away. The change reaches them either way, and Ripple cannot say whether anyone '
          + 'outside your team reads them.'
      }));
      if (shownReached < reached.length) {
        reachedNote.appendChild(el('p', {
          class: 'small muted',
          text: (reached.length - shownReached) + ' of them are in the list of every other table below rather than drawn as cards.'
        }));
      }
    }
  }

  if (rest.length) {
    const list = scrollBox();
    rest.forEach(function (c) {
      list.appendChild(chip((c.kind === 'prod' ? 'published · ' : '') + (c.table || 'no table named')
        + ' · ' + plural(listOf(c.rows).length, 'finding', 'findings'), 'mono'));
    });
    notes.appendChild(el('div', {},
      el('h4', { text: 'Every other table the change reaches' }),
      el('p', {
        class: 'prose',
        text: 'Ripple drew the ' + MAX_TABLE_CARDS + ' worst tables above. Nothing has been dropped. The remaining '
          + rest.length + ' ' + oneOrMany(rest.length, 'table is', 'tables are')
          + ' named here with the number of findings under each.'
      }),
      list));
  }

  if (otherNote && otherHost) {
    if (!other.length) {
      otherNote.appendChild(el('p', {
        class: 'small muted',
        text: 'Every usage the change reaches builds a table Ripple can name.'
      }));
    } else {
      let feedRows = 0;
      other.forEach(function (r) { if (r && r.feed) feedRows += 1; });
      otherNote.appendChild(el('p', {
        class: 'prose',
        text: 'These are real usages in code that builds no table Ripple can name, so where the value goes next is '
          + 'somewhere Ripple cannot see.'
      }));
      if (feedRows > 0) {
        otherNote.appendChild(note('bad', el('p', {
          text: feedRows + ' of them ' + oneOrMany(feedRows, 'delivers', 'deliver')
            + ' a file out of the warehouse instead. Those are named in the deliveries section above.'
        })));
      }
      const group = el('div', { class: 'group' }, rowsHeader());
      other.forEach(function (r, i) { addFindingRow(group, r, 'other-' + i); });
      otherHost.appendChild(group);
    }
  }
}

function groupCard(c, index, openByDefault) {
  const key = c.kind + ':' + (c.table || index);
  /* The worst card opens once, on the first draw of a scan. Keyed off a flag
   * rather than off the set being empty, or closing that card would open it
   * again on the next render. */
  if (openByDefault && !S.groupsDefaulted) {
    S.groupsDefaulted = true;
    S.openGroups.add(key);
  }
  const open = S.openGroups.has(key);

  const body = el('div', { hidden: !open }, rowsHeader());
  listOf(c.rows).forEach(function (r, i) { addFindingRow(body, r, key + ':' + i); });

  const toggle = el('button', {
    type: 'button',
    class: 'navitem',
    'aria-expanded': open ? 'true' : 'false',
    text: open ? 'Close' : 'Open'
  });
  toggle.addEventListener('click', function () {
    const nowOpen = body.hidden;
    body.hidden = !nowOpen;
    toggle.textContent = nowOpen ? 'Close' : 'Open';
    toggle.setAttribute('aria-expanded', nowOpen ? 'true' : 'false');
    if (nowOpen) S.openGroups.add(key); else S.openGroups.delete(key);
  });

  return el('div', { class: 'group' },
    el('div', { class: 'ghead' },
      c.kind === 'prod' ? badge('PRODUCTION TABLE', 'red') : badge('reached', 'grey'),
      el('h3', { text: c.table || 'no table named' }),
      el('span', { class: 'small muted', text: plural(listOf(c.rows).length, 'finding', 'findings') }),
      c.note ? el('span', { class: 'small muted', text: c.note }) : null,
      el('span', { class: 'spacer' }),
      toggle),
    body);
}

/* Four columns, because that is the grid styles.css draws. The alias rides in
 * the attribute cell as its own chip rather than being dropped. */
function rowsHeader() {
  return el('div', { class: 'rowhead' },
    el('span', { text: 'Table it lands in' }),
    el('span', { text: 'Attribute impacted, and the alias used' }),
    el('span', { text: 'What the code does' }),
    el('span', { text: 'Value' }));
}

function addFindingRow(host, finding, key) {
  const f = finding || {};
  const open = S.openRows.has(key);

  const attrCell = el('span', {},
    el('span', { class: 'mono', text: fieldOf(f, 'attr') || 'no attribute named' }));
  /* Where a row's column is no longer what the person asked about, say so. */
  const from = fieldOf(f, 'from') || (listOf(f.roots).length ? listOf(f.roots).join(', ') : '');
  if (from && from !== fieldOf(f, 'attr')) {
    attrCell.appendChild(el('div', { class: 'small muted', text: 'from ' + from }));
  }
  attrCell.appendChild(el('div', {},
    f.alias ? chip(f.alias, 'alias') : el('span', { class: 'small muted', text: 'no rename' })));

  const doesCell = el('span', { class: 'chips' });
  if (f.logic) doesCell.appendChild(badge(fieldOf(f, 'logic'), 'blue'));
  /* These sit inside the same cell as the "what the code does" badge, so a row
   * that has them still lines up with the rows that do not. */
  if (f.certain === false) doesCell.appendChild(badge('table not stated', 'grey'));
  if (f.inferredHops && f.viaStar) doesCell.appendChild(badge('column list not visible', 'amber'));
  if (f.inferredHops && !f.viaStar) doesCell.appendChild(badge('inferred', 'amber'));
  if (f.builtAsText) doesCell.appendChild(badge('run as text', 'amber'));
  if (f.feed) doesCell.appendChild(badge('to a destination', 'red'));

  const row = el('button', {
    type: 'button',
    class: 'row' + (open ? ' on' : ''),
    'aria-expanded': open ? 'true' : 'false'
  },
    el('span', { class: 'mono', text: fieldOf(f, 'inter') || 'no table named' }),
    attrCell,
    doesCell,
    el('span', { text: fieldOf(f, 'mode') || '' }));

  const detail = findingDetail(f);
  detail.hidden = !open;
  row.addEventListener('click', function () {
    const nowOpen = detail.hidden;
    detail.hidden = !nowOpen;
    row.classList.toggle('on', nowOpen);
    row.setAttribute('aria-expanded', nowOpen ? 'true' : 'false');
    if (nowOpen) S.openRows.add(key); else S.openRows.delete(key);
  });

  host.appendChild(row);
  host.appendChild(detail);
}

function findingDetail(f) {
  const tone = f.noLocalFix ? 'bad' : (f.breaking ? 'warn' : 'info');
  const words = f.noLocalFix
    ? 'No local fix - the upstream team must supply a replacement'
    : (f.breaking ? 'This breaks' : 'Changes, but does not break');

  const box = el('div', { class: 'detail' }, note(tone, el('p', { text: words })));
  if (f.impact) box.appendChild(el('p', { class: 'prose', text: fieldOf(f, 'impact') }));

  if (f.certain === false) {
    box.appendChild(note('', el('p', {
      text: 'Table not stated. The usage is on that line and it is real; what is inferred is which table the column '
        + 'came from. The statement reads more than one table with a column of that name and the SQL does not say '
        + 'which. Ripple has counted it as ' + (fieldOf(f, 'inter') || 'the table above')
        + '. The code below is worth a look before acting on it.'
    })));
  }
  if (f.inferredHops && f.viaStar) {
    box.appendChild(note('warn', el('p', {
      text: 'Column list not visible. The statement takes every column, so the attribute is carried into the next '
        + 'table without ever being named. The hop is real; what Ripple cannot promise is that the column still '
        + 'carries that name by the time it lands.'
    })));
  }
  if (f.copiedBy) {
    box.appendChild(note('warn', el('p', {
      text: 'The file does not say SELECT * here. It uses ' + fieldOf(f, 'copiedBy') + ' to copy the whole table.'
    })));
  }
  if (f.builtAsText) {
    box.appendChild(note('warn', el('p', {
      text: 'Run as text. The line below holds the statement as a quoted string, built with '
        + fieldOf(f, 'builtAsText') + ', so the code shown is the string rather than the statement. Ripple read '
        + 'what is inside the quotes and it is complete SQL, which is why this row exists. Anything added to that '
        + 'text when the job runs is not covered here.'
    })));
  }
  if (f.feed) {
    box.appendChild(note('bad', el('p', {
      text: 'This usage delivers a file out of the warehouse, to ' + fieldOf(f, 'feed')
        + '. Whoever reads that file is outside this repository.'
    })));
  }
  const hops = count(f.inferredHops);
  if (hops !== null && hops > 0) {
    box.appendChild(el('p', {
      class: 'small muted',
      text: hops + ' ' + oneOrMany(hops, 'hop behind this row was', 'hops behind this row were')
        + ' carried by a SELECT *, so ' + oneOrMany(hops, 'it was', 'they were') + ' worked out rather than read.'
    }));
  }

  const lines = listOf(f.lines);
  const code = el('div', { class: 'code' },
    el('div', { class: 'f' },
      el('span', { text: fieldOf(f, 'file') || 'file not named' }),
      f.lang ? el('span', { text: '· ' + fieldOf(f, 'lang') }) : null));
  if (lines.length) {
    const body = el('div', { class: 'body' });
    lines.forEach(function (ln) {
      const l = ln || {};
      const row = el('div', { class: 'ln' + (l.hit ? ' hit' : '') },
        el('span', { class: 'n', text: count(l.n) === null ? '' : String(l.n) }),
        el('span', { class: 't' }, str(l.t)));
      if (l.hit) {
        /* The reason rides on the matched line itself, so the eye finds it in a
         * fifteen-line snippet. */
        row.lastChild.appendChild(el('span', {
          class: 'why',
          text: (fieldOf(f, 'logic') || 'the usage') + ' of ' + (fieldOf(f, 'attr') || 'this column')
        }));
      }
      body.appendChild(row);
    });
    code.appendChild(body);
  } else {
    code.appendChild(el('div', { class: 'body' },
      el('div', { class: 'ln' }, el('span', { class: 'n' }), el('span', { class: 't', text: 'Ripple did not carry the lines of code for this row.' }))));
  }
  box.appendChild(code);
  return box;
}

/* Published tables that stop being refreshed. A different kind of impact, and
 * it gets its own words: nothing fails on anybody's screen, the numbers are
 * simply out of date. */
function stopsLoadingBlock(scan) {
  const stops = listOf(scan.stopsLoading);
  if (!stops.length) return null;
  const body = el('div', {},
    el('p', {
      class: 'prose',
      text: 'This is NOT because a column of these changes. The change stops the statement that fills them from '
        + 'running at all, so they go on holding whatever they held yesterday. Nothing fails on the screen of '
        + 'whoever reads them. The numbers are simply out of date, and stay out of date until somebody fixes the job.'
    }));
  if (scan.stopsLoadingCapped) {
    body.appendChild(note('warn', el('p', {
      text: 'This list was cut short after 400 tables downstream, so there may be more than these.'
    })));
  }
  stops.forEach(function (s) {
    const via = listOf(s.via).map(function (v) { return fieldOf(v, 'table', 'name', 'value'); }).join(' → ');
    body.appendChild(el('div', { class: 'factrow' },
      el('div', {}, badge('PRODUCTION TABLE', 'red')),
      el('div', {},
        el('div', { class: 'mono', text: fieldOf(s, 'table', 'name') }),
        el('div', {
          class: 'small muted',
          text: 'Because ' + (fieldOf(s, 'because') || 'an upstream statement') + ' stops loading. The path: '
            + (via || 'not written down')
        }))));
  });
  return note('bad',
    el('h3', {
      text: stops.length + ' ' + oneOrMany(stops.length, 'published table stops', 'published tables stop') + ' being refreshed'
    }),
    body);
}

/* Deliveries out of the warehouse. Never folded into production tables at risk:
 * these are not tables at all. */
function feedsBlock(scan) {
  const feeds = listOf(scan.feeds);
  if (!feeds.length) return null;
  const body = el('div', {},
    el('p', {
      class: 'prose',
      text: 'These are not tables. The statement writes a file to a bucket, and whoever reads that file is outside '
        + 'this repository, so nothing Ripple can scan will tell you who they are. They have to be told before the '
        + 'change ships.'
    }));
  feeds.forEach(function (f) {
    const where = fieldOf(f, 'to', 'uri', 'destination');
    const attrs = listOf(f.attributes).join(', ') || fieldOf(f, 'attr');
    const line = fieldOf(f, 'line');
    body.appendChild(el('div', { class: 'factrow' },
      el('div', {}, badge(f.breaking ? 'DELIVERY BREAKS' : 'DELIVERY CHANGES', f.breaking ? 'red' : 'amber')),
      el('div', {},
        el('div', { class: 'mono', text: where || 'destination not written down' }),
        el('div', {
          class: 'small muted',
          text: 'Carries ' + (attrs || 'the attribute') + ' out of '
            + (fieldOf(f, 'from') || 'a statement Ripple could not name') + ' · '
            + fieldOf(f, 'file') + (line ? ':' + line : '')
        }))));
  });
  return note('bad',
    el('h3', { text: feeds.length + ' ' + oneOrMany(feeds.length, 'delivery', 'deliveries') + ' out of the warehouse' }),
    body);
}

/* ---------------------------- how to check this result ------------------- */

function drawHowToCheck(root, scan) {
  const host = fill(root, 'unfollowed');
  if (!host) return;
  host.appendChild(el('h3', { text: 'How to check this result' }));
  host.appendChild(attributePanel(scan));
  const byHand = checkByHandBlock(scan);
  if (byHand) host.appendChild(byHand);
  const mentions = mentionsOnlyBlock(scan);
  if (mentions) host.appendChild(mentions);
  const refs = referencedHereBlock(scan);
  if (refs) host.appendChild(refs);
  const text = builtAsTextBlock(scan);
  if (text) host.appendChild(text);
}

/* One badge per attribute, chosen in this order. */
function attributeBadge(scan, a) {
  const lookupFailed = a.lookupFailed === undefined ? Boolean(scan.lookupFailed) : Boolean(a.lookupFailed);
  if (a.reachesProduction) return badge('reaches a published table', 'red');
  const found = count(a.found);
  if (found !== null && found > 0) {
    return badge('used in ' + found + ' ' + oneOrMany(found, 'file', 'files'), 'amber');
  }
  if (lookupFailed) return badge('Ripple never saw a column of this name', 'amber');
  const mentioned = count(a.mentionedIn);
  if (mentioned !== null && mentioned > 0) {
    return badge('named in ' + mentioned + ' ' + oneOrMany(mentioned, 'file', 'files') + ', never read from', 'grey');
  }
  return badge('this name is not in the repository at all', 'grey');
}

function attributePanel(scan) {
  const attrs = listOf(scan.attributes);
  const box = el('div', {}, el('h4', { text: 'Every attribute you asked about' }));
  if (!attrs.length) {
    box.appendChild(note('warn', el('p', { text: 'Ripple did not report any attribute for this scan.' })));
    return box;
  }

  attrs.forEach(function (a) {
    const lookupFailed = a.lookupFailed === undefined ? Boolean(scan.lookupFailed) : Boolean(a.lookupFailed);
    const endsAt = listOf(a.endsAt);
    const cutShortAt = listOf(a.cutShortAt);
    const notVisible = listOf(a.notVisible);
    const entry = el('div', {});

    const headRow = el('div', { class: 'chips' },
      el('strong', { class: 'mono', text: fieldOf(a, 'name', 'attr', 'column') }),
      attributeBadge(scan, a));
    if (endsAt.length) {
      headRow.appendChild(el('span', { class: 'small muted', text: 'ends at ' + joinNames(endsAt, ', ') }));
    }
    /* Two badges that read the same and mean opposite things: one is where the
     * code ran out, the other is where Ripple stopped looking. */
    if (cutShortAt.length) {
      headRow.appendChild(badge('still going at ' + joinNames(cutShortAt, ', '), 'red'));
    }
    entry.appendChild(headRow);

    if (lookupFailed) {
      const seen = listOf(a.columnsRead);
      entry.appendChild(note('warn', el('p', {
        text: 'Ripple never met this column name. ' + (seen.length
          ? 'The columns it did read on that table are: ' + seen.join(', ') + '.'
          : 'Ripple did not report which columns it read on that table.')
      })));
    }
    if (cutShortAt.length) {
      const hops = count(scan.maxHops);
      entry.appendChild(note('bad', el('p', {
        text: 'Ripple follows ' + (hops === null ? 'a set number of' : num(hops)) + ' renames and then stops. This '
          + 'trail had not finished, so whether it reaches a published table is not something this scan can tell '
          + 'you. There is a button above to follow it further.'
      })));
    }
    if (notVisible.length) {
      const inferred = count(a.inferred);
      entry.appendChild(note('warn', el('p', {
        text: 'The trail goes through ' + joinNames(notVisible, ', ') + '. Every column carried on and none of them '
          + 'named, and ' + (inferred === null ? 'some' : num(inferred)) + ' of the findings below '
          + oneOrMany(inferred, 'sits', 'sit') + ' past that point and ' + oneOrMany(inferred, 'is', 'are')
          + ' worked out rather than read.'
      })));
    }

    const nameIn = count(a.nameInTables);
    const tablesRead = count(a.tablesRead);
    /* Both conditions matter. "3 of the 3 tables" is a fact about a folder with
     * three files in it, and printing it there teaches somebody to skip the
     * line in the repository where it is the whole point. */
    if (nameIn !== null && tablesRead !== null && nameIn >= 8 && tablesRead > 0 && nameIn >= tablesRead / 4) {
      entry.appendChild(note('', el('p', {
        text: 'This name is a column in ' + num(nameIn) + ' of the ' + num(tablesRead) + ' tables Ripple could read. '
          + 'The findings follow it out of this one table only, so a long list here is the name being common rather '
          + 'than the change being bigger.'
      })));
    }

    const uncertain = count(a.uncertain);
    if (uncertain !== null && uncertain > 0) {
      entry.appendChild(note('', el('p', {
        text: num(uncertain) + ' ' + oneOrMany(uncertain, 'finding is', 'findings are')
          + ' on a line where the SQL did not say which table the column came from, and more than one table in that '
          + 'statement has one. ' + oneOrMany(uncertain, 'It is', 'They are')
          + ' marked "table not stated" above, as real usages with the table inferred.'
      })));
    }
    box.appendChild(entry);
  });
  return box;
}

/* Where the same advice applies to more than one file, say it once at the top.
 * Printed sixty-eight times it stops being advice and becomes wallpaper the eye
 * skips, taking the file names with it. */
function checkByHandBlock(scan) {
  const items = listOf(scan.unreadable);
  if (!items.length) return null;
  const order = [];
  const byReason = Object.create(null);
  items.forEach(function (u) {
    const reason = fieldOf(u, 'reason', 'why') || 'Ripple did not say why';
    if (!byReason[reason]) { byReason[reason] = []; order.push(reason); }
    byReason[reason].push(u);
  });

  const box = el('div', {},
    el('h4', { text: 'To check by hand' }),
    el('p', {
      class: 'prose',
      text: items.length + ' ' + oneOrMany(items.length, 'thing', 'things') + ' Ripple could not follow. Each one '
        + 'gives the file and the line, so it can be opened at the right place.'
    }));
  order.forEach(function (reason) {
    box.appendChild(el('p', { class: 'lbl', text: reason }));
    const list = scrollBox();
    byReason[reason].forEach(function (u) {
      const line = fieldOf(u, 'line');
      list.appendChild(chip(fieldOf(u, 'file') + (line ? ' · line ' + line : '')
        + (u.text ? ' · ' + str(u.text) : ''), 'mono'));
    });
    box.appendChild(list);
  });
  return note('warn', box);
}

function mentionsOnlyBlock(scan) {
  const items = listOf(scan.mentionsOnly);
  if (!items.length) return null;
  const list = scrollBox();
  items.forEach(function (i) { list.appendChild(chip(fieldOf(i, 'file', 'path', 'name'), 'mono')); });
  return el('div', {},
    el('h4', { text: 'Files that mention the name but carry it nowhere' }),
    el('p', {
      class: 'prose',
      text: items.length + ' ' + oneOrMany(items.length, 'file mentions', 'files mention')
        + ' the name and carries it nowhere Ripple could follow.'
    }),
    list);
}

function referencedHereBlock(scan) {
  const refs = listOf(scan.referencedHere);
  if (!refs.length) return null;
  const list = scrollBox();
  refs.forEach(function (r) {
    list.appendChild(chip(fieldOf(r, 'table', 'name') + ' - '
      + (listOf(r.columns).join(', ') || 'no column named') + ' · '
      + fieldOf(r, 'file') + ':' + fieldOf(r, 'line'), 'mono'));
  });
  return el('div', {},
    el('h4', {
      text: refs.length + ' ' + oneOrMany(refs.length, 'place names this, and carries it nowhere',
        'places name this, and carry it nowhere')
    }),
    el('p', {
      class: 'prose',
      text: 'These places name the table and carry nothing out of it, so they are not findings. They are worth a '
        + 'look because a name written down is a place somebody reads.'
    }),
    list);
}

function builtAsTextBlock(scan) {
  const built = listOf(scan.builtAsText);
  if (!built.length) return null;
  const list = scrollBox();
  built.forEach(function (b) {
    list.appendChild(chip(fieldOf(b, 'file') + ':' + fieldOf(b, 'line') + ' - '
      + (fieldOf(b, 'how', 'builtAsText', 'built_as_text') || 'run as text'), 'mono'));
  });
  return note('warn',
    el('h4', {
      text: built.length + ' ' + oneOrMany(built.length, 'statement is', 'statements are') + ' written as text and run'
    }),
    el('p', {
      text: 'The code shown under a row that came out of one of these is a quoted string and looks nothing like the '
        + 'statement the row describes. Ripple read what is inside the quotes; anything added to that text when the '
        + 'job runs is not covered here.'
    }),
    list);
}

/* ====================================================================
   STEP 5 - the dependency map
   ==================================================================== */

function stepMap(root) {
  const scan = S.scan;
  onClick(root, 'back5', function () { goStep(4); });

  if (!scan) {
    fill(root, 'mapNote', note('warn',
      el('p', { text: 'Nothing was scanned, so there is nothing to draw.' }),
      el('div', { class: 'foot' }, buttonEl('Go to the repository', 'pri sm', function () { goStep(3); }))));
    onClick(root, 'next5', function () { goStep(3); }, true);
    return;
  }

  const graphs = listOf(scan.graphs);
  if (!graphs.length) {
    fill(root, 'mapNote', note('',
      el('h3', { text: 'No lineage to draw' }),
      el('p', {
        text: 'Ripple followed no column out of the table you named, so there is no chain to draw here. The findings '
          + 'screen says what was read.'
      })));
    /* Sending somebody straight on leaves the next screen with nothing to draw
     * and two buttons that do nothing, which only ever happens on a clean
     * result - exactly when somebody most wants to get to the reply. */
    const next = onClick(root, 'next5', function () { writeSummary(); }, S.busy);
    if (next) next.textContent = 'Write the summary';
    return;
  }

  let tab = numberOr(S.mapTab, 0);
  if (tab >= graphs.length || tab < 0) tab = 0;

  const tabs = el('div', { class: 'pills' });
  graphs.forEach(function (g, i) {
    const b = el('button', {
      type: 'button',
      class: 'pill tab' + (i === tab ? ' on' : ''),
      text: fieldOf(g, 'attr', 'name', 'column') || 'attribute ' + (i + 1)
    });
    b.addEventListener('click', function () { S.mapTab = i; render(); });
    tabs.appendChild(b);
  });

  const graph = graphs[tab];
  const facts = branchFacts(graph);
  fill(root, 'mapNote', tabs, el('p', { class: 'prose', text: mapLede(scan, facts) }));
  drawMapPicture(root, graph, facts);
  drawLegend(root);
  drawMapCapped(root, facts);

  const next = onClick(root, 'next5', function () { writeSummary(); }, S.busy);
  if (next) next.textContent = 'Write the summary and continue';
}

function branchFacts(graph) {
  const branches = listOf(graph ? graph.branches : null);
  let reaching = 0;
  let cutBranches = 0;
  let endsOutside = 0;
  branches.forEach(function (b) {
    const nodes = listOf(b.nodes);
    let hitsProd = false;
    let wasCut = false;
    nodes.forEach(function (n) {
      if (n && n.prod) hitsProd = true;
      if (n && n.cut) wasCut = true;
    });
    if (hitsProd) reaching += 1;
    if (wasCut) cutBranches += 1;
    if (!hitsProd && nodes.length) endsOutside += 1;
  });
  /* Longest and production-reaching first. */
  const ordered = branches.slice().sort(function (a, b) {
    const an = listOf(a.nodes);
    const bn = listOf(b.nodes);
    let ap = 0;
    let bp = 0;
    an.forEach(function (n) { if (n && n.prod) ap = 1; });
    bn.forEach(function (n) { if (n && n.prod) bp = 1; });
    if (ap !== bp) return bp - ap;
    return bn.length - an.length;
  });
  return {
    total: branches.length,
    reaching: reaching,
    cut: cutBranches,
    endsOutside: endsOutside,
    drawn: ordered.slice(0, MAX_BRANCHES),
    hidden: Math.max(0, ordered.length - MAX_BRANCHES)
  };
}

/* The line under the title must be true of the picture underneath it, and it
 * has three versions for that reason. */
function mapLede(scan, facts) {
  if (facts.reaching > 0) {
    return facts.reaching + ' of these ' + facts.total + ' '
      + oneOrMany(facts.total, 'branch reaches', 'branches reach') + ' a table on your published list.';
  }
  if (facts.cut > 0) {
    const hops = count(scan.maxHops);
    return 'Ripple stopped following ' + facts.cut + ' ' + oneOrMany(facts.cut, 'branch', 'branches') + ' at '
      + (hops === null ? 'the hop limit' : num(hops) + ' renames deep') + ', so where '
      + oneOrMany(facts.cut, 'it ends', 'they end') + ' is not known.';
  }
  return 'No branch on this picture reaches a table on your published list.';
}

function drawMapPicture(root, graph, facts) {
  const host = fill(root, 'map');
  if (!host) return;
  const branches = el('div', { class: 'branches' });
  facts.drawn.forEach(function (b) {
    const line = el('div', { class: 'branch' });
    listOf(b.nodes).forEach(function (node, i) {
      if (i > 0) line.appendChild(el('span', { class: 'arrow', text: '→' }));
      line.appendChild(mapNode(node || {}));
    });
    branches.appendChild(line);
  });
  host.appendChild(el('div', { class: 'maprow' },
    el('div', { class: 'mapsrc' },
      el('div', { class: 'small', text: 'The change starts here' }),
      el('div', { text: fieldOf(graph, 'source', 'from', 'table') || 'source not named' }),
      el('div', { text: fieldOf(graph, 'attr', 'name', 'column') })),
    branches));
}

/* Two things a box can hide, and the box itself has to say them, because a
 * picture of a chain is exactly where somebody reads "and then it stops".
 * Published tables are red here: the green in this stylesheet would read as
 * reassurance on the one box that is the whole point of the picture. */
function mapNode(node) {
  const cls = node.prod ? 'node risk' : (node.inferred ? 'node star' : (node.cut ? 'node blind' : 'node'));
  const box = el('div', { class: cls },
    el('div', { text: fieldOf(node, 'table', 'name') || 'no table named' }),
    el('div', { class: 'small', text: fieldOf(node, 'alias') || 'no rename' }));
  if (node.prod) box.appendChild(el('div', { class: 'small', text: 'on your published list' }));
  if (node.inferred) {
    const how = fieldOf(node, 'how');
    box.appendChild(el('div', {
      class: 'small',
      text: how ? how + ' of a whole table - column list not visible' : 'built with SELECT * - column list not visible'
    }));
  }
  if (node.cut) {
    box.appendChild(el('div', { class: 'small', text: 'Ripple stopped here - hop limit, not the end of the chain' }));
  }
  return box;
}

function drawLegend(root) {
  const host = fill(root, 'legend');
  if (!host) return;
  host.appendChild(el('span', {}, el('span', { class: 'mapsrc', text: 'source' }), ' where the change starts'));
  host.appendChild(el('span', {}, el('span', { class: 'node risk', text: 'table' }), ' on your published list'));
  host.appendChild(el('span', {}, el('span', { class: 'node star', text: 'table' }), ' column list not visible'));
  host.appendChild(el('span', {}, el('span', { class: 'node blind', text: 'table' }), ' Ripple stopped at the hop limit'));
  host.appendChild(el('span', { text: 'The alias under each box is the rename a word search would miss.' }));
}

function drawMapCapped(root, facts) {
  const host = fill(root, 'mapCapped');
  if (!host) return;
  if (facts.hidden > 0) {
    host.appendChild(note('', el('p', {
      text: facts.hidden + ' further ' + oneOrMany(facts.hidden, 'branch is', 'branches are')
        + ' not drawn here. Nothing has been dropped: every one of them is already a finding on the previous step.'
    })));
  }
  if (facts.endsOutside > 0) {
    host.appendChild(note('warn', el('p', {
      text: facts.endsOutside + ' ' + oneOrMany(facts.endsOutside, 'branch ends', 'branches end')
        + ' at a table that is not on your published list. '
        + oneOrMany(facts.endsOutside, 'It is', 'They are') + ' drawn because the change reaches '
        + oneOrMany(facts.endsOutside, 'it', 'them') + ' either way, and Ripple simply cannot say whether anyone '
        + 'outside your team reads ' + oneOrMany(facts.endsOutside, 'it', 'them') + '.'
    })));
  }
}

/* ====================================================================
   STEP 6 - the summary
   ==================================================================== */

function valsForServer() {
  const v = S.vals || {};
  return {
    subject: str(v.subject),
    description: str(v.description),
    sourceSystem: str(v.sourceSystem),
    changeType: str(v.changeType),
    changeKind: str(v.changeType),
    effectiveDate: str(v.effectiveDate),
    contactName: str(v.contactName),
    contactTeam: str(v.contactTeam),
    contactEmails: listOf(v.contactEmails),
    upstream: upstreamForScan(),
    filledBy: str(v.filledBy),
    mode: S.mode
  };
}

function writeSummary() {
  run(async function () {
    const res = await postJson('/api/summary', { scan: S.scan || {}, vals: valsForServer() });
    S.summary = res && res.summary ? res.summary : res;
    S.reply = res && res.reply ? res.reply : null;
    S.replyEdits = null;
    S.savedAs = '';
    S.saveError = '';
    S.step = 6;
    S.screen = '';
    if (stepOrder().indexOf(6) > stepOrder().indexOf(S.maxStep)) S.maxStep = 6;
  }, 'Writing the summary from the findings');
}

function stepSummary(root) {
  onClick(root, 'back6', function () { goStep(5); });

  if (!S.summary) {
    /* A screen with nothing on it and two buttons that do nothing is the worst
     * way to say this. */
    fill(root, 'verdict', note('warn',
      el('h3', { text: 'No summary has been written for this scan' }),
      el('p', {
        text: 'The summary is written from the findings when you leave the dependency map, and it has not been '
          + 'written for this scan.'
      }),
      el('div', { class: 'foot' },
        buttonEl('Write the summary now', 'pri sm', function () { writeSummary(); }, S.busy || !S.scan))));
    onClick(root, 'copySummary', function () {}, true);
    onClick(root, 'next6', function () { goStep(7); }, true);
    return;
  }

  const summary = S.summary;
  const scan = S.scan;

  fill(root, 'verdict', el('section', { class: 'card clip' },
    el('div', { class: 'chead' },
      el('h2', { text: fieldOf(summary, 'headline') || 'No headline was written' }),
      el('span', { class: 'spacer' }),
      scan ? headlineBadges(scan) : null)));
  fill(root, 'riskBadge', scan ? headlineBadges(scan) : null);

  const main = el('div', {});
  const narrative = fieldOf(summary, 'narrative', 'text', 'summary', 'body');
  main.appendChild(el('p', { class: 'prose', text: narrative || 'Ripple wrote no narrative for this result.' }));

  const bullets = listOf(summary.bullets);
  if (bullets.length) {
    const list = el('ul', {});
    bullets.forEach(function (b) {
      list.appendChild(el('li', { class: 'prose', text: typeof b === 'string' ? b : fieldOf(b, 'text', 'value') }));
    });
    main.appendChild(list);
  }

  const details = listOf(pick(summary, 'details', 'change', 'fields'));
  if (details.length) {
    main.appendChild(el('h4', { text: 'The change' }));
    details.forEach(function (d) {
      main.appendChild(kv(fieldOf(d, 'label', 'name'), fieldOf(d, 'value', 'text')));
    });
  }

  const rail = el('div', { class: 'rail' });
  const deadline = fieldOf(summary, 'deadline', 'effectiveDate') || str((S.vals || {}).effectiveDate);
  const left = count(pick(summary, 'daysLeft'));
  const computed = left === null ? daysLeftOf((S.vals || {}).effectiveDate) : left;
  rail.appendChild(el('div', {},
    el('h4', { text: 'Deadline' }),
    el('p', { class: 'mono', text: deadline || 'no date was given' }),
    el('p', {
      class: 'prose',
      text: computed === null
        ? 'Ripple did not report how many days are left.'
        : computed + ' ' + oneOrMany(computed, 'day', 'days') + ' left'
          + (left === null ? ', worked out from the date on this screen.' : '.')
    })));

  const blast = count(pick(summary, 'blastRadius', 'blast_radius'));
  rail.appendChild(el('div', {},
    el('h4', { text: 'Blast radius' }),
    el('p', {
      class: 'prose',
      text: blast === null
        ? 'Ripple did not report a blast radius for this result.'
        : num(blast) + ' ' + oneOrMany(blast, 'thing this change touches', 'things this change touches')
    })));

  const todo = listOf(pick(summary, 'whatToDo', 'what_to_do', 'actions', 'next'));
  const todoBox = el('div', {}, el('h4', { text: 'What to do' }));
  if (todo.length) {
    const list = el('ol', {});
    todo.forEach(function (t) {
      list.appendChild(el('li', { class: 'prose', text: typeof t === 'string' ? t : fieldOf(t, 'text', 'value') }));
    });
    todoBox.appendChild(list);
  } else {
    todoBox.appendChild(el('p', { class: 'small muted', text: 'Ripple did not write a next step for this result.' }));
  }
  rail.appendChild(todoBox);

  fill(root, 'summary', el('div', { class: 'grid2' }, main, rail));

  /* This is the screen people read, so the check-by-hand list is here again. */
  const gapsHost = fill(root, 'summaryGaps');
  if (gapsHost) {
    if (scan) {
      const byHand = checkByHandBlock(scan);
      if (byHand) gapsHost.appendChild(byHand);
    }
    const saveFoot = el('div', { class: 'foot' },
      buttonEl('Save this analysis', 'ghost', function () { saveAnalysis(); }, S.busy));
    /* Where "saved" does not really mean saved, say it in the same breath. */
    if (limitsOf().historyKept === false) {
      saveFoot.appendChild(el('span', {
        class: 'small muted',
        text: 'This host wipes saved analyses. Copy out anything worth keeping.'
      }));
    }
    gapsHost.appendChild(saveFoot);
    if (S.savedAs) {
      gapsHost.appendChild(note('good', el('p', { text: 'Saved as analysis ' + S.savedAs + '.' })));
    }
    if (S.saveError) {
      gapsHost.appendChild(note('bad', el('p', { text: 'Not saved: ' + S.saveError })));
    }
  }

  onClick(root, 'copySummary', function () {
    copyText(summaryAsText(summary), root, 'summaryGaps');
  });
  onClick(root, 'next6', function () { goStep(7); }, S.busy);
}

function summaryAsText(summary) {
  const parts = [fieldOf(summary, 'headline'), fieldOf(summary, 'narrative', 'text', 'summary', 'body')];
  listOf(summary.bullets).forEach(function (b) {
    parts.push('- ' + (typeof b === 'string' ? b : fieldOf(b, 'text', 'value')));
  });
  return parts.filter(function (p) { return p; }).join('\n\n');
}

function saveAnalysis() {
  postJson('/api/history', {
    vals: valsForServer(),
    scan: S.scan || {},
    summary: S.summary || {},
    mode: S.mode
  }).then(function (res) {
    const id = fieldOf(res, 'id', 'number', 'savedAs')
      || (res && res.saved ? fieldOf(res.saved, 'id', 'number') : '');
    S.savedAs = id || '';
    S.saveError = id ? '' : 'The service saved it but did not send back a number for it.';
    S.past = null;
    render();
  }, function (err) {
    S.saveError = errorText(err);
    S.savedAs = '';
    render();
  });
}

/* ====================================================================
   STEP 7 - the reply
   ==================================================================== */

function stepReply(root) {
  onClick(root, 'back7', function () { goStep(6); });
  onClick(root, 'startOver', function () { startOver(); });

  const reply = S.reply;
  if (!reply) {
    fill(root, 'replyNote', note('warn',
      el('h3', { text: 'No reply has been drafted' }),
      el('p', { text: 'The reply is written from the summary, and no summary has been written for this scan.' }),
      el('div', { class: 'foot' },
        buttonEl('Write the summary now', 'pri sm', function () { writeSummary(); }, S.busy || !S.scan))));
    onClick(root, 'copyReply', function () {}, true);
    return;
  }

  if (!S.replyEdits) {
    S.replyEdits = {
      subject: fieldOf(reply, 'subject'),
      body: fieldOf(reply, 'body', 'text')
    };
  }

  const to = listOf(pick(reply, 'to', 'recipients', 'addresses'));
  const toHost = fill(root, 'replyTo');
  if (toHost) {
    if (!to.length) {
      toHost.appendChild(el('span', { class: 'small muted', text: 'No recipient was written down.' }));
    } else {
      const chips = el('div', { class: 'chips' });
      to.forEach(function (a) { chips.appendChild(chip(typeof a === 'string' ? a : fieldOf(a, 'email', 'address'), 'mono')); });
      toHost.appendChild(chips);
    }
  }

  const subjectHost = fill(root, 'replySubject');
  if (subjectHost) {
    const input = el('input', { type: 'text', value: str(S.replyEdits.subject) });
    input.addEventListener('input', function (ev) { S.replyEdits.subject = ev.target.value; });
    subjectHost.appendChild(input);
  }

  const body = x(root, 'replyBody');
  if (body) {
    body.value = str(S.replyEdits.body);
    body.addEventListener('input', function (ev) { S.replyEdits.body = ev.target.value; });
  }

  fill(root, 'replyNote',
    el('p', {
      class: 'prose',
      text: 'Nothing on this screen sends anything. Copy it into your own mail client when you are happy with it.'
    }),
    el('p', { class: 'small copy-said', text: str(S.copySaid) }));

  onClick(root, 'copyReply', function () {
    const text = 'To: ' + to.map(function (a) { return typeof a === 'string' ? a : fieldOf(a, 'email', 'address'); }).join(', ')
      + '\nSubject: ' + str(S.replyEdits.subject) + '\n\n' + str(S.replyEdits.body);
    copyText(text, root, 'replyNote');
  }, S.busy);
}

/* Copying a reply and then having to gather the addresses again by hand is half
 * a job, so the recipients go with it. */
function copyText(text, root, noteName) {
  const say = function (message) {
    S.copySaid = message;
    const host = x(root, noteName);
    if (!host) return;
    let line = $('.copy-said', host);
    if (!line) {
      line = el('p', { class: 'small copy-said' });
      host.appendChild(line);
    }
    line.textContent = message;
  };
  if (!navigator.clipboard || !navigator.clipboard.writeText) {
    say('This browser did not offer Ripple the clipboard. Select the text and copy it by hand.');
    return;
  }
  navigator.clipboard.writeText(text).then(function () {
    say('Copied, with the recipients at the top.');
  }, function (err) {
    say('Nothing was copied: ' + errorText(err));
  });
}

function startOver() {
  S.step = 1;
  S.maxStep = 1;
  S.screen = '';
  S.vals = null;
  S.emailPreview = null;
  S.chosenFile = null;
  S.scan = null;
  S.summary = null;
  S.reply = null;
  S.replyEdits = null;
  S.savedAs = '';
  S.saveError = '';
  S.copySaid = '';
  S.manRows = [{ table: '', attrs: '' }];
  S.man = {
    sourceSystem: '', changeType: '', effectiveDate: '', whatChanges: '',
    contactName: '', contactTeam: '', contactRaw: '', contactEmails: []
  };
  S.openGroups = new Set();
  S.openRows = new Set();
  S.groupsDefaulted = false;
  lastError = '';
  render();
}

/* ====================================================================
   PAST ANALYSES
   ==================================================================== */

function pastScreen(host) {
  ensureHealth();
  const card = el('section', { class: 'card clip' },
    el('div', { class: 'chead' }, el('h2', { text: 'Past analyses' })));
  const pad = el('div', { class: 'pad' });
  card.appendChild(pad);
  host.appendChild(card);

  if (limitsOf().historyKept === false) {
    pad.appendChild(note('bad',
      el('h3', { text: 'This host does not keep saved analyses' }),
      el('p', {
        text: 'Saved analyses live on the machine Ripple is running on, and this host wipes that storage. Anything '
          + 'here can disappear the next time Ripple is restarted or redeployed, and nothing on this screen will '
          + 'warn you when it does. Copy out anything worth keeping.'
      })));
  }

  if (S.pastError) {
    pad.appendChild(note('bad',
      el('h3', { text: 'The saved analyses could not be read' }),
      el('p', { text: S.pastError }),
      el('div', { class: 'foot' },
        buttonEl('Try reading them again', 'ghost sm', function () {
          S.pastError = '';
          S.past = null;
          render();
        }))));
    return;
  }
  if (!S.past) {
    loadPastAnalyses();
    pad.appendChild(el('p', { class: 'small muted', text: 'Reading the saved analyses.' }));
    return;
  }

  const rows = listOf(S.past);
  if (!rows.length) {
    pad.appendChild(el('p', { class: 'prose', text: 'Nothing has been saved yet.' }));
    return;
  }

  pad.appendChild(el('p', { class: 'small muted', text: 'Newest first. A status is saved when you leave the box.' }));
  const list = el('div', { class: 'hist' });
  rows.forEach(function (r) {
    const id = fieldOf(r, 'id', 'number');
    const status = el('input', { type: 'text', value: fieldOf(r, 'status') });
    status.addEventListener('change', function (ev) { saveStatus(id, ev.target.value); });
    list.appendChild(el('div', {},
      kv('Number', id || 'not numbered'),
      kv('Saved', fieldOf(r, 'when', 'saved', 'created', 'at') || 'no date recorded'),
      kv('Table', fieldOf(r, 'table', 'upstream') || 'not recorded'),
      kv('Attribute', fieldOf(r, 'attribute', 'attr', 'column') || 'not recorded'),
      kv('Risk', fieldOf(r, 'risk') || 'not recorded'),
      el('div', { class: 'factrow' },
        el('div', { text: 'Status' }),
        el('div', {}, status))));
  });
  pad.appendChild(list);
  pad.appendChild(el('p', { class: 'small', id: 'past-said', text: str(S.pastSaid) }));
}

function loadPastAnalyses() {
  api('/api/history').then(function (res) {
    if (res && res.available === false) {
      S.past = [];
      S.pastError = 'This build keeps no store of saved analyses, so there is nothing to list.';
    } else {
      S.past = Array.isArray(res)
        ? res
        : listOf(pick(res, 'items', 'analyses', 'history', 'rows', 'saved'));
      S.pastError = '';
    }
    if (S.screen === 'past') render();
  }, function (err) {
    S.pastError = errorText(err);
    if (S.screen === 'past') render();
  });
}

function saveStatus(id, status) {
  if (!id) {
    S.pastSaid = 'That row carries no number, so the service has nothing to save the status against.';
    const said = document.getElementById('past-said');
    if (said) said.textContent = S.pastSaid;
    return;
  }
  patchJson('/api/history/' + encodeURIComponent(id), { status: status }).then(function () {
    S.pastSaid = 'Status saved for analysis ' + id + '.';
    const said = document.getElementById('past-said');
    if (said) said.textContent = S.pastSaid;
  }, function (err) {
    S.pastSaid = 'The status for analysis ' + id + ' was not saved: ' + errorText(err);
    const said = document.getElementById('past-said');
    if (said) said.textContent = S.pastSaid;
  });
}

/* ====================================================================
   SETTINGS AND CHECKS
   ==================================================================== */

function settingsScreen(host) {
  ensureHealth();
  if (!S.health) {
    host.appendChild(el('section', { class: 'card clip' },
      el('div', { class: 'chead' }, el('h2', { text: 'Settings and checks' })),
      el('div', { class: 'pad' },
        el('p', { class: 'small muted', text: 'Asking the service what it is set to.' }))));
    return;
  }
  host.appendChild(folderCard());
  host.appendChild(publishedTablesCard());
  host.appendChild(connectedCard());
  host.appendChild(readerCard());
  const build = buildCard();
  if (build) host.appendChild(build);
}

/* THE FOLDER BOX, and it is the difference between a demo and a tool. Without
 * it the only way to point Ripple at real SQL is to set RIPPLE_REPO and restart
 * it, and until somebody does that every answer describes the practice pipeline
 * - confidently, correctly, and about nothing anybody cares about. */
function folderCard() {
  const repo = repoOf();
  const files = count(pick(repo, 'files'));
  const box = el('input', { type: 'text', value: fieldOf(repo, 'path'), placeholder: 'C:\\work\\pipelines' });
  const said = el('p', { class: 'small', text: str(S.folderSaid) });

  return el('section', { class: 'card clip' },
    el('div', { class: 'chead' }, el('h2', { text: 'The repository Ripple reads' })),
    el('div', { class: 'pad' },
      el('div', { class: 'lbl', text: 'Repository facts' }),
      kv('Folder', fieldOf(repo, 'path') || 'none chosen'),
      kv('Label', fieldOf(repo, 'label') || 'not named'),
      kv('Branch', fieldOf(repo, 'branch') || 'none recorded'),
      kv('Files read', files === null ? 'not reported' : num(files)),
      kv('Statements understood', count(pick(repo, 'statements')) === null ? 'not reported' : num(repo.statements)),
      el('label', { class: 'faint', text: 'The folder Ripple is reading now' }),
      box,
      el('div', { class: 'foot' },
        buttonEl('Read this folder', 'pri sm', function () {
          run(function () { return readFolder(box.value); }, 'Reading that folder');
        }, S.busy)),
      said,
      el('p', {
        class: 'small muted',
        text: 'The choice is held only while Ripple is running. RIPPLE_REPO is what keeps it, and there is nowhere '
          + 'for this build to write it down, so tomorrow\u2019s Ripple will not still be reading this folder unless '
          + 'that is set.'
      })));
}

function publishedTablesCard() {
  const area = el('textarea', { rows: 12, class: 'mono' });
  const readHost = el('div', {});
  const saidHost = el('p', { class: 'small' });
  const pad = el('div', { class: 'pad' },
    el('label', { class: 'faint', text: 'The tables your team publishes, one to a line' }),
    area,
    readHost,
    saidHost,
    el('p', {
      class: 'small muted',
      text: 'This one setting decides whether "no production table is impacted" is a result or an accident.'
    }));
  const card = el('section', { class: 'card clip' },
    el('div', { class: 'chead' }, el('h2', { text: 'Published tables' })),
    pad);
  productionControl(area, readHost, saidHost);
  return card;
}

function connectedCard() {
  const repo = repoOf();
  const rule = productionRuleText();
  return el('section', { class: 'card clip' },
    el('div', { class: 'chead' }, el('h2', { text: 'What is connected' })),
    el('div', { class: 'pad' },
      kv('Repository', fieldOf(repo, 'path') || 'none chosen'),
      kv('SQL dialect', str(pick(S.health, 'sqlDialect')) || 'not reported'),
      kv('Renames followed before Ripple stops',
        count(pick(S.health, 'maxHops')) === null ? 'not reported' : num(S.health.maxHops)),
      kv('Published-table rule in force', rule || 'not reported'),
      kv('Saved analyses kept on this host',
        limitsOf().historyKept === false ? 'no - this host wipes them'
          : (limitsOf().historyKept === true ? 'yes' : 'not reported')),
      kv('Largest message this build accepts',
        uploadCeiling() === null ? 'not reported' : mb(uploadCeiling()) + ' MB')));
}

/* No key box. api.py carries no AI routes at all, so a box to paste a key into
 * would be a control with nothing behind it, and "rejected" is what somebody
 * would read on a perfectly good key. */
function readerCard() {
  const ai = aiOf();
  const reason = fieldOf(ai, 'reason');
  return el('section', { class: 'card clip' },
    el('div', { class: 'chead' }, el('h2', { text: 'How the fields are read' })),
    el('div', { class: 'pad' },
      aiAvailable()
        ? note('good', el('p', {
          text: 'The service reports an AI reader: '
            + (fieldOf(ai, 'modelLabel', 'model') || 'the model was not named') + '. The email is read by it.'
        }))
        : note('warn',
          el('p', {
            text: 'There is no AI reader in this build, so there is nowhere for a key to go and no key box on this '
              + 'screen. Fields are found by matching the repository catalogue, and every summary and drafted reply '
              + 'is written by the rules.'
          }),
          reason ? el('p', { text: reason }) : null)));
}

/* Written once and shown wherever a settings screen is drawn. The copy nobody
 * can check is exactly the one that turns out to be months old. The label is
 * shown exactly as the server sends it: one place decides how honest that line
 * is, and it is the server. */
function buildCard() {
  const build = S.health ? S.health.build : null;
  if (!build) return null;
  const from = fieldOf(build, 'from');
  const lines = {
    build: 'Recorded when this copy was packaged.',
    host: 'Reported by the host that deployed it.',
    git: 'Read from the repository this copy is running out of.',
    files: 'No build record was found, so that is the date of the newest file in this folder. It moves whenever '
      + 'anything is touched, and it does not tell you whether this copy was ever installed anywhere.'
  };
  const under = Object.prototype.hasOwnProperty.call(lines, from)
    ? lines[from]
    : 'Ripple did not say where this came from.';
  return el('section', { class: 'card clip' },
    el('div', { class: 'chead' }, el('h2', { text: 'This build' })),
    el('div', { class: 'pad' },
      el('p', { class: 'mono', text: fieldOf(build, 'label') || 'The service sent no label for this build.' }),
      el('p', { class: 'small muted', text: under })));
}

/* ====================================================================
   Boot
   ==================================================================== */

/* Claimed before the first draw so the screens do not each fire a second
 * request for the same block. */
healthAsked = true;

/* Drawn once before the service answers, so the page says what it is waiting
 * for instead of showing a blank pane. */
render();

api('/api/health').then(function (health) {
  S.health = health;
  render();
}, function (err) {
  /* A blank page claims nothing and shows nothing, so the reason is put on
   * screen where the answer would have been. */
  lastError = 'Ripple could not read its own health block, so nothing on this page has been checked against the '
    + 'service: ' + errorText(err);
  render();
});
