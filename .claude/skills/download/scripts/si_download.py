"""Download Supporting Information for an academic paper by DOI.

Dispatches by publisher prefix and uses the right HTTP client per host:
  * `curl_cffi` (Chrome impersonation) for hosts behind Cloudflare TLS-fingerprint
    checks that demand a real browser TLS stack — ACS, PNAS PoW page, PMC web UI.
  * Plain `urllib` for hosts where curl_cffi gets scored MORE suspicious than
    plain curl (Cloudflare bot scoring) — bioRxiv, NCBI eutils, Europe PMC,
    Springer, RSC.

When NCBI eutils is unreachable we fall back to Europe PMC's REST API.

Usage as a module:
    from si_download import download
    saved = download("10.1021/jacs.6b12265", "papers/bhowmick_2017/")

Usage from CLI:
    python si_download.py <DOI> <output_dir>

Requires:
    pip install curl_cffi
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Iterable, List, Optional
import urllib.parse
import urllib.request

from curl_cffi import requests as cffi_requests

try:
    from .pmc_pow import fetch_with_pow
except ImportError:
    from pmc_pow import fetch_with_pow

CHROME_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
REFERER_GOOGLE = {"Referer": "https://www.google.com/"}


def _make_cffi_session():
    """curl_cffi session with Chrome TLS fingerprint — for Cloudflare-fronted hosts."""
    return cffi_requests.Session(impersonate="chrome")


def _plain_get(url: str,
               referer: Optional[str] = None,
               timeout: int = 60,
               attempts: int = 3) -> bytes:
    """Fetch via stdlib urllib with retry on transient TLS/timeout failures."""
    import time as _time
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": CHROME_UA,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            **({
                "Referer": referer
            } if referer else {}),
        },
    )
    last_err = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    data = gzip.decompress(data)
                return data
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                _time.sleep(2.0 * (i + 1))
    raise last_err


def _plain_get_text(url: str, referer: Optional[str] = None, timeout: int = 60) -> str:
    return _plain_get(url, referer, timeout).decode("utf-8", errors="replace")


def _curl_get(url: str, referer: Optional[str] = None, timeout: int = 60) -> bytes:
    """Fetch via system curl. Use for hosts where urllib's TLS stack gets 403'd
    by Cloudflare bot scoring (notably bioRxiv) but bash curl + browser UA passes.
    """
    cmd = [
        "/usr/bin/curl",
        "-sL",
        "--compressed",
        "--max-time",
        str(timeout),
        "-A",
        CHROME_UA,
    ]
    if referer:
        cmd.extend(["-H", f"Referer: {referer}"])
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, timeout=timeout + 30)
    if result.returncode != 0:
        raise RuntimeError(
            f"curl failed: rc={result.returncode} stderr={result.stderr[:200]!r}")
    return result.stdout


def _curl_get_text(url: str, referer: Optional[str] = None, timeout: int = 60) -> str:
    return _curl_get(url, referer, timeout).decode("utf-8", errors="replace")


# ---------- Springer / Nature ----------


def download_springer_si(doi: str, out_dir: str) -> List[str]:
    suffix = doi.split("/", 1)[1]
    article_url = f"https://www.nature.com/articles/{suffix}"
    try:
        html = _plain_get_text(article_url,
                               referer="https://www.google.com/",
                               timeout=60)
    except Exception:
        return []
    links = sorted(
        set(
            re.findall(
                r'href="(https://static-content\.springer\.com/esm/[^"]+\.(?:pdf|zip|docx|xlsx))"',
                html,
            )))
    saved: List[str] = []
    for url in links:
        fname = url.rsplit("/", 1)[-1]
        try:
            data = _plain_get(url, timeout=180)
        except Exception:
            continue
        if len(data) > 100:
            path = os.path.join(out_dir, f"SI_{fname}")
            with open(path, "wb") as f:
                f.write(data)
            saved.append(path)
    return saved


# ---------- RSC ----------


def _cffi_fetch_resilient(url: str,
                          headers: dict,
                          attempts: int = 6,
                          timeout: int = 180):
    """Retry curl_cffi.get against transient TLS / mid-stream failures.

    Each attempt creates a FRESH Session so a stuck TLS state from the previous
    attempt cannot poison the next one. Returns the response on success;
    raises the last exception if all attempts fail.
    """
    import time
    last_err = None
    for i in range(attempts):
        try:
            s = _make_cffi_session()
            r = s.get(url, headers=headers, timeout=timeout)
            return r
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                time.sleep(2.0 * (i + 1))
    raise last_err


def download_rsc_si(doi: str, out_dir: str) -> List[str]:
    """RSC pattern: https://www.rsc.org/suppdata/{ab}/{j}/{base}/{base}{N}.pdf

    RSC's `suppdata/` path is TLS-fingerprint-gated — plain curl/urllib get
    silently time out, but curl_cffi with Chrome impersonate works. RSC's
    edge sometimes stalls mid-stream; we retry with a fresh Session each time
    to escape any half-open connection state.
    """
    basename = doi.split("/", 1)[1].lower()
    ab = basename[:2]
    journal_match = re.match(r"^[a-z]\d*([a-z]+)\d", basename)
    journal = journal_match.group(1) if journal_match else basename[1:3]
    saved: List[str] = []
    for i in range(1, 10):
        url = f"https://www.rsc.org/suppdata/{ab}/{journal}/{basename}/{basename}{i}.pdf"
        try:
            r = _cffi_fetch_resilient(url, headers=REFERER_GOOGLE)
        except Exception:
            break
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            path = os.path.join(out_dir, f"SI_{basename}{i}.pdf")
            with open(path, "wb") as f:
                f.write(r.content)
            saved.append(path)
        else:
            break
    return saved


# ---------- bioRxiv ----------


def download_biorxiv_si(doi: str, out_dir: str) -> List[str]:
    """bioRxiv 403s urllib (TLS stack mismatch) but accepts bash curl with Chrome UA.
    Shell out to /usr/bin/curl rather than fight Python's TLS.
    """
    suffix = doi.split("/", 1)[1]
    landing = f"https://www.biorxiv.org/content/10.1101/{suffix}v1.supplementary-material"
    try:
        html = _curl_get_text(landing, referer="https://www.biorxiv.org/", timeout=60)
    except Exception:
        return []
    media = re.findall(r'href="(https?://[^"]*?/DC1/embed/[^"]+)"', html)
    saved: List[str] = []
    for url in media:
        clean = url.split("?")[0]
        fname = clean.rsplit("/", 1)[-1]
        try:
            data = _curl_get(url, referer="https://www.biorxiv.org/", timeout=180)
        except Exception:
            continue
        if len(data) > 100 and (data[:4] == b"%PDF" or data[:2] == b"PK"):
            path = os.path.join(out_dir, f"SI_{fname}")
            with open(path, "wb") as f:
                f.write(data)
            saved.append(path)
    return saved


# ---------- ACS / PNAS via PMC + direct ACS ----------


def lookup_pmcid(doi: str) -> Optional[str]:
    """Resolve DOI -> PMCID. Tries NCBI idconv, falls back to Europe PMC search."""
    # NCBI idconv (legacy URL — may redirect to broken endpoint)
    try:
        text = _plain_get_text(
            f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={doi}&format=json",
            timeout=20,
        )
        m = re.search(r'"pmcid":"(PMC\d+)"', text)
        if m:
            return m.group(1)
    except Exception:
        pass

    # Europe PMC search fallback
    try:
        encoded = urllib.parse.quote(doi, safe="")
        text = _plain_get_text(
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{encoded}&format=json&resultType=core",
            timeout=30,
        )
        d = json.loads(text)
        for r in d.get("resultList", {}).get("result", [])[:1]:
            pmcid = r.get("pmcid")
            if pmcid:
                return pmcid
    except Exception:
        pass
    return None


def get_oa_tarball_url(pmcid: str) -> Optional[str]:
    """Return https tarball URL (deprecated path) if PMC marks the article OA."""
    try:
        text = _plain_get_text(
            f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}&format=tgz",
            timeout=30,
        )
    except Exception:
        return None
    m = re.search(r'href="(ftp://[^"]+\.tar\.gz)"', text)
    if not m:
        return None
    return m.group(1).replace(
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/",
        "https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_package/",
    )


def get_europe_pmc_supplementary_zip(pmcid: str) -> Optional[bytes]:
    """Europe PMC's supplementaryFiles endpoint returns a ZIP for OA articles."""
    try:
        data = _plain_get(
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/supplementaryFiles",
            timeout=120,
        )
    except Exception:
        return None
    if data[:2] == b"PK":
        return data
    return None


