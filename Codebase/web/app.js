/* Ripple — front end.
   Plain JavaScript on purpose: no build step, no framework, nothing to install.
   The same file can be opened, read and changed by anyone. */

//<online-only>
// This file is also the front end of Ripple Offline, which is built from it
// rather than being a second copy — a copy would drift, and the drifting one
// would be the build running where nobody can check it. The lines between
// //<online-only> and //</online-only> are deleted from that build: they are
// the parts that reach out (the GitHub source and the AI key form), which must
// not merely be unused offline but absent. Deleting those lines has to leave
// working JavaScript, so each block is written to read correctly with its
// marked lines gone. The offline build then checks the result for the words
// that should be gone, and fails with the line it found rather than shipping a
// key box onto a locked-down machine. Moving a marker is safe; quietly dropping
// one is not. See Ripple Offline/ripple_offline/webbuild.py.
//</online-only>

const STEPS = [
  ['Notification',    'Upload or type it in'],
  ['Review fields',   'Check before scanning'],
  ['Repository',      'What will be searched'],
  ['Impact analysis', 'Grouped by production table'],
  ['Dependency map',  'Where the change goes'],
  ['Summary',         'What it means'],
  ['Reply',           'Answer the upstream team'],
];

const S = {
  step: 1, maxStep: 1, view: 'wizard',
  mode: 'email',
  health: null,
  vals: null,          // {source, changeType, changeKind, changeDesc, subject, effectiveDate, poc*, upstream:[{table,attrs}]}
  emailPreview: null,
  scan: null,
  summary: null,
  reply: null,
  savedId: null,
  //<online-only>
  aiMsg: null,        // result of the last AI key action, kept across redraws
  //</online-only>
  manRows: [{ table: '', attrs: '', whole: false }],
  man: { source: '', changeKind: 'unknown', effectiveDate: '', changeDesc: '',
         pocName: '', pocEmail: '', pocTeam: '' },
  busy: false, busyWhat: '',
  openGroup: 'p0', openRow: null, graphTab: 0,
  // Which information buttons are open, by label. Kept here so a redraw does
  // not shut a panel somebody is in the middle of reading.
  why: {},
  // Which folded lists are open, by label. Same reason: a redraw must not
  // shut a list somebody has just opened.
  folds: {},
  //<online-only>
  // Repository step. The token is held here only long enough to send it once;
  // it is cleared as soon as the server has accepted it.
  repoTab: null,
  gh: { repo: '', branch: '', token: '' },
  connecting: false, connectMsg: '',
  //</online-only>
};

// Typed by hand, so the awkward ones are given the right control rather than a
// box and a format to remember: a real calendar for the date, the same list of
// change types the scan actually understands, and a contact box that takes as
// many addresses as you care to paste in.
const MAN_FIELDS = [
  ['source', 'Source system', 'text', 'e.g. C360'],
  ['changeKind', 'Change type', 'kind', ''],
  ['effectiveDate', 'Effective date', 'date', ''],
  // A sentence, not a word. In a single-line box a real one is typed once and
  // then unreadable, which is a field nobody can check.
  ['changeDesc', 'What is changing', 'lines', 'One line describing the change'],
  ['pocName', 'Contact name', 'text', 'Who sent the notice'],
  ['pocEmail', 'Contact email', 'emails', 'name@corp.example.com, other@corp.example.com'],
  ['pocTeam', 'Contact team', 'text', 'e.g. C360 Data Governance'],
];

// No "attribute" in front of the change: the same notice can be about a whole
// table, and "Attribute decommission" over a table being dropped describes a
// change that is not the one happening.
const CHANGE_KINDS = [
  ['unknown', 'Not specified'],
  ['removal', 'Decommission'],
  ['value_change', 'Value format change'],
  ['type_change', 'Data type change'],
  ['rename', 'Rename'],
];
const kindLabel = (id) => (CHANGE_KINDS.find(([k]) => k === id) || CHANGE_KINDS[0])[1];

// ── helpers ───────────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const el = (tag, props = {}, ...kids) => {
  const n = Object.assign(document.createElement(tag), props);
  for (const k of kids.flat()) if (k != null) n.append(k.nodeType ? k : String(k));
  return n;
};
const x = (root, name) => root.querySelector(`[data-x="${name}"]`);
const esc = (s) => String(s ?? '');

/* ── the information button ───────────────────────────────────────────────
   The fact stays on the page. The reasoning opens underneath it.

   There is ONE of these and every screen calls it. The line it draws:

     STAYS ON THE PAGE   the fact, the number and the names. "1 file is of a
                         type Ripple does not open — .ipynb". "4 production
                         tables at risk". "2 gaps in what Ripple could see."
     GOES BEHIND THE i   why that fact matters, what Ripple did about it, and
                         what somebody should do next.

   Somebody who never presses the button still sees everything Ripple knows it
   missed. They lose the reasoning, never the fact. Putting a count, a table
   name or a warning that something was not read behind this button breaks the
   product.

   It is a real button, not a title= tooltip: a tooltip cannot be opened on a
   touch screen, cannot be reached from a keyboard, and disappears while it is
   being read. It is reached by Tab, opened by Enter or Space, closed by Escape,
   and announced as a collapsed disclosure because of aria-expanded and
   aria-controls. Nothing is downloaded, so it works with no internet.

   `fact` is the node that stays visible; `label` names it for a screen reader
   and keys whether it is open, so a redraw does not shut a panel somebody is
   reading. Everything after that is the explanation — a string becomes a
   paragraph, a node is appended as it is. */
function why(fact, label, ...body) {
  const id = 'why-' + label.toLowerCase().replace(/[^a-z0-9]+/g, '-');
  const open = !!(S.why && S.why[label]);
  const wrap = el('div', { className: 'iwrap' });
  const btn = el('button', { className: 'i', type: 'button', textContent: 'i' });
  btn.setAttribute('aria-controls', id);
  btn.setAttribute('aria-expanded', String(open));
  btn.setAttribute('aria-label', 'Why this matters: ' + label);
  const panel = el('div', { className: 'ipanel', id, role: 'note' });
  panel.hidden = !open;
  body.flat().filter(b => b != null && b !== '').forEach(b =>
    panel.append(b.nodeType ? b : el('p', { textContent: String(b) })));
  btn.onclick = () => {
    const now = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!now));
    panel.hidden = now;
    S.why = S.why || {};
    S.why[label] = !now;
  };
  // Escape closes it from anywhere inside, so a keyboard is never trapped in an
  // open panel, and the focus goes back to the button that opened it.
  wrap.onkeydown = (e) => {
    if (e.key === 'Escape' && !panel.hidden) { btn.click(); btn.focus(); }
  };
  wrap.append(el('div', { className: 'ifact' }, fact, btn), panel);
  return wrap;
}

/* ── the folded list ──────────────────────────────────────────────────────
   A long list folds shut by default. The heading stays on the page and carries
   the fact -- what the list is, and how many are in it -- so somebody who never
   opens it still sees everything Ripple knows it missed. What folds is the list
   itself: the names, the chips, the rows.

   Measured on a repository the size of the one this was built for: the
   findings screen ran to forty thousand pixels, and every caveat on it was a
   heading over a list nobody could scroll past. The heading is the caveat;
   the list is the evidence. Only the evidence folds.

   `label` keys whether it is open, so a redraw does not shut a list somebody
   is reading. `head` is the heading, a node or a string. `body` is the list,
   built only when it is open. `opts.count` is drawn as a badge, `opts.tag`
   as the small capitals label, `opts.after` is a node that stays visible
   under the heading whether or not the list is open -- a button that acts
   on the list belongs there, not inside it. */
function fold(label, head, body, opts = {}) {
  const open = S.folds[label] == null ? !!opts.open : !!S.folds[label];
  const card = el('div', { className: 'card clip fold' + (open ? ' open' : '') + (opts.tone ? ' ' + opts.tone : ''),
    style: opts.style || '' });
  const h = el('div', { className: 'fhead', tabIndex: 0, role: 'button' });
  h.setAttribute('aria-expanded', String(open));
  if (opts.tag) h.append(el('span', { className: 'tag', textContent: opts.tag, style: opts.tagStyle || '' }));
  h.append(el('div', { className: 'ftitle' }, head));
  if (opts.count != null) {
    h.append(el('span', { className: 'badge sm ' + (opts.badge || 'grey'), textContent: String(opts.count) }));
  }
  h.append(el('span', { className: 'fhint', textContent: open ? 'hide' : 'show' }),
    el('span', { className: 'caret', textContent: '›' }));
  const toggle = () => { S.folds[label] = !open; render(); };
  // The information button inside a heading opens its own panel; it must not
  // fold the list underneath it as well.
  h.onclick = (e) => { if (e.target.closest && e.target.closest('button')) return; toggle(); };
  h.onkeydown = (e) => {
    if (e.target !== h) return;
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
  };
  card.append(h);
  if (opts.after) card.append(el('div', { className: 'fextra' }, opts.after));
  if (open) card.append(el('div', { className: 'fbody' }, typeof body === 'function' ? body() : body));
  return card;
}

/* A card that was built the old way -- heading first, then the list -- turned
   into a folded one. The first child becomes the heading that stays; everything
   after it becomes the list that folds. */
function foldFrom(label, card, opts = {}) {
  const kids = [...card.childNodes];
  const head = kids.shift();
  const body = el('div');
  kids.forEach(k => body.append(k));
  return fold(label, head, body, opts);
}

/* The one control that turns "which column" into "the whole table". A real
   checkbox with a label, so it can be reached by keyboard and read out. When
   it is on, the attribute box is emptied and disabled: the two are different
   questions, and a row that asks both would be answering neither. */
let wholeToggleCount = 0;
function wholeToggle(on, onchange) {
  const id = 'whole-' + (++wholeToggleCount);
  const box = el('input', { type: 'checkbox', id, checked: !!on });
  box.onchange = () => onchange(box.checked);
  return el('label', { htmlFor: id, className: 'small wholetoggle' }, box, 'Whole table');
}

/* Every email address in a blob of text, once each.
   People do not type addresses one at a time into a form. They copy the To line
   out of Outlook, which arrives as "Priya Raman <priya@corp.com>; Marcus Hale
   <marcus@corp.com>", or they paste a comma-separated list. Rather than telling
   anyone which of those is allowed, the addresses are picked out of whatever
   arrives and shown back as separate values, so it is obvious what was
   understood. */
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
function emailList(text) {
  const found = String(text ?? '').match(EMAIL_RE) || [];
  return [...new Set(found.map(a => a.toLowerCase()))];
}

/* A box that takes any number of addresses, showing what it found underneath.
   It updates itself rather than redrawing the screen, which would throw the
   cursor out of the box on every keystroke. */
function emailField(value, onchange, opts = {}) {
  const wrap = el('div');
  const inp = el('input', { type: 'text', value: value || '', placeholder: opts.hint || '',
    style: opts.style || '' });
  const chips = el('div', { className: 'chips', style: 'margin-top:8px' });
  const note = el('div', { className: 'small faint', style: 'margin-top:5px;line-height:1.5' });
  const sync = () => {
    const found = emailList(inp.value);
    chips.innerHTML = '';
    found.forEach(a => chips.append(el('span', { className: 'chip mono', textContent: a })));
    note.textContent = found.length
      ? `${found.length} address${found.length === 1 ? '' : 'es'} read. Separate with commas, or paste the whole To line.`
      : (inp.value.trim() ? 'No email address in what is typed here.' : '');
    onchange(inp.value, found);
  };
  inp.oninput = sync;
  sync();
  wrap.append(inp, chips, note);
  return wrap;
}

/* ── the tables your team publishes ───────────────────────────────────────
   The most expensive setting in Ripple: a finding only counts as production
   impact when the table it ends at is on this list, so a list that is wrong
   turns a change that really breaks three published tables into a calm "no
   production impact". The same control is used on both settings screens —
   online it is held by the running server, offline it is written to the
   settings file beside the program — so there is one of it, here.

   The list can be pasted from wherever it lives: an Excel column, a Slack
   message, a Confluence page, a query result. Nothing is tidied silently:
   whatever the reader declined to use comes back with a reason, and every
   table on the list that Ripple has never seen in the repository is said out
   loud, because that is the one thing that has to be known before a result
   from this list is believed. */
function productionState() {
  if (!S.prod) {
    S.prod = { text: S.health?.productionRule?.text ?? '', report: null,
               checking: false, msg: null, loaded: false, timer: null };
  }
  return S.prod;
}

const PROD_HELP =
  'Paste the real list — one per line, or however it arrives from Excel, Slack or '
  + 'Confluence. Ripple reads it as written. A naming pattern works alongside: a word '
  + 'starting with an underscore matches the end of a table name (_PROD matches '
  + 'sales_prod), * matches anything (PROD_*), and * on its own means treat every table '
  + 'as published.';

/* Which build is running. Shared by both editions on purpose: this exists
   because "it does not work" has more than once turned out to be "that was
   fixed a while ago, on a copy that was never installed", and the copy nobody
   can check is exactly the offline one. Where the answer came from is shown
   too — a commit hash is a fact, a file date is a guess, and they must never
   read the same. */
function buildCard(h) {
  const b = h && h.build;
  if (!b) return null;
  const card = el('div', { className: 'card pad lg', style: 'margin-top:18px' });
  card.append(el('span', { className: 'lbl', textContent: 'This build' }));
  card.append(el('div', { className: 'mono', style: 'margin-top:10px;line-height:1.55',
    textContent: b.label }));
  if (b.from === 'files') {
    card.append(el('div', { className: 'small muted', style: 'margin-top:8px;line-height:1.55',
      textContent: 'No build record was found, so that is the date of the newest file in '
        + 'this folder. It moves whenever anything is touched, and it does not tell you '
        + 'whether this copy was ever installed anywhere.' }));
  } else {
    card.append(el('div', { className: 'small muted', style: 'margin-top:8px;line-height:1.55',
      textContent: b.from === 'build'
        ? 'Recorded when this copy was packaged.'
        : b.from === 'host'
        ? 'Reported by the host that deployed it.'
        : 'Read from the repository this copy is running out of.' }));
  }
  return card;
}

function productionCard(opts = {}) {
  const p = productionState();
  const card = el('div', { className: 'card pad lg' });
  card.append(why(
    el('span', { className: 'lbl', textContent: 'The tables your team publishes' }),
    'how this list is read',
    PROD_HELP));

  const ta = el('textarea', { className: 'mono', rows: 8, value: p.text,
    placeholder: 'cust360_customer_demographics\nfoundation.cust360_customer_address\n_PROD',
    style: 'margin-top:12px;font-size:12.5px;line-height:1.6;resize:vertical' });
  card.append(ta);

  const out = el('div', { style: 'margin-top:14px' });
  const paint = () => { out.innerHTML = ''; out.append(productionReport(p, opts)); };

  const check = () => {
    p.checking = true; paint();
    api('/api/production/read', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: p.text }),
    }).then(r => { p.report = r; })
      .catch(e => { p.report = null; p.msg = { ok: false, text: e.message }; })
      .finally(() => { p.checking = false; paint(); });
  };

  ta.oninput = () => {
    p.text = ta.value; p.msg = null;
    // Checked as it is typed rather than behind a button, but not on every
    // keystroke: the check walks the repository, which is not free.
    clearTimeout(p.timer);
    p.timer = setTimeout(check, 600);
  };
  if (opts.onSave) {
    const row = el('div', { className: 'foot', style: 'margin-top:14px' });
    const save = el('button', { className: 'pri', textContent: 'Save and use this list' });
    save.onclick = () => run(async () => {
      try {
        await opts.onSave(p.text);
        p.msg = { ok: true, text: opts.savedNote || 'Saved. Every scan from now on uses this list.' };
      } catch (e) { p.msg = { ok: false, text: e.message }; }
      p.report = null; p.loaded = false;
    });
    row.append(save);
    if (opts.persistNote) row.append(el('span', { className: 'small faint', textContent: opts.persistNote }));
    card.append(row);
  }
  card.append(out);
  // The list already in force is checked the moment the screen opens, rather
  // than waiting for somebody to touch the box. A rule that matches nothing is
  // worth knowing about before it is edited, not after.
  if (!p.loaded) { p.loaded = true; check(); } else { paint(); }
  return card;
}

/* What Ripple made of the list: what it read, what it ignored and why, and —
   the point of the whole thing — which of these tables it has never seen. */
function productionReport(p, opts = {}) {
  const box = el('div');
  if (p.msg) {
    box.append(el('div', { className: 'note ' + (p.msg.ok ? 'good' : 'bad'), style: 'margin-bottom:12px' },
      p.msg.text));
  }
  if (p.checking && !p.report) {
    box.append(el('div', { className: 'foot' }, el('span', { className: 'spin' }),
      el('span', { className: 'small muted', textContent: 'Reading the list and checking it against the repository…' })));
    return box;
  }
  const r = p.report;
  if (!r) return box;
  if (p.checking) {
    box.append(el('div', { className: 'small faint', style: 'margin-bottom:8px' },
      el('span', { className: 'spin' }), ' Re-checking…'));
  }

  if (!r.entries.length) {
    box.append(el('div', { className: 'note bad' },
      el('b', { textContent: 'Nothing in that box was read as a table name. ' }),
      'So nothing can be scanned yet. Ripple does not guess a rule — a list nobody '
      + 'chose produces an answer that looks exactly like a real one. Paste the list '
      + 'again, one table per line.'));
    if (r.notes.length) box.append(productionNotes(r));
    return box;
  }

  // ── what was read ──
  const head = el('div', { style: 'display:flex;gap:10px;align-items:baseline;flex-wrap:wrap' });
  head.append(el('b', { style: 'font-size:14px', textContent:
    r.nameCount
      ? `${r.nameCount} table name${r.nameCount === 1 ? '' : 's'} read`
      : 'No exact table names — patterns only' }));
  if (r.patternCount) {
    head.append(el('span', { className: 'badge sm violet',
      textContent: `${r.patternCount} pattern${r.patternCount === 1 ? '' : 's'}` }));
  }
  box.append(head);

  const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
  r.entries.forEach(e => {
    const chip = el('span', { className: 'chip mono' + (e.isPattern ? ' pattern' : ''),
      textContent: e.given });
    if (e.isPattern) chip.title = e.kind === 'glob'
      ? 'A pattern — matched against the whole table name'
      : 'A pattern — matches the end of a table name';
    chips.append(chip);
  });
  box.append(chips);
  if (r.patternCount) {
    box.append(el('div', { className: 'small faint', style: 'margin-top:8px;line-height:1.5',
      textContent: 'The outlined ones are patterns, not table names. Everything else is matched exactly.' }));
  }

  if (r.notes.length) box.append(productionNotes(r));
  box.append(productionCheck(r));
  return box;
}

function productionNotes(r) {
  const wrap = el('div', { className: 'note info', style: 'margin-top:12px' });
  wrap.append(el('b', { style: 'display:block', textContent: 'What Ripple did with that paste' }));
  r.notes.forEach(n => {
    const line = el('div', { style: 'margin-top:6px;line-height:1.55' }, n.text);
    if (n.examples && n.examples.length) {
      line.append(el('span', { className: 'small faint',
        textContent: ' — ' + n.examples.join(' · ') }));
    }
    wrap.append(line);
  });
  return wrap;
}

/* The important one. If fifty tables are pasted and Ripple has only ever seen
   forty-four of them, the other six are either misspelled or built somewhere it
   could not read — and either way a clean result for those six means nothing. */
function productionCheck(r) {
  const c = r.check;
  const wrap = el('div');
  if (!c || !c.checked) {
    wrap.append(el('div', { className: 'note warn', style: 'margin-top:12px' },
      el('b', { textContent: 'This list has not been checked against a repository. ' }),
      'Nothing has been read yet, so Ripple cannot say whether these tables exist. '
      + 'Choose the repository, then come back to this box.'));
    return wrap;
  }
  const missing = c.missing || [];
  const total = c.foundCount + missing.length;
  if (total) {
    wrap.append(el('div', { className: 'note ' + (missing.length ? 'bad' : 'good'), style: 'margin-top:12px' },
      el('b', { style: 'display:block;font-size:14px', textContent: missing.length
        ? `${missing.length} of the ${total} table${total === 1 ? '' : 's'} on this list `
          + `${missing.length === 1 ? 'is' : 'are'} not in this repository`
        : `All ${total} table${total === 1 ? '' : 's'} on this list were found in this repository` }),
      el('div', { style: 'margin-top:6px;line-height:1.55', textContent: missing.length
        ? `Ripple read ${c.tablesKnown.toLocaleString()} table names out of the code it could `
          + 'understand, and these are not among them. Either the name is spelled differently '
          + 'here, or the table is built somewhere Ripple could not read. Until that is settled, '
          + 'a clean result for these tables means nothing.'
        : `Checked against the ${c.tablesKnown.toLocaleString()} table names Ripple read out of `
          + 'this repository.' })));
    // Found as a family rather than by the exact name: the list says
    // order_lines, the code writes order_lines_20260101. Said here, because
    // "found" over a family match is half the truth, and half the truth is
    // what this whole screen exists to prevent.
    const family = (c.found || []).filter(f => f.how && f.how !== 'exact');
    if (family.length) {
      const fam = el('div', { className: 'note info', style: 'margin-top:12px' });
      fam.append(why(
        el('b', { textContent: `${family.length} of the found table${family.length === 1 ? '' : 's'} `
          + `${family.length === 1 ? 'was' : 'were'} matched as a family, not by exact name` }),
        'tables matched as a family',
        'The code writes these with a date or a run-time placeholder on the end — '
        + 'order_lines_20260101, or fact_returns with a run date glued on — and the list has '
        + 'the name without it. Ripple counts every such copy as the published table. That is '
        + 'a loose match in the safe direction: it can only add a finding, never hide one.'));
      const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:8px' });
      family.forEach(f => chips.append(el('span', { className: 'chip mono',
        textContent: `${f.given} → ${(f.as || []).join(', ')}`
          + (f.asCount > (f.as || []).length ? ` and ${f.asCount - f.as.length} more` : '')
          + ` (${f.how === 'shard' ? 'dated copies' : 'a placeholder on the end'})` })));
      fam.append(chips);
      wrap.append(fam);
    }
    // Grouped rather than listed one sentence at a time. Sixty rows each saying
    // the same thing is a page nobody scrolls to the end of, and the two groups
    // send a person to two completely different places.
    [['nowhere', 'Not written anywhere in this repository',
      'A misspelling, a table from another repository, or one no code here names at all.'],
     ['written', 'The name is here, but nothing Ripple could read builds it',
      'Something creates these somewhere it could not follow — a procedure, a generated statement, or a job it has never seen.'],
    ].forEach(([state, title, why]) => {
      const group = missing.filter(m => m.state === state);
      if (!group.length) return;
      wrap.append(el('div', { style: 'margin-top:12px' },
        el('span', { className: 'lbl', textContent: `${title} — ${group.length}` }),
        el('div', { className: 'small faint', style: 'margin-top:4px;line-height:1.5', textContent: why })));
      const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:8px' });
      group.forEach(m => chips.append(el('span', { className: 'chip mono', textContent: m.given })));
      wrap.append(chips);
    });
    // A name nobody uses as a table may have been meant as a naming rule. Said
    // rather than guessed at: quietly re-reading it as a pattern is how a rule
    // stops meaning what it says.
    const meant = missing.filter(m => m.endsWith);
    if (meant.length) {
      const note = el('div', { className: 'note warn', style: 'margin-top:12px' },
        el('b', { style: 'display:block', textContent: meant.length === 1
          ? `No table is called ${meant[0].given} — but ${meant[0].endsWith} table`
            + `${meant[0].endsWith === 1 ? '' : 's'} end with it`
          : `${meant.length} of those names are the end of a real table name here` }),
        el('div', { style: 'margin-top:6px;line-height:1.55', textContent:
          'Ripple is treating them as exact table names, so they match nothing. If they were '
          + 'meant as a naming rule, write each one with an underscore or a star in front — '
          + `${meant.slice(0, 3).map(m => '_' + m.given).join(', ')} — and it will match the `
          + 'end of a name instead.' }));
      wrap.append(note);
    }
  }
  const dead = (c.patterns || []).filter(x => !x.matches);
  if (dead.length) {
    // "Your patterns" is wrong when nobody has set a list and these are Ripple's
    // own guess -- and the consequence used to be spelled out here in the same
    // twenty-two words as the note directly underneath, so the screen said the
    // same thing twice in two amber boxes touching each other.
    const mine = S.health?.productionSet ? 'your patterns' : 'the patterns entered';
    wrap.append(el('div', { className: 'note warn', style: 'margin-top:12px' },
      why(el('b', { textContent: dead.length === 1
          ? `The pattern ${dead[0].given} matches no table in this repository`
          : `${dead.length} of ${mine} match no table here — ${dead.map(d => d.given).join(', ')}` }),
        'patterns that match nothing',
      'A pattern that matches nothing does nothing. If your published tables are named some '
      + 'other way, Ripple will not count any of them as published, and the result will look '
      + 'safer than it is. Correct the list above.')));
  }
  const live = (c.patterns || []).filter(x => x.matches);
  if (live.length) {
    live.forEach(x => wrap.append(el('div', { className: 'small muted', style: 'margin-top:8px;line-height:1.55' },
      el('span', { className: 'chip mono pattern', textContent: x.given }),
      ` matches ${x.matches} table${x.matches === 1 ? '' : 's'} here — ${x.examples.join(', ')}`
        + (x.matches > x.examples.length ? ' and others' : ''))));
  }
  return wrap;
}

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = `${r.status}`;
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.json();
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + (iso.length === 10 ? 'T00:00:00' : ''));
  if (isNaN(d)) return iso;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}
