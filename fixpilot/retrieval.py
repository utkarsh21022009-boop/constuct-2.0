"""Retrieval engine for FixPilot AI industrial equipment documentation."""

import re
import math
from typing import List, Dict, Tuple, Optional
from fixpilot.models import Passage, Citation, Manual
from fixpilot.knowledge_base import KnowledgeBase


STOP_WORDS = {
    "a", "an", "the", "and", "or", "is", "in", "at", "of", "to", "for", "with",
    "on", "by", "from", "up", "about", "into", "over", "after", "it", "this",
    "that", "these", "those", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "can", "could", "should", "would",
    "how", "what", "why", "where", "when", "which", "who", "i", "we", "you", "my"
}

# Industrial synonyms & symptom aliases for enhanced matching
SYNONYM_MAP = {
    "overcurrent": ["overload", "high current", "igbt", "trip", "current"],
    "jam": ["stuck", "obstruction", "blockage", "product pileup"],
    "sensor": ["photocell", "photoeye", "proximity", "pe-04", "transducer"],
    "interlock": ["safety switch", "door switch", "guard switch", "light curtain"],
    "leak": ["leakage", "fluid bypass", "seal failure", "pressure loss"],
    "pressure": ["bar", "psi", "hydraulic", "accumulator", "pneumatic"],
    "spindle": ["motor", "drive", "rotation", "rpm", "bearing"],
    "temperature": ["temp", "overheat", "thermal", "cooling", "deg c"]
}


def tokenize(text: str) -> List[str]:
    """Tokenize and normalize text into clean alphanumeric terms."""
    if not text:
        return []
    # Keep hyphenated codes like P-102, H-405, ALM-304 intact or split
    tokens = re.findall(r'[a-zA-Z0-9_\-]+', text.lower())
    clean_tokens = []
    for t in tokens:
        # Also split hyphens for sub-token matching (e.g. "p-102" -> "p-102", "p", "102")
        clean_tokens.append(t)
        if "-" in t:
            parts = t.split("-")
            clean_tokens.extend([p for p in parts if len(p) > 1])
    return clean_tokens


def extract_potential_error_codes(query: str) -> List[str]:
    """Extract industrial error codes from query text (e.g. 304, P-102, H-405, ALM-112)."""
    patterns = [
        r'\b[a-zA-Z]{1,4}[-_]?[0-9]{2,4}\b',  # P-102, ALM-304, H-405, E112
        r'\balarm\s+([0-9]{2,4})\b',          # alarm 304
        r'\bfault\s+([a-zA-Z0-9\-_]+)\b',     # fault P-102
        r'\berror\s+([a-zA-Z0-9\-_]+)\b',     # error 304
        r'\b([0-9]{3,4})\b'                   # raw numbers like 304, 112
    ]
    codes = set()
    q_clean = query.strip()
    for pat in patterns:
        matches = re.finditer(pat, q_clean, re.IGNORECASE)
        for m in matches:
            code = m.group(1) if m.groups() else m.group(0)
            codes.add(code.upper().strip())
            # Normalize variations: "ALM-304" -> "304", "P-102" -> "P102"
            num_only = re.sub(r'[^0-9]', '', code)
            if num_only:
                codes.add(num_only)
    return list(codes)


class DocumentRetriever:
    """Industrial document search & evidence retrieval engine."""

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self._build_index()

    def _build_index(self):
        """Build term-frequency index across all approved passages."""
        self.doc_count = len(self.kb.all_passages)
        self.df: Dict[str, int] = {}
        self.passage_tokens: Dict[str, List[str]] = {}
        self.passage_error_codes: Dict[str, List[str]] = {}

        for p in self.kb.all_passages:
            tokens = tokenize(p.content) + tokenize(p.section_title) + [k.lower() for k in p.keywords]
            tokens = [t for t in tokens if t not in STOP_WORDS]
            self.passage_tokens[p.passage_id] = tokens
            self.passage_error_codes[p.passage_id] = [c.upper() for c in p.error_codes]

            unique_terms = set(tokens)
            for term in unique_terms:
                self.df[term] = self.df.get(term, 0) + 1

    def retrieve(self, query: str, machine_filter: Optional[str] = None, top_k: int = 5) -> List[Tuple[Passage, float, Citation]]:
        """
        Retrieve top-k relevant manual passages given technician query.
        Returns list of (Passage, score, Citation).
        """
        query_tokens = [t for t in tokenize(query) if t not in STOP_WORDS]
        query_error_codes = extract_potential_error_codes(query)

        # Expand query tokens with synonyms
        expanded_tokens = list(query_tokens)
        for qt in query_tokens:
            if qt in SYNONYM_MAP:
                expanded_tokens.extend(SYNONYM_MAP[qt])

        scored_passages = []

        for p in self.kb.all_passages:
            # If machine filter is specified, check against model, title, manual_id or brand token
            if machine_filter and machine_filter.strip():
                mf = machine_filter.lower().strip()
                target_str = f"{p.machine_model} {p.manual_title} {p.manual_id}".lower()
                mf_tokens = [t for t in tokenize(mf) if len(t) > 2]
                if not any(t in target_str for t in mf_tokens) and mf not in target_str:
                    continue

            score = 0.0
            p_tokens = self.passage_tokens.get(p.passage_id, [])
            p_codes = self.passage_error_codes.get(p.passage_id, [])

            # 1. Error Code exact match (Massive boost for industrial fault codes)
            for q_code in query_error_codes:
                for p_code in p_codes:
                    if q_code == p_code or q_code in p_code or p_code in q_code:
                        score += 35.0

            # 2. Section Title and Content TF-IDF matching
            p_text = (p.content + " " + p.section_title).lower()
            token_counts = {}
            for t in p_tokens:
                token_counts[t] = token_counts.get(t, 0) + 1

            doc_len = len(p_tokens) or 1
            for qt in expanded_tokens:
                tf = token_counts.get(qt, 0)
                if tf > 0:
                    doc_freq = self.df.get(qt, 1)
                    idf = math.log((self.doc_count + 1) / (doc_freq + 0.5)) + 1.0
                    # BM25-like saturation term
                    k1 = 1.2
                    b = 0.75
                    norm_tf = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / 40.0)))
                    weight = 1.0 if qt in query_tokens else 0.5
                    score += norm_tf * idf * weight

            # 3. Exact phrase match bonus
            clean_query = query.lower().strip()
            if len(clean_query) > 4 and clean_query in p_text:
                score += 15.0

            if score > 0.5:
                # Generate clean excerpt highlighting the matched passage
                excerpt = p.content
                if len(excerpt) > 280:
                    excerpt = excerpt[:277] + "..."

                citation = Citation(
                    manual_id=p.manual_id,
                    manual_title=p.manual_title,
                    section_id=p.section_id,
                    section_title=p.section_title,
                    page_number=p.page_number,
                    excerpt=excerpt,
                    relevance_score=round(score, 2),
                    anchor_id=f"{p.passage_id}"
                )
                scored_passages.append((p, score, citation))

        # Sort by relevance score descending
        scored_passages.sort(key=lambda x: x[1], reverse=True)
        return scored_passages[:top_k]
