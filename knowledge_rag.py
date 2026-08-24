"""
knowledge_rag.py — RAG Engine cho Easy Trip & Visa Bot
Dùng TF-IDF + cosine similarity để tìm kiếm Q&A liên quan từ lịch sử chat.
Không cần vector DB bên ngoài, hoàn toàn local.
"""

import os
import json
import math
import re
import sys
from pathlib import Path

# Cấu hình encoding UTF-8 cho Windows stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# =====================================================================
# Cấu hình đường dẫn
# =====================================================================
BASE_DIR = Path(__file__).parent
QA_FILES = [
    BASE_DIR / "extracted_qa_telegram.json",
    BASE_DIR / "extracted_qa_meta.json",
    BASE_DIR / "extracted_qa_zalo_docx.json",
    BASE_DIR / "extracted_qa_excel.json",
]
MANUAL_QA_FILE = BASE_DIR / "manual_qa.json"  # Admin tự thêm Q&A thủ công

# =====================================================================
# TF-IDF thuần Python (không cần scikit-learn)
# =====================================================================

def tokenize(text: str) -> list[str]:
    """Tách từ đơn giản, hỗ trợ tiếng Anh, Việt, Nga, Hàn."""
    text = text.lower()
    # Giữ lại chữ cái, số, khoảng trắng (ghép các lớp ký tự Latin + Nga + Việt vào làm một từ contiguous)
    tokens = re.findall(r'[a-z0-9а-яё\u00c0-\u00ff\u0100-\u017f\u0180-\u024f\u1ea0-\u1eff]+|[\uac00-\ud7a3]+|[\u4e00-\u9fff]+', text)
    return [t for t in tokens if len(t) > 1]


def compute_tf(tokens: list[str]) -> dict[str, float]:
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    n = len(tokens) or 1
    return {t: c / n for t, c in tf.items()}


def compute_idf(documents: list[list[str]]) -> dict[str, float]:
    N = len(documents)
    df = {}
    for doc in documents:
        for t in set(doc):
            df[t] = df.get(t, 0) + 1
    idf = {}
    for t, count in df.items():
        idf[t] = math.log((N + 1) / (count + 1)) + 1
    return idf


def tfidf_vector(tf: dict, idf: dict) -> dict[str, float]:
    return {t: tf_val * idf.get(t, 1.0) for t, tf_val in tf.items()}


