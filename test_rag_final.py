import sys
sys.path.insert(0, r'C:\Users\Admin\.gemini\antigravity\scratch\backend')
import knowledge_rag

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

print("=== VERIFYING FINAL RAG INDEX ===")
knowledge_rag.rebuild()

total_pairs = len(knowledge_rag._rag_index.qa_pairs)
print(f"Total Q&A pairs in Index: {total_pairs}")

queries = [
    "Laos visa Bo Y border cost",
    "How much for Moc Bai Cambodia",
    "What time does the bus leave?",
    "Can I cancel my ticket?",
]

for q in queries:
    print(f"\nQuery: '{q}'")
    results = knowledge_rag.search(q, top_k=3)
    for idx, r in enumerate(results, 1):
        try:
            print(f"  [{idx}] [Score: {r['score']:.3f}]")
            print(f"      Q: {r['question'][:80]}")
            print(f"      A: {r['answer'][:100]}")
        except UnicodeEncodeError:
            print(f"  [{idx}] (Unicode Text)")
