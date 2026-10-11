"""Embedding models. The real model is pinned by revision; tests use a hash embedder."""
import hashlib
import math
from fdi.db.config import ROOT

DIMENSION = 384  # must match fdi.chunks.embedding vector(384)


class SentenceTransformerEmbedder:
    model_id = 'BAAI/bge-small-en-v1.5'
    revision = '5c38ec7c405ec4b44b94cc5a9bb96e735b38267a'
    # bge-v1.5 recommends this instruction for short retrieval queries only.
    query_instruction = 'Represent this sentence for searching relevant passages: '
    name = f'{model_id}@{revision[:12]}'

    def __init__(self, batch_size=32):
        from sentence_transformers import SentenceTransformer
        self.batch_size = batch_size
        self.model = SentenceTransformer(self.model_id, revision=self.revision, device='cpu',
                                         cache_folder=str(ROOT / 'work/models'))
        if self.model.get_embedding_dimension() != DIMENSION:
            raise RuntimeError('Embedding dimension does not match schema')

    def max_tokens(self):
        return self.model.max_seq_length

    def token_counts(self, texts):
        return [len(ids) for ids in self.model.tokenizer(list(texts), add_special_tokens=True)['input_ids']]

    def embed_documents(self, texts):
        return self.model.encode(list(texts), batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False,
                                 convert_to_numpy=True).tolist()

    def embed_query(self, text):
        return self.model.encode([self.query_instruction + text], normalize_embeddings=True,
                                 convert_to_numpy=True)[0].tolist()


class HashEmbedder:
    """Deterministic test double: same text, same unit vector. Not semantic."""
    name = 'test-hash-embedder'

    def embed_documents(self, texts):
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        return self._vector(text)

    def _vector(self, text):
        raw = hashlib.shake_256(text.encode()).digest(DIMENSION * 2)
        values = [int.from_bytes(raw[i:i + 2], 'big') - 32768 for i in range(0, len(raw), 2)]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


def vector_literal(values):
    if len(values) != DIMENSION or not all(math.isfinite(v) for v in values):
        raise ValueError('Invalid embedding')
    return '[' + ','.join(f'{v:.8g}' for v in values) + ']'