def _is_si_member(name: str) -> bool:
    bn = os.path.basename(name).lower()
    return any(k in bn for k in ("si_", "supplement", "appendix", "sapp", "_supp"))


def extract_si_from_tarball(tar_bytes: bytes, out_dir: str) -> List[str]:
    saved: List[str] = []
    with tempfile.TemporaryDirectory() as td:
        tar_path = os.path.join(td, "pkg.tar.gz")
        with open(tar_path, "wb") as f:
            f.write(tar_bytes)
        with tarfile.open(tar_path) as tf:
            for m in tf.getnames():
                if _is_si_member(m):
                    tf.extract(m, td)
                    src = os.path.join(td, m)
                    dst = os.path.join(out_dir, f"SI_{os.path.basename(m)}")
                    shutil.copy(src, dst)
                    saved.append(dst)
    return saved


def extract_si_from_zip(zip_bytes: bytes, out_dir: str) -> List[str]:
    """Europe PMC supplementaryFiles returns flat ZIP with SI files at top level."""
    import io
    import zipfile
    saved: List[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            bn = os.path.basename(name)
            if not bn:
                continue
            # Skip thumbnails/figures, keep SI-like files
            if not (_is_si_member(bn) or bn.lower().endswith(
                (".pdf", ".xlsx", ".docx", ".zip"))):
                continue
            # Skip raster figures
            if bn.lower().endswith((".jpg", ".jpeg", ".gif", ".png", ".tif", ".tiff")):
                continue
            data = zf.read(name)
            dst = os.path.join(out_dir, f"SI_{bn}")
            with open(dst, "wb") as f:
                f.write(data)
            saved.append(dst)
    return saved


def find_pmc_si_filenames(pmcid: str) -> List[str]:
    """Discover SI filenames by parsing PMC article XML.

    Tries NCBI eutils efetch first, falls back to Europe PMC fullTextXML.
    Returns empty list if both fail (caller should fall back to heuristic candidates).
    """
    sources = [
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmcid}",
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
    ]
    for url in sources:
        try:
            text = _plain_get_text(url, timeout=60)
        except Exception:
            continue
        if "<supplementary-material" not in text and "xlink:href" not in text:
            continue
        sections = re.findall(
            r'<supplementary-material[^>]*>(.*?)</supplementary-material>',
            text,
            re.S,
        )
        names: set[str] = set()
        for sec in sections:
            names.update(re.findall(r'xlink:href="([^"]+)"', sec))
        if not names:
            names.update(
                re.findall(
                    r'xlink:href="([^"]*(?:si_|supplement|appendix)[^"]+)"',
                    text,
                    re.I,
                ))
        if names:
            return sorted(names)
    return []


