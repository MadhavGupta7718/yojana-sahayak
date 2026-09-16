# Embedding models

Local multilingual model used by hybrid NLP (`ml/inference/nlp.py`).

## Download (same as Rishi’s commands)

```bash
pip install -U sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; model=SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); model.save('./models/paraphrase-multilingual-MiniLM-L12-v2')"
```

Or via Docker:

```bash
docker compose exec backend python /app/ml/../scripts/download_embedding_model.py
# if script path differs:
docker compose exec backend python -c "from sentence_transformers import SentenceTransformer; model=SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); model.save('/app/models/paraphrase-multilingual-MiniLM-L12-v2')"
```

Then set in `.env`:

```
ENABLE_EMBEDDINGS=true
EMBEDDING_MODEL_NAME=/app/models/paraphrase-multilingual-MiniLM-L12-v2
```
