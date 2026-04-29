class PromptService:
    # Prompt 组装服务：将系统提示词、历史对话和引用上下文拼成最终输入。
    @staticmethod
    def build_prompt(system_prompt: str, question: str, citations: list[dict], history: list[dict] | None = None) -> str:
        context_lines = []
        for idx, item in enumerate(citations, start=1):
            location_parts = [f'chunk={item["chunk_index"]}']
            if item.get('page') is not None:
                location_parts.append(f'page={item.get("page")}')
            if item.get('heading_path'):
                location_parts.append(f'heading={" > ".join(item["heading_path"])}')
            elif item.get('heading'):
                location_parts.append(f'heading={item["heading"]}')
            context_lines.append(
                f'[{idx}] 文档：{item["document_name"]} | ' + ' | '.join(location_parts) + f'\n{item["content"]}'
            )
        context = '\n\n'.join(context_lines) if context_lines else '未检索到相关上下文。'

        history_lines = []
        for item in history or []:
            role = item.get('role')
            label = '用户' if role == 'user' else '助手' if role == 'assistant' else '系统'
            content = item.get('content', '')
            if content:
                history_lines.append(f'{label}: {content}')
        history_text = '\n\n'.join(history_lines) if history_lines else '无历史上下文。'

        return f'''你是一个专业的知识库问答助手。

系统提示词：{system_prompt}

历史对话：
{history_text}

参考上下文：
{context}

用户问题：{question}

请基于参考上下文回答，并尽量给出引用编号；如果历史问题对当前问题有指代消解作用，请结合历史理解后再回答。'''