function daysLeft(iso) {
  if (!iso) return null;
  const d = new Date(iso + 'T00:00:00');
  if (isNaN(d)) return null;
  return Math.round((d - new Date(new Date().toDateString())) / 86400000);
}
/* "No impact" is the only thing this tool sells, so there has to be a word for
   "I found nothing AND there is something here I could not read". Those are not
   the same answer, and printed as the same green badge the second one is a lie
   that reads as a promise. See _risk_of in lineage.py. */
const RISK = {
  high:    ['red',   'High risk'],
  medium:  ['amber', 'Medium risk'],
  low:     ['blue',  'Low risk'],
  unknown: ['amber', 'Not sure — needs a person'],
  none:    ['green', 'No impact'],
};

// ── chrome ────────────────────────────────────────────────────────────────
/* Typing the change in by hand and then being shown "check what Ripple read"
   is being asked to check your own typing. In that mode step 1 is the review,
   so the review step is not in the wizard at all -- rather than being in it,
   greyed out, or silently skipped past while the count still says 7. */
function manualFlow() {
  if (S.step === 1) return S.mode === 'manual';
  return S.vals ? S.vals.extractedBy === 'manual' : false;
}
function stepNumbers() {
  return manualFlow() ? [1, 3, 4, 5, 6, 7] : [1, 2, 3, 4, 5, 6, 7];
}
function nextStepAfter(n) {
  const list = stepNumbers();
  return list[Math.min(list.indexOf(n) + 1, list.length - 1)];
}

function renderSteps() {
  const box = $('#steps');
  box.innerHTML = '';
  stepNumbers().forEach((n, i) => {
    const [label, sub] = STEPS[n - 1];
    const on = S.view === 'wizard' && S.step === n;
    const done = n < S.maxStep && !on;
    const b = el('button', { className: `step${on ? ' on' : ''}${done ? ' done' : ''}` });
    b.disabled = n > S.maxStep;
    b.append(el('span', { className: 'n', textContent: done ? '✓' : String(i + 1) }),
      el('span', {}, el('span', { className: 't', textContent: label }),
        el('span', { className: 's', textContent: sub })));
    b.onclick = () => { if (n <= S.maxStep) { S.view = 'wizard'; S.step = n; render(); } };
    box.append(b);
  });
  $('#navHistory').className = 'navbtn' + (S.view === 'history' ? ' on' : '');
  $('#navSettings').className = 'navbtn' + (S.view === 'settings' ? ' on' : '');
}

function renderStatus() {
  const h = S.health;
  const box = $('#status');
  box.innerHTML = '';
  if (!h) return;
  const repoOk = h.repo.exists && h.repo.files > 0;
  box.append(
    el('div', { className: 'srow' },
      el('span', { className: 'dot ' + (repoOk ? 'ok' : 'warn') }),
      el('span', { textContent: repoOk ? `${h.repo.label} · ${h.repo.files} files` : 'No repository found' })),
    //<online-only>
    el('div', { className: 'srow' },
      el('span', { className: 'dot ' + (h.ai.available ? 'ok' : 'off') }),
      el('span', { textContent: h.ai.available ? 'AI on' : 'AI off — rules only' })),
    //</online-only>
    el('div', { className: 'srow' },
      el('span', { className: 'dot ' + (h.sqlDialect === 'generic' ? 'warn' : 'ok') }),
      el('span', { textContent: `SQL read as ${h.sqlDialect}` })),
  );
}

function setHeader(title, sub) { $('#hTitle').textContent = title; $('#hSub').textContent = sub; }

// ── step 1 ────────────────────────────────────────────────────────────────
function step1(root) {
  x(root, 'title').textContent = S.mode === 'manual' ? 'Enter the change by hand' : 'New impact notification';
  x(root, 'sub').textContent = S.mode === 'manual'
    ? 'Type the upstream table and attributes yourself.'
    : 'Upload the notification file.';
  $$('[data-mode]', root).forEach(b => {
    b.className = 'pill' + (b.dataset.mode === S.mode ? ' on' : '');
    b.onclick = () => { S.mode = b.dataset.mode; render(); };
  });
  x(root, 'emailMode').classList.toggle('hide', S.mode !== 'email');
  x(root, 'manualMode').classList.toggle('hide', S.mode !== 'manual');

  if (S.mode === 'email') {
    //<online-only>
    const ai = S.health?.ai?.available;
    x(root, 'aiState').textContent = ai
      ? ` The email is read by ${S.health.ai.modelLabel}.`
      : ' AI is off — fields are matched against the repository instead.';
    //</online-only>
    // What Ripple does, in one line, with the four steps behind the button.
    const does = x(root, 'does');
    does.append(el('span', { className: 'lbl', textContent: 'What Ripple does' }));
    const steps = el('ol', { className: 'nums', style: 'margin-top:0' });
    ['Reads the tables, attributes, date and contact out of the notice',
     'Searches every file in the connected repository',
     'Follows each rename to the production table it feeds',
     'Says what breaks — and what it could not read',
    ].forEach(t => steps.append(el('li', {}, t)));
    does.append(why(
      el('span', { style: 'line-height:1.55',
        textContent: 'Reads your notification, searches your repository, and says what this '
          + 'change breaks.' }),
      'what Ripple does, step by step', steps));
    const confirm = x(root, 'confirm');
    confirm.append(why(
      el('b', { textContent: 'Nothing is scanned until you confirm.' }),
      'confirming before a scan',
      'Ripple shows you everything it read out of the email first, and every field can be '
      + 'edited. The scan then uses what is on that screen — not the email.'));
    const drop = $('#drop', root), file = $('#file', root);
    drop.onclick = () => file.click();
    drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); };
    drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = (e) => {
      e.preventDefault(); drop.classList.remove('over');
      if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
    };
    file.onchange = () => file.files[0] && upload(file.files[0]);
    return;
  }

  // manual
  x(root, 'noAi').append(why(
    el('b', { textContent: 'No AI used in this mode.' }),
    'what happens without AI',
      'Ripple searches for exactly the names you type. Nothing is sent anywhere.'));
  const rows = x(root, 'manRows');
  rows.innerHTML = '';
  S.manRows.forEach((r, i) => {
    const wrap = el('div', { style: 'display:flex;gap:20px;align-items:flex-end;padding:16px 20px;flex-wrap:wrap' + (i ? ';border-top:1px solid var(--hair)' : '') });
    const t = el('input', { type: 'text', className: 'mono', value: r.table, placeholder: 'CUSTOMER_DEMOGRAPHICS', style: 'margin-top:6px' });
    t.oninput = () => { r.table = t.value; updateManHint(root); };
    // Emptied and disabled while "Whole table" is on: the table itself is
    // changing, so there is no one column to name.
    const a = el('input', { type: 'text', className: 'mono', value: r.whole ? '' : r.attrs,
      placeholder: r.whole ? 'every column — the table itself is changing' : 'MARKET_CODE, MARKET_NAME',
      disabled: !!r.whole, style: 'margin-top:6px' });
    a.oninput = () => { r.attrs = a.value; updateManHint(root); };
    wrap.append(
      el('div', { style: 'flex:1;min-width:220px' }, el('span', { className: 'lbl faint', textContent: 'Upstream table name' }), t),
      el('div', { style: 'flex:1.4;min-width:260px' }, el('span', { className: 'lbl faint', textContent: 'Attributes — comma separated' }), a),
      el('div', { style: 'padding-bottom:9px' },
        wholeToggle(r.whole, (on) => { r.whole = on; if (on) r.attrs = ''; render(); })));
    if (S.manRows.length > 1) {
      const rm = el('button', { className: 'danger', textContent: 'Remove' });
      rm.onclick = () => { S.manRows.splice(i, 1); render(); };
      wrap.append(rm);
    }
    rows.append(wrap);
  });
  x(root, 'addRow').onclick = () => { S.manRows.push({ table: '', attrs: '', whole: false }); render(); };

  const fields = x(root, 'manFields');
  fields.innerHTML = '';
  const small = 'margin-top:7px;font-size:12.5px;font-weight:400;color:var(--mute);padding:7px 11px';
  MAN_FIELDS.forEach(([key, label, type, hint]) => {
    const field = el('div', { className: 'field' }, el('span', { className: 'lbl faint', textContent: label }));
    if (type === 'kind') {
      const sel = el('select', { style: 'margin-top:7px;padding:7px 11px;font-size:12.5px' });
      CHANGE_KINDS.forEach(([k, l]) => sel.append(el('option', { value: k, textContent: l, selected: k === S.man.changeKind })));
      sel.onchange = () => { S.man.changeKind = sel.value; };
      field.append(sel);
    } else if (type === 'emails') {
      field.append(emailField(S.man.pocEmail, (raw) => { S.man.pocEmail = raw; },
        { hint, style: small }));
    } else if (type === 'lines') {
      const ta = el('textarea', { rows: 3, value: S.man[key], placeholder: hint,
        style: small + ';line-height:1.55' });
      ta.oninput = () => { S.man[key] = ta.value; };
      field.append(ta);
    } else {
      const inp = el('input', { type: type === 'date' ? 'date' : 'text',
        value: S.man[key], placeholder: hint, style: small });
      inp.oninput = () => { S.man[key] = inp.value; };
      field.append(inp);
      // A date typed in a box is a date somebody has to work out. The picker is
      // the control; this is the answer in words, so a slip is visible.
      if (type === 'date') {
        const said = el('div', { className: 'small faint', style: 'margin-top:5px' });
        const sayDate = () => {
          const dl = daysLeft(inp.value);
          said.textContent = inp.value
            ? fmtDate(inp.value) + (dl === null ? '' : dl < 0 ? ' — that date has passed'
              : ` — ${dl} day${dl === 1 ? '' : 's'} away`)
            : '';
        };
        inp.addEventListener('input', sayDate);
        sayDate();
        field.append(said);
      }
    }
    fields.append(field);
  });

  x(root, 'manDemo').onclick = () => {
    S.manRows = [{ table: 'CUSTOMER_DEMOGRAPHICS', attrs: 'MARKET_CODE, MARKET_NAME' },
                 { table: 'CUSTOMER_ADDRESS', attrs: 'COUNTRY_CODE' }];
    S.man = { source: 'C360', changeKind: 'value_change', effectiveDate: '2026-09-18',
      changeDesc: "Values change from ISO abbreviations to full country names ('US' becomes 'United States').",
      pocName: 'Priya Raman',
      pocEmail: 'priya.raman@corp.example.com, dl-c360-governance@corp.example.com',
      pocTeam: 'C360 Data Governance' };
    render();
  };
  x(root, 'manStart').onclick = () => startManual();
  updateManHint(root);
}

/* A row can be scanned when it names a table and either names an attribute or
   says the whole table is changing. A table with neither is refused by the
   server with the same words, so it is refused here first, in the open. */
function manRowReady(r) { return !!r.table.trim() && (!!r.whole || !!r.attrs.trim()); }
function manValid() { return S.manRows.some(manRowReady); }
function updateManHint(root) {
  const tables = S.manRows.filter(r => r.table.trim()).length;
  const attrs = S.manRows.reduce((a, r) => a + (r.whole ? 0 : r.attrs.split(',').map(s => s.trim()).filter(Boolean).length), 0);
  const whole = S.manRows.filter(r => r.table.trim() && r.whole).length;
  const half = S.manRows.filter(r => r.table.trim() && !manRowReady(r)).length;
  x(root, 'manCount').textContent = tables
    ? `${tables} table${tables > 1 ? 's' : ''} · ${attrs} attribute${attrs === 1 ? '' : 's'}`
      + (whole ? ` · ${whole} whole table${whole === 1 ? '' : 's'}` : '')
    : 'Nothing entered yet';
  const ok = manValid();
  x(root, 'manStart').disabled = !ok;
  // The button says where it goes, so the hint no longer repeats it. It used to
  // read "Run impact analysis" and land on the repository screen instead, beside
  // a second button of the same name.
  x(root, 'manHint').textContent = !ok
    ? 'Enter a table name and an attribute — or tick "Whole table" if the table itself is changing.'
    : half
      ? `${half} table${half === 1 ? ' has' : 's have'} no attribute and ${half === 1 ? 'is' : 'are'} not `
        + `marked whole, so ${half === 1 ? 'it' : 'they'} will not be scanned. Nothing is scanned yet.`
      : 'Nothing is scanned yet.';
}

function startManual() {
  if (!manValid()) return;
  S.vals = {
    source: S.man.source.trim() || 'Entered manually',
    changeType: kindLabel(S.man.changeKind),
    changeKind: S.man.changeKind || 'unknown',
    changeDesc: S.man.changeDesc.trim() || 'Entered by hand — no notification email was used.',
    subject: 'Manual impact check — ' + S.manRows.filter(manRowReady).map(r => r.table.trim()).join(', '),
    effectiveDate: S.man.effectiveDate.trim(),
    pocName: S.man.pocName.trim(),
    pocEmail: S.man.pocEmail.trim(), pocEmails: emailList(S.man.pocEmail),
    pocTeam: S.man.pocTeam.trim(),
    upstream: S.manRows.filter(manRowReady).map(r => ({
      table: r.table.trim(),
      attrs: r.whole ? [] : r.attrs.split(',').map(s => s.trim()).filter(Boolean),
      whole: !!r.whole,
    })),
    extractedBy: 'manual', warnings: [],
  };
  S.emailPreview = null; S.scan = null; S.summary = null; S.savedId = null;
  // Straight to the repository. There is nothing on the review step that was
  // not just typed on this one.
  goto(3);
}

function upload(f) {
  // Check the size here as well as on the server. A hosted copy sits behind a
  // host that rejects an oversized upload itself, and its refusal is a bare
  // number with no explanation — so say it properly before sending anything.
  const cap = S.health?.limits?.maxUploadBytes || 25000000;
  if (f.size > cap) {
    alert(`That file is ${(f.size / 1e6).toFixed(1)} MB. The most this copy of Ripple accepts is `
      + `${Math.round(cap / 1e6)} MB.`
      + (S.health?.serverless
        ? ' It is running on a serverless host, which refuses anything bigger before Ripple'
          + ' sees it. Save the email as .eml, which is far smaller than a .msg, or enter the'
          + ' change by hand on the Enter manually tab.'
        : ''));
    return;
  }
  run(async () => {
    const fd = new FormData();
    fd.append('file', f);
    const out = await api('/api/read-email?useAI=true', { method: 'POST', body: fd });
    acceptExtract(out);
  }, 'Reading the notification…');
}

function acceptExtract(out) {
  S.emailPreview = out.emailPreview || null;
  S.vals = {
    source: out.source || '', changeType: out.changeType || '', changeKind: out.changeKind || 'unknown',
    changeDesc: out.changeDesc || '', subject: out.subject || '', effectiveDate: out.effectiveDate || '',
    pocName: out.pocName || '', pocEmail: out.pocEmail || '', pocEmails: emailList(out.pocEmail),
    pocTeam: out.pocTeam || '',
    // A named attribute wins over "whole", as it does in the reader: the two
    // scans are different questions, and a row asking both answers neither.
    upstream: (out.upstream || []).map(u => ({ table: u.table, attrs: u.attrs || [],
      whole: !!u.whole && !(u.attrs || []).length })),
    extractedBy: out.extractedBy || 'rules',
    warnings: out.warnings || [], aiNote: out.aiNote || '',
  };
  S.scan = null; S.summary = null; S.savedId = null;
  goto(2);
}

// ── step 2 ────────────────────────────────────────────────────────────────
function step2(root) {
  const v = S.vals;
  const manual = v.extractedBy === 'manual';
  x(root, 'title').textContent = manual ? 'Change details' : 'What Ripple read';
  x(root, 'sub').textContent = manual
    ? 'Edit anything before scanning.'
    : 'Ripple scans on exactly what is here, not on the email.';
  x(root, 'by').textContent = manual ? 'Entered by you — no AI used'
    //<online-only>
    : v.extractedBy === 'ai' ? 'Read by AI — check it'
    //</online-only>
    : 'Found by matching the catalogue — check it';

  const warn = x(root, 'warnings'); warn.innerHTML = '';
  (v.warnings || []).forEach(w => warn.append(el('div', { className: 'note warn', textContent: w, style: 'margin-bottom:12px' })));

  const meta = x(root, 'meta'); meta.innerHTML = '';
  const dl = daysLeft(v.effectiveDate);
  const metaDefs = [
    ['Source system', 'source', 'text'],
    ['Change type', 'changeKind', 'select'],
    ['Effective date', 'effectiveDate', 'date'],
    ['Contact', 'pocName', 'text'],
  ];
  metaDefs.forEach(([label, key, type]) => {
    const card = el('div', { className: 'stat' });
    card.append(el('span', { className: 'lbl', textContent: label }));
    if (type === 'select') {
      const sel = el('select', { style: 'margin-top:8px' });
      CHANGE_KINDS.forEach(([k, l]) => sel.append(el('option', { value: k, textContent: l, selected: k === v.changeKind })));
      sel.onchange = () => { v.changeKind = sel.value; v.changeType = sel.selectedOptions[0].textContent; };
      card.append(sel);
    } else {
      const inp = el('input', { type: type === 'date' ? 'date' : 'text', value: v[key] || '', style: 'margin-top:8px' });
      inp.oninput = () => { v[key] = inp.value; };
      card.append(inp);
      if (key === 'effectiveDate' && dl !== null) {
        card.append(el('span', { className: 'badge sm ' + (dl <= 21 ? 'amber' : 'blue'),
          textContent: dl < 0 ? 'date has passed' : `${dl} day${dl === 1 ? '' : 's'} left`, style: 'margin-top:8px' }));
      }
      // Every address, editable, and as many as there are. A notification is
      // often sent by one person on behalf of a mailbox, and the reply has to
      // go to both.
      if (key === 'pocName') {
        card.append(emailField(v.pocEmail, (raw, found) => { v.pocEmail = raw; v.pocEmails = found; },
          { hint: 'name@corp.example.com, other@corp.example.com', style: 'margin-top:8px' }));
      }
    }
    meta.append(card);
  });

  const subj = x(root, 'subject'); subj.value = v.subject || ''; subj.oninput = () => { v.subject = subj.value; };
  const desc = x(root, 'desc'); desc.value = v.changeDesc || ''; desc.oninput = () => { v.changeDesc = desc.value; };

  renderUpstreamRows(root, v);
  x(root, 'addRow').onclick = () => { v.upstream.push({ table: '', attrs: [], whole: false }); render(); };
  x(root, 'next').onclick = () => goto(3);
}

/* A row can be scanned when it names a table and either names an attribute or
   says the whole table is changing. The same rule as the manual screen and
   the server, in the same words. */
function rowReady(u) { return !!(u.table || '').trim() && (!!u.whole || (u.attrs || []).length > 0); }

