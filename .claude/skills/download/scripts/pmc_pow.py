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


def fetch_with_pow(session, url: str, referer: Optional[str] = None):
    """Fetch a URL via a curl_cffi Session, transparently solving PMC PoW.

    The 'Preparing to download...' stub is ~1.8 KB and contains the challenge
    inline; a real browser executes JS, sets `cloudpmc-viewer-pow=<challenge>,<nonce>`,
    then reloads. We replicate that without JS.

    Includes brief retry for transient TLS handshake failures against NCBI.
    """
    headers = {"Referer": referer} if referer else {}
    r = _retrying_get(session, url, headers)
    if r.status_code != 200 or b"POW_CHALLENGE" not in r.content:
        return r
    info = parse_pow_page(r.text)
    if not info:
        return r
    nonce = solve(info["challenge"], info["difficulty"])
    cookie_value = f"{info['challenge']},{nonce}"
    session.cookies.set(
        info["cookie_name"],
        cookie_value,
        domain="pmc.ncbi.nlm.nih.gov",
        path=info["cookie_path"],
    )
    return _retrying_get(session, url, headers)
