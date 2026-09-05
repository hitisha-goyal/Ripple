# Which file do I follow?

Two files. You need one, and this page picks it.

---

## First, two words that mean opposite things

This trips everybody, so it is worth thirty seconds.

**What most people mean:** "offline" = running on my own laptop, "online" = once
it is hosted somewhere.

**What a codebase usually means:** "offline" = a build that may not reach the
network at all. A different question entirely, and a file named for one of them
gets read as the other. So no file here is named either word.

**And the thing worth knowing:** running Ripple on your own machine and hosting
it later are **the same files**. One codebase. `run.py` starts it here; a hosting
platform's entry point loads the very same application. Nothing is rebuilt,
ported or reconfigured when it gets hosted. Getting it running on a laptop is not
a detour on the way to hosting it — it is the same thing, started a different way.

---

## Pick one

### I want to BUILD Ripple, in a chat, on this machine

**`BUILD-KIT.md`.** Twelve chat windows, about two evenings. You do not need to
be able to code — the chat writes it, you save the files and run one command to
check each phase.

It is a set of instructions, not the finished code. It describes what each part
has to do, which colours to use, what Ripple must never hide from the person
reading its answer, and what each test has to prove — with the reason behind
every rule. Everything you need is in it. There is nothing else to open.

It ends with a working Ripple, and a program you can double-click and hand to
somebody.

### I have built it, and now want to change something

**`BUILD-KIT-REPAIR.md`.** One prompt to paste. Type what is wrong underneath it
and the chat answers with the files to open and where they are saved — every
file that has to change together, not just the obvious one, because the prompt
carries the real dependency graph.

### I have built it, and just want to start it again

No kit needed. From the `Codebase` folder:

```
python -m pip install -r requirements.txt
```
```
python run.py
```

It prints the address it got — read it rather than assuming 8000.

---

## Before anything, on a managed laptop

Three commands, in this order. `BUILD-KIT.md` opens with them and explains what
each one prevents.

```
python -m ensurepip --upgrade --user
```
```
python -m pip config set global.index-url <your company mirror>
```
```
python -m pip install --user sqlglot==30.17.0 fastapi==0.115.0 uvicorn==0.30.6 pydantic==2.13.4 typing-inspection==0.4.2 python-multipart==0.0.9 extract-msg==0.48.7 httpx==0.27.2 pytest==8.3.3
```

**If none of that can reach anything**, `BUILD-KIT.md` has a section called *"If
the install step will not work at all"* with three routes for getting `sqlglot`
onto the machine as files. It is the only package that cannot be worked around —
183 files, 2.7 MB, and it is what makes Ripple more than a word search.

**Python itself:** 3.10 or newer. It was developed on 3.12.

---

## What is in this folder

| | |
|---|---|
| `Codebase/` | The product. Python plus plain HTML, CSS and JavaScript. This is what runs locally and what gets hosted. |
| `Ripple Offline/` | A separate packaging of the same engine as a double-clickable program. Generated from `Codebase`, never forked. |
| `BUILD-KIT.md` | How to build Ripple from nothing, written for a chat. Self-contained. |
| `BUILD-KIT-REPAIR.md` | One prompt that routes a complaint to the right files. Generated — do not edit by hand. |

*`BUILD-KIT-REPAIR.md` is written by `Ripple Offline/tools/make_repair_kit.py`
and checked by `Ripple Offline/tests/test_kits.py`, which reads the real line
counts and dependencies off the code. Edit it by hand and that test fails.*