function renderUpstreamRows(root, v) {
  const box = x(root, 'rows'); box.innerHTML = '';
  const tables = v.upstream.filter(u => u.table.trim()).length;
  const attrs = v.upstream.reduce((a, u) => a + (u.whole ? 0 : (u.attrs || []).length), 0);
  const whole = v.upstream.filter(u => u.table.trim() && u.whole).length;
  x(root, 'count').textContent = `${tables} table${tables === 1 ? '' : 's'} · ${attrs} attribute${attrs === 1 ? '' : 's'}`
    + (whole ? ` · ${whole} whole table${whole === 1 ? '' : 's'}` : '');
  v.upstream.forEach((u, i) => {
    const wrap = el('div', { style: 'padding:16px 20px;animation:fadeUp .3s ease' + (i ? ';border-top:1px solid var(--hair)' : '') });
    const line = el('div', { style: 'display:flex;gap:24px;align-items:flex-end;flex-wrap:wrap' });
    const t = el('input', { type: 'text', className: 'mono', value: u.table, style: 'margin-top:6px' });
    t.oninput = () => { u.table = t.value; };
    const a = el('input', { type: 'text', className: 'mono', value: u.whole ? '' : (u.attrs || []).join(', '),
      placeholder: u.whole ? 'every column — the table itself is changing' : 'MARKET_CODE, MARKET_NAME',
      disabled: !!u.whole, style: 'margin-top:6px' });
    a.oninput = () => { u.attrs = a.value.split(',').map(s => s.trim()).filter(Boolean); };
    const rm = el('button', { className: 'danger', textContent: 'Remove' });
    rm.onclick = () => { v.upstream.splice(i, 1); render(); };
    line.append(
      el('div', { style: 'width:288px;flex-shrink:0' }, el('span', { className: 'lbl faint', textContent: 'Upstream table name' }), t),
      el('div', { style: 'flex:1;min-width:240px' }, el('span', { className: 'lbl faint', textContent: 'Upstream attributes name' }), a),
      el('div', { style: 'padding-bottom:9px' },
        wholeToggle(u.whole, (on) => { u.whole = on; if (on) u.attrs = []; render(); })),
      rm);
    wrap.append(line);
    // Said on the row, in the words the scan will use. A whole-table row and a
    // row with nothing on it look alike from across the room, and they are
    // opposites: one scans everything, the other cannot be scanned at all.
    if (u.table.trim() && u.whole) {
      wrap.append(el('div', { className: 'note warn', style: 'margin-top:10px;padding:10px 14px' },
        el('b', { textContent: 'Whole table. ' }),
        `Ripple will follow every statement that reads ${u.table.trim()}, and every table built `
        + 'from those. Untick this if only some attributes change, and name them instead.'));
    } else if (u.table.trim() && !rowReady(u)) {
      wrap.append(el('div', { className: 'note bad', style: 'margin-top:10px;padding:10px 14px' },
        el('b', { textContent: 'Nothing to scan on this row. ' }),
        'Add the attribute that is changing, or tick "Whole table" if the table itself is '
        + 'changing. As it stands Ripple will refuse to scan it.'));
    }
    box.append(wrap);
  });
  if (!v.upstream.length) box.append(el('div', { className: 'pad muted', textContent: 'Nothing to scan yet — add a table below.' }));
  // The button follows the rows. Nothing can go forward while a named table
  // has nothing on it: the server refuses that row, in the same words.
  const next = x(root, 'next');
  next.disabled = !v.upstream.some(rowReady) || v.upstream.some(u => u.table.trim() && !rowReady(u));
}

// ── step 3 ────────────────────────────────────────────────────────────────
/* Anything worth saying about the repository before anything is scanned, or
   nothing at all. Online that is a failed connection; offline it is a folder
   that has been moved or deleted since it was chosen, so the offline build
   replaces this whole function rather than sharing it. */
//<online-only>
function repoAlert(h) {
  if (S.connectMsg) {
    return el('div', { className: 'note bad', style: 'margin-bottom:18px' },
      el('b', { textContent: 'Could not connect. ' }), S.connectMsg);
  }
  if (h.connectError) {
    return el('div', { className: 'note warn', style: 'margin-bottom:18px' },
      el('b', { textContent: 'Reading the folder on this machine instead. ' }), h.connectError);
  }
  return null;
}
//</online-only>

function step3(root) {
  const h = S.health;
  if (!h) return;
  //<online-only>
  if (S.repoTab === null) S.repoTab = h.source === 'github' ? 'github' : 'folder';
  const onGit = S.repoTab === 'github';
  const live = h.source === 'github';
  //</online-only>

  x(root, 'title').textContent =
    //<online-only>
    onGit ? 'Read a GitHub repository' :
    //</online-only>
    'Connected repository';
  x(root, 'sub').textContent =
    //<online-only>
    onGit ? 'Point Ripple at a repository and give it an access token. It only ever reads.' :
    //</online-only>
    'This is the code Ripple will search. It is read, never written to.';

  //<online-only>
  $$('[data-src]', root).forEach(b => {
    b.className = 'pill' + (b.dataset.src === S.repoTab ? ' on' : '');
    b.onclick = () => { S.repoTab = b.dataset.src; S.connectMsg = ''; render(); };
  });
  //</online-only>

  const alert = x(root, 'alert'); alert.innerHTML = '';
  const said = repoAlert(h);
  if (said) alert.append(said);

  x(root, 'left').innerHTML = '';
  x(root, 'left').append(
    //<online-only>
    onGit ? gitHubForm(h, live) :
    //</online-only>
    repoFacts(h));

  // the same confirmation the prototype shows, on the numbers Ripple really has
  const ready = x(root, 'ready'); ready.innerHTML = '';
  const repoOk = h.repo.exists && h.repo.files > 0;
  // Where the code came from, and the one fact that pins down which version of
  // it was read. A folder that was never a git checkout has no branch, and says
  // nothing rather than claiming "main" because that is the usual answer.
  let where = 'a folder on this machine';
  let pin = h.repo.branch ? ['Branch ', el('span', { className: 'mono', textContent: h.repo.branch })] : [];
  //<online-only>
  // Pulled from a hosted repository instead, where the commit is the exact
  // version. Naming the source here is what stops a connect form sitting beside
  // this note from being mistaken for "connected" when the folder is what is
  // really loaded.
  if (live) {
    where = 'from GitHub';
    pin = ['Commit ', el('span', { className: 'mono', textContent: h.github.shortCommit || h.github.branch })];
  }
  //</online-only>
  ready.append(el('div', { className: 'note ' + (repoOk ? 'good' : 'warn') },
    el('b', { textContent: repoOk ? `✓ ${h.repo.label} connected` : `Nothing to scan in ${h.repo.label}`,
      style: 'display:block;font-size:14px' }),
    el('div', { className: 'small', style: 'margin-top:2px;font-weight:600;opacity:.8',
      textContent: where }),
    el('div', { style: 'margin-top:8px;line-height:1.55' },
      pin,
      (pin.length ? ' — ' : '') + (repoOk
        ? `${h.repo.files} file${h.repo.files === 1 ? '' : 's'} ready to scan.`
        : 'check the repository folder in Settings & checks.'))));
  ready.append(neverOpenedNote(h.repo.heldOnline || 0, h.repo.pathTooLong || 0));
  // Only when nobody has said. This is not a warning any more: nothing is
  // scanned until the list has been given. Ripple used to fill it in with a
  // guess -- _PROD, _PRD, _PUBLISHED -- and on a warehouse that names its
  // published tables any other way that guess matched nothing. Matching nothing
  // did not read as "I do not know which tables are yours"; it read as "no
  // production table is affected", in green, over a change that broke them all.
  if (!h.productionSet) {
    ready.append(el('div', { className: 'note warn', style: 'margin-top:12px' },
      why(el('b', { textContent: 'Ripple needs to know which tables you publish.' }),
        'why it will not scan without this',
      'A published table is one people outside your team read, and Ripple has no way of '
      + 'working out which of yours those are — every warehouse names them differently. '
      + 'Without the list, every table fails that test, and a change that breaks three of '
      + 'them comes back as "no production table is affected". That is the same green tick '
      + 'as a genuinely clean answer, which is why Ripple will not give it.',
      'Open Settings & checks and paste your published table names, or a pattern they all '
      + 'share such as _PUBLISHED. It takes a minute and it is the setting the whole answer '
      + 'rests on.')));
  }
  if (h.repo.inSkippedDirs) {
    const box = el('div', { className: 'note warn', style: 'margin-top:12px' });
    box.append(why(
      el('b', { textContent: `${h.repo.inSkippedDirs} file${h.repo.inSkippedDirs === 1 ? '' : 's'} `
        + 'skipped — in ' + (h.repo.skippedDirNames || []).join(', ') }),
      'folders Ripple skips',
      'Folders with these names usually hold generated copies of code, so Ripple walks past '
      + 'them. If your real pipeline lives in one, none of it was read and none of it is in '
      + 'this answer.'));
    ready.append(box);
  }

  // what kinds of file are in the index — counted, not assumed
  const kinds = x(root, 'kinds'); kinds.innerHTML = '';
  // Nothing indexed means nothing to list, and an empty card sitting there
  // reads as a panel that failed to load.
  kinds.classList.toggle('hide', !h.repo.kinds?.length);
  if (h.repo.kinds?.length) {
    kinds.append(el('span', { className: 'lbl', textContent: 'What gets read' }));
    const chips = el('div', { className: 'chips', style: 'margin-top:12px' });
    h.repo.kinds.forEach(k => chips.append(el('span', { className: 'chip', textContent: `${k.lang} · ${k.files}` })));
    kinds.append(chips);
    // A DAG that runs a query kept in a separate .sql file holds no SQL of its
    // own, so it used to be indistinguishable from a config file with nothing
    // in it. The query itself is read on its own account — this is the link
    // between the two, said so that "Python · 240" is not read as 240 files
    // Ripple learned nothing from.
    if (h.repo.runsSqlFrom) {
      kinds.append(el('div', { className: 'small muted', style: 'margin-top:14px' },
        why(el('span', { textContent: `${h.repo.runsSqlFrom} of these run SQL kept in a `
          + 'separate .sql file' }),
          'files that run SQL from elsewhere',
      'These files hold no SQL of their own — they run a .sql file kept beside them. Ripple '
      + 'read those .sql files separately, so nothing is lost. If one of them points at a file '
      + 'that is not in this repository, the result will say so.')));
    }
    // File types Ripple does not open. Nothing recorded these before — the walk
    // had a bare `continue` with no counter — so a repository whose pipeline is
    // written in .ipynb or .tf files looked exactly like one with no pipeline
    // in it. The point is not to read them. It is that the NEXT unlisted
    // extension is visible instead of silent.
    if (h.repo.unknownExt?.length) {
      const total = h.repo.unknownExt.reduce((n, k) => n + k.files, 0);
      // The count and the extensions stay on the page. Only the consequence and
      // what to do about it go behind the button.
      kinds.append(el('div', { className: 'small muted', style: 'margin-top:14px' },
        why(el('span', { textContent: `${total} other file${total === 1 ? '' : 's'} `
          + `${total === 1 ? 'is' : 'are'} of a type Ripple does not open — `
          + h.repo.unknownExt.map(k => `${k.ext} · ${k.files}`).join(', ') }),
          'file types Ripple does not open',
      'Ripple opens SQL files and the file types that usually hold SQL. It did not look inside '
      + 'these at all, so nothing written in them can appear in any answer. If part of your '
      + 'pipeline lives in one of these types, ask whoever set Ripple up to add it.')));
    }
  }

  const c = x(root, 'cat'); c.innerHTML = '';
  // Until the answer arrives this card has a heading and nothing under it. On a
  // repository of a few thousand files the read takes minutes, and for all of
  // them that is an empty box sitting on the screen. It says what it is waiting
  // for instead — and gets replaced, not added to, when the answer comes.
  c.append(el('div', { className: 'small faint', style: 'margin-top:10px',
    textContent: 'Counted once every file has been read.' }));
  api('/api/catalog').then(cat => {
    c.innerHTML = '';
    c.append(el('div', { style: 'display:flex;gap:26px;margin-top:10px' },
      el('div', {}, el('div', { textContent: String(cat.tableCount), style: 'font-size:26px;font-weight:800;font-variant-numeric:tabular-nums' }),
        el('div', { className: 'small faint', textContent: 'tables found' })),
      el('div', {}, el('div', { textContent: String(cat.columnCount), style: 'font-size:26px;font-weight:800;font-variant-numeric:tabular-nums' }),
        el('div', { className: 'small faint', textContent: 'columns found' }))));
    // Tables built with SELECT * whose list Ripple filled in from the table
    // they copy. Said here, so the count above is not read as "N tables with
    // a list, and the SELECT * ones unknown".
    if ((cat.derived || []).length) {
      const n = cat.derived.length;
      const line = el('div', { className: 'small muted', style: 'margin-top:12px;line-height:1.55' });
      line.append(why(
        el('span', { textContent: `${n} of these ${n === 1 ? 'is' : 'are'} built with SELECT * and `
          + `${n === 1 ? 'has its' : 'have their'} column list read from the table ${n === 1 ? 'it copies' : 'they copy'}.` }),
        'column lists read through a SELECT *',
        'A SELECT * publishes every column of the table it reads. Where that table’s columns '
        + 'are written down, the new table’s list is known too, and a scan reads it rather '
        + 'than guessing.'));
      const chips = el('div', { className: 'chips', style: 'margin-top:8px' });
      cat.derived.forEach(d => chips.append(el('span', { className: 'chip mono',
        textContent: `${d.table} ← ${(d.from || []).join(', ')} (${d.columns} column${d.columns === 1 ? '' : 's'})` })));
      line.append(chips);
      c.append(line);
    }
    const g = x(root, 'gaps'); g.innerHTML = '';
    if (cat.gaps.length) {
      // This list used to be headed "tables Ripple could not fully read", which
      // read as a list of dead ends — and while the scan really did stop at
      // them, that was true. It no longer is: a scan follows the column
      // straight through a SELECT * and marks every step past it. Leaving the
      // old heading up would have somebody reading this page as the reason a
      // result was short, when it is not.
      const box = el('div', { className: 'note info' });
      const names = el('div');
      cat.gaps.forEach(gap => names.append(el('div', { style: 'margin-top:6px' },
        el('span', { className: 'mono', textContent: gap.table }), ' — ' + gap.reason)));
      box.append(why(
        el('b', { textContent: `${cat.gaps.length} table${cat.gaps.length === 1 ? '' : 's'} `
          + `here ${cat.gaps.length === 1 ? 'has' : 'have'} no column list written down` }),
        'tables with no column list',
      'These tables take every column at once, so the code never writes down what their '
      + 'columns are called. Your attribute still travels through them and the scan follows '
      + 'it. What Ripple cannot promise is the name it carries on the other side.'));
      box.append(names);
      g.append(box);
    } else if (!cat.tableCount) {
      // "Every table definition was readable" is technically true of nothing at
      // all, and reads as a clean bill of health for a repository that was
      // never read.
      g.append(el('div', { className: 'note info',
        textContent: 'No table definitions were read, so there is no catalogue to check.' }));
    } else if ((h.repo.heldOnline || 0) + (h.repo.pathTooLong || 0)) {
      // The same trap one branch up, one step subtler. "Every table definition
      // was readable" is true of the files that were opened, and sitting in
      // green under a warning that some were not, it reads as a clean bill of
      // health for the repository. It has to say which repository it means.
      g.append(el('div', { className: 'note info', textContent:
        'Every table definition in the files that could be opened was readable. '
        + 'The files above were not opened, so nothing is known about them.' }));
    } else {
      g.append(el('div', { className: 'note good', textContent: 'Every table definition was readable.' }));
    }
  });

  const reread = x(root, 'reindex');
  reread.disabled = S.busy;
  if (S.busy) reread.textContent = 'Reading the repository…';
  reread.onclick = () => run(async () => {
    S.health = await api('/api/reindex', { method: 'POST' });
    render();
  }, `Reading every file in ${h.repo.label}…`);
  x(root, 'next').onclick = () => runScan();
  x(root, 'hint').textContent = S.busy
    // Measured on a repository the size of his: a couple of thousand files and
    // statements six hundred lines long take minutes, not seconds. Saying
    // "a few seconds" and then taking four minutes is how a working program
    // gets reported as hung.
    ? (progressText(S.progress)
       || 'Reading every file. On a repository of a few thousand files this takes '
          + 'a few minutes — the count appears as soon as the first files are read.')
    : repoOk
      ? `The scan will search ${h.repo.label}.`
      : 'Nothing is indexed, so a scan would find nothing.';
  // Every half matters, and this is the ONLY place the button's state is set --
  // it was set twice, further up as well, and the second assignment quietly
  // undid the first. Files can be indexed from a folder that has since been
  // moved or deleted, and offering to scan it would be scanning a memory. And
  // with no published-table list there is nothing to measure an answer against:
  // the engine refuses the scan anyway, and a button that runs and comes back
  // with an error is a worse way of being told than one that says what is
  // missing before it is pressed.
  x(root, 'next').disabled = !repoOk || S.busy || !h.productionSet;
  if (!h.productionSet && !S.busy) {
    x(root, 'next').textContent = 'Add your published tables first';
  }
}

/* What Ripple is reading now — the same facts either way. */
function repoFacts(h) {
  //<online-only>
  const live = h.source === 'github';
  //</online-only>
  const r = el('div', { className: 'card pad lg' });
  r.append(el('span', { className: 'lbl', textContent:
    //<online-only>
    live ? 'GitHub repository' :
    //</online-only>
    'Folder on this machine' }));
  r.append(el('div', { className: 'mono', textContent: h.repo.label,
    style: 'font-size:17px;font-weight:600;color:var(--blued);margin-top:8px;word-break:break-all' }));
  r.append(el('div', { className: 'small faint', textContent: h.repo.path,
    style: 'margin-top:5px;word-break:break-all' }));
  const facts = [
    ['Files indexed', String(h.repo.files)],
    // Only when there are some. "Files indexed 1,770" is the number somebody
    // reads to decide the whole folder was covered, so when it was not, every
    // row saying otherwise has to sit directly underneath it.
    ...(((h.repo.heldOnline || 0) + (h.repo.pathTooLong || 0))
      ? [['Files never opened', String((h.repo.heldOnline || 0) + (h.repo.pathTooLong || 0))]]
      : []),
    ...(h.repo.unreadable ? [['Files that would not parse', String(h.repo.unreadable)]] : []),
    ...(h.repo.inSkippedDirs
      ? [['Files in folders Ripple skips', String(h.repo.inSkippedDirs)]] : []),
    ['Statements understood', String(h.repo.statements)],
    // A folder that was never a git checkout has no branch, and an empty row
    // would read as a missing answer rather than as "there isn't one".
    ...(h.repo.branch ? [['Branch', h.repo.branch]] : []),
    ['SQL read as', h.sqlDialect],
    ['Renames followed', hopsPhrase(h.maxHops)],
    // The setting that decides whether the answer says "production impact" at
    // all, on the screen where somebody decides to press Run -- rather than
    // only on a settings screen they have never opened. Learning after a clean
    // result that Ripple was guessing which tables you publish is learning it
    // one step too late.
    ['Counts as published', h.production || 'not set'],
  ];
  //<online-only>
  if (live) {
    facts.splice(3, 0, ['Commit read', h.github.commit ? h.github.commit.slice(0, 12) : 'unknown']);
    facts.push(['Visibility', h.github.private ? 'private' : 'public']);
  }
  //</online-only>
  const t = el('div', { style: 'margin-top:18px' });
  facts.forEach(([k, val]) => t.append(el('div', { style: 'display:flex;gap:14px;padding:9px 0;border-top:1px solid var(--hair)' },
    el('span', { className: 'small muted', textContent: k, style: 'flex:1' }),
    el('span', { className: 'small' + (k === 'Commit read' ? ' mono' : ''), textContent: val, style: 'font-weight:700' }))));
  r.append(t);
  //<online-only>
  if (live) {
    const off = el('button', { className: 'ghost sm', textContent: 'Disconnect and forget the token', style: 'margin-top:18px' });
    off.onclick = () => run(async () => {
      S.health = await api('/api/repo/disconnect', { method: 'POST' });
      S.repoTab = 'folder'; S.connectMsg = ''; S.gh.token = '';
      render();
    });
    r.append(off);
  }
  //</online-only>
  return r;
}

/* The connect form. Nothing here pretends: the button does one real request. */
//<online-only>
function gitHubForm(h, live) {
  const card = el('div', { className: 'card pad lg' });
  const envToken = h.tokenFrom === 'environment';

  // Built first so typing a repository name can switch it on straight away,
  // without redrawing the form and throwing away the cursor.
  const btn = el('button', { className: 'pri',
    textContent: S.connecting ? 'Reading the repository…' : (live ? 'Read it again' : 'Connect and read it') });
  const syncBtn = () => { btn.disabled = S.connecting || (!S.gh.repo.trim() && !live); };

  const field = (label, key, opts = {}) => {
    const wrap = el('div', { style: 'margin-bottom:18px' });
    wrap.append(el('label', { className: 'lbl', textContent: label, style: 'display:block;margin-bottom:7px' }));
    const inp = el('input', {
      type: opts.secret ? 'password' : 'text',
      value: S.gh[key], placeholder: opts.hint || '',
      className: opts.mono ? 'mono' : '',
      style: 'padding:12px 14px' + (opts.width ? `;width:${opts.width}` : ''),
    });
    if (opts.secret) inp.autocomplete = 'off';
    inp.oninput = () => { S.gh[key] = inp.value; syncBtn(); };
    inp.onkeydown = (e) => { if (e.key === 'Enter') doConnect(); };
    wrap.append(inp);
    if (opts.note) wrap.append(el('div', { className: 'small faint', textContent: opts.note, style: 'margin-top:6px' }));
    return wrap;
  };

  card.append(field('Repository', 'repo', {
    mono: true, hint: 'owner/repository', note: 'Or paste the address straight from GitHub.' }));
  card.append(field('Branch', 'branch', {
    mono: true, hint: 'leave blank for the default', width: '240px' }));

  if (envToken) {
    card.append(el('div', { style: 'margin-bottom:18px' },
      el('span', { className: 'lbl', style: 'display:block;margin-bottom:7px', textContent: 'Access token' }),
      el('div', { className: 'note good' },
        el('b', { textContent: 'A token is already set on this server. ' }),
        'It was set as an environment variable, so it survives restarts. Leave the box below empty to keep using it.')));
    card.append(field('Use a different token instead', 'token', { secret: true, hint: 'optional' }));
  } else {
    card.append(field('Access token', 'token', {
      secret: true, hint: 'ghp_… or github_pat_…',
      note: 'Needed for a private repository. A public one can be read without a token. '
          + 'Read access is all it needs — Ripple never writes.' }));
  }

  syncBtn();
  btn.onclick = () => doConnect();
  const row = el('div', { className: 'foot', style: 'margin-top:4px' }, btn);
  if (S.connecting) row.append(el('span', { className: 'spin' }),
    el('span', { className: 'small muted', textContent: 'Downloading and indexing. A large repository takes a moment.' }));
  card.append(row);

  card.append(el('div', { className: 'note info', style: 'margin-top:20px' },
    why(el('b', { textContent: 'The token is never written to disk, and never sent back to '
        + 'this page.' }),
      'where the token goes',
      'Your token is sent to GitHub and held in memory while the server runs. It is never '
      + 'written to a file, never logged, and never sent back to this page.',
      h.serverless
        ? 'This copy runs on a host that replaces its machine often. Ask whoever runs it to '
          + 'set the token on the server so it lasts.'
        : 'Restart the server and you will need to enter it again.')));
  return card;
}