def heuristic_pmc_si_filenames(doi: str, pmcid: str) -> List[str]:
    """Generate likely SI filenames when XML discovery fails.

    Patterns observed:
      ACS NIH author manuscript: `nihmsXXXXX-supplement-N.pdf` (XXXXX hard to guess)
      ACS direct on PMC:         `<journal_suffix>_si_001.pdf` (e.g. ja4c09428_si_001.pdf)
      PNAS legacy:               `<numeric_pubid>_Appendix.pdf` or `_SI.pdf`
    """
    cands: List[str] = []
    if doi.startswith("10.1021/"):
        suffix = doi.split("/", 1)[1].replace(".", "")  # ja4c09428 from jacs.4c09428
        # Some ACS journals keep dotted DOI; normalize
        for n in (1, 2, 3):
            cands.append(f"{suffix}_si_{n:03d}.pdf")
    elif doi.startswith("10.1073/pnas."):
        pubid = doi.split("/pnas.", 1)[1]  # numeric ID
        cands.extend([
            f"{pubid}_Appendix.pdf",
            f"{pubid}_SI.pdf",
            f"pnas.{pubid}.sapp.pdf",
        ])
    return cands


def download_pmc_si(pmcid: str, out_dir: str, doi: Optional[str] = None) -> List[str]:
    # 1) Try OA tarball from NCBI (sanctioned, contains everything)
    oa_url = get_oa_tarball_url(pmcid)
    if oa_url:
        try:
            data = _plain_get(oa_url, timeout=180)
            if data[:2] == b"\x1f\x8b" and len(data) > 5000:
                return extract_si_from_tarball(data, out_dir)
        except Exception:
            pass

    # 2) Try Europe PMC supplementaryFiles ZIP (also OA-only, but uses different host)
    zip_data = get_europe_pmc_supplementary_zip(pmcid)
    if zip_data:
        return extract_si_from_zip(zip_data, out_dir)

    # 3) Non-OA: solve PMC PoW and probe `/articles/instance/<num>/bin/<file>`
    pmcnum = pmcid[3:]
    s = _make_cffi_session()
    article = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
    try:
        fetch_with_pow(s, article, "https://www.google.com/")  # warm-up
    except Exception:
        pass  # warm-up failure is non-fatal — pre-existing cookies may suffice

    candidates = find_pmc_si_filenames(pmcid)
    if not candidates and doi:
        candidates = heuristic_pmc_si_filenames(doi, pmcid)
    if not candidates:
        return []

    saved: List[str] = []
    for fname in candidates:
        url = f"https://pmc.ncbi.nlm.nih.gov/articles/instance/{pmcnum}/bin/{fname}"
        try:
            r = fetch_with_pow(s, url, article)
        except Exception:
            continue  # transient TLS failure — skip this candidate
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            path = os.path.join(out_dir, f"SI_{fname}")
            with open(path, "wb") as f:
                f.write(r.content)
            saved.append(path)
    return saved


