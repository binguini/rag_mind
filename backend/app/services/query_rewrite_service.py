class QueryRewriteService:
    # 查询改写服务：利用最近的用户历史，补全当前问题的上下文指代。
    @staticmethod
    def rewrite(question: str, history: list[dict] | None = None) -> str:
        if not history:
            return question

        last_user_messages = [item.get('content', '') for item in history if item.get('role') == 'user']
        if not last_user_messages:
            return question

        context = last_user_messages[-1]
        if len(context) > 80:
            context = context[:80]
        return f'{context}。{question}'