function doConnect() {
  const repo = S.gh.repo.trim() || (S.health?.github?.slug || '');
  if (!repo || S.connecting) return;
  S.connecting = true; S.connectMsg = ''; render();
  api('/api/repo/connect', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo, branch: S.gh.branch.trim(), token: S.gh.token }),
  }).then(out => {
    S.health = out;
    S.gh.token = '';            // the server has it now; do not keep a copy here
    S.gh.repo = out.github?.slug || repo;
    S.gh.branch = '';
    S.connectMsg = '';
    S.scan = null; S.summary = null;   // anything scanned before was another repo
  }).catch(e => {
    S.connectMsg = e.message;
  }).finally(() => { S.connecting = false; render(); });
}
//</online-only>

/* deeper is set when a trail was cut short by the hop limit and the person
   asked for it to be followed further. It applies to that one scan; the setting
   on the settings screen is left where it was. */
function runScan(deeper) {
  // Zero is a REAL choice here -- "follow it to the end of the code" -- so this
  // asks whether an argument was given rather than whether it is truthy. Read
  // as falsy, pressing "follow these to the end" sent nothing at all and ran the
  // scan again at the same limit, for the same answer: a button that does
  // nothing, on the one screen that is meant to be honest.
  const asked = deeper !== undefined && deeper !== null;
  run(async () => {
    S.scan = await api('/api/scan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        upstream: S.vals.upstream,
        changeKind: S.vals.changeKind || 'unknown',
        ...(asked ? { maxHops: deeper } : {}),
      }),
    });
    S.summary = null; S.openGroup = 'p0'; S.openRow = null; S.graphTab = 0;
    goto(4);
  }, !asked ? 'Searching every file for these names…'
    : deeper ? `Following the same attributes again, up to ${deeper} renames deep…`
    : 'Following the same attributes again, to the end of the code…');
}

// ── step 4 ────────────────────────────────────────────────────────────────
function step4(root) {
  const sc = S.scan;
  if (!sc) { x(root, 'progress').append(el('div', { className: 'note info', textContent: 'No scan yet.' })); return; }
  // Nothing was read, so there is no result to grade. A green "No impact" over
  // an empty folder is a statement about the folder wearing the clothes of a
  // statement about the pipeline.
  const nothingRead = !sc.filesScanned;
  // "I never saw that column" was worded exactly like "that column goes
  // nowhere" — the same green tick, the same empty list, byte for byte. They
  // are opposite answers: one is an answer to the question, the other is the
  // question never having been asked. A typo in an attribute name shipped as
  // "no impact", which is the most convincing wrong answer this tool can give.
  // A scan of a whole table asks a different question, and the screen says
  // which question it answered wherever the two would read differently.
  const wholeScan = !!(sc.stats && sc.stats.wholeTables);
  const [cls, label] = nothingRead ? ['amber', 'Nothing was scanned']
    : sc.lookupFailed ? ['amber', (wholeScan ? 'Table' : 'Column') + ' not found — nothing was checked']
    : (RISK[sc.risk] || RISK.none);
  x(root, 'risk').append(el('span', { className: 'badge ' + cls, textContent: label }));
  // Beside the risk word, never on another screen. "No impact, and I could
  // follow every step of it" and "no impact, and three tables on the way were
  // invisible to me" printed as the same three words — everything below was
  // already counted and then thrown away. Counts, not a percentage: there is no
  // honest denominator for "how much of a trail exists", and a made-up one
  // would put a precise number on a guess.
  // Not shown beside a failed lookup. "Whole trail seen" is true and reads as a
  // reassurance, over a scan that followed no trail at all because the column
  // it was given is not in this repository.
  const cov = sc.coverage;
  if (cov && !nothingRead && !sc.lookupFailed) {
    x(root, 'risk').append(el('span', {
      className: 'badge ' + (cov.complete ? 'green' : 'grey'),
      style: 'margin-left:8px',
      textContent: cov.complete
        ? 'whole trail seen'
        : `${cov.gaps.length} gap${cov.gaps.length === 1 ? '' : 's'} in what Ripple could see` }));
  }
  // The line under the title has to be true of the screen underneath it, and
  // "grouped under the production table" is not true when there is not one.
  x(root, 'sub').textContent = sc.lookupFailed
    ? (wholeScan
      ? 'Ripple never met this table. Check the spelling before reading anything below.'
      : 'Ripple never met these column names. Check the spelling before reading anything below.')
    : sc.groups.length
    ? (wholeScan
      ? 'Every statement that reads the table, and every table built from those, grouped under the production table at risk.'
      : 'Every finding grouped under the production table it puts at risk.')
    : (sc.reached || []).length || (sc.other || []).length
      ? 'Nothing matched your published-table rule. Every table the change does reach is below.'
      : 'What the change touches in this repository, and what could not be read.';

  // What was actually read. Real counts only — the scan has already finished by
  // the time this renders, so there is nothing to animate.
  const done = el('div', { className: 'card pad lg' });
  done.append(el('div', { style: 'display:flex;align-items:center;gap:12px;flex-wrap:wrap' },
    el('span', { className: 'chip mono', textContent: S.health.repo.label }),
    // A folder that was never a git checkout has no branch, and an empty chip
    // sitting there reads as something that failed to load.
    S.health.repo.branch ? el('span', { className: 'chip', textContent: S.health.repo.branch }) : null,
    el('span', { textContent: nothingRead
      ? 'No files were read'
      : sc.stats.filesWithImpact
        ? `Scan complete — ${sc.stats.filesWithImpact} file${sc.stats.filesWithImpact === 1 ? '' : 's'} with impact`
        : 'Scan complete — nothing carries these attributes',
      style: 'margin-left:auto;font-size:13px;font-weight:600;color:var(--blued)' })));
  done.append(el('div', { style: 'display:flex;align-items:baseline;gap:9px;margin-top:18px;flex-wrap:wrap' },
    el('span', { className: 'big', textContent: String(sc.filesScanned) }),
    el('span', { className: 'small muted', textContent: `files read · ${sc.filesMatched} mention the names you confirmed` })));
  // The sentence that qualifies every other sentence on this screen. Ripple read
  // one folder. "No impact" is a fact about that folder and about nothing else —
  // and the single commonest way to be wrong with this tool is to read it as a
  // fact about the warehouse.
  done.append(el('div', { className: 'small muted', style: 'margin-top:10px' },
    why(el('span', { textContent: `Ripple read these ${sc.filesScanned} files and nothing else.` }),
      'what "nothing found" covers',
      'Ripple only read this repository. Something it did not find here could still exist in '
      + 'another repository, in a scheduled query, or in a dashboard built straight on the '
      + 'table.')));
  x(root, 'progress').append(done);

  const st = sc.stats;
  const reached = sc.reached || [], other = sc.other || [];
  // Two rows under two headings, rather than seven cards in one row that wraps
  // six-and-one. They are not the same kind of number: the first row is the
  // answer, the second is how much of the repository the answer covers — and
  // the second one is the one that decides whether the first can be believed.
  const box = x(root, 'stats');
  const statCard = ([l, v, colour, sub]) => el('div', { className: 'stat' },
    el('span', { className: 'lbl', textContent: l }),
    el('div', { className: 'v', textContent: String(v), style: colour ? `color:${colour}` : '' }),
    el('div', { className: 's', textContent: sub }));

  box.append(el('span', { className: 'lbl', style: 'display:block;margin-bottom:10px',
    textContent: 'What the change reaches' }));
  // One grid, not two. The second row used to hold one or two cards in a
  // five-column grid of its own, which stranded them on a line looking like an
  // afterthought — and these are the two most alarming numbers on the screen.
  // Worst first, so that when there are more cards than fit a row it is the
  // mildest one that wraps. The two red ones used to sit in a grid of their own
  // underneath, which stranded the most alarming number on the screen on a line
  // by itself looking like an afterthought.
  const reach = el('div', { className: 'stats' });
  [['Production tables at risk', st.productionTables, st.productionTables ? 'var(--red)' : 'var(--green)', 'On your published-table list'],
   // Kept OUT of "production tables at risk" on purpose. Nothing about these
   // tables' columns changes — the job that fills them stops running — and one
   // number covering two different kinds of impact is a number that means
   // neither. Shown only when there are some.
   ...(st.productionStopsLoading
     ? [['Published tables that stop refreshing', st.productionStopsLoading,
         'var(--red)', 'Their columns do not change — their data stops']] : []),
   // A file delivered to a bucket is not a published table, and folding the two
   // counts together would make both of them mean nothing. Whoever reads that
   // file is outside this repository, which is exactly why it needs saying: no
   // scan of this repository will ever find them.
   ...(st.feedsBroken
     ? [['Deliveries out of the warehouse', st.feedsBroken,
         'var(--red)', 'Files another team reads — tell them']] : []),
   ['Other tables reached', st.tablesReached ?? 0, (st.tablesReached ? 'var(--amber)' : ''), 'The chain ends at these'],
   [st.wholeTables ? 'Tables and attributes impacted' : 'Attributes impacted',
    st.attributesImpacted, '', 'Of those you confirmed'],
   ['Files to change', st.filesWithImpact, '', `Of ${sc.filesScanned} scanned`],
   // "Across every table reached" is load-bearing: the summary counts only the
   // usages feeding a published table, so without it this card and that sentence
   // give two different numbers for the same thing one screen apart.
   ['Breaking usages', st.breakingUsages, st.breakingUsages ? 'var(--amber)' : '', 'Across every table reached'],
  ].forEach(c => reach.append(statCard(c)));
  box.append(reach);

  const uncovered = [
    ['To check by hand', st.couldNotRead, st.couldNotRead ? 'var(--amber)' : '', 'Ripple could not follow these'],
  ];
  // A trail Ripple gave up on is not a trail that ended, and a table it cannot
  // see inside is not a table it has read. Both used to be invisible on this
  // screen, so a result built on either looked exactly like one built on the
  // whole picture.
  if (st.trailsCutShort) {
    uncovered.push(['Trails cut short', st.trailsCutShort, 'var(--red)',
      `Stopped at ${sc.maxHops} renames deep`]);
  }
  if (st.tablesNotVisible) {
    // Some of these are not SELECT * at all — they are a whole table copied or
    // renamed into another. This card used to say SELECT * about all of them,
    // one card above the card that said "copied or renamed", so the screen
    // contradicted itself about the same two tables.
    const anyCopy = (sc.starTables || []).some(t => t.how && !t.known);
    const anyStar = (sc.starTables || []).some(t => !t.how && !t.known);
    uncovered.push(['Tables not fully readable', st.tablesNotVisible, 'var(--amber)',
      anyCopy && anyStar ? 'Copied whole, or SELECT * — no column list'
        : anyCopy ? 'Copied or renamed whole — no column list'
        : 'Built with SELECT * — no column list']);
  }
  // Only ever shown when there are some. A "0 never opened" card would be a
  // reassurance nobody asked for.
  if (st.neverOpened) {
    uncovered.push(['Never opened', st.neverOpened, 'var(--red)', 'Not on this machine, or path too long']);
  }
  if (S.health?.repo?.inSkippedDirs) {
    uncovered.push(['In folders Ripple skips', S.health.repo.inSkippedDirs, 'var(--amber)',
      (S.health.repo.skippedDirNames || []).join(', ')]);
  }
  // A file type Ripple does not open is exactly as unread as a folder it was
  // told to skip. Seen on the rendered screen and nowhere else: the green
  // "Every file was opened and read" note sat DIRECTLY ABOVE the card saying a
  // notebook had never been looked inside. Counting it here puts it in the row
  // and takes that note away, which is the same fix twice.
  const unopenedTypes = (sc.fileTypesUnopened || []).reduce((n, t) => n + t.count, 0);
  if (unopenedTypes) {
    uncovered.push(['Types Ripple does not open', unopenedTypes, 'var(--amber)',
      (sc.fileTypesUnopened || []).map(t => t.ext || 'no extension').join(', ')]);
  }
  box.append(el('span', { className: 'lbl', style: 'display:block;margin:22px 0 10px',
    textContent: 'What this result does not cover' }));
  const gaps3 = el('div', { className: 'stats' });
  uncovered.forEach(c => gaps3.append(statCard(c)));
  box.append(gaps3);
  // Only a reassurance when there was something to be reassured about. "Every
  // file was opened and read" is true of no files at all, and reads as a clean
  // bill of health for a repository that was never there.
  if (!st.couldNotRead && !unopenedTypes && uncovered.length === 1 && !nothingRead) {
    gaps3.append(el('div', { className: 'note good', style: 'grid-column:span 2;align-self:stretch;display:flex;align-items:center' },
      el('div', {}, el('b', { style: 'display:block', textContent: 'Every file was opened and read.' }),
        'Nothing was skipped, and nothing was left for a person to follow by hand.')));
  }

  // Before the findings, not after them: this is the card that says how much of
  // the repository the findings are a statement about.
  renderNeverOpened(box, sc);
  renderTrailGaps(box, sc);

  const groups = x(root, 'groups');
  groups.append(el('span', { className: 'lbl', style: 'display:block;margin-bottom:2px',
    textContent: 'The findings' }));
  // The clean result is only ever offered when there is genuinely nothing:
  // no production table, no other table, and no loose usage anywhere. Anything
  // less than that and a green tick is the tool lying to your face.
  if (nothingRead) {
    groups.append(el('div', { className: 'note bad', style: 'padding:18px 22px' },
      el('b', { style: 'display:block;font-size:15px', textContent: 'No files were read, so nothing was searched' }),
      el('div', { style: 'margin-top:5px', textContent:
        'This is not a result about your pipeline — it is a result about an empty folder. '
        + 'Point Ripple at the folder holding the code on the settings screen, then run the '
        + 'scan again.' })));
  } else if (sc.lookupFailed) {
    // Not the same answer as the green tick below, and it used to print as if
    // it were. "No table is built from them, and no code reads them" is a
    // finished answer about a real column. Ripple never met this name as a
    // column at all, so it has not answered the question — it has failed to
    // ask it, and a typo shipped as "no impact".
    groups.append(el('div', { className: 'note warn', style: 'display:flex;align-items:center;gap:14px;padding:18px 22px' },
      el('span', { textContent: '?', style: 'width:30px;height:30px;border-radius:50%;background:var(--amber);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;flex-shrink:0' }),
      el('div', {}, el('b', { textContent: wholeScan
          ? 'Ripple never met this table, so nothing was checked'
          : 'Ripple never met these column names, so nothing was checked', style: 'display:block' }),
        el('div', { style: 'margin-top:3px', textContent: wholeScan
          ? 'This is not "the change is safe" — it is "the question was not answered". Nothing here reads a table of that name and nothing here builds one. Check the spelling, and check that the table is used in this repository at all.'
          : 'This is not "the change is safe" — it is "the question was not answered". The columns Ripple did read on that table are listed below; if one of them is what you meant, scan again for that name.' }))));
  } else if (!sc.groups.length && !reached.length && !other.length) {
    // "No table is built from them, and no code reads them" is a claim about
    // the WHOLE repository, and it was printed in green directly above a card
    // saying three files could not be read. Those two cannot both be true. Where
    // anything at all went unread the claim is narrowed to what Ripple could
    // read, and the box stops being a green tick — a reassuring sentence may not
    // appear while a gap is known.
    const clear = sc.coverage?.complete;
    const gaps = (sc.coverage?.gaps || []).length;
    groups.append(el('div', { className: 'note ' + (clear ? 'good' : 'info'),
      style: 'display:flex;align-items:center;gap:14px;padding:18px 22px' },
      el('span', { textContent: clear ? '✓' : '·',
        style: 'width:30px;height:30px;border-radius:50%;flex-shrink:0;color:#fff;font-weight:700;'
          + 'display:flex;align-items:center;justify-content:center;'
          + `background:var(${clear ? '--green' : '--blue'})` }),
      why(el('b', { textContent: clear
          ? 'Nothing in this repository uses these attributes'
          : `Nothing Ripple could read uses these attributes — ${gaps} gap${gaps === 1 ? '' : 's'} below` }),
        'what a clean result means',
      clear
        ? 'Nothing here builds a table from these attributes, and nothing here reads them. '
          + 'Worth checking that the names below are the ones you meant.'
        : 'Nothing that Ripple could read uses these attributes. But there are places it could '
          + 'not see into, listed below, so this is not the same as "nothing uses them". Check '
          + 'the names first, then check those gaps.')));
  }
  // With nothing on the production list, the first table the change reaches is
  // the most important thing on the screen, so it opens rather than sitting
  // shut behind a caret like a footnote.
  if (!sc.groups.length && reached.length && S.openGroup === 'p0') S.openGroup = 'r0';
  drawGroups(groups, sc.groups, 'p', 'Production table', '',
             'production table', 'production tables');

  if (reached.length) {
    // These used to be thrown away. A chain that ends at a table nobody has
    // told Ripple is published is not a chain that goes nowhere.
    groups.append(el('div', { className: 'note warn', style: 'margin-top:20px' },
      why(el('b', { textContent: `The change reaches ${reached.length} more table${reached.length === 1 ? '' : 's'}, `
          + `${sc.groups.length ? 'beyond the ones above' : 'none of them on your published list'}` }),
        'why these are not called production',
      'Ripple calls a table published only when its name is on your published-table list. '
      + 'These are not on it, so Ripple cannot tell you whether anyone outside your team reads '
      + 'them. If they are yours, add them on Settings & checks and scan again.')));
    drawGroups(groups, reached, 'r', 'Chain ends here', 'background:var(--amber);color:#fff',
               'table the chain ends at', 'tables the chain ends at');
  }

  if (other.length) {
    const card = el('div', { className: 'card clip', style: 'margin-top:20px' });
    card.append(el('div', { className: 'chead' },
      el('b', { textContent: other.length === 1
        ? '1 more usage that builds no table'
        : `${other.length} more usages that build no table` })));
    const p = el('div', { className: 'pad lg' });
    // "Builds no table" is true of all of these and only tells the whole story
    // about some of them. An EXPORT DATA writes no table either — and Ripple
    // knows exactly where it delivers to, and says so on its own card lower
    // down. Telling somebody here that the destination is "somewhere it cannot
    // see" contradicts that card by two paragraphs.
    const exports = other.filter(r => r.feed).length;
    p.append(why(
      el('span', { className: 'prose', textContent: other.length === 1
        ? 'A real usage, in code that builds no table.'
        : 'Real usages, in code that builds no table.' }),
      'usages that build no table',
      'The attribute is read here, but this code creates no table Ripple can name — it is a '
      + 'plain query, or the destination is set somewhere Ripple cannot see. These are real '
      + 'usages all the same.',
      exports
        ? `${exports === 1 ? 'One of these writes' : `${exports} of these write`} a file out of `
          + 'the warehouse instead. The destination is on the row, and again further down.'
        : null));
    other.forEach((r, ri) => {
      const key = `o${ri}`, ro = S.openRow === key;
      const line = el('div', { style: 'display:flex;gap:10px;align-items:baseline;margin-top:10px;flex-wrap:wrap;cursor:pointer' },
        el('span', { className: 'chip mono', textContent: r.file }),
        el('span', { className: 'badge sm ' + (r.breaking ? 'red' : 'grey'), textContent: r.logic }),
        r.feed
          ? el('span', { className: 'badge sm red', textContent: '→ ' + r.feed })
          : null,
        el('span', { className: 'small muted', textContent: `on ${r.attr}` }));
      line.onclick = () => { S.openRow = ro ? null : key; render(); };
      p.append(line);
      if (ro) p.append(detailFor(r));
    });
    card.append(p);
    groups.append(foldFrom('other-usages', card, { count: other.length }));
  }

  renderStopsLoading(groups, sc);
  renderFeeds(groups, sc);

  const gapBox = x(root, 'gaps');
  gapBox.innerHTML = '';
  gapBox.append(el('span', { className: 'lbl', style: 'display:block;margin:26px 0 2px',
    textContent: 'How to check this result' }));
  renderCoverage(gapBox, sc);
  renderChecks(gapBox, sc);
  renderGaps(gapBox, sc);
  x(root, 'next').onclick = () => goto(5);
}

/* A run of table cards, with a readable number of them drawn.

   Measured on a repository the size of the one this was built for: following a
   key column reaches over two hundred tables, and two hundred identical
   collapsed cards is a page nobody scrolls to the end of — so the tables at the
   bottom of it are, in practice, hidden. Nothing is dropped: the ones with the
   most impacts are drawn (they are sorted that way), and every remaining table
   is named, with its count, in a list underneath. */
const GROUPS_DRAWN = 20;

function drawGroups(box, list, prefix, tag, tagStyle, one, many) {
  list.slice(0, GROUPS_DRAWN).forEach((g, gi) =>
    box.append(groupCard(g, `${prefix}${gi}`, tag, tagStyle)));
  const rest = list.slice(GROUPS_DRAWN);
  if (!rest.length) return;
  const card = el('div', { className: 'card pad lg', style: 'margin-top:16px' });
  card.append(why(
    el('span', { className: 'lbl', textContent:
      `${rest.length} more ${rest.length === 1 ? one : many}` }),
    'why only ' + GROUPS_DRAWN + ' are drawn as cards',
      `Every table is still counted in the analysis. Only the ${GROUPS_DRAWN} with the most `
      + 'impacts get a card of their own; the rest are named here with their counts.'));
  const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
  rest.forEach(g => chips.append(el('span', { className: 'chip mono',
    textContent: `${g.prod} · ${g.rows.length}` })));
  card.append(chips);
  box.append(foldFrom('more-' + prefix, card, { count: rest.length }));
}

/* One production table, or one table a chain ends at. The same rows either
   way -- what differs is what Ripple is able to claim about the table. */
