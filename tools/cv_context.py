"""
Hybrid Context Module for Career Assistant AI Agent

Bu modul CV context'ini stratejik olarak sağlar:
- CV len < 2000 karakter → direkt return (prompt'a gömülür)
- CV len >= 2000 → ChromaDB RAG (sorguya alakalı chunk'lar)
"""

from pathlib import Path
from typing import Optional


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
