"""
ChromaDB CV Indexer

Bu script CV'yi chunk'lara bölüp ChromaDB'ye indexler.
Chunk stratejisi:
- Chunk size: ~500 karakter
- Overlap: 50 karakter
- Metadata: chunk_index, source="cv.txt"

Kullanım:
    python -m tools.index_cv
"""

from pathlib import Path
import chromadb
from chromadb.config import Settings


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Metni belirli boyutta chunk'lara böler.

    Args:
        text: Bölünecek metin
        chunk_size: Chunk boyutu (karakter)
        overlap: Chunk'lar arası overlap (karakter)

    Returns:
        Chunk listesi
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]

        if chunk:
            chunks.append(chunk.strip())

        start = end - overlap

    return chunks


def index_cv(
    cv_path: str = "data/cv.txt",
    persist_dir: str = "./data/chromadb",
    chunk_size: int = 500,
    overlap: int = 50
) -> None:
    """
    CV'yi ChromaDB'ye indexler.

    Args:
        cv_path: CV dosya yolu
        persist_dir: ChromaDB veri dizini
        chunk_size: Chunk boyutu
        overlap: Chunk overlap
    """
    # CV'yi oku
    cv_file = Path(cv_path)

    if not cv_file.exists():
        print(f"Hata: {cv_path} bulunamadı.")
        return

    cv_text = cv_file.read_text(encoding="utf-8")
    cv_length = len(cv_text)

    print(f"CV yükleniyor: {cv_path}")
    print(f"CV boyutu: {cv_length} karakter")

    # Chunk'la
    chunks = chunk_text(cv_text, chunk_size, overlap)
    print(f"{len(chunks)} chunk oluşturuldu")

    # ChromaDB client
    client = chromadb.PersistentClient(path=persist_dir)

    # Mevcut collection'ı sil ve yeniden oluştur (temiz başlangıç)
    try:
        client.delete_collection("cv_chunks")
        print("Mevcut 'cv_chunks' collection'ı silindi")
    except Exception:
        pass  # Collection yoksa, sorun değil

    # Yeni collection oluştur
    collection = client.create_collection(
        name="cv_chunks",
        metadata={"hnsw:space": "cosine"}
    )
    print("Yeni 'cv_chunks' collection'ı oluşturuldu")

    # ID'ler ve metadata
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"chunk_index": i, "source": "cv.txt", "chunk_size": len(c)}
        for i, c in enumerate(chunks)
    ]

    # ChromaDB'ye ekle
    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas
    )

    print(f"✅ {len(chunks)} chunk ChromaDB'ye indexlendi")
    print(f"📁 Veri dizini: {persist_dir}")

    # Test query
    print("\n--- Test Query ---")
    results = collection.query(
        query_texts=["LLM deneyimi"],
        n_results=2,
        include=["documents", "metadatas"]
    )

    if results and results.get("documents"):
        for i, (doc, meta) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0]
        )):
            print(f"\nChunk {i} (index: {meta['chunk_index']}):")
            print(f"  {doc[:150]}...")


def main():
    """CLI entry point."""
    index_cv()


if __name__ == "__main__":
    main()