function groupCard(g, key, tag, tagStyle) {
  const card = el('div', { className: 'card clip group' });
  const open = S.openGroup === key;
  const head = el('div', { className: 'ghead' + (open ? ' open' : '') });
  head.append(
    el('span', { className: 'tag', textContent: tag, style: tagStyle }),
    el('div', { className: 'mono', textContent: g.prod, style: 'font-size:15px;font-weight:600' }),
    el('span', { className: 'badge grey', textContent: `${g.rows.length} impact${g.rows.length === 1 ? '' : 's'}` }),
    el('span', { className: 'small muted', textContent: g.note }),
    el('span', { className: 'caret', textContent: '›' }));
  head.onclick = () => { S.openGroup = open ? null : key; S.openRow = null; render(); };
  card.append(head);
  if (!open) return card;
  const hr = el('div', { className: 'rowhead' });
  ['Table it lands in', 'Attribute impacted', 'Alias used', 'What the code does', 'Value', ''].forEach(h => hr.append(el('span', { textContent: h })));
  card.append(hr);
  g.rows.forEach((r, ri) => {
    const rowKey = `${key}-${ri}`, ro = S.openRow === rowKey;
    const row = el('div', { className: 'row' + (ro ? ' open' : '') });
    // Two hops down the chain the column is no longer called what the person
    // typed into the notification, so a row can read "mc" on a scan of three
    // attributes with nothing to say which of them it belongs to. The
    // attribute that was asked about is named whenever it differs.
    const other = (r.roots || []).filter(n => n.toUpperCase() !== (r.attr || '').toUpperCase());
    row.append(
      el('span', { className: 'mono', textContent: r.inter, style: 'font-weight:600;font-size:13px;min-width:0;overflow-wrap:break-word' }),
      el('span', { style: 'min-width:0' },
        // The row is about the table itself. There is no column and no alias
        // to name, and a blank in either cell reads as a value that failed to
        // load, so each says what it is.
        r.whole
          ? el('span', { className: 'chip whole', textContent: 'whole table' })
          : el('span', { className: 'mono', textContent: r.attr,
              style: 'font-size:13px;font-weight:600;color:var(--blued);overflow-wrap:break-word' }),
        other.length && !r.whole
          ? el('span', { className: 'small faint', style: 'display:block;margin-top:3px',
              textContent: 'from ' + other.join(', ') })
          : null),
      el('span', {}, r.whole
        ? el('span', { className: 'small faint', textContent: 'every column' })
        : el('span', { className: 'chip alias', textContent: r.alias })),
      // The second badge goes inside the same cell rather than adding a column,
      // so a row that has it lines up with the rows that do not.
      el('span', {}, el('span', { className: 'badge sm ' + (r.breaking ? 'red' : 'grey'), textContent: r.logic }),
        r.certain === false
          ? el('span', { className: 'badge sm grey', style: 'margin-left:6px',
              textContent: 'table not stated' })
          : null,
        // The chain got here through a table whose column list is not written
        // down. The row is real; what is inferred is that the column still
        // travels under this name on the far side of the star.
        r.inferredHops
          ? el('span', { className: 'badge sm amber', style: 'margin-left:6px',
              textContent: r.viaStar ? 'column list not visible' : 'inferred' })
          : null,
        // A SELECT * whose column list is written down after all. Read, not
        // inferred, and the badge says so where the amber one would have been.
        r.starKnown
          ? el('span', { className: 'badge sm grey', style: 'margin-left:6px',
              textContent: 'SELECT * — column list known' })
          : null,
        // The line holds a quoted string, not the statement this row describes.
        r.builtAsText
          ? el('span', { className: 'badge sm amber', style: 'margin-left:6px',
              textContent: 'run as text' })
          : null),
      el('span', {}, el('span', { className: 'badge sm ' + (r.whole ? 'grey' : r.mode === 'Direct pull' ? 'blue' : 'violet'), textContent: r.mode })),
      el('span', { className: 'caret', textContent: '›' }));
    row.onclick = () => { S.openRow = ro ? null : rowKey; render(); };
    card.append(row);
    if (ro) card.append(detailFor(r));
  });
  return card;
}

/* Attribute by attribute: what was looked for and what came back.
   "It said no impact and I have no way to check" is answered here rather than
   by asking anyone to trust the headline. An attribute that is not written
   down anywhere in the repository looks nothing like one that is used in nine
   files, and both used to end up behind the same green tick. */
/* How much of this trail Ripple could see, in the counts it already had.

   Every number here was being worked out and then thrown away. "No impact" was
   computed from one thing only — whether any finding was breaking — so a scan
   that followed every step of the chain and a scan with three invisible tables
   on it printed the same three words. This is not a score and not a percentage:
   there is no honest denominator for "how much of a trail exists", and putting
   a precise-looking number on a guess is the one thing this tool may not do. */
function renderCoverage(box, sc) {
  const cov = sc.coverage;
  // Nothing was followed, so there is no coverage to report — and "every step
  // of every trail was read" over a trail that does not exist is the same
  // reassuring nonsense in longer words.
  if (!cov || sc.lookupFailed) return;
  const card = el('div', { className: 'card pad lg', style: 'margin-top:12px' });
  if (cov.complete) {
    card.append(why(
      el('b', { textContent: 'Every step of every trail above was read out of the SQL' }),
      'what "every step was read" means',
      'Ripple read the real SQL for every step of every trail above. Nothing was skipped, '
      + 'guessed at, or cut short. That is true of the files it read, and of nothing outside '
      + 'them.'));
    box.append(card);
    return;
  }
  const list = el('div', { style: 'margin-top:10px' });
  cov.gaps.forEach(g => list.append(el('div', {
    className: 'small', style: 'margin-top:6px;line-height:1.55' },
    el('b', { textContent: String(g.count) + ' ' }),
    g.what)));
  // No count in this heading. It would be counting KINDS of gap, sitting above
  // lines that count files and findings, so "1 place ... 3 files" read as two
  // numbers for one thing. The badge beside the risk word carries the count.
  card.append(why(
    el('span', { className: 'lbl', textContent: 'Where Ripple could not see through' }),
    'why these are counts and not a score',
      'Each of these is somewhere Ripple could not see through. They are given as counts, not '
      + 'as a percentage: nobody knows how big the whole picture is, so a percentage would be '
      + 'made up.'));
  card.append(list);
  box.append(card);
}

function renderChecks(box, sc) {
  const rows = sc.attributes || [];
  if (!rows.length) return;
  const card = el('div', { className: 'card clip', style: 'margin-top:20px' });
  card.append(el('div', { className: 'chead' },
    why(el('b', { textContent: 'Every attribute you asked about' }),
      'how to check a scan',
      'If a result looks too quiet, start here. An attribute that is not written down anywhere '
      + 'in your code is the usual reason a scan comes back clean.')));
  const p = el('div', { className: 'pad lg' });
  rows.forEach(a => {
    const used = a.found > 0;
    // A name Ripple never met as a column on ANY table is not a column with no
    // impact — it is a question that never got asked. Said first, and in amber,
    // because the two used to be the same grey line.
    const badge = a.reachesProduction
      ? ['red', 'reaches a published table']
      : used
        ? ['amber', `used in ${a.files} file${a.files === 1 ? '' : 's'}`]
        : a.lookupFailed
          ? ['amber', 'Ripple never saw a column of this name']
          : a.mentionedIn
          ? ['grey', `named in ${a.mentionedIn} file${a.mentionedIn === 1 ? '' : 's'}, never read from`]
          : ['grey', 'this name is not in the repository at all'];
    p.append(el('div', { style: 'display:flex;gap:10px;align-items:baseline;margin-top:10px;flex-wrap:wrap' },
      // "table.column" for a column; a whole table is not a column of itself.
      el('span', { className: 'chip mono', textContent: a.whole ? `${a.table} · whole table` : `${a.table}.${a.attr}` }),
      el('span', { className: 'badge sm ' + badge[0], textContent: badge[1] }),
      (a.endsAt || []).length
        ? el('span', { className: 'small muted', textContent: 'ends at ' + a.endsAt.join(', ') })
        : null,
      // Kept apart from "ends at" on purpose. They read the same and mean
      // opposite things: one is where the code ran out, the other is where
      // Ripple stopped looking.
      (a.cutShortAt || []).length
        ? el('span', { className: 'badge sm red',
            textContent: 'still going at ' + a.cutShortAt.join(', ') })
        : null));
    // The instant self-correction. Printing back the columns Ripple DID read on
    // the table turns a silent wrong answer into a spelling mistake somebody
    // spots in two seconds. An empty list is a different answer again and says
    // so: it means Ripple has no column list for this table at all, so "I never
    // saw it" is not the same as "it is not there".
    if (a.lookupFailed) {
      // The columns Ripple DID read stay on the page: that list is what turns a
      // silent wrong answer into a spelling mistake somebody spots in seconds.
      const cols = a.tableColumns || [];
      const box = el('div', { className: 'note warn', style: 'margin:8px 0 0 4px' });
      box.append(why(
        el('b', { textContent: `Nothing was checked for ${a.attr}.` }),
        'nothing was checked for ' + a.attr,
      cols.length
        ? `Ripple read ${a.table} and never found a column called ${a.attr} — on it, or on `
          + 'anything else here. The columns it did find are listed below. If one of those is '
          + 'the one you meant, scan again for that name.'
        : `Ripple never found a column called ${a.attr} anywhere here, and nothing in your code `
          + `writes down what the columns of ${a.table} are. So this is not "that column is `
          + 'safe" — it is "Ripple could not check". Check the spelling, and check that this '
          + 'table is built in this repository at all.'));
      if (cols.length) {
        box.append(el('div', { className: 'small', style: 'margin-top:8px;line-height:1.55' },
          `What Ripple did read on ${a.table}: `, el('span', { className: 'mono', textContent: cols.join(', ') })));
      }
      p.append(box);
    }
    if ((a.cutShortAt || []).length) {
      p.append(el('div', { className: 'small muted', style: 'margin:6px 0 0 4px' },
        why(el('span', { textContent: `Ripple stopped at ${sc.maxHops} renames — the trail had `
          + 'not finished.' }),
          'a trail that was cut short',
      'Whether it ends at a published table is not something this scan can tell you. Use the '
      + 'button above to follow it further.')));
    }
    if ((a.notVisible || []).length) {
      // Both counts stay on the page. Only the "why" moved.
      p.append(el('div', { className: 'small muted', style: 'margin:6px 0 0 4px;line-height:1.55',
        textContent: `Goes through ${a.notVisible.join(', ')} — ${a.inferred} finding`
          + `${a.inferred === 1 ? '' : 's'} past that point ${a.inferred === 1 ? 'is' : 'are'} `
          + 'worked out, not read.' }));
    }
    // How widely the name is used as a name. A scan for a column half the
    // warehouse shares looks identical on screen to a scan for one only this
    // table has, and the two are not remotely the same answer: the first
    // produces a long list because the name is everywhere, the second because
    // something is badly wrong. Only said when the name really is widespread —
    // "this name is in 1 of 60 tables" is a fact nobody needs.
    // Two conditions, and both matter. A big share says the name is common;
    // a real count says the repository is big enough for that to mean anything.
    // "3 of the 3 tables" is a fact about a folder with three files in it, and
    // printing it there teaches somebody to skip the line in the repository
    // where it is the whole point.
    if (a.nameInTables >= 8 && a.tablesRead) {
      const share = a.nameInTables / a.tablesRead;
      if (share >= 0.25) {
        p.append(el('div', { className: 'small muted', style: 'margin:6px 0 0 4px' },
          why(el('span', { textContent: `"${a.attr}" is a column name in ${a.nameInTables} of the `
            + `${a.tablesRead} tables Ripple could read.` }),
            'a column name that is everywhere',
      `Plenty of tables use this column name. The findings only follow it out of ${a.table}, so `
      + 'a long list here means the name is common — not that the change is bigger.')));
      }
    }
    if (a.uncertain) {
      p.append(el('div', { className: 'small muted', style: 'margin:6px 0 0 4px' },
        why(el('span', { textContent: `${a.uncertain} of these `
          + `${a.uncertain === 1 ? 'is' : 'are'} marked "table not stated".` }),
          'rows where the table is inferred',
      `On these lines the SQL does not say which table the ${a.attr} came from, and more than `
      + 'one table in the same statement has a column of that name. The usage is real; which '
      + 'table it belongs to is Ripple\u2019s best guess.')));
    }
  });
  card.append(p);
  // Open when it is short, or when it holds a correction somebody has to see:
  // a name Ripple never met, or a trail it stopped following.
  const mustSee = rows.some(a => a.lookupFailed || (a.cutShortAt || []).length);
  box.append(foldFrom('every-attribute', card, {
    count: rows.length, open: mustSee || rows.length <= 3,
    badge: rows.some(a => a.reachesProduction) ? 'red' : rows.some(a => a.lookupFailed) ? 'amber' : 'grey' }));
}

/* The address of a finding in the connected repository, or nothing at all.
   Points at the first line that actually matched, not the top of the file. */
//<online-only>
function fileUrl(r) {
  const tpl = S.scan?.repo?.urlTemplate;
  if (!tpl || !r.file) return '';
  const hit = (r.lines || []).find(l => l.hit) || (r.lines || [])[0];
  return tpl.replace('{path}', r.file).replace('{line}', String(hit?.n ?? 1));
}
//</online-only>

function detailFor(r) {
  const d = el('div', { className: 'detail' });
  d.append(el('div', { className: 'note ' + (r.noLocalFix ? 'bad' : r.breaking ? 'warn' : 'info') },
    el('b', { textContent: r.noLocalFix ? 'No local fix — the upstream team must supply a replacement. ' : r.breaking ? 'This breaks. ' : 'Changes, but does not break. ' }),
    r.impact));
  // The usage is on that line and it is real. What is inferred is which table
  // the column came from, and in a warehouse where the same key columns are in
  // nearly every table that is worth stating rather than glossing.
  if (r.certain === false) {
    d.append(el('div', { className: 'note info', style: 'margin-top:10px' },
      el('b', { textContent: 'The table is inferred here. ' }),
      r.whole
        ? `Whether this statement reads ${r.from} is worked out, not read: it names a family `
          + 'of dated tables by wildcard, or a shard the file does not pin to a date, and '
          + `${r.from} falls inside that. Worth a look at the code below before acting on it.`
        : `This statement reads more than one table with a column called ${r.attr}, and the SQL `
          + `does not say which one this is. Ripple has counted it as ${r.from}'s. Worth a look at `
          + 'the code below before acting on it.'));
  }
  // How much of the path to this row was read and how much was worked out. A
  // row two hops past a SELECT * is exactly as real as the code below it, and
  // exactly as uncertain about what the column is called by the time it lands.
  // A SELECT * whose column list is written down after all: the table it
  // copies has its columns listed, so this hop was read rather than guessed.
  if (r.viaStar && r.starKnown) {
    d.append(el('div', { className: 'note info', style: 'margin-top:10px' },
      el('b', { textContent: 'This step is a SELECT *, and the column list is known. ' }),
      `The statement takes every column of ${r.from}, whose columns are written down in the `
      + `code, so Ripple read the list rather than guessing — ${r.attr} is on it. Nothing past `
      + 'this point is inferred.'));
  }
  if (r.inferredHops) {
    d.append(el('div', { className: 'note warn', style: 'margin-top:10px' },
      el('b', { textContent: r.viaStar
        ? 'This step is a SELECT *. '
        : `${r.inferredHops} step${r.inferredHops === 1 ? '' : 's'} on the way here could not be read. ` }),
      r.viaStar
        ? `The statement takes every column, so ${r.attr} is carried into ${r.inter} without `
          + `ever being named. The hop is real — that is what ${r.copiedBy || 'SELECT *'} does — `
          + 'but Ripple cannot read the column list of the table it builds, so anything past '
          + 'this point is worked out rather than read.'
        : `A table earlier in this chain takes every column at once, so its column list is not `
          + `in the code. This row is a real usage on a real line; what Ripple cannot promise is `
          + `that ${r.attr} is still the name the column carries by the time it gets here.`));
  }
  // The statement is inside quotes on the line below. Said here as well as on
  // the card, because the code shown underneath is a string and looks nothing
  // like the CREATE this row describes — and a row somebody cannot verify on
  // the line it points at is a row they dismiss.
  if (r.builtAsText) {
    d.append(el('div', { className: 'note warn', style: 'margin-top:10px' },
      el('b', { textContent: `Written as text and run — ${r.builtAsText}. ` }),
      'The line below holds this statement as a quoted string, so the code shown is the '
      + 'string rather than the statement. Ripple read what is inside the quotes and it is '
      + 'complete SQL, which is why this row exists. If anything is added to that text when '
      + 'the job runs, this scan has not seen it.'));
  }
  const code = el('div', { className: 'code' });
  const head = el('div', { className: 'f' },
    el('span', { className: 'name', textContent: r.file }),
    el('span', { className: 'lang', textContent: r.lang }));
  // Only offered when Ripple genuinely knows the address of this code. On a
  // local folder there is nothing to link to, so no link is shown.
  //<online-only>
  const href = fileUrl(r);
  if (href) {
    head.append(el('a', { href, textContent: 'Open in GitHub ↗', target: '_blank', rel: 'noopener' }));
  }
  //</online-only>
  code.append(head);
  const body = el('div', { className: 'body' });
  (r.lines || []).forEach(ln => {
    const line = el('div', { className: 'ln' + (ln.hit ? ' hit' : '') },
      el('span', { className: 'n', textContent: String(ln.n) }),
      el('span', { className: 't', textContent: ln.t }));
    // why this line matched, sitting on the line itself rather than under it
    if (ln.hit) line.append(el('span', { className: 'why', textContent: ln.hit }));
    body.append(line);
  });
  code.append(body);
  d.append(code);
  return d;
}

/* Files that were never opened at all.

   Not the same thing as a file that was read and not understood, and much
   worse. A file Ripple could not parse is on the "check by hand" list and
   somebody goes and looks at it. A file that was never opened leaves no trace
   anywhere: the finding list is shorter, the tick is green, and nothing on the
   screen is false — it is just answering a question about half a repository.

   So this says the number, says why, and says the one thing that fixes it. */
function neverOpenedNote(heldOnline, tooLong) {
  const total = (heldOnline || 0) + (tooLong || 0);
  if (!total) return el('span', { className: 'hide' });
  // Every count and every reason stays on the page. Only "why it happened" and
  // "how to fix it" move behind the button — this is the one card that decides
  // whether the numbers above it can be believed at all.
  const note = el('div', { className: 'note warn', style: 'margin-top:12px' });
  const reasons = [
    heldOnline ? `${heldOnline} held online-only by OneDrive` : null,
    tooLong ? `${tooLong} with a path too long for Windows` : null,
  ].filter(Boolean);
  note.append(why(
    el('b', { style: 'font-size:14px',
      textContent: `${total} file${total === 1 ? '' : 's'} here ${total === 1 ? 'was' : 'were'} `
        + 'never opened — ' + reasons.join(', ') }),
    'files that were never opened',
      'Nothing in these files was read, so nothing in them can appear in this answer.',
      heldOnline
        ? 'OneDrive is keeping them in the cloud rather than on this machine. To fix it: '
          + 'right-click the repository folder in File Explorer, choose "Always keep on this '
          + 'device", wait for OneDrive to finish, then read the repository again.'
        : null,
      tooLong
        ? 'Windows cannot open a file whose path is this long. To fix it: move the repository '
          + 'nearer the top of the drive — C:\\repo rather than a deep folder inside '
          + 'Documents — then read it again.'
        : null));
  return note;
}

/* Files that were never opened. Drawn directly under the counts rather than at
   the bottom of the page, because it is the one card that decides whether every
   number above it can be believed — and the bottom of a long page is where a
   caveat goes to be missed. */
function renderNeverOpened(box, sc) {
  if (sc.heldOnline?.length || sc.pathTooLong?.length) {
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px;border-color:var(--amberln)' });
    card.append(neverOpenedNote(sc.heldOnline?.length || 0, sc.pathTooLong?.length || 0));
    const names = [...(sc.heldOnline || []), ...(sc.pathTooLong || [])];
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:12px' });
    names.slice(0, 300).forEach(f => chips.append(el('span', { className: 'chip mono', textContent: f })));
    card.append(chips);
    if (names.length > 300) {
      card.append(el('div', { className: 'small muted', style: 'margin-top:8px',
        textContent: `and ${names.length - 300} more, not listed here to keep this page readable.` }));
    }
    box.append(foldFrom('never-opened', card, { count: names.length, badge: 'red', tone: 'red' }));
  }
  // A whole folder of code walked past because of what it is called. In most
  // repositories "build" and "target" hold generated output; in a few they hold
  // the pipeline, and then this is a scan of half a repository with a green
  // tick on it.
  // Only when the scan itself did not report them. The scan's own card lists the
  // file names and the folders; this one has the same count and no names, and
  // the two sat ten cards apart on the same screen saying the same thing about
  // the same 310 files — with the stat card above making it three times.
  const skipped = sc.skippedInFolders?.length ? 0 : (S.health?.repo?.inSkippedDirs || 0);
  if (skipped) {
    box.append(el('div', { className: 'note warn', style: 'margin-top:16px' },
      why(el('b', { style: 'font-size:14px',
          textContent: `${skipped} file${skipped === 1 ? '' : 's'} Ripple can read `
            + `${skipped === 1 ? 'was' : 'were'} skipped — in `
            + (S.health.repo.skippedDirNames || []).join(', ') }),
        'files skipped for the folder they are in',
      'Folders with these names usually hold generated copies of code, so Ripple walks past '
      + 'them. If your real pipeline lives in one, nothing in it was read and nothing in it can '
      + 'appear in this answer.')));
  }
}

/* Three ways a trail can be shorter than the truth, all of them invisible until
   now, and all of them producing a calm answer over less than the whole picture.

   These are drawn on the RESULT, beside the findings they qualify. Two of them
   were already known somewhere else in the app — the repository screen has
   listed the tables built with SELECT * for months — and a warning on another
   screen is a warning nobody reads while they are deciding whether to worry. */
