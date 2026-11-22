#!/usr/bin/env python3
r"""ST-700 portrait generation tool.

Drives the Perchance AI text-to-image generator in a Chrome you started with
a debugging port, generates portrait batches from editable templates, and saves
the images straight into a folder as
    <category>.<ethnicity>.<age>.<gender>.<N>.jpg
No gallery export, no zip, no "OK" click: images are read directly from the page.

See README.txt for step-by-step instructions.

Examples:
    python st700_portrait_generation_tool.py --ethnicity Indonesian --genders androgyne --dry-run
    python st700_portrait_generation_tool.py --ethnicity Arab,Indian --genders androgyne --out "D:\some\folder"
    python st700_portrait_generation_tool.py --ethnicity Sikh --genders androgyne --categories hydroponic --ages young,adult
"""
import argparse
import base64
import hashlib
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL = "https://perchance.org/ai-text-to-image-generator"
MINUTES_PER_BATCH = 3.0

NEUTRAL = [(r"\bhe\b", "they"), (r"\bshe\b", "they"), (r"\bhis\b", "their"),
           (r"\bhers\b", "theirs"), (r"\bher\b", "their"), (r"\bhim\b", "them"),
           (r"\bhimself\b", "themself"), (r"\bherself\b", "themself")]


# ----------------------------------------------------------------- prompts --
def pick(spec, gender, gclass):
    """A template value is a string or a dict keyed by gender, gender class or 'default'.
    An entry for the exact gender wins, then its class, then 'default'."""
    if isinstance(spec, dict):
        for key in (gender, gclass, "default"):
            if key in spec:
                return spec[key]
        return ""
    return spec


def pick_cat(spec, category, default=""):
    """A value that is a text, or {category: text, 'default': text}."""
    if isinstance(spec, dict):
        return spec.get(category, spec.get("default", default))
    return spec


def apply_rules(cfg, eth_tag, category, gender, gclass, age):
    """Merge the matching ethnic_rules -> (head clause, headgear, suffix, negative prompt)."""
    head, suffix, negative = "", "", []
    headgear = cfg.get("defaults", {}).get("headgear", "")
    for r in cfg.get("ethnic_rules", []):
        if eth_tag not in r.get("ethnicities", []):
            continue
        classes = r.get("classes")
        if classes and gclass not in classes and gender not in classes:
            continue
        if r.get("ages") and age not in r["ages"]:
            continue
        if r.get("negative"):
            negative.append(r["negative"])
        if "head" in r:
            head += pick_cat(r["head"], category)
        if "headgear" in r:
            headgear = pick_cat(r["headgear"], category, headgear)
        if "suffix" in r:
            suffix += pick(r["suffix"], gender, gclass)
    return head, headgear, suffix, ", ".join(negative)


def neutralize(prompt):
    """he/she/his/her/him -> they/their/them, keeping capital letters."""
    for pat, rep in NEUTRAL:
        prompt = re.sub(pat, lambda m, rep=rep: rep.capitalize() if m.group(0)[0].isupper() else rep,
                        prompt, flags=re.IGNORECASE)
    return prompt


def build_prompt(cfg, category, eth_tag, ethnicity, gender, age):
    gclass = cfg["gender_class"].get(gender, gender)
    person = pick(cfg["person"][age], gender, gclass).format(gender=gender)
    clothing = pick(cfg["clothing"].get(age, ""), gender, gclass)
    head, headgear, suffix, negative = apply_rules(cfg, eth_tag, category, gender, gclass, age)
    article = "an" if ethnicity[:1].lower() in "aeiou" else "a"
    prompt = cfg["categories"][category]["template"].format(
        article=article, ethnicity=ethnicity, person=person, gender=gender,
        clothing=clothing, head=head, headgear=headgear, suffix=suffix)
    if gender in cfg.get("neutral_pronoun_genders", []):
        prompt = neutralize(prompt)
    return prompt, negative


def known_ethnicities(cfg):
    return {k: v for k, v in cfg.get("ethnicities", {}).items() if not k.startswith("_")}


