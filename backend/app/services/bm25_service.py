from collections import Counter, defaultdict
from math import log

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk


class BM25Service:
    # BM25 召回服务：基于文档切片文本做关键词检索并返回候选结果。
    @staticmethod
    def search(db: Session, knowledge_base_id: int, query: str, top_k: int = 8) -> list[dict]:
        # 读取知识库下的所有切片，计算简单的 BM25 风格分数。
        chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.knowledge_base_id == knowledge_base_id)).all()
        if not chunks:
            return []

        query_terms = [term.lower() for term in query.split() if term.strip()]
        if not query_terms:
            return []

        doc_freq = Counter()
        doc_tokens: list[tuple[DocumentChunk, list[str]]] = []
        for chunk in chunks:
            tokens = chunk.content.lower().split()
            doc_tokens.append((chunk, tokens))
            for term in set(tokens):
                doc_freq[term] += 1

        total_docs = len(chunks)
        scores: list[dict] = []
        for chunk, tokens in doc_tokens:
            token_counts = Counter(tokens)
            score = 0.0
            for term in query_terms:
                tf = token_counts.get(term, 0)
                if tf == 0:
                    continue
                idf = log((total_docs - doc_freq.get(term, 0) + 0.5) / (doc_freq.get(term, 0) + 0.5) + 1)
                score += tf * idf
            if score > 0:
                scores.append(
                    {
                        'document_id': chunk.document_id,
                        'chunk_id': chunk.id,
                        'content': chunk.content,
                        'metadata_json': chunk.metadata_json,
                        'score': score,
                        'source': 'bm25',
                    }
                )

        return sorted(scores, key=lambda item: item['score'], reverse=True)[:top_k]
