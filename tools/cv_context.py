"""
Hybrid Context Module for Career Assistant AI Agent

Bu modul CV context'ini stratejik olarak sağlar:
- CV len < 2000 karakter → direkt return (prompt'a gömülür)
- CV len >= 2000 → ChromaDB RAG (sorguya alakalı chunk'lar)

check_cv_relevance() ile sorgunun CV'de karşılığı olup olmadığını ölçer.
ChromaDB cosine distance: 0 = aynı, 2 = tamamen farklı.
RELEVANCE_THRESHOLD = 0.65 → üzerindeyse konu CV'de yok → admin'e git.
"""

from pathlib import Path
from typing import Optional, Tuple

# Cosine distance threshold — bu değerin ÜSTÜNDE = konu CV'de yok
# 0 = aynı, 2 = tamamen zıt. 1.4 = gerçekten alakasız (spor, politika vb.)
# Genel career sorular (kendinizden bahsedin, merhaba) ~0.9-1.2 aralığında
RELEVANCE_THRESHOLD = 1.4


def get_cv_context(query: str = "") -> str:
    """
    Hybrid context stratejisi ile CV içeriğini döndürür.

    Args:
        query: İşveren mesajı veya soru (ChromaDB için)

    Returns:
        CV içeriği (tam veya RAG ile ilgili chunk'lar)

    Examples:
        >>> ctx = get_cv_context("LLM deneyiminiz nedir?")
        >>> print(ctx[:100])  # İlk 100 karakter
    """
    cv_path = Path("data/cv.txt")

    if not cv_path.exists():
        return "CV bulunamadı."

    cv_text = cv_path.read_text(encoding="utf-8")

    # Kısa CV: direkt return (prompt'a gömülür, token tasarrufu)
    if len(cv_text) < 2000:
        return cv_text

    # Uzun CV: ChromaDB RAG
    try:
        import chromadb

        client = chromadb.PersistentClient(path="./data/chromadb")
        collection = client.get_or_create_collection(
            name="cv_chunks",
            metadata={"hnsw:space": "cosine"}
        )

        # Query yoksa, ilk chunk'ları al
        if not query:
            results = collection.get(limit=3, include=["documents"])
            if results and results.get("documents"):
                return "\n".join(results["documents"])
            return cv_text[:1000]  # Fallback

        # Query var, alakalı chunk'ları al
        results = collection.query(
            query_texts=[query],
            n_results=3,
            include=["documents"]
        )

        if results and results.get("documents"):
            chunks = results["documents"][0]
            return "\n".join(chunks)

    except Exception as e:
        # ChromaDB hatası durumunda fallback
        print(f"ChromaDB hatası: {e}, CV başlangıcı kullanılıyor")
        return cv_text[:1000]

    return cv_text[:1000]


def get_cv_length() -> int:
    """CV karakter sayısını döndürür."""
    cv_path = Path("data/cv.txt")
    if cv_path.exists():
        return len(cv_path.read_text(encoding="utf-8"))
    return 0


def should_use_rag() -> bool:
    """RAG kullanılıp kullanılmayacağını döndürür."""
    return get_cv_length() >= 2000


def check_cv_relevance(query: str) -> Tuple[bool, str, float]:
    """
    Sorgunun CV'deki içerikle ne kadar alakalı olduğunu ölçer.

    CV kısa ise (< 2000 char) her zaman relevant kabul edilir çünkü
    tam CV zaten prompt'a gömülür, Judge hallucination'ı yakalar.

    CV uzun ise ChromaDB cosine distance kullanılır:
    - distance <= RELEVANCE_THRESHOLD → konu CV'de var → (True, context, distance)
    - distance > RELEVANCE_THRESHOLD  → konu CV'de yok → (False, "", distance)

    Args:
        query: İşveren mesajı

    Returns:
        Tuple of:
            - is_relevant: bool
            - cv_context: str (relevant ise dolu, değilse boş)
            - best_distance: float (0.0 = mükemmel eşleşme, 2.0 = hiç alakasız)
    """
    cv_path = Path("data/cv.txt")
    if not cv_path.exists():
        return False, "CV bulunamadı.", 2.0

    cv_text = cv_path.read_text(encoding="utf-8")

    # Kısa CV → tam metni dön, her zaman relevant
    if len(cv_text) < 2000:
        return True, cv_text, 0.0

    # Uzun CV → ChromaDB similarity check
    try:
        import chromadb

        client = chromadb.PersistentClient(path="./data/chromadb")
        collection = client.get_or_create_collection(
            name="cv_chunks",
            metadata={"hnsw:space": "cosine"}
        )

        results = collection.query(
            query_texts=[query],
            n_results=3,
            include=["documents", "distances"]
        )

        if not results or not results.get("documents") or not results.get("distances"):
            # ChromaDB boş — fallback: CV başlangıcını dön, relevant say
            return True, cv_text[:1000], 0.0

        docs = results["documents"][0]
        distances = results["distances"][0]

        best_distance = min(distances) if distances else 2.0
        context = "\n".join(docs)

        is_relevant = best_distance <= RELEVANCE_THRESHOLD
        return is_relevant, context if is_relevant else "", best_distance

    except Exception as e:
        print(f"ChromaDB relevance check hatası: {e}, fallback: relevant")
        # ChromaDB hatasında güvenli taraf: relevant say, Judge hallucination'ı yakalar
        return True, cv_text[:1000], 0.0