def resolve_ethnicity(cfg, name):
    """Accept a file tag or a prompt word (any case). Unknown names are used as typed."""
    known = known_ethnicities(cfg)
    low = name.strip().lower()
    for tag, word in known.items():
        if low in (tag.lower(), word.lower()):
            return tag, word
    return low.replace(" ", ""), name.strip()


def split_list(text):
    return [x.strip() for x in text.split(",") if x.strip()]


def expand(text, universe, what):
    """'All' (any case) -> every option. Otherwise validate each item, case-insensitively."""
    items = split_list(text)
    if any(x.lower() == "all" for x in items):
        return list(universe)
    by_low = {u.lower(): u for u in universe}
    bad = [x for x in items if x.lower() not in by_low]
    if bad:
        sys.exit(f"Unknown {what}: {', '.join(bad)}\nAvailable {what}: "
                 f"{', '.join(universe)}  (or All)")
    return [by_low[x.lower()] for x in items]


def list_options(cfg, what):
    """Print the available options for one parameter (used by the launcher)."""
    if what == "ethnicities":
        for tag, word in known_ethnicities(cfg).items():
            print(f"  {word}")
        print("  (or type any NEW name, e.g. Polynesian)")
    elif what == "genders":
        for g in cfg["gender_class"]:
            print(f"  {g}")
    elif what == "categories":
        for c, spec in cfg["categories"].items():
            print(f"  {c:<11} ages: {', '.join(spec['ages'])}")
    elif what == "ages":
        for age in cfg["person"]:
            cats = [c for c, s in cfg["categories"].items() if age in s["ages"]]
            print(f"  {age:<7} used by: {', '.join(cats) if cats else '(only with All)'}")
        print("  Enter alone = each category's usual ages.")
        print("  'All' = every age in every category (also adds uniform teen).")
    else:
        sys.exit(f"Unknown list: {what}")
    print("  All         = every option above")


def plan_groups(cfg, ethnicities, genders, categories, ages):
    """ethnicities: list of (file_tag, prompt_word)."""
    groups = []
    for eth_tag, eth in ethnicities:
        for cat in categories:
            cat_ages = ages or cfg["categories"][cat]["ages"]
            for age in cat_ages:
                if (age == "child") != (cat == "street"):
                    continue  # street is children only; the others never are
                for gen in genders:
                    prompt, negative = build_prompt(cfg, cat, eth_tag, eth, gen, age)
                    groups.append({
                        "eth": eth, "cat": cat, "age": age, "gender": gen,
                        "prefix": f"{cat}.{eth_tag}.{age}.{gen}",
                        "prompt": prompt, "negative": negative})
    return groups


# ------------------------------------------------------------------- files --
def used_indices(out, prefix):
    rx = re.compile(re.escape(prefix) + r"\.(\d+)\.jpg$", re.IGNORECASE)
    return {int(m.group(1)) for p in out.glob(prefix + ".*.jpg")
            if (m := rx.match(p.name))}


def save_images(out, prefix, images):
    """Save under the lowest free numbers; never overwrite. Returns saved numbers."""
    used = used_indices(out, prefix)
    saved, n = [], 1
    for data in images:
        while n in used:
            n += 1
        dest = out / f"{prefix}.{n}.jpg"
        if dest.exists():  # paranoia: never overwrite
            n += 1
            continue
        dest.write_bytes(data)
        used.add(n)
        saved.append(n)
    return saved


