#!/usr/bin/env python3
"""Read the Brauns Fam pool on CBS Sports Pick'em with a real browser (Playwright), on the GitHub runner.
Credentials come only from environment variables (CBS_USERNAME / CBS_PASSWORD, set as repository secrets).
They are never printed, never written to disk, never committed.

    python3 scrape_cbs.py --mode discover   # log in, save standings/picks pages to out/ for parser development
    python3 scrape_cbs.py --mode scrape     # (later) parse standings + revealed picks and write standings.json / pool_picks.csv

Pool: https://picks.cbssports.com/football/pickem/pools/<POOL_ID>/...
"""
import argparse, os, sys, time, re
from playwright.sync_api import sync_playwright

POOL_ID = os.environ.get("CBS_POOL_ID", "kbxw63b2ge3dknjtgq4de===")
BASE = f"https://picks.cbssports.com/football/pickem/pools/{POOL_ID}"
OUT = "out"

def log(msg): print(time.strftime("%H:%M:%S"), msg, flush=True)

def save(page, name):
    os.makedirs(OUT, exist_ok=True)
    page.screenshot(path=f"{OUT}/{name}.png", full_page=True)
    open(f"{OUT}/{name}.html", "w").write(page.content())
    log(f"saved {name}: url={page.url} title={page.title()!r}")

def describe(page, label):
    """Structural summary of the current page, printed to the log (no values, no credentials)."""
    inputs = page.eval_on_selector_all("input", "els => els.map(e => [e.type, e.name, e.id, e.placeholder, !!(e.offsetWidth||e.offsetHeight)].join('|'))")
    buttons = page.eval_on_selector_all("button, input[type=submit], a[role=button]", "els => els.map(e => (e.innerText||e.value||'').trim().slice(0,30)).filter(Boolean)")
    frames = page.eval_on_selector_all("iframe", "els => els.map(e => (e.src||'').split('/')[2]||'')")
    text = page.inner_text("body")[:20000].lower()
    hits = [w for w in ("incorrect", "invalid", "error", "verify", "verification", "code", "captcha", "robot", "try again", "locked", "two-step", "2-step") if w in text]
    log(f"[{label}] inputs={inputs}")
    log(f"[{label}] buttons={buttons[:15]}")
    log(f"[{label}] iframes={frames[:10]}")
    log(f"[{label}] keyword hits={hits}")
    for w in ("incorrect", "invalid", "verify", "captcha", "robot", "code"):
        i = text.find(w)
        if i >= 0: log(f"[{label}] context '{w}': ...{text[max(0,i-120):i+120]!r}...")

def login(page, user, pw):
    page.goto(f"{BASE}/standings", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    log(f"landing url={page.url}")
    if "login" not in page.url.lower() and page.locator("input[type=password]").count() == 0:
        # maybe a sign-in button first
        for sel in ("text=Log In", "text=Sign In", "text=Log in", "text=Sign in", "a[href*='login']"):
            if page.locator(sel).count():
                page.locator(sel).first.click(); page.wait_for_timeout(3000); log(f"clicked {sel} -> {page.url}"); break
    describe(page, "login page")
    pwd = page.locator("input[type=password]")
    if pwd.count() == 0:
        log("no password field found; saving page for inspection"); save(page, "no_login_form"); return False
    # the username field is the visible text/email input that is not the password
    cand = page.locator("input[type=email], input[type=text], input[name*=user], input[name*=email], input[id*=user], input[id*=email]")
    filled = False
    for i in range(cand.count()):
        el = cand.nth(i)
        if el.is_visible():
            el.fill(user); filled = True; break
    if not filled: log("no username field found"); save(page, "no_username_field"); return False
    pwd.first.fill(pw)
    submit = page.locator("button[type=submit], input[type=submit], button:has-text('Sign In'), button:has-text('Log In'), button:has-text('Continue')")
    if submit.count():
        log(f"clicking submit button ({submit.count()} candidates)"); submit.first.click()
    else:
        log("no submit button; pressing Enter"); pwd.first.press("Enter")
    try:
        page.wait_for_url(lambda u: "login" not in u.lower(), timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(4000)
    log(f"after submit url={page.url}")
    describe(page, "after submit")
    if page.locator("input[type=password]").count() and "login" in page.url.lower():
        log("still on a login page after submit (bad credentials, a challenge, or a code prompt)"); save(page, "login_failed"); return False
    return True

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--mode", default="discover"); a = ap.parse_args()
    user, pw = os.environ.get("CBS_USERNAME"), os.environ.get("CBS_PASSWORD")
    if not user or not pw: sys.exit("CBS_USERNAME / CBS_PASSWORD not set (repository secrets)")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 1600}, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36")
        page = ctx.new_page()
        ok = login(page, user, pw)
        log(f"login ok={ok}")
        if not ok: browser.close(); sys.exit(2)
        for name, url in (("standings", f"{BASE}/standings"), ("standings_weekly", f"{BASE}/standings?view=weekly"),
                          ("picks", f"{BASE}/picks"), ("pool_home", f"{BASE}")):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000); page.wait_for_timeout(4000); save(page, name)
            except Exception as e:
                log(f"{name}: {e.__class__.__name__}")
        # links on the pool page, to learn the site's structure (paths only)
        hrefs = sorted({re.sub(r"\?.*", "", h) for h in page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))") if h and "pools" in h})
        log("pool links: " + " | ".join(hrefs[:40]))
        browser.close()

if __name__ == "__main__":
    main()