function renderTrailGaps(box, sc) {
  // 1. The hop limit stopped the walk. This is a setting, and until now it was
  //    reported as a fact: "the chain ends at t4 and does not reach production".
  if (sc.cutShort?.length) {
    const deeper = Math.min((sc.maxHops || 4) * 2, 25);
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px;border-color:var(--redln)' });
    card.append(why(
      el('b', { style: 'font-size:14px', textContent:
        `${sc.cutShort.length} trail${sc.cutShort.length === 1 ? '' : 's'} `
        + 'stopped because of a setting, not because the code ran out' }),
      'trails cut short',
      `Ripple follows a column through ${sc.maxHops} renames and then stops. `
      + `${sc.cutShort.length === 1 ? 'This one had' : 'These had'} not finished. Anything past `
      + 'that point was never looked at, so this result cannot tell you whether they reach a '
      + 'published table.'));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:12px' });
    sc.cutShort.forEach(c => chips.append(el('span', { className: 'chip mono',
      textContent: `${c.table} · ${c.attr}` })));
    card.append(chips);
    // The button stays visible whether or not the list is open: it acts on the
    // list, and a button hidden inside a folded list is a button nobody presses.
    let after = null;
    if (sc.maxHops) {
      // To the END, not twice as far. Doubling was a button that could be
      // pressed and pressed and never finish: measured on a 36-hop chain, ten
      // renames cut the trail short, twenty cut it short, and twenty-five --
      // the deepest this ever offered -- cut it short as well, for the same
      // empty answer each time. There is no number worth offering, so it offers
      // the only thing that answers the question.
      const again = el('button', { className: 'ghost',
        textContent: 'Follow these to the end of the code' });
      again.onclick = () => runScan(0);
      after = why(again, 'what following them to the end costs',
      'This runs the scan again on code Ripple has already read. No file is opened a second '
      + 'time, and nothing on the settings screen changes.');
    }
    box.append(foldFrom('cut-short', card, { count: sc.cutShort.length, badge: 'red', tone: 'red', after }));
  }

  // 2. A table built with SELECT * carries every column and names none of them.
  //    Only the ones whose list really is nowhere. A star over a table whose
  //    columns are written down was READ, and gets its own calm card below.
  const unknownStars = (sc.starTables || []).filter(s => !s.known);
  const knownStars = (sc.starTables || []).filter(s => s.known);
  if (unknownStars.length) {
    const n = unknownStars.length;
    // Some of these are not SELECT * at all — they are a staging table promoted
    // into a published one with COPY, CLONE, LIKE or RENAME. Ripple follows them
    // the same way, because they do the same thing, but the card has to name the
    // word the file actually uses or it describes a statement that is not there.
    const copies = unknownStars.filter(s => s.how);
    // Not a star in the file either — a placeholder where the column list goes,
    // filled in by the job at run time. Ripple used to read it as a column
    // called "cols" and report the published table as having exactly that one.
    const holes = unknownStars.filter(s => s.filledIn);
    const stars = unknownStars.length - copies.length - holes.length;
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px;border-color:var(--amberln)' });
    card.append(why(
      el('b', { style: 'font-size:14px', textContent:
        `${n} table${n === 1 ? '' : 's'} the column passes through ${n === 1 ? 'has' : 'have'} no column list to read` }),
      'tables with no column list on the trail',
      // "Either way" only makes sense when there ARE two ways. On a scan with
      // one kind it referred back to nothing.
      (copies.length && stars
        ? 'Some of these take every column at once with a SELECT *; the rest are a whole table '
          + 'copied or renamed into another. Either way, the code never writes down what their '
          + 'columns are called. Your attribute '
        : copies.length
        ? 'These are a whole table copied or renamed into another, so the code never writes '
          + 'down what their columns are called. Your attribute '
        : 'These take every column at once with a SELECT *, so the code never writes down what '
          + 'their columns are called. Your attribute ')
      + 'really does travel through — what Ripple cannot promise is the name it carries on the '
      + 'other side.',
      holes.length
        ? 'Some of these do not say SELECT * at all. The file leaves a gap where the column '
          + 'list goes and the job fills it in when it runs, so the list is never in the file '
          + 'to read.'
        : null));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:12px' });
    // The chip says WHY the list is not there, so nobody reads this card as
    // Ripple having failed to read a file: the table it copies has no written
    // column list either — or has one, and the column asked about is not on it.
    unknownStars.forEach(s => chips.append(el('span', { className: 'chip mono',
      textContent: s.how
        ? `${s.table} — ${s.how} of ${s.from}`
        : s.filledIn
        ? `${s.table} — column list filled in at run time, from ${s.from}`
        : (s.listedWithout || []).length
        ? `${s.table} — from ${s.from}, whose written column list has no ${s.listedWithout.join(', ')} — followed anyway`
        : `${s.table} — from ${s.from}, whose own column list is not written down here` })));
    card.append(chips);
    box.append(foldFrom('star-tables', card, { count: n, badge: 'amber', tone: 'amber' }));
  }

  // 2a. A SELECT * from a table whose columns ARE written down. The built
  //     table's list was filled in from there, so the hop was read, not
  //     inferred. Said calmly, apart from the ones above. Measured on a real
  //     file: `select distinct a.*` from a stage table built with a full
  //     projection two files earlier was listed among the tables Ripple could
  //     not see inside, and read as Ripple failing to read a file.
  if (knownStars.length) {
    const n = knownStars.length;
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px' });
    card.append(why(
      el('span', { className: 'lbl', textContent:
        `${n} table${n === 1 ? '' : 's'} built with SELECT * ${n === 1 ? 'has' : 'have'} a column list Ripple could read` }),
      'SELECT * tables whose column list is known',
      'These take every column of a table whose columns are written down in the code — a '
      + 'CREATE TABLE with the columns listed, or a query that names them — so Ripple read the '
      + 'list from there instead of guessing. Your attribute is on it. Nothing past these '
      + 'tables is inferred.'));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
    knownStars.forEach(s => chips.append(el('span', { className: 'chip mono',
      textContent: `${s.table} — every column of ${s.from}`
        + (s.columns ? ` (${s.columns} column${s.columns === 1 ? '' : 's'}`
          + (s.listedIn ? `, listed in ${s.listedIn}` : '') + ')' : '') })));
    card.append(chips);
    box.append(foldFrom('star-tables-known', card, { count: n }));
  }

  // 3. One name, more than one table, and nothing in the SQL to tell them apart.
  if (sc.mergedNames?.length) {
    const n = sc.mergedNames.length;
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px' });
    card.append(why(
      el('span', { className: 'lbl', textContent:
        `${n} table name${n === 1 ? '' : 's'} here may stand for more than one table` }),
      'one name, more than one table',
      'Two different tables here share a name. Ripple followed both, so nothing is missed — but '
      + 'a finding under this name could be about either one. Open the file to check before '
      + 'you act on it.',
      sc.mergedNames.some(m => m.reason === 'capitals')
        ? 'BigQuery treats capital letters as significant, so two names that differ only in '
          + 'case really are two different tables there.'
        : null));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
    sc.mergedNames.forEach(m => chips.append(el('span', { className: 'chip mono',
      textContent: m.reason === 'capitals'
        ? `${m.spellings.join('  vs  ')} — same name, different capitals`
        : `${m.table} — in ${m.datasets.join(', ')}` })));
    card.append(chips);
    box.append(foldFrom('merged-names', card, { count: n }));
  }

  // 4. The SQL named a family of date-sharded tables, not the one being scanned.
  //    This has to sit here, beside the findings it qualifies. Ripple used to
  //    match the name literally, asterisk and all, so a scan of a real shard
  //    matched nothing and printed a clean "no impact" — on a warehouse where
  //    date sharding is how half the source tables are read.
  if (sc.wildcardNames?.length) {
    const n = sc.wildcardNames.length;
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px' });
    card.append(why(
      el('span', { className: 'lbl', textContent:
        `${n} table${n === 1 ? '' : 's'} here ${n === 1 ? 'is' : 'are'} read through a wildcard, not by name` }),
      'tables read through a wildcard',
      'The query asks for a whole family of dated tables at once instead of naming one. The '
      + 'table you scanned is inside that family, so these usages are real — but the same '
      + 'query reads the others too, so a fix has to cover all of them.'));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
    sc.wildcardNames.forEach(w => chips.append(el('span', { className: 'chip mono',
      textContent: `${w.table} — matched by ${w.patterns.join(', ')}` })));
    card.append(chips);
    // The family name as a person says it, without the separator BigQuery
    // requires. BigQuery matches nothing here; Ripple matches it anyway so
    // that typing the name you say out loud cannot produce a clean "no
    // impact" — and then says out loud that it is a guess about what you
    // meant, because it used to ship as certain.
    const loose = (sc.wildcardNames || []).filter(w => (w.shorthand || []).length);
    if (loose.length) {
      card.append(el('div', { className: 'note warn', style: 'margin-top:12px' },
        why(el('b', { textContent: 'Some of these are the family name, not a shard — '
            + loose.map(w => `${w.table} vs ${w.shorthand.join(', ')}`).join('; ') }),
          'the family name, not a shard',
      'You scanned the family name rather than one dated table. A real query cannot read a '
      + 'table by that exact name, so Ripple matched the whole family instead — which is a '
      + 'guess about what you meant. Every row from it is marked "table not stated". To be '
      + 'exact, scan for the full name of one table.')));
    }
    box.append(foldFrom('wildcard-names', card, { count: n }));
  }

  // 4a. One table, two files that build it from scratch. Only one of them can
  //     be the definition that runs, and nothing in the files says which. The
  //     measured case: the only finding came from a stale copy under archive/,
  //     presented as certainly as any live one, while the live definition sat
  //     under "mentions only".
  if (sc.twoDefinitions?.length) {
    const n = sc.twoDefinitions.length;
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px' });
    card.append(why(
      el('span', { className: 'lbl', textContent:
        `${n} table${n === 1 ? '' : 's'} here ${n === 1 ? 'is' : 'are'} built from scratch in more than one file` }),
      'a table built in two files',
      'Two files each build this table from scratch, so only one of them can be the one that '
      + 'really runs — and the code does not say which. Ripple followed both. Check what your '
      + 'scheduler actually runs before acting on a finding from one of them.'));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
    sc.twoDefinitions.forEach(t => chips.append(el('span', { className: 'chip mono',
      textContent: `${t.table} — ${t.files.join('  and  ')}` })));
    card.append(chips);
    box.append(foldFrom('two-definitions', card, { count: n }));
  }

  // 4b. Code files Ripple would have read, sitting in a folder it skips. The
  //     count used to reach the repository screen and nothing else, so a scan
  //     of a dbt project — whose target/ folder holds the SQL that actually
  //     runs — came back clean with the reason on a screen nobody looked at.
  if (sc.skippedInFolders?.length) {
    const n = sc.skippedInFolders.length;
    const where = (sc.skippedFolderNames || []).join(', ');
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px;border-color:var(--amberln)' });
    card.append(why(
      el('b', { style: 'font-size:14px', textContent:
        `${n} code file${n === 1 ? '' : 's'} ${n === 1 ? 'was' : 'were'} not read — in ${where}` }),
      'code in a skipped folder',
      `Folders called ${where} usually hold generated copies of code, so Ripple walks past `
      + 'them. Nothing in there was read. If your pipeline really runs from one of them — '
      + "dbt's target folder does — change the skip list on Settings & checks and scan again."));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:12px' });
    sc.skippedInFolders.slice(0, 200).forEach(f => chips.append(
      el('span', { className: 'chip mono', textContent: f })));
    card.append(chips);
    if (n > 200) {
      card.append(el('div', { className: 'small muted', style: 'margin-top:8px',
        textContent: `Showing the first 200 of ${n}.` }));
    }
    box.append(foldFrom('skipped-folders', card, { count: n, badge: 'amber', tone: 'amber' }));
  }

  // 4c. File types Ripple does not open at all. The repository screen has always
  //     listed these; the ANSWER never did. Measured: the middle hop of a chain
  //     sat in a .ipynb, and the scan printed "the name appears, but no lineage
  //     to a production table" with nothing beside it saying a file had been
  //     passed over. A caveat may never live on a different screen from the
  //     answer it qualifies.
  if (sc.fileTypesUnopened?.length) {
    const total = sc.fileTypesUnopened.reduce((n, t) => n + t.count, 0);
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px;border-color:var(--amberln)' });
    card.append(why(
      el('b', { style: 'font-size:14px', textContent:
        `${total} file${total === 1 ? '' : 's'} ${total === 1 ? 'is' : 'are'} of a type Ripple does not open` }),
      'file types not opened by this scan',
      'Ripple opens SQL files and the file types that usually hold SQL. It did not look inside '
      + 'these at all. If part of your chain sits in one of them, the answer stops there. '
      + 'Notebooks and Terraform files are the usual ones to check.'));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:12px' });
    sc.fileTypesUnopened.slice(0, 40).forEach(t => chips.append(
      el('span', { className: 'chip mono', textContent: `${t.ext || 'no extension'} — ${t.count}` })));
    card.append(chips);
    box.append(foldFrom('file-types', card, { count: total, badge: 'amber', tone: 'amber' }));
  }

  // 5. The file builds a table but never writes its name. A dbt model is a bare
  //    SELECT — dbt names the table after the file when it runs it. Ripple
  //    follows the same rule, because without it a dbt repository produced no
  //    lineage at all: every chain came back empty and the answer was a clean
  //    "no impact". Saying so here matters — anybody who opens the file to check
  //    will not find the table name written in it.
  if (sc.namedByFile?.length) {
    const n = sc.namedByFile.length;
    // "dbt" and "Dataform" are facts — both tools name a model after its file.
    // "file" is the weaker reading: one query, no CREATE, and something runs it.
    const dbt = sc.namedByFile.filter(t => t.how !== 'file').length;
    const tools = [...new Set(sc.namedByFile.filter(t => t.how !== 'file').map(t => t.how))].join(' and ');
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px' });
    card.append(why(
      el('span', { className: 'lbl', textContent:
        `${n} table${n === 1 ? '' : 's'} here ${n === 1 ? 'is' : 'are'} named after ${n === 1 ? 'its' : 'their'} file, not by the SQL` }),
      'tables named after their file',
      (dbt === n
        ? `These are ${tools} models. A model is a query with no CREATE in front of it, and the `
          + 'tool that runs it names the table after the file. '
        : dbt
        ? `Some are ${tools} models; the rest hold one query and no CREATE. Whatever runs them `
          + 'puts the rows in a table named after the file. '
        : 'Each of these files holds one query and no CREATE. Whatever runs it puts the rows in '
          + 'a table named after the file. ')
      + 'So you will not find the table name written inside the file — only the query.'));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
    sc.namedByFile.forEach(t => chips.append(el('span', { className: 'chip mono',
      textContent: `${t.table} — from ${t.file}` })));
    card.append(chips);
    box.append(foldFrom('named-by-file', card, { count: n }));
  }

  // 6. SQL the file holds as a quoted string and runs as text. Ripple reads the
  //    string, so the hop is followed instead of lost — measured before this, a
  //    whole CREATE OR REPLACE TABLE of the scanned column inside an EXECUTE
  //    IMMEDIATE gave no production tables at all. But the line the rows point
  //    at holds a string, not the CREATE they describe, and somebody who opens
  //    it expecting the statement will doubt the finding rather than the label.
  if (sc.builtAsText?.length) {
    const n = sc.builtAsText.length;
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px' });
    card.append(why(
      el('span', { className: 'lbl', textContent:
        `${n} statement${n === 1 ? '' : 's'} here ${n === 1 ? 'is' : 'are'} written as text and run, not written as SQL` }),
      'SQL written as text and run',
      'The file keeps the whole statement inside quotes and hands that text to the warehouse to '
      + 'run. Ripple read what is inside the quotes, so the trail carries on. But open that '
      + 'line and you will see a quoted string, not the statement — and anything added to the '
      + 'text while the job runs is not covered here.'));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
    sc.builtAsText.forEach(t => chips.append(el('span', { className: 'chip mono',
      textContent: `${t.file}:${t.line} — ${t.how} → ${t.table}` })));
    card.append(chips);
    box.append(foldFrom('built-as-text', card, { count: n }));
  }

  // 7. Statements that NAME the table or the column and carry it nowhere: a
  //    search index, a vector index, a row access policy, an UNDROP. These are
  //    not lineage and are never drawn as a hop — but a policy filtering on the
  //    column stops working on the day it goes, and no lineage anywhere would
  //    ever have said so. Measured before this: the parser gave up on the whole
  //    statement, the file landed on the "check by hand" list, and nothing said
  //    which table or which column it was about.
  if (sc.referencedHere?.length) {
    const rows = sc.referencedHere;
    const named = rows.filter(r => (r.namesColumns || []).length);
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px' });
    // The count of places that name the COLUMN stays on the page: those stop
    // working on the day it changes, which is the whole reason this card exists.
    card.append(why(
      el('span', { className: 'lbl', textContent:
        `${rows.length} place${rows.length === 1 ? '' : 's'} name${rows.length === 1 ? 's' : ''} this, and carr${rows.length === 1 ? 'ies' : 'y'} it nowhere`
        + (named.length ? ` — ${named.length} name${named.length === 1 ? 's' : ''} the column itself` : '') }),
      'named here, but carried nowhere',
      (named.length
        ? `The ${named.length} that name the column itself stop working the day it changes. `
        : '')
      + 'None of these passes the column on to another table, so none of them is on a chain '
      + 'above. They are listed because nothing else on this screen would mention them.'));
    const list = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
    rows.forEach(r => list.append(el('span', { className: 'chip mono', textContent:
      `${r.verb} ${r.kind} on ${r.table}`
      + ((r.namesColumns || []).length ? ` — names ${r.namesColumns.join(', ')}` : '')
      + ` · ${r.file}:${r.line}` })));
    card.append(list);
    box.append(foldFrom('referenced-here', card, { count: rows.length }));
  }
}

/* Published tables that stop being REFRESHED, rather than ones whose columns
   change. A different question, so it gets its own words and its own place —
   folding it into the findings above would make both of them vaguer.

   Why it exists: a column used only in a WHERE, a JOIN or a GROUP BY never
   reaches the table the statement builds, so the trail for that COLUMN really
   does end there, and Ripple said so and stopped. But the statement itself
   stops working on the day the column goes. The table it builds stops being
   rebuilt, and everything under it is served from data nobody is updating any
   more — which is an outage that arrives quietly, days later. */
function renderStopsLoading(box, sc) {
  const rows = sc.stopsLoading || [];
  if (!rows.length) return;
  const n = rows.length;
  box.append(el('span', { className: 'lbl', style: 'display:block;margin:26px 0 2px',
    textContent: `${n} published table${n === 1 ? '' : 's'} stop${n === 1 ? 's' : ''} being refreshed` }));
  const card = el('div', { className: 'card pad lg', style: 'margin-top:12px;border-color:var(--redln)' });
  card.append(why(
    el('b', { textContent: 'Not because a column of these changes.' }),
    'tables that stop being refreshed',
      'The change stops the job that fills these tables from running at all, so they keep '
      + 'whatever data they already held. Nobody sees an error — the numbers simply stop being '
      + 'current, and stay that way until somebody fixes the job.'));
  rows.forEach(r => {
    const line = el('div', { style: 'margin-top:14px' });
    line.append(el('div', {},
      el('span', { className: 'badge sm red', textContent: 'PRODUCTION TABLE' }),
      el('span', { className: 'mono', style: 'margin-left:10px;font-weight:600',
        textContent: r.prod })));
    line.append(el('div', { className: 'small muted', style: 'margin-top:6px;line-height:1.55' },
      'Because ',
      el('span', { className: 'mono', textContent: r.because }),
      ' stops loading. The path: ',
      el('span', { className: 'mono', textContent: (r.via || []).join(' → ') })));
    card.append(line);
  });
  if (sc.stopsLoadingCapped) {
    card.append(el('div', { className: 'note warn', style: 'margin-top:14px' },
      why(el('b', { textContent: 'This list was cut short — there may be more than these.' }),
        'why this list was cut short',
      'Ripple stopped after looking 400 tables downstream, so there may be more than these.')));
  }
  // Open when short enough to read at a glance. Measured on a real repository
  // this list runs to four hundred, and then the heading with its count is the
  // answer and the list is the evidence.
  box.append(foldFrom('stops-loading', card, { count: n, badge: 'red', tone: 'red', open: n <= 5 }));
}

/* A file delivered OUT of the warehouse, rather than a table inside it.

   EXPORT DATA writes a file to a bucket and somebody else's job picks it up
   every morning. It builds no table, so the trail had nothing to carry the
   column on to, and the answer read "no production table is affected" — true,
   and no use to anybody. The delivery is what breaks, and whoever reads it is
   outside this repository, so no scan of this repository will ever find them.
   That is exactly why it has to be named here. */
function renderFeeds(box, sc) {
  const rows = sc.feeds || [];
  if (!rows.length) return;
  const n = rows.length;
  box.append(el('span', { className: 'lbl', style: 'display:block;margin:26px 0 2px',
    textContent: `${n} deliver${n === 1 ? 'y' : 'ies'} out of the warehouse` }));
  const card = el('div', { className: 'card pad lg', style: 'margin-top:12px;border-color:var(--redln)' });
  card.append(why(
    el('b', { textContent: 'These are not tables — tell whoever reads them.' }),
    'deliveries out of the warehouse',
      'This writes a file to a bucket rather than a table. Whoever picks that file up is '
      + 'outside this repository, so no scan can tell you who they are. Tell them before the '
      + 'change goes live.'));
  rows.forEach(r => {
    const line = el('div', { style: 'margin-top:14px' });
    line.append(el('div', {},
      el('span', { className: 'badge sm ' + (r.breaking ? 'red' : 'grey'),
        textContent: r.breaking ? 'DELIVERY BREAKS' : 'DELIVERY CHANGES' }),
      el('span', { className: 'mono', style: 'margin-left:10px;font-weight:600',
        textContent: r.uri || 'destination not written down' })));
    line.append(el('div', { className: 'small muted', style: 'margin-top:6px;line-height:1.55' },
      'Carries ',
      el('span', { className: 'mono', textContent: (r.attrs || []).join(', ') }),
      ' out of ',
      el('span', { className: 'mono', textContent: r.from }),
      ` · ${r.file}:${r.line}`));
    card.append(line);
  });
  box.append(foldFrom('feeds', card, { count: n, badge: 'red', tone: 'red', open: n <= 5 }));
}

/* The honest half of the report: what Ripple could NOT account for. Styled to
   stand out, never to shrink — a clean finding list is only worth what was read. */
