"""PMC cloudpmc-viewer-pow solver.

PMC's web UI gates `/articles/instance/<num>/bin/<file>` behind a SHA-256
hashcash. This module solves the challenge and injects the cookie so a
`curl_cffi` session can fetch SI binaries from PMC.

Algorithm (extracted from cdn.ncbi.nlm.nih.gov/.../pow-*.js):

    nonce = 0
    while True:
        if sha256((challenge + str(nonce)).encode()).hexdigest().startswith("0" * difficulty):
            break
        nonce += 1
    cookie_value = f"{challenge},{nonce}"

Cookie name: `cloudpmc-viewer-pow`, path `/`, domain `pmc.ncbi.nlm.nih.gov`.
Difficulty observed in 2026-04: 4 (hex zeros) — solves in milliseconds.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional


def solve(challenge: str, difficulty: int = 4) -> int:
    """Find a nonce so sha256(challenge+nonce) starts with `difficulty` hex zeros."""
    target = "0" * difficulty
    nonce = 0
    while True:
        if hashlib.sha256(
            (challenge + str(nonce)).encode()).hexdigest().startswith(target):
            return nonce
        nonce += 1


def parse_pow_page(html: str) -> Optional[dict]:
    """Extract challenge parameters from the 'Preparing to download...' stub."""
    if "POW_CHALLENGE" not in html:
        return None
    m_ch = re.search(r'POW_CHALLENGE\s*=\s*"([^"]+)"', html)
    m_diff = re.search(r'POW_DIFFICULTY\s*=\s*"(\d+)"', html)
    m_name = re.search(r'POW_COOKIE_NAME\s*=\s*"([^"]+)"', html)
    m_path = re.search(r'POW_COOKIE_PATH\s*=\s*"([^"]+)"', html)
    if not (m_ch and m_diff and m_name):
        return None
    return {
        "challenge": m_ch.group(1),
        "difficulty": int(m_diff.group(1)),
        "cookie_name": m_name.group(1),
        "cookie_path": m_path.group(1) if m_path else "/",
    }


def _retrying_get(session, url: str, headers: dict, attempts: int = 5):
    """curl_cffi can throw transient TLS errors against NCBI. Retry with backoff."""
    import time
    last_err = None
    for i in range(attempts):
        try:
            return session.get(url, headers=headers, timeout=60)
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(2.0 * (i + 1))  # 2,4,6,8s — total ~20s budget
    raise last_err


def _is_recaptcha_page(content: bytes) -> bool:
    """PMC sometimes fronts /articles/instance/<num>/bin/<file> with reCAPTCHA
    on the first request — same session's second request goes through to the
    actual binary."""
    return b"recaptcha" in content[:2000].lower(
    ) or b"challengepage" in content[:2000].lower()


def fetch_with_pow(session,
                   url: str,
                   referer: Optional[str] = None,
                   max_pow_cycles: int = 3,
                   max_recaptcha_retries: int = 2):
    """Fetch a URL via a curl_cffi Session, transparently solving PMC's two
    independent gates:

      1. **SHA-256 hashcash PoW** — 'Preparing to download...' stub (~1.8 KB)
         containing a challenge string. A real browser solves it via JS and
         sets `cloudpmc-viewer-pow=<challenge>,<nonce>`. We replicate that.
      2. **reCAPTCHA challenge** — a ~20 KB HTML page served on the first
         request to a binary URL when the session lacks proper warm-up. The
         challenge itself sets cookies; the SAME session's next request to
         the same URL passes through to the binary.

    Strategy: retry the SAME URL within the SAME session until either we get
    a non-gate response, or we exhaust the retry budgets.
    """
    headers = {"Referer": referer} if referer else {}
    r = _retrying_get(session, url, headers)

    pow_cycles = 0
    recaptcha_retries = 0
    while True:
        if r.status_code != 200:
            return r
        # PoW gate
        if b"POW_CHALLENGE" in r.content and pow_cycles < max_pow_cycles:
            info = parse_pow_page(r.text)
            if not info:
                return r
            nonce = solve(info["challenge"], info["difficulty"])
            session.cookies.set(
                info["cookie_name"],
                f"{info['challenge']},{nonce}",
                domain="pmc.ncbi.nlm.nih.gov",
                path=info["cookie_path"],
            )
            pow_cycles += 1
            r = _retrying_get(session, url, headers)
            continue
        # reCAPTCHA gate — just retry the same URL with the cookies the
        # challenge page already set on us
        if _is_recaptcha_page(r.content) and recaptcha_retries < max_recaptcha_retries:
            recaptcha_retries += 1
            r = _retrying_get(session, url, headers)
            continue
        return r
