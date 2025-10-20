#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
readme_extractor.py — Phase 1++
Batch extraction from README.pdf:
- Convert PDF to text (prefer pdfminer.six, fallback to PyPDF2)
- Identify fragments like "Declaration (I/We certify …)" and "Data Availability/Source"
- Extract: dataset names / filenames, collection period, source organization, URLs
- Output to CSV / JSONL
- Sample limit and strategy; optional visualization output

Usage:
python readme_extractor.py \
  --input-dir data/readmes --glob "*.pdf" \
  --out-csv outputs/results.csv --out-jsonl outputs/results.jsonl \
  --save-text --max-samples 200 --sample-mode random --seed 42 --viz
"""

import argparse, json, re, sys, random
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# -------- PDF to text ---------
def _pdfminer_extract(path: str) -> str:
    try:
        from pdfminer.high_level import extract_text
    except Exception:
        try:
            from pdfminer.high_level import extract_text
        except Exception:
            extract_text = None
    try:
        if extract_text is None:
            return ""
        return extract_text(path)
    except Exception:
        return ""

def _pypdf_extract(path: str) -> str:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        out = []
        for p in reader.pages:
            try:
                out.append(p.extract_text() or "")
            except Exception:
                pass
        return "\n".join(out)
    except Exception:
        return ""

def pdf_to_text(path: str) -> str:
    txt = _pdfminer_extract(path)
    if not txt or len(txt.strip()) < 60:
        txt = _pypdf_extract(path)
    return txt or ""

# -------- Preprocessing & regex ---------
def normalize_text(t: str) -> str:
    t = t.replace("\r", "\n")
    t = re.sub(r"-\n", "", t)
    t = re.sub(r"\u2013|\u2014|\u2212", "-", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t

# -------- Sampling & Visualization ---------
def select_sample(paths: List[Path], max_samples: int, mode: str, seed: int) -> List[Path]:
    if max_samples is None or max_samples <= 0 or max_samples >= len(paths):
        return paths
    if mode == "first":
        return paths[:max_samples]
    rnd = random.Random(seed)
    return rnd.sample(paths, k=max_samples)

def _try_import_matplotlib():
    try:
        import matplotlib.pyplot as plt  # Use default style
        return plt
    except Exception:
        return None

def _domain_of(url: str) -> str:
    from urllib.parse import urlparse
    try:
        netloc = urlparse(url).netloc or ""
        return netloc.lower()
    except Exception:
        return ""

def save_visualizations(records: List[Dict[str, Any]], out_dir: Path, topk: int = 20) -> None:
    """
    Generate summary charts from in-memory records
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    plt = _try_import_matplotlib()
    if plt is None:
        print("[!] matplotlib not installed. Please run `pip install matplotlib`", file=sys.stderr)
        return

    from collections import Counter

    # Counters
    source_counter = Counter()
    dataset_counter = Counter()
    domain_counter = Counter()
    url_count_list = []
    year_list = []
    needs_review_counter = Counter()
    has_decl_counter = Counter()
    has_avail_counter = Counter()

    year_re = re.compile(r"\b(19|20)\d{2}\b")

    for r in records:
        # sources
        for s in (r.get("sources_mentions") or []):
            if s:
                source_counter[s] += 1
        # datasets
        for ds in (r.get("dataset_candidates") or []):
            if ds:
                dataset_counter[ds] += 1
        # url count and domain
        urls = r.get("urls") or []
        url_count_list.append(len(urls))
        for u in urls:
            d = _domain_of(u)
            if d:
                domain_counter[d] += 1
        # years
        times = r.get("time_mentions") or []
        for t in times:
            for y in year_re.findall(t):
                pass  # findall returns ("19","20") prefixes — skip
            for y2 in re.findall(r"\b((?:19|20)\d{2})\b", t):
                year_list.append(int(y2))
        # flags
        needs_review_counter[str(bool(r.get("needs_review")))] += 1
        has_decl_counter[str(bool(r.get("has_declaration")))] += 1
        has_avail_counter[str(bool(r.get("availability_section_found")))] += 1

    # — Chart 1: TopK Sources
    if source_counter:
        top_s = source_counter.most_common(topk)
        labels, vals = zip(*top_s)
        plt.figure()
        plt.barh(range(len(vals)), vals)
        plt.yticks(range(len(vals)), labels)
        plt.xlabel("Count")
        plt.title(f"Top {topk} Sources")
        plt.tight_layout()
        plt.savefig(out_dir / "sources_top20.png", dpi=160)
        plt.close()

    # — Chart 2: TopK Datasets
    if dataset_counter:
        top_d = dataset_counter.most_common(topk)
        labels, vals = zip(*top_d)
        plt.figure()
        plt.barh(range(len(vals)), vals)
        plt.yticks(range(len(vals)), labels)
        plt.xlabel("Count")
        plt.title(f"Top {topk} Dataset Candidates")
        plt.tight_layout()
        plt.savefig(out_dir / "datasets_top20.png", dpi=160)
        plt.close()

    # — Chart 3: TopK URL domains
    if domain_counter:
        top_dom = domain_counter.most_common(topk)
        labels, vals = zip(*top_dom)
        plt.figure()
        plt.barh(range(len(vals)), vals)
        plt.yticks(range(len(vals)), labels)
        plt.xlabel("Count")
        plt.title(f"Top {topk} URL Domains")
        plt.tight_layout()
        plt.savefig(out_dir / "domains_top20.png", dpi=160)
        plt.close()

    # — Chart 4: Histogram of URLs per file
    if url_count_list:
        plt.figure()
        plt.hist(url_count_list, bins=min(20, max(5, len(set(url_count_list)))))
        plt.xlabel("URLs per file")
        plt.ylabel("Frequency")
        plt.title("Distribution of URL Counts per PDF")
        plt.tight_layout()
        plt.savefig(out_dir / "urls_per_file_hist.png", dpi=160)
        plt.close()

    # — Chart 5: Year mentions histogram
    if year_list:
        bins = sorted(set(year_list))
        if len(bins) >= 2:
            plt.figure()
            plt.hist(year_list, bins=range(min(year_list), max(year_list) + 2))
            plt.xlabel("Year mentioned")
            plt.ylabel("Frequency")
            plt.title("Histogram of Mentioned Years")
            plt.tight_layout()
            plt.savefig(out_dir / "years_hist.png", dpi=160)
            plt.close()

    # — Chart 6: needs_review bar chart
    if needs_review_counter:
        labels = list(needs_review_counter.keys())
        vals = [needs_review_counter[k] for k in labels]
        plt.figure()
        plt.bar(labels, vals)
        plt.xlabel("needs_review")
        plt.ylabel("Count")
        plt.title("Files Marked as Needs Review")
        plt.tight_layout()
        plt.savefig(out_dir / "needs_review_bar.png", dpi=160)
        plt.close()