function renderGaps(box, sc) {
  if (sc.unreadable?.length) {
    const card = el('div', { className: 'card clip', style: 'margin-top:20px;border-color:var(--amberln)' });
    card.append(el('div', { className: 'chead', style: 'background:var(--amberbg);border-bottom-color:var(--amberln)' },
      el('span', { className: 'tag', style: 'background:var(--amber);color:#fff', textContent: 'Check by hand' }),
      el('b', { textContent: `${sc.unreadable.length} file${sc.unreadable.length === 1 ? '' : 's'} to check by hand` })));
    const p = el('div', { className: 'pad lg' });
    p.append(why(
      el('span', { className: 'prose', textContent: 'Not covered by the findings above.' }),
      'why a person has to read these',
      'Ripple could not read these files, or found your column somewhere it cannot follow — '
      + 'inside a procedure call, a loop, or written as text. Nothing in them is covered by the '
      + 'findings above, so somebody has to open them.'));
    // The advice is usually the same sentence on every entry — "this repository
    // is being read as generic SQL", on sixty-eight files. Printed sixty-eight
    // times it stops being advice and becomes wallpaper the eye skips, taking
    // the file names with it. Anything said more than once is said once, here.
    const counts = {};
    sc.unreadable.forEach(u => { if (u.hint) counts[u.hint] = (counts[u.hint] || 0) + 1; });
    const shared = Object.keys(counts).filter(h => counts[h] > 1);
    shared.forEach(h => p.append(el('div', { className: 'note info', style: 'margin-top:12px' },
      why(el('b', { textContent: `Applies to ${counts[h]} of these files.` }),
        'the reason shared by ' + counts[h] + ' of these files', h))));
    // The point of this list is that somebody opens those files and checks
    // them, so it gives them the line to open at and the line itself. "Could
    // not parse" sends a person hunting through a thousand-line file.
    //
    // Measured on a repository the size of the one this was built for: two
    // hundred and twelve of these, each with a name, a reason and a snippet,
    // made this one card 22,000 pixels tall -- more than half of a 40,000-pixel
    // page. A list that long is not worked through on screen. So the ones most
    // likely to be SQL are given in full (they are sorted that way) and every
    // remaining file is still NAMED, with its count said out loud. Nothing is
    // dropped from the analysis or from the page -- only from the long form.
    const SHOWN = 40;
    sc.unreadable.slice(0, SHOWN).forEach(u => {
      const item = el('div', { style: 'margin-top:14px' });
      item.append(el('div', { style: 'display:flex;gap:10px;align-items:baseline;flex-wrap:wrap' },
        el('span', { className: 'chip mono', textContent: u.file }),
        el('span', { className: 'small muted',
          textContent: u.reason + (u.places > 1 ? ` — in ${u.places} places` : '') })));
      if (u.snippet) {
        item.append(el('div', { className: 'mono small',
          style: 'margin-top:6px;padding:8px 12px;background:var(--amberbg);border:1px solid var(--amberln);'
            + 'border-radius:6px;overflow-x:auto;white-space:pre' },
          `line ${u.line} · ${u.snippet}`));
      }
      if (u.hint && !shared.includes(u.hint)) {
        item.append(el('div', { className: 'small muted', style: 'margin-top:6px;line-height:1.55', textContent: u.hint }));
      }
      p.append(item);
    });
    const rest = sc.unreadable.slice(SHOWN);
    if (rest.length) {
      p.append(why(
        el('span', { className: 'lbl', style: 'display:block;margin-top:20px',
          textContent: `${rest.length} more file${rest.length === 1 ? '' : 's'} to check by hand` }),
        'the rest of the check-by-hand list',
      `The ${SHOWN} most likely to hold SQL are shown above, each with the line to open. The `
      + 'rest are named here. None of them is covered by the findings.'));
      const more = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
      rest.forEach(u => more.append(el('span', { className: 'chip mono', textContent: u.file })));
      p.append(more);
    }
    card.append(p);
    box.append(foldFrom('check-by-hand', card, { count: sc.unreadable.length, badge: 'amber', tone: 'amber' }));
  }
  if (sc.mentionsOnly?.length) {
    const card = el('div', { className: 'card pad lg', style: 'margin-top:16px' });
    card.append(el('span', { className: 'lbl',
      textContent: sc.mentionsOnly.length === 1
        ? '1 file mentions the name but carries it nowhere'
        : `${sc.mentionsOnly.length} files mention the name but carry it nowhere` }));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:10px' });
    sc.mentionsOnly.forEach(m => chips.append(el('span', { className: 'chip mono', textContent: m.file })));
    card.append(chips);
    box.append(foldFrom('mentions-only', card, { count: sc.mentionsOnly.length }));
  }
}

// ── step 5 ────────────────────────────────────────────────────────────────
function step5(root) {
  const gs = S.scan?.graphs || [];
  const tabs = x(root, 'tabs'), map = x(root, 'map');
  // The line under the title has to be true of the picture underneath it, and
  // "to the production tables it feeds" is not true of a branch that ends at a
  // table Ripple has not been told is published — which is most of them when
  // the published-table list is wrong, exactly when it matters most.
  const anyProd = gs.some(g => (g.branches || []).length);
  // "None of these reach a published table" is a claim, and it is not one this
  // picture can make while some of its branches were cut short by a setting.
  const anyCut = (S.scan?.cutShort || []).length;
  // "The changed attribute" is wrong over a whole-table scan: nothing there
  // is called anything at any step. Say what was followed.
  const wholeMap = !!(S.scan?.stats?.wholeTables);
  x(root, 'sub').textContent = anyProd
    ? (wholeMap
      ? 'Where the change travels — every table built from the one that is changing — and which published tables it reaches.'
      : 'Where the changed attribute travels, what it is called at each step, and which published tables it reaches.')
    : anyCut
      ? `Where the changed attribute travels, and what it is called at each step. Ripple stopped `
        + `following ${anyCut === 1 ? 'one branch' : `${anyCut} branches`} at ${S.scan.maxHops} `
        + `renames deep, so where ${anyCut === 1 ? 'it ends' : 'they end'} is not known.`
      : 'Where the changed attribute travels, and what it is called at each step. None of these branches reach a table on your published list.';
  if (!gs.length) {
    // The same rule as the findings screen: a reassuring sentence may not appear
    // while a gap is known, and this picture is an answer in its own right.
    const clear = S.scan?.coverage?.complete;
    const gaps = (S.scan?.coverage?.gaps || []).length;
    map.append(el('div', { className: 'note ' + (clear ? 'good' : 'info'),
      style: 'max-width:600px;padding:22px 26px' },
      why(el('b', { style: 'font-size:15px', textContent: clear
          ? 'No downstream lineage found'
          : `No downstream lineage found — ${gaps} gap${gaps === 1 ? '' : 's'} on the previous step` }),
        'what no lineage means',
      clear
        ? 'These attributes do not feed any table on your published-table list.'
        : 'These attributes do not feed any table on your published-table list, out of what '
          + 'Ripple could read. There are places it could not see into, listed on the impact '
          + 'analysis step — so this picture may not be the whole picture.')));
    // The summary is written here, not on the summary step. Sending someone
    // straight on to step 6 left that screen with nothing to draw and two
    // buttons that did nothing -- which only ever happened on a clean result,
    // exactly when somebody most wants to get to the reply.
    x(root, 'next').onclick = () => makeSummary();
    return;
  }
  const gi = Math.min(S.graphTab, gs.length - 1);
  tabs.append(el('span', { className: 'lbl faint', textContent: 'Attribute', style: 'margin-right:4px' }));
  gs.forEach((g, i) => {
    const b = el('button', { className: 'pill tab' + (i === gi ? ' on' : '') });
    b.append(el('span', { className: 'mono', textContent: g.attr }),
      el('span', { className: 'sub', textContent: g.table }));
    b.onclick = () => { S.graphTab = i; render(); };
    tabs.append(b);
  });
  const g = gs[gi];
  const ends = g.endBranches || [];
  const all = g.branches.concat(ends);
  const card = el('div', { className: 'card pad lg' });
  const row = el('div', { className: 'maprow' });
  const src = el('div', { className: 'mapsrc' });
  src.append(el('div', {},
    el('div', { className: 'k', textContent: 'Upstream source' }),
    el('div', { className: 'tb', textContent: g.table }),
    el('div', { className: 'at', textContent: g.attr }),
    el('div', { className: 'ct', textContent: `${all.length} branch${all.length === 1 ? '' : 'es'} followed`
      + (g.branches.length ? ` · ${g.branches.length} to production` : '') })));
  const branches = el('div', { className: 'branches' });
  // Branches that share their first steps are drawn once, as one tree, instead
  // of once per branch as a row of boxes running off the right of the screen.
  // Measured before this on the practice pipeline: four rows of three boxes,
  // with the published table on every row cut off at the right edge. On a
  // repository the size of the one this was built for, a key column has about
  // 1,500 branches and nearly all of them share their first two hops -- so the
  // tree is a fraction of the rows, and a reader follows one path down instead
  // of re-reading the same start forty times.
  //
  // Still capped, and the cap is COUNTED OUT LOUD rather than quietly left
  // off. Nothing is lost: every branch is already a finding on the previous
  // step, grouped by published table. The ones that reach a published table
  // come first, because those are the ones that matter.
  const DRAWN = 60;
  branches.append(treeEl(treeOf(all.slice(0, DRAWN))));
  row.append(src, branches);
  card.append(row);
  if (all.length > DRAWN) {
    card.append(el('div', { className: 'note info', style: 'margin-top:14px' },
      why(el('b', { textContent: `${all.length - DRAWN} of the ${all.length} branches are not drawn here.` }),
        'branches not drawn',
      'Every branch is still in the findings on the previous step, grouped by published table. '
      + 'The ones drawn here are the ones that reach a published table, longest first.')));
  }
  map.append(card);
  if (ends.length) {
    map.append(el('div', { className: 'note warn', style: 'margin-top:14px' },
      why(el('b', { textContent: ends.length === 1
          ? 'One of these branches ends at a table that is not on your published list.'
          : `${ends.length} of these branches end at a table that is not on your published list.` }),
        'branches that end off the published list',
      'The change reaches them either way. Ripple simply cannot tell you whether anyone outside '
      + 'your team reads them, because they are not on your published-table list.')));
  }

  const legend = el('div', { className: 'legend' });
  [['var(--redbg)', 'var(--redln)', 'Production table'],
   ['#F4F9FE', '#9CC4EA', 'Intermediate table'],
   ['var(--violetbg)', 'var(--violetln)', 'Alias used for the attribute']].forEach(([bg, ln, label]) =>
    legend.append(el('div', {}, el('i', { style: `background:${bg};border:1px solid ${ln}` }), label)));
  map.append(legend);
  map.append(el('div', { className: 'small muted', style: 'margin-top:12px' },
    why(el('span', { textContent: 'Each box is a table.' }),
      'reading this map',
      'The alias is what your column is called at that point. That rename is exactly what a '
      + 'plain search of the code would miss.')));
  x(root, 'next').onclick = () => makeSummary();
}

/* Branches folded into one tree. Two branches that start the same way share
   the same boxes until they part; a box is the same box when its table, its
   alias and its markers are the same. */
function treeOf(branches) {
  const root = { kids: [], index: new Map() };
  branches.forEach(br => {
    let at = root;
    br.forEach(n => {
      const key = [n.name, n.alias || '', n.prod ? 'p' : '', n.cut ? 'c' : '', n.inferred ? 'i' : '',
        n.starKnown ? 'k' : ''].join('|');
      let next = at.index.get(key);
      if (!next) {
        next = { node: n, kids: [], index: new Map() };
        at.index.set(key, next);
        at.kids.push(next);
      }
      at = next;
    });
  });
  return root;
}

function treeEl(t) {
  const ul = el('ul', { className: 'tree' });
  t.kids.forEach(k => {
    const li = el('li');
    const box = nodeEl(k.node);
    // A leaf that is not a published table is where the code ran out -- unless
    // Ripple stopped, and then the box itself already says so.
    if (!k.kids.length && !k.node.prod && !k.node.cut) box.classList.add('end');
    li.append(box);
    if (!k.kids.length && !k.node.cut) {
      li.append(el('span', { className: 'tail',
        textContent: k.node.prod ? 'published table' : 'chain ends here' }));
    }
    if (k.kids.length) li.append(treeEl(k));
    ul.append(li);
  });
  return ul;
}

function nodeEl(n) {
  const d = el('div', { className: 'node' + (n.prod ? ' prod' : '') });
  d.append(el('div', { className: 'top' },
    el('span', { className: 'k', textContent: n.kind }),
    el('span', { className: 'nm', textContent: n.name })));
  if (n.alias) d.append(el('div', { className: 'al' },
    el('span', { textContent: 'alias' }),
    el('span', { className: 'chip alias', textContent: n.alias })));
  // The two things a box on this map can hide. Drawn on the box itself, because
  // a picture of a chain is exactly where somebody reads "and then it stops".
  if (n.inferred) {
    d.append(el('div', { className: 'small muted', style: 'margin-top:5px;line-height:1.4',
      textContent: (n.how ? `${n.how} of a whole table` : 'built with SELECT *')
        + ' — column list not visible' }));
  }
  if (n.starKnown) {
    d.append(el('div', { className: 'small muted', style: 'margin-top:5px;line-height:1.4',
      textContent: (n.how ? `${n.how} of a whole table` : 'built with SELECT *')
        + ' — column list known' }));
  }
  if (n.cut) {
    d.append(el('div', { className: 'small', style: 'margin-top:5px;line-height:1.4;color:var(--red)',
      textContent: 'Ripple stopped here — hop limit, not the end of the chain' }));
  }
  return d;
}

// ── step 6 ────────────────────────────────────────────────────────────────
function makeSummary() {
  if (S.summary) { goto(6); return; }
  run(async () => {
    const out = await api('/api/summary', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scan: S.scan, vals: { ...S.vals, effectiveLabel: fmtDate(S.vals.effectiveDate) }, useAI: true }),
    });
    S.summary = out.summary; S.reply = out.reply; S.aiNote = out.aiNote || '';
    goto(6);
  }, 'Writing the summary…');
}

function step6(root) {
  const s = S.summary;
  // A screen with nothing on it and two buttons that do nothing is the worst
  // way to say "the summary has not been written yet". If we ever arrive here
  // without one, say so and offer the one button that fixes it.
  if (!s) {
    x(root, 'sub').textContent = 'The summary has not been written yet.';
    const b = x(root, 'body');
    const go = el('button', { className: 'pri', textContent: 'Write the summary now' });
    go.onclick = () => makeSummary();
    b.append(el('div', { className: 'note info', style: 'max-width:620px' },
      el('b', { textContent: 'Nothing to show yet. ', style: 'display:block' }),
      'The summary is written from the findings when you leave the dependency map. '
      + 'It has not been written for this scan.'), el('div', { style: 'margin-top:14px' }, go));
    x(root, 'next').onclick = () => makeSummary();
    x(root, 'save').disabled = true;
    x(root, 'saved').textContent = 'Nothing to save until the summary is written.';
    return;
  }
  const [cls, label] = RISK[S.scan.risk] || RISK.none;
  x(root, 'sub').textContent =
    //<online-only>
    s.writtenBy === 'ai' ? `Written by ${S.health.ai.modelLabel} from the findings — no code was sent to it.` :
    //</online-only>
    'Written from the findings without AI.';

  const b = x(root, 'body');
  const grid = el('div', { className: 'grid2', style: 'grid-template-columns:1.7fr 1fr' });

  // ── the summary itself ──
  const main = el('div', { className: 'card clip' });
  main.append(el('div', { className: 'chead', style: 'background:#fff;padding:18px 26px' },
    el('b', { textContent: s.headline, style: 'font-size:16px;font-weight:800;line-height:1.35' }),
    el('span', { className: 'badge ' + cls, textContent: label, style: 'margin-left:auto;flex-shrink:0' })));
  main.append(el('p', { style: 'padding:20px 26px 4px;font-size:14.5px;line-height:1.7;color:var(--body)', textContent: s.narrative }));
  const ul = el('ul', { className: 'ticks', style: 'padding:16px 26px 24px;margin-top:0' });
  (s.bullets || []).forEach(t => ul.append(el('li', {}, t)));
  main.append(ul);
  const fields = el('div', { style: 'padding:0 26px 24px;display:grid;grid-template-columns:1fr 1fr;gap:16px 24px' });
  [['Source system', S.vals.source, false], ['Change type', S.vals.changeType, false],
   ['Upstream tables name', S.vals.upstream.map(u => u.table).join(', '), true],
   // "the whole table" where that is what was scanned, never a blank.
   ['Attributes, or the whole table', S.vals.upstream.map(u => u.whole
       ? `${u.table} — whole table` : (u.attrs || []).join(', ')).filter(Boolean).join(', '), true]].forEach(([k, v, mono]) =>
    fields.append(el('div', {}, el('span', { className: 'lbl', textContent: k }),
      el('div', { textContent: v || '—',
        style: 'margin-top:5px;font-size:14px;font-weight:600;line-height:1.45;overflow-wrap:break-word;'
          + (mono ? 'font-family:var(--mono);color:var(--blued)' : 'color:var(--ink)') }))));
  main.append(fields);

  // ── right rail ──
  const rail = el('div', { className: 'rail' });
  const dl = daysLeft(S.vals.effectiveDate);
  const dead = el('div', { className: 'card pad' });
  dead.append(el('span', { className: 'lbl', textContent: 'Deadline' }));
  dead.append(el('div', { textContent: fmtDate(S.vals.effectiveDate) || 'Not given',
    style: 'font-size:20px;font-weight:800;margin-top:8px' }));
  if (dl !== null) dead.append(el('span', { className: 'badge sm ' + (dl <= 21 ? 'amber' : 'blue'),
    textContent: dl < 0 ? 'date has passed' : `${dl} day${dl === 1 ? '' : 's'} left`, style: 'margin-top:8px' }));
  if (S.vals.pocName || S.vals.pocTeam) {
    dead.append(el('div', { className: 'small muted', style: 'margin-top:12px;line-height:1.55' },
      'Upstream contact: ', el('b', { textContent: S.vals.pocName || '—', style: 'color:var(--body)' }),
      S.vals.pocTeam ? ', ' + S.vals.pocTeam : ''));
  }

  const st = S.scan.stats;
  const radius = el('div', { className: 'card pad' });
  radius.append(el('span', { className: 'lbl', textContent: 'Blast radius' }));
  [[st.productionTables, 'production tables impacted'], [st.intermediateTables, 'intermediate tables in the path'],
   [st.filesWithImpact, 'code files to change'], [st.couldNotRead, 'files that must be checked by hand']]
    .forEach(([n, lab]) => radius.append(el('div', { style: 'display:flex;align-items:baseline;gap:10px;padding:6px 0' },
      el('span', { textContent: String(n), style: 'font-size:18px;font-weight:800;color:var(--blued);font-variant-numeric:tabular-nums;min-width:26px' }),
      el('span', { style: 'font-size:13px;color:var(--body)', textContent: lab }))));

  const acts = el('div', { className: 'card pad' });
  acts.append(el('span', { className: 'lbl', textContent: 'What to do' }));
  const ol = el('ol', { className: 'acts' });
  (s.actions || []).forEach(a => ol.append(el('li', {}, a)));
  acts.append(ol);

  rail.append(dead, radius, acts);
  grid.append(main, rail);
  b.append(grid);
  // The caveat has to be on the same screen as the answer it qualifies, so it
  // stays -- but not the whole card. The findings screen already carries every
  // line, every reason and every snippet; repeating that here printed a hundred
  // and forty identical words two clicks apart, which is how a warning stops
  // being read. The count and the file names are the facts, so they are here.
  if (S.scan.unreadable?.length) {
    const n = S.scan.unreadable.length;
    const card = el('div', { className: 'card pad lg', style: 'margin-top:20px;border-color:var(--amberln)' });
    card.append(why(
      el('b', { style: 'font-size:14px', textContent: `${n} file${n === 1 ? '' : 's'} to check by hand` }),
      'the files a person still has to read',
      'Ripple could not read these, or found your column somewhere it cannot follow. They are '
      + 'not covered by the findings above. The line to open in each one is on the impact '
      + 'analysis step.'));
    const chips = el('div', { className: 'chips scrollbox', style: 'margin-top:12px' });
    S.scan.unreadable.forEach(u => chips.append(el('span', { className: 'chip mono',
      textContent: u.file })));
    card.append(chips);
    b.append(card);
  }

  x(root, 'next').onclick = () => goto(7);
  // "Saved" has to mean saved. Where it does not really last, say so in the
  // same breath rather than letting the word stand on its own. This sits in a
  // row between two buttons, so it stays one short line -- the full
  // explanation is on the Past analyses screen.
  const saved = x(root, 'saved');
  saved.textContent = '';
  if (S.savedId) {
    saved.append(el('span', { className: 'badge sm green', textContent: `Saved as analysis #${S.savedId}` }));
    if (S.health?.limits?.historyKept === false) {
      saved.append(el('span', { className: 'small faint',
        textContent: ' This host wipes saved analyses — copy out anything you need to keep.' }));
    }
  }
  x(root, 'save').onclick = () => run(async () => {
    const out = await api('/api/history', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vals: S.vals, scan: S.scan, summary: S.summary, mode: S.vals.extractedBy }),
    });
    S.savedId = out.id || null;
    if (!out.saved) alert('History is not available here: ' + (out.reason || ''));
    render();
  }, 'Saving this analysis…');
}

// ── step 7 ────────────────────────────────────────────────────────────────
function step7(root) {
  const r = S.reply || { subject: '', body: '' };
  const subj = x(root, 'subject'); subj.value = r.subject; subj.oninput = () => { r.subject = subj.value; };
  const body = x(root, 'body'); body.value = r.body; body.oninput = () => { r.body = body.value; };
  const ol = x(root, 'acts');
  (S.summary?.actions || []).forEach(a => ol.append(el('li', {}, a)));

  // who the reply is for — real values only, and nothing here sends anything.
  // Every address, one chip each, so a list of four is not one long unreadable
  // string that hides a typo in the middle of it.
  const to = x(root, 'to');
  const addresses = S.vals.pocEmails?.length ? S.vals.pocEmails : emailList(S.vals.pocEmail);
  to.append(el('span', { className: 'small', textContent: 'To', style: 'font-weight:700;color:var(--mute);flex-shrink:0' }));
  if (S.vals.pocName) to.append(el('span', { className: 'chip', textContent: S.vals.pocName }));
  addresses.forEach(a => to.append(el('span', { className: 'chip mono', textContent: a })));
  if (!S.vals.pocName && !addresses.length) {
    to.append(el('span', { className: 'chip', textContent: 'No contact was given' }));
  }
  if (S.vals.pocTeam) to.append(el('span', { className: 'badge sm blue', textContent: S.vals.pocTeam }));

  if (S.scan) {
    const [cls, label] = RISK[S.scan.risk] || RISK.none;
    x(root, 'risk').append(el('span', { className: 'badge ' + cls, textContent: label }));
  }
  const dl = daysLeft(S.vals.effectiveDate);
  if (S.vals.effectiveDate) {
    x(root, 'deadline').append(el('div', { className: 'note info', style: 'padding:14px 18px' },
      el('span', { className: 'lbl', style: 'color:var(--blued);display:block', textContent: 'Respond by' }),
      el('div', { style: 'font-size:15px;font-weight:700;margin-top:6px;color:var(--ink)',
        textContent: fmtDate(S.vals.effectiveDate) + (dl !== null ? ` · ${dl} day${dl === 1 ? '' : 's'} left` : '') })));
  }

  x(root, 'copy').onclick = async () => {
    // The addresses go with it. Copying a reply and then having to gather the
    // recipients again by hand is half a job.
    const head = addresses.length ? `To: ${addresses.join('; ')}\n` : '';
    await navigator.clipboard.writeText(`${head}Subject: ${r.subject}\n\n${r.body}`);
    x(root, 'copied').textContent = addresses.length
      ? `Copied, with ${addresses.length} recipient${addresses.length === 1 ? '' : 's'} — paste it into Outlook.`
      : 'Copied — paste it into Outlook.';
  };
  x(root, 'restart').onclick = () => {
    Object.assign(S, { step: 1, maxStep: 1, vals: null, scan: null, summary: null, reply: null,
      savedId: null, emailPreview: null, openGroup: 'p0', openRow: null, graphTab: 0 });
    render();
  };
}