# ----------------------------------------------------------------- browser --
def wait_generator_frame(page, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        for f in page.frames:
            try:
                if f.locator("textarea.paragraph-input").count():
                    return f
            except Exception:
                pass
        page.wait_for_timeout(500)
    raise RuntimeError("Generator frame not found (page changed or blocked?)")


def set_select(frame, text):
    got = frame.evaluate("""(text)=>{
        for (const s of document.querySelectorAll('select')) {
          const o=[...s.options].find(o=>o.text===text);
          if(o){ s.value=o.value; s.dispatchEvent(new Event('change',{bubbles:true}));
                 return s.options[s.selectedIndex].text; }
        }
        return null; }""", text)
    if got != text:
        raise RuntimeError(f"Could not set option {text!r} (got {got!r})")


GET_SRC = ("()=>{const i=document.images[0];"
           "return (i&&i.naturalWidth>0&&i.src.startsWith('data:image'))?i.src:null}")


def collect_images(page, gen, expected, timeout):
    """Scroll each image iframe into view (they lazy-load) until all are loaded."""
    loaded = {}
    end = time.time() + timeout
    last_report = 0
    while time.time() < end:
        n = gen.locator("iframe").count()
        for i in range(n):
            if i in loaded:
                continue
            el = gen.locator("iframe").nth(i)
            try:
                el.scroll_into_view_if_needed(timeout=3000)
                fr = el.element_handle().content_frame()
                src = fr.evaluate(GET_SRC) if fr else None
            except Exception:
                src = None
            if src:
                loaded[i] = src
        if n >= expected and len(loaded) >= expected:
            break
        if time.time() - last_report > 15:
            print(f"      {len(loaded)}/{expected} images ready...", flush=True)
            last_report = time.time()
        page.wait_for_timeout(2500)
    images, seen = [], set()
    for i in sorted(loaded):
        data = base64.b64decode(loaded[i].split(",", 1)[1])
        h = hashlib.sha1(data).hexdigest()
        if h not in seen:  # drop exact duplicates inside a batch
            seen.add(h)
            images.append(data)
    return images


def install_negative_prompt(page, negative):
    """The generator has no negative-prompt box, but every image request carries a
    "negativePrompt" field. Add our text to it. Returns a counter dict."""
    stats = {"rewritten": 0}

    def handler(route, request):
        try:
            data = json.loads(request.post_data or "{}")
            old = (data.get("negativePrompt") or "").strip()
            data["negativePrompt"] = ", ".join(x for x in (old, negative) if x)
            stats["rewritten"] += 1
            route.continue_(post_data=json.dumps(data))
        except Exception:
            route.continue_()

    page.route("**/api/generate*", handler)
    return stats


def generate_batch(browser, cfg, prompt, batch_size, timeout, negative=""):
    page = browser.contexts[0].new_page()
    try:
        neg_stats = install_negative_prompt(page, negative) if negative else None
        page.goto(URL, wait_until="domcontentloaded")
        gen = wait_generator_frame(page)
        # The plus button reveals shape/count but also appends a random phrase
        # to the prompt, so the prompt is filled in AFTER it.
        gen.get_by_role("button", name="➕").first.click()
        page.wait_for_timeout(500)
        set_select(gen, cfg["settings"]["style"])
        set_select(gen, cfg["settings"]["shape"])
        set_select(gen, str(batch_size))
        ta = gen.locator("textarea.paragraph-input:visible").first
        ta.click()
        ta.fill(prompt)
        if ta.input_value() != prompt:
            raise RuntimeError("Prompt text did not stick")
        gen.get_by_role("button", name="generate").first.click()
        page.wait_for_timeout(3000)
        images = collect_images(page, gen, batch_size, timeout)
        if neg_stats is not None:
            n = neg_stats["rewritten"]
            print(f"      negative prompt '{negative}' added to {n} generation request(s)"
                  + ("" if n else "  (WARNING: not applied!)"), flush=True)
        return images
    finally:
        page.close()


# -------------------------------------------------------------------- main --
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ethnicity", default="",
                    help="comma-separated, e.g. Arab,Indian, or All (the list in the templates file)")
    ap.add_argument("--genders", default="male,female,androgyne", help="comma-separated, or All")
    ap.add_argument("--categories", default="all", help="comma-separated, or All (default)")
    ap.add_argument("--ages", default="",
                    help="e.g. teen,young, or All. Default: each category's usual ages")
    ap.add_argument("--list", dest="list_what", default="",
                    help="print the options for ethnicities|genders|categories|ages and exit")
    ap.add_argument("--target", type=int, default=16, help="images wanted per group")
    ap.add_argument("--batch-size", type=int, default=0, help="images per batch (4,6,8,16,32,2)")
    ap.add_argument("--max-batches", type=int, default=3, help="max batches per group")
    ap.add_argument("--keep-extra", action="store_true", help="save every image even beyond target")
    ap.add_argument("--out", default=str(Path.cwd()),
                    help="folder to save images in (default: the current folder)")
    ap.add_argument("--templates", default=str(HERE / "st700_portrait_templates.json"))
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--timeout", type=int, default=600, help="seconds to wait per batch")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and prompts only")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation pause")
    a = ap.parse_args()

    cfg = json.loads(Path(a.templates).read_text(encoding="utf-8"))
    batch_size = a.batch_size or cfg["settings"]["batch_size"]
    if a.list_what:
        list_options(cfg, a.list_what)
        return
    if not a.ethnicity.strip():
        sys.exit("Please give --ethnicity (a name, a comma-separated list, or All).")
    known = known_ethnicities(cfg)
    if any(x.lower() == "all" for x in split_list(a.ethnicity)):
        ethnicities = list(known.items())
    else:
        ethnicities = [resolve_ethnicity(cfg, x) for x in split_list(a.ethnicity)]
    genders = expand(a.genders, list(cfg["gender_class"]), "genders")
    categories = expand(a.categories, list(cfg["categories"]), "categories")
    ages = expand(a.ages, list(cfg["person"]), "ages") if a.ages.strip() else []
    groups = plan_groups(cfg, ethnicities, genders, categories, ages)
    out = Path(a.out)
    if not groups:
        sys.exit("Nothing to do: no valid category/age combination.")

    total_batches = 0
    print(f"\nOutput folder: {out}\nTarget {a.target} per group, batches of {batch_size}\n")
    for g in groups:
        g["have"] = len(used_indices(out, g["prefix"])) if out.exists() else 0
        g["batches"] = 0 if g["have"] >= a.target else -(-(a.target - g["have"]) // batch_size)
        total_batches += g["batches"]
        flag = "skip (complete)" if g["batches"] == 0 else f"{g['batches']} batch(es)"
        print(f"  {g['prefix']:<46} have {g['have']:>3}  -> {flag}")
        print(f"      {g['prompt']}")
        if g["negative"]:
            print(f"      NEGATIVE: {g['negative']}")
    print(f"\n{total_batches} batch(es), about {total_batches * MINUTES_PER_BATCH:.0f} minutes.")
    if a.dry_run or total_batches == 0:
        return
    if not out.exists():
        out.mkdir(parents=True)
        print(f"Created output folder: {out}")
    if not a.yes:
        input("\nCheck the prompts above. Press Enter to start (Ctrl+C aborts)... ")

    from playwright.sync_api import sync_playwright
    summary = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{a.port}")
        except Exception:
            sys.exit(f"Cannot reach Chrome on port {a.port}. Start it with the command "
                     f"shown at the top of this script, then run again.")
        for k, g in enumerate(groups, 1):
            have = len(used_indices(out, g["prefix"]))
            print(f"\n[{k}/{len(groups)}] {g['prefix']}  (have {have})")
            if have >= a.target:
                summary.append((g["prefix"], have, 0, "complete"))
                continue
            added = batches = 0
            while len(used_indices(out, g["prefix"])) < a.target and batches < a.max_batches:
                batches += 1
                need = a.target - len(used_indices(out, g["prefix"]))
                print(f"   batch {batches}: generating {batch_size} (need {need})", flush=True)
                try:
                    imgs = generate_batch(browser, cfg, g["prompt"], batch_size, a.timeout,
                                          g["negative"])
                except Exception as e:
                    print(f"   ERROR: {e}")
                    continue
                imgs = imgs if a.keep_extra else imgs[:need]
                saved = save_images(out, g["prefix"], imgs)
                added += len(saved)
                print(f"   saved {len(saved)} (numbers {saved[:1]}..{saved[-1:]})")
            final = len(used_indices(out, g["prefix"]))
            summary.append((g["prefix"], final, added,
                            "ok" if final >= a.target else f"SHORT by {a.target - final}"))

    print("\n==== Summary ====")
    for name, final, added, status in summary:
        print(f"  {name:<46} {final:>3} files (+{added})  {status}")


if __name__ == "__main__":
    main()