def download_acs_direct_si(doi: str, out_dir: str) -> List[str]:
    """ACS landing pages list SI as `/doi/suppl/{DOI}/suppl_file/{name}`.

    SI files themselves are NOT paywalled — only the article PDF is.
    Cloudflare blocks plain curl, so use curl_cffi here.
    """
    s = _make_cffi_session()
    article_url = f"https://pubs.acs.org/doi/{doi}"
    try:
        html = s.get(article_url, headers=REFERER_GOOGLE, timeout=60).text
    except Exception:
        return []
    paths = sorted(set(re.findall(r'/doi/suppl/[^"\s<>]+', html)))
    saved: List[str] = []
    for p in paths:
        url = f"https://pubs.acs.org{p}"
        fname = url.rsplit("/", 1)[-1]
        try:
            r = s.get(url, headers={"Referer": article_url}, timeout=180)
        except Exception:
            continue
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            out = os.path.join(out_dir, f"SI_{fname}")
            with open(out, "wb") as f:
                f.write(r.content)
            saved.append(out)
    return saved


# ---------- Top-level dispatcher ----------


def download(doi: str, out_dir: str) -> List[str]:
    """Download SI for a DOI into out_dir. Returns list of saved paths."""
    os.makedirs(out_dir, exist_ok=True)

    if doi.startswith("10.1038/"):
        return download_springer_si(doi, out_dir)
    if doi.startswith("10.1039/"):
        return download_rsc_si(doi, out_dir)
    if doi.startswith("10.1101/"):
        return download_biorxiv_si(doi, out_dir)

    if doi.startswith("10.1021/"):
        # Try ACS landing first (publicly accessible SI for most ACS papers)
        saved = download_acs_direct_si(doi, out_dir)
        if saved:
            return saved
        # Fall through to PMC for NIH author manuscripts
        pmcid = lookup_pmcid(doi)
        if pmcid:
            return download_pmc_si(pmcid, out_dir, doi=doi)
        return []

    if doi.startswith("10.1073/"):
        pmcid = lookup_pmcid(doi)
        if not pmcid:
            return []
        return download_pmc_si(pmcid, out_dir, doi=doi)

    raise ValueError(f"No SI handler for DOI prefix: {doi}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python si_download.py <DOI> <output_dir>", file=sys.stderr)
        sys.exit(1)
    saved = download(sys.argv[1], sys.argv[2])
    if saved:
        for p in saved:
            print(p)
    else:
        print("(no SI files found)", file=sys.stderr)
        sys.exit(2)