// ── history & settings ────────────────────────────────────────────────────
function historyView(root) {
  const kept = S.health?.limits?.historyKept !== false;
  root.append(el('div', { className: 'head' }, el('div', {},
    el('h2', { textContent: 'Past analyses' }),
    // "On this server" is wrong in the copy that runs as a program on somebody's
    // own laptop, where there is no server and nothing is shared with anyone.
    el('p', { textContent: kept
      ? (S.health?.offline
        ? 'Everything saved on this machine, newest first. They stay in the folder beside Ripple.'
        : 'Everything saved on this server, newest first.')
      : 'Newest first — but this list does not last on this host. See the note below.' }))));
  // A hosted copy is replaced constantly and takes its saved rows with it.
  // An empty list would otherwise look like a bug or like lost work.
  if (!kept) {
    root.append(el('div', { className: 'note warn', style: 'margin-bottom:18px' },
      why(el('b', { textContent: 'Saved analyses do not survive here — copy out anything you '
          + 'need to keep.' }),
        'why saved analyses do not last here',
      'This copy runs on a shared host that replaces its machine constantly and wipes anything '
      + 'saved on it. An analysis can disappear within minutes, and the list can look different '
      + 'from one refresh to the next. Nothing is broken — there is simply nowhere permanent '
      + 'to save.')));
  }
  const card = el('div', { className: 'card clip' });
  root.append(card);
  api('/api/history').then(rows => {
    if (!rows.length) {
      card.append(el('div', { className: 'pad lg muted', textContent: kept
        ? 'Nothing saved yet.'
        : 'Nothing here — either nothing has been saved yet, or this host has already been replaced.' }));
      return;
    }
    const t = el('table', { className: 'hist' });
    const hr = el('tr');
    ['When', 'Subject', 'Source', 'Change', 'Risk', 'Mode', 'Status'].forEach(h => hr.append(el('th', { textContent: h })));
    t.append(hr);
    rows.forEach(r => {
      const [cls, label] = RISK[r.risk] || RISK.none;
      const sel = el('select', { className: 'statussel' });
      ['New', 'In progress', 'Verified', 'Closed'].forEach(s =>
        sel.append(el('option', { value: s, textContent: s, selected: s === r.status })));
      sel.onchange = () => api(`/api/history/${r.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: sel.value }),
      });
      // The same date format as every other screen. This column used to print
      // the raw stored value -- 2026-08-13 04:38 beside "18 Sept 2026"
      // everywhere else, which reads as two different kinds of date.
      const when = (r.created_at || '');
      t.append(el('tr', {},
        el('td', { className: 'small muted',
          textContent: (fmtDate(when.slice(0, 10)) + ' ' + when.slice(11, 16)).trim() }),
        el('td', { textContent: r.subject || '—' }),
        el('td', { textContent: r.source || '—' }),
        el('td', { className: 'small', textContent: r.change_type || '—' }),
        el('td', {}, el('span', { className: 'badge ' + cls, textContent: label })),
        el('td', { className: 'small muted', textContent: r.mode || '' }),
        el('td', {}, sel)));
    });
    card.append(t);
  });
}

/* Settings, and the AI key form that is most of it. The offline build replaces
   this whole screen: it has no key to set, and it has two settings of its own
   that online reads from environment variables — which folder to scan, and
   which SQL dialect to read it as. */
//<online-only>
function settingsView(root) {
  const h = S.health;
  root.append(el('div', { className: 'head' }, el('div', {},
    el('h2', { textContent: 'Settings & checks' }),
    el('p', { textContent: 'What Ripple is connected to, and whether it is working.' }))));

  // First, and on its own: the one setting on this screen that can turn a real
  // impact into a clean result.
  root.append(productionCard({
    onSave: (text) => api('/api/production', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }).then(out => { S.health = out; }),
    persistNote: 'Held by this server while it runs. Set RIPPLE_PROD_TABLES to keep it after a restart.',
    savedNote: 'Saved. Every scan from now on uses this list — until this server restarts.',
  }));
  if (!h.productionSet) {
    root.append(el('div', { className: 'note warn', style: 'margin:14px 0 24px' },
      why(el('b', { textContent: 'Nothing can be scanned until this list is set.' }),
        'why this one setting stops everything',
      'A published table is one people outside your team read. Ripple has no way of working '
      + 'out which of yours those are — every warehouse names them differently — so until you '
      + 'say, every table fails that test and every scan would come back "no production table '
      + 'is affected". That sentence is the one thing this tool sells, and it would be '
      + 'meaningless.',
      'Paste the table names above, or a pattern they all share such as _PUBLISHED. You can '
      + 'change it whenever you like.')));
  } else {
    root.append(el('div', { style: 'height:24px' }));
  }

  const grid = el('div', { className: 'grid2 even' });
  const left = el('div', { className: 'card pad lg' });
  left.append(el('span', { className: 'lbl', textContent: 'Repository' }));
  [['Folder', h.repo.path], ['Label', h.repo.label], ['Files indexed', String(h.repo.files)],
   ['Statements understood', String(h.repo.statements)], ['Files unreadable', String(h.repo.unreadable)],
   ...(((h.repo.heldOnline || 0) + (h.repo.pathTooLong || 0))
     ? [['Files never opened', String((h.repo.heldOnline || 0) + (h.repo.pathTooLong || 0))]]
     : []),
   ['SQL dialect', h.sqlDialect], ['Renames followed', hopsPhrase(h.maxHops)],
   ['Tables you publish', h.production || 'not set']].forEach(([k, v]) =>
    left.append(el('div', { className: 'factrow' },
      el('span', { className: 'small muted', textContent: k }),
      el('span', { className: 'small', textContent: v }))));
  left.append(folderBox(h));

  left.append(el('div', { className: 'note info', style: 'margin-top:14px' },
    'The rest are set before Ripple starts, with ',
    el('span', { className: 'mono', textContent: 'RIPPLE_SQL_DIALECT' }), ', ',
    el('span', { className: 'mono', textContent: 'RIPPLE_PROD_TABLES' }), ' and ',
    el('span', { className: 'mono', textContent: 'RIPPLE_AI_KEY' }), '. See the README.'));

  grid.append(left, el('div', {}, aiCard(h), buildCard(h)));
  root.append(grid);
}

/* Choosing which folder Ripple reads, from the screen.

   RIPPLE_REPO decides which folder Ripple starts on, which is right for a server
   somebody administers and wrong for a laptop: it meant the only way to point
   Ripple at your own SQL was to edit a file and restart it. Until you did, every
   answer described the small practice pipeline — confidently, correctly, and
   about nothing anybody cares about.

   The choice lasts until Ripple is restarted, and the line underneath says so.
   Anything else would be a promise this build cannot keep: there is nowhere for
   it to write the choice down, exactly as with the published-table list, the
   GitHub token and the AI key. */
function folderBox(h) {
  const wrap = el('div', { style: 'margin-top:16px' });
  wrap.append(el('span', { className: 'lbl', textContent: 'The folder Ripple reads' }));

  const box = el('input', {
    className: 'mono', type: 'text', value: (h.repo && h.repo.path) || '',
    placeholder: 'C:\\work\\our-pipeline',
    style: 'margin-top:8px;width:100%;font-size:12.5px',
  });
  wrap.append(box);

  const msg = el('div', { style: 'margin-top:10px' });
  const row = el('div', { className: 'foot', style: 'margin-top:12px' });
  const go = el('button', { className: 'pri', textContent: 'Read this folder' });

  go.onclick = () => run(async () => {
    msg.innerHTML = '';
    try {
      S.health = await api('/api/repo/folder', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: box.value }),
      });
      // Everything read from the previous folder is gone, so anything on screen
      // that was worked out from it has to go with it. A scan left showing from
      // the folder before is the worst possible thing this screen could leave
      // behind: right-looking, and about a repository nobody is now reading.
      S.scan = null; S.summary = null; S.vals = S.vals || {};
      msg.append(el('div', { className: 'note good' },
        'Reading ' + ((S.health.repo && S.health.repo.path) || box.value) + ' — '
        + ((S.health.repo && S.health.repo.files) || 0) + ' files. Any earlier '
        + 'result on screen has been cleared, because it was about the other folder.'));
    } catch (e) {
      msg.append(el('div', { className: 'note bad' }, e.message));
    }
  }, 'Reading that folder…');

  row.append(go);
  row.append(el('span', { className: 'small faint',
    textContent: 'Held by this server while it runs. Set RIPPLE_REPO to keep it after a restart.' }));
  wrap.append(row, msg);
  return wrap;
}

/* Turning the AI on from the screen. Same rules as the GitHub token: the key
   goes to the server, is held in memory only, and never comes back to this
   page — so this form can show whether one is set, never what it is. */
/* Which company issued a key, worked out from the key itself.

   One box, not one box per provider. Somebody pasting a key should not have to
   tell Ripple who issued it — the key says so in its first few characters, and
   asking is one more thing to get wrong. The prefixes come from the server, so
   there is one list of them and this screen cannot drift from it.

   Nothing is sent anywhere while this runs: it reads the box as it is typed. */
function whoIssued(h, key) {
  key = (key || '').trim();
  if (!key) return null;
  for (const u of (h.ai.unsupported || [])) {
    if (u.prefixes.some(px => key.startsWith(px))) return { unsupported: u.label };
  }
  let best = null, longest = -1;
  for (const pr of (h.ai.providers || [])) {
    for (const px of pr.prefixes) {
      if (key.startsWith(px) && px.length > longest) { best = pr; longest = px.length; }
    }
  }
  return best;
}

/* "a OpenAI key" reads as a typo on the one screen that has to look careful. */
function anOrA(word) {
  return /^[AEIOU]/i.test(word || '') ? 'an' : 'a';
}

function aiCard(h) {
  const card = el('div', { className: 'card pad lg' });
  const on = h.ai.available;
  const fromEnv = h.ai.keyFrom === 'environment';

  card.append(el('span', { className: 'lbl', textContent: 'AI (optional)' }));
  card.append(el('div', { className: 'note ' + (on ? 'good' : 'info'), style: 'margin-top:12px' },
    why(el('b', { textContent: on ? `AI is on — ${h.ai.modelLabel}.` : 'No key set — rules alone.' }),
      on ? 'what is sent to the model' : 'what runs without a key',
      on
        ? (fromEnv
          ? 'The key is set on the server, so it survives a restart. Only the notification text '
            + 'and the findings are sent to the model — never your code.'
          : 'Only the notification text and the findings are sent to the model — never your '
            + 'code.')
        : 'Ripple works exactly the same without a key. The wording it writes is just plainer.')));

  // ── the key ─────────────────────────────────────────────────────────────
  card.append(el('label', { className: 'lbl', style: 'display:block;margin:18px 0 7px',
    textContent: fromEnv ? 'Use a different key instead' : 'API key' }));
  const key = el('input', { type: 'password', autocomplete: 'off',
    placeholder: 'sk-…   AIza…   gsk_…', style: 'padding:12px 14px' });
  card.append(key);

  const who = el('div', { className: 'small', style: 'margin-top:7px;line-height:1.5' });
  const names = (h.ai.providers || []).map(pr => pr.label);
  const blank = names.length
    ? `Paste a key from ${names.slice(0, -1).join(', ')} or ${names[names.length - 1]}. `
      + 'Ripple works out which from the key itself.'
    : '';
  const sayWho = () => {
    const found = whoIssued(h, key.value);
    who.className = 'small' + (found && found.unsupported ? ' warn' : ' faint');
    if (!found) {
      who.textContent = key.value.trim()
        ? 'Ripple does not recognise that key. It reads OpenAI, Google Gemini and Groq keys.'
        : blank;
      return;
    }
    if (found.unsupported) {
      who.textContent = `That is ${anOrA(found.unsupported)} ${found.unsupported} key. `
        + 'Ripple cannot use one — it reads OpenAI, Google Gemini and Groq keys.';
      return;
    }
    who.textContent = `That is ${anOrA(found.label)} ${found.label} key. `
      + `Get one at ${found.where}.`;
  };
  key.oninput = sayWho;
  sayWho();
  card.append(who);

  // ── the model ───────────────────────────────────────────────────────────
  // Only after a key has been accepted, because the list is the provider's own
  // answer to "what can this key use" rather than a list written down here. A
  // written-down list is wrong within months, and then it offers a model that
  // no longer exists to somebody in the middle of reading an email.
  let sel = null;
  if ((h.ai.models || []).length) {
    card.append(el('label', { className: 'lbl', style: 'display:block;margin:18px 0 7px',
      textContent: 'Model' }));
    sel = el('select', { className: 'statussel', style: 'width:100%;padding:11px 12px' });
    h.ai.models.forEach(m => sel.append(el('option', {
      value: m, textContent: m, selected: m === h.ai.model })));
    card.append(sel);
    card.append(el('div', { className: 'small faint', style: 'margin-top:6px;line-height:1.5' },
      `${h.ai.models.length} model${h.ai.models.length === 1 ? '' : 's'} this key can use, `
      + `asked of ${h.ai.providerLabel} rather than remembered. The one at the top is the `
      + 'one Ripple would pick.'));
  } else if (!on) {
    card.append(el('div', { className: 'small faint', style: 'margin-top:14px;line-height:1.5',
      textContent: 'The model list appears once a key is accepted — Ripple asks the provider '
        + 'which models that key can actually use.' }));
  }

  const out = el('div', { style: 'margin-top:14px' });
  if (S.aiMsg) {
    out.append(el('div', { className: 'note ' + (S.aiMsg.ok ? 'good' : 'warn'), textContent: S.aiMsg.text }));
  }
  const say = (ok, text) => { S.aiMsg = { ok, text }; };

  const save = el('button', { className: 'pri', textContent: on ? 'Save and re-test' : 'Turn the AI on' });
  save.onclick = () => run(async () => {
    S.aiMsg = null;
    try {
      S.health = await api('/api/ai/connect', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        // No model on a brand-new key: the provider has not been asked yet, so
        // Ripple takes whichever it recommends and shows the list afterwards.
        body: JSON.stringify({ key: key.value, model: sel ? sel.value : '' }),
      });
      key.value = '';                    // the server has it; keep no copy here
      say(true, `AI is on. The model answered, using ${S.health.ai.modelLabel}.`);
    } catch (e) { say(false, 'That did not work — ' + e.message); }
  });

  const test = el('button', { className: 'ghost', textContent: 'Test the key' });
  test.onclick = () => run(async () => {
    const res = await api('/api/ai/check', { method: 'POST' });
    say(res.ok, res.ok ? `Working — the model replied, using ${res.model}.` : `Not working — ${res.reason}`);
  });

  const row = el('div', { className: 'foot', style: 'margin-top:16px' }, save, test);
  if (on && h.ai.keyFrom === 'entered') {
    const forget = el('button', { className: 'ghost', textContent: 'Forget the key' });
    forget.onclick = () => run(async () => {
      S.health = await api('/api/ai/forget', { method: 'POST' });
      S.aiMsg = { ok: true, text: 'Key forgotten. Ripple is back to rules alone.' };
    });
    row.append(forget);
  }
  card.append(row, out);

  // On a host that is replaced constantly, a typed key does not last -- and
  // while it does last, every other visitor to this copy is spending it.
  if (h.ai.keyLasts === false) {
    card.append(el('div', { className: 'note warn', style: 'margin-top:18px' },
      why(el('b', { textContent: 'A key typed in here is shared, and temporary.' }),
        'a key typed into a public copy',
      'Anyone with this address can open this copy. While your key is loaded, other people '
      + 'using the site are spending it — and it disappears whenever the host replaces the '
      + 'machine, often within minutes.',
      'For anything more than a demonstration, run Ripple on your own machine, or ask whoever '
      + 'hosts this to set the key on the server.')));
  }
  return card;
}
//</online-only>

// ── plumbing ──────────────────────────────────────────────────────────────
function goto(n) { S.step = n; S.maxStep = Math.max(S.maxStep, n); S.view = 'wizard'; render(); }

/* Everything slow goes through here, and everything slow says what it is doing.
   Reading a repository takes seconds on a big one, and a spinning dot in the
   far corner is not an answer -- numbers that change by themselves a while
   later read as a page that did something on its own. */
function run(fn, what) {
  S.busy = true; S.busyWhat = what || 'Working…'; S.progress = null; render();
  watchProgress();
  Promise.resolve(fn()).catch(e => {
    alert('Something went wrong: ' + e.message);
  }).finally(() => { S.busy = false; S.busyWhat = ''; S.progress = null; render(); });
}

/* Ask the running program what it is doing, twice a second, for as long as it
   is doing something.

   On a repository of a few thousand files, reading it takes minutes and a scan
   takes about a minute. A spinner and a fixed sentence for that long is
   indistinguishable from a program that has hung, and the usual answer to that
   is a progress bar with a number nobody can check underneath it. This shows
   only what the engine has actually counted: files really read, statements
   really followed. Where there is no total — a chain looks at as many
   statements as it turns out to need — it says the count and no fraction,
   because a fraction would need a denominator nobody knows. */
function watchProgress() {
  if (S.progressTimer) return;
  S.progressTimer = setInterval(async () => {
    if (!S.busy) { clearInterval(S.progressTimer); S.progressTimer = null; S.progress = null; return; }
    try {
      const p = await api('/api/progress');
      const was = progressText(S.progress);
      S.progress = p.job ? p : null;
      if (progressText(S.progress) !== was) render();
    } catch { /* the request it belongs to will report the real failure */ }
  }, 500);
}

/* How deep the trail is followed, in words. Zero is not "0 hops" -- it means
   the trail is followed until the CODE runs out, which is the default and is
   the whole answer to "why did it stop there". Printed as a number, zero read
   as "Ripple follows no renames at all", which is the opposite of what it is. */
function hopsPhrase(n) {
  return n ? `${n} renames deep` : 'to the end of the code';
}

function progressText(p) {
  if (!p || !p.job) return '';
  const label = p.label || ({ reading: 'Reading the files',
                              parsing: 'Understanding the SQL',
                              scanning: 'Following the column' })[p.job] || 'Working';
  if (p.total > 0) return `${label} — ${p.done.toLocaleString()} of ${p.total.toLocaleString()}`;
  if (p.done > 0) return `${label} — ${p.done.toLocaleString()} so far`;
  return label;
}

function render() {
  renderSteps(); renderStatus();
  const view = $('#view'); view.innerHTML = '';
  $('#hRight').innerHTML = '';
  if (S.busy) {
    // The counted line if there is one, the fixed sentence until there is.
    $('#hRight').append(el('span', { className: 'spin' }),
      el('span', { className: 'small', textContent: progressText(S.progress) || S.busyWhat,
        style: 'margin-left:9px;font-weight:600;color:var(--blued)' }));
  }

  if (S.view === 'history') {
    setHeader('Past analyses', S.health?.limits?.historyKept === false
      ? 'Kept only until this host is replaced'
      : S.health?.offline ? 'Saved beside Ripple, on this machine' : 'Saved on this server');
    historyView(view); return;
  }
  if (S.view === 'settings') { setHeader('Settings & checks', 'Connections and health'); settingsView(view); return; }

  const list = stepNumbers();
  setHeader(STEPS[S.step - 1][0], `Step ${list.indexOf(S.step) + 1} of ${list.length}`);
  const tpl = $(`#t-step${S.step}`);
  if (!tpl) return;
  const node = tpl.content.cloneNode(true);
  const holder = el('div');
  holder.append(node);
  view.append(holder);
  ({ 1: step1, 2: step2, 3: step3, 4: step4, 5: step5, 6: step6, 7: step7 })[S.step](holder);
}

$('#navHistory').onclick = () => { S.view = 'history'; render(); };
$('#navSettings').onclick = () => { S.view = 'settings'; render(); };

/* Run once, after the server has answered and before the first screen is drawn.
   Nothing to do online. The offline build replaces this to open on the settings
   screen the very first time, when no repository folder has been chosen yet —
   there, that is a question that has to be asked rather than a default that can
   be assumed. */
//<online-only>
function afterBoot() {}
//</online-only>

/* Reading a repository the size of a real warehouse takes minutes. Measured on
   7,304 files: 101 seconds, during which this page was blank and had no way to
   ask what was going on, because the only request that would answer was the one
   it was waiting on. A working program that says nothing for a hundred seconds
   is reported as a hung one.

   So the server reads on a thread and answers straight away with indexing:true,
   and this waits here — showing the counted file numbers it was already keeping
   — until the read is done. Nothing is estimated and no bar moves on a timer:
   every number below is files that have really been read. */
async function waitForTheRepository() {
  while (S.health && S.health.indexing) {
    renderReading();
    await new Promise(r => setTimeout(r, 700));
    try { S.health = await api('/api/health'); }
    catch (e) { S.bootError = e.message; return; }
  }
}

function renderReading() {
  const h = S.health || {};
  const p = h.progress || {};
  const view = $('#view');
  if (!view) return;
  view.innerHTML = '';
  const card = el('div', { className: 'card pad lg', style: 'margin:40px auto;max-width:640px' });
  card.append(el('b', { style: 'font-size:15px;display:block',
    textContent: `Reading ${h.repo?.label || 'the repository'}` }));
  card.append(el('div', { className: 'small muted', style: 'margin-top:8px',
    textContent: h.readError
      ? h.readError
      : (progressText(p)
         || 'Opening every file and reading the SQL in it. On a repository of a few '
            + 'thousand files this takes a few minutes. Nothing has been missed — '
            + 'Ripple is still going.') }));
  card.append(el('div', { className: 'small muted', style: 'margin-top:10px',
    textContent: h.repo?.path || '' }));
  view.append(card);
}

(async function boot() {
  try { S.health = await api('/api/health'); }
  catch (e) { alert('Could not reach the Ripple server: ' + e.message); }
  await waitForTheRepository();
  afterBoot();
  render();
})();
