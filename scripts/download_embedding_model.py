"""Download paraphrase-multilingual-MiniLM-L12-v2 for local hybrid NLP."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
HF_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    from sentence_transformers import SentenceTransformer

    print(f"Downloading {HF_ID} ...")
    model = SentenceTransformer(HF_ID)
    model.save(str(TARGET))
    print(f"Saved to {TARGET}")


if __name__ == "__main__":
    main()
