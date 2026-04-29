class RerankService:
    # 简单 rerank 服务：通过问题关键词与候选内容的重叠度重排结果。
    @staticmethod
    def rerank(question: str, candidates: list[dict]) -> list[dict]:
        # 提取问题中的关键词，用于和候选内容做粗粒度匹配。
        keywords = {word for word in question.lower().split() if len(word) > 1}

        def score(item: dict) -> tuple[int, float]:
            content = item.get('content', '').lower()
            overlap = sum(1 for word in keywords if word in content)
            return overlap, float(item.get('score', 0.0))

        return sorted(candidates, key=score, reverse=True)