def cosine_similarity(v1: dict, v2: dict) -> float:
    common = set(v1) & set(v2)
    if not common:
        return 0.0
    dot = sum(v1[t] * v2[t] for t in common)
    mag1 = math.sqrt(sum(x * x for x in v1.values()))
    mag2 = math.sqrt(sum(x * x for x in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


# =====================================================================
# RAG Index
# =====================================================================

class RAGIndex:
    def __init__(self):
        self.qa_pairs: list[dict] = []       # [{"question": ..., "answer": ...}]
        self.doc_tokens: list[list[str]] = [] # tokens của mỗi Q&A
        self.idf: dict[str, float] = {}
        self.doc_vectors: list[dict] = []
        self._built = False
        self._file_mtimes: dict = {}

    def _load_qa_files(self) -> list[dict]:
        all_qa = []
        for qa_file in QA_FILES:
            if qa_file.exists():
                try:
                    with open(qa_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        all_qa.extend(data)
                    print(f"RAG: Loaded {len(data)} Q&A from {qa_file.name}")
                except Exception as e:
                    print(f"RAG: Error reading {qa_file.name}: {str(e)}")

        # Load manual Q&A nếu có
        if MANUAL_QA_FILE.exists():
            try:
                with open(MANUAL_QA_FILE, "r", encoding="utf-8") as f:
                    manual = json.load(f)
                if isinstance(manual, list):
                    all_qa.extend(manual)
                    print(f"RAG: Loaded {len(manual)} manual Q&A")
            except Exception as e:
                print(f"RAG: Error reading manual_qa.json: {str(e)}")

        return all_qa

    def _needs_rebuild(self) -> bool:
        """Kiểm tra xem files có thay đổi không."""
        if not self._built:
            return True
        for qa_file in [*QA_FILES, MANUAL_QA_FILE]:
            if qa_file.exists():
                mtime = qa_file.stat().st_mtime
                if self._file_mtimes.get(str(qa_file)) != mtime:
                    return True
        return False

    def build(self):
        """Build TF-IDF index từ tất cả Q&A files."""
        qa_pairs = self._load_qa_files()
        if not qa_pairs:
            print("RAG: No Q&A data to index!")
            self._built = True
            return

        self.qa_pairs = qa_pairs
        # Tokenize: dùng cả question + answer làm document
        self.doc_tokens = [
            tokenize(qa.get("question", "") + " " + qa.get("answer", ""))
            for qa in qa_pairs
        ]

        # Tính IDF
        self.idf = compute_idf(self.doc_tokens)

        # Tính TF-IDF vector cho mỗi document
        self.doc_vectors = []
        for tokens in self.doc_tokens:
            tf = compute_tf(tokens)
            vec = tfidf_vector(tf, self.idf)
            self.doc_vectors.append(vec)

        # Lưu mtimes
        for qa_file in [*QA_FILES, MANUAL_QA_FILE]:
            if qa_file.exists():
                self._file_mtimes[str(qa_file)] = qa_file.stat().st_mtime

        self._built = True
        print(f"RAG Index built: {len(self.qa_pairs)} Q&A pairs indexed")

    def search(self, query: str, top_k: int = 5, threshold: float = 0.05) -> list[dict]:
        """
        Tìm kiếm Q&A liên quan nhất với query.
        Returns: list of {"question": ..., "answer": ..., "score": ...}
        """
        # Auto rebuild nếu cần
        if self._needs_rebuild():
            self.build()

        if not self.qa_pairs or not self.doc_vectors:
            return []

        # Tính vector của query
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        query_tf = compute_tf(query_tokens)
        query_vec = tfidf_vector(query_tf, self.idf)

        # Tính cosine similarity
        scores = []
        for i, doc_vec in enumerate(self.doc_vectors):
            score = cosine_similarity(query_vec, doc_vec)
            if score >= threshold:
                scores.append((i, score))

        # Sort và lấy top K
        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scores[:top_k]:
            qa = self.qa_pairs[idx]
            results.append({
                "question": qa.get("question", ""),
                "answer": qa.get("answer", ""),
                "score": round(score, 4),
            })

        return results

    def format_for_prompt(self, query: str, top_k: int = 5) -> str:
        """
        Trả về chuỗi text để inject vào system prompt.
        """
        results = self.search(query, top_k=top_k)
        if not results:
            return ""

        lines = ["RELEVANT PAST EXPERIENCE FROM REAL CUSTOMER CHATS (use these as reference):"]
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] Q: {r['question']}")
            lines.append(f"    A: {r['answer']}")
        lines.append("(Above are real examples — adapt naturally, don't copy verbatim)")

        return "\n".join(lines)


# =====================================================================
# Singleton instance
# =====================================================================
_rag_index = RAGIndex()


def search(query: str, top_k: int = 5) -> list[dict]:
    """Public API: tìm kiếm Q&A liên quan."""
    return _rag_index.search(query, top_k=top_k)


def format_for_prompt(query: str, top_k: int = 5) -> str:
    """Public API: lấy context để inject vào prompt."""
    return _rag_index.format_for_prompt(query, top_k=top_k)


def rebuild():
    """Force rebuild index (gọi khi thêm Q&A mới)."""
    _rag_index.build()


# =====================================================================
# Test khi chạy trực tiếp
# =====================================================================
if __name__ == "__main__":
    print("=== Test RAG Engine ===\n")
    _rag_index.build()

    test_queries = [
        "How much does the visa run cost?",
        "What time does the bus depart?",
        "Can I get a refund?",
        "What documents do I need?",
        "Cambodian visa process",
        "pickup location",
        "Laos visa free",
    ]

    for q in test_queries:
        print(f"\nQuery: '{q}'")
        results = _rag_index.search(q, top_k=3)
        if results:
            for r in results:
                try:
                    print(f"  [{r['score']:.3f}] Q: {r['question'][:60]}")
                    print(f"         A: {r['answer'][:80]}")
                except UnicodeEncodeError:
                    # Fallback cho terminal không hỗ trợ Unicode
                    print(f"  [{r['score']:.3f}] Q: (Unicode text, cannot print in this terminal)")
        else:
            print("  (no results)")
