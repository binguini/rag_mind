from __future__ import annotations

import json
from typing import Iterator

import httpx


class LLMService:
    # LLM 调用封装：统一对接 OpenAI 兼容接口并提供流式输出。
    @staticmethod
    def _build_openai_payload(messages: list[dict[str, str]], model: str, temperature: float = 0.2):
        return {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'stream': True,
        }

    @staticmethod
    def _normalize_messages(prompt: str | None, messages: list[dict[str, str]] | None) -> list[dict[str, str]]:
        # 若外部未直接提供消息序列，则把单轮 prompt 包装成标准消息格式。
        if messages:
            return messages
        return [
            {'role': 'system', 'content': '你是一个专业、简洁、准确的助手。'},
            {'role': 'user', 'content': prompt or ''},
        ]

    @staticmethod
    def stream_answer(
        prompt: str | None = None,
        messages: list[dict[str, str]] | None = None,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> Iterator[str]:
        provider = provider or 'openai_compatible'
        model = model or 'gpt-4o-mini'
        base_url = base_url or 'https://xiaoai.plus/v1'
        api_key = api_key or ''

        if provider not in {'openai_compatible', 'local', 'qwen', 'ernie'}:
            raise ValueError('不支持的 LLM provider')

        if provider == 'local':
            raise RuntimeError('当前为本地占位模型模式，尚未提供真实对话生成能力，请先在模型设置中配置可用的在线模型。')

        payload = LLMService._build_openai_payload(LLMService._normalize_messages(prompt, messages), model=model)
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        try:
            with httpx.stream('POST', f'{base_url.rstrip("/")}/chat/completions', headers=headers, json=payload, timeout=60.0) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode('utf-8')
                    if not line.startswith('data: '):
                        continue
                    data = line.removeprefix('data: ').strip()
                    if data == '[DONE]':
                        break
                    try:
                        event = json.loads(data)
                        delta = event['choices'][0].get('delta', {})
                        content = delta.get('content')
                        if content:
                            yield content
                    except Exception:
                        continue
        except Exception as exc:
            raise RuntimeError(f'模型调用失败，请检查模型配置、API Key 或网络连接。详细信息：{exc}') from exc

    @staticmethod
    def test_connection(provider: str, api_key: str, base_url: str | None = None, model: str | None = None) -> dict:
        if provider not in {'openai_compatible', 'local', 'qwen', 'ernie'}:
            raise ValueError('不支持的 LLM provider')
        if provider == 'local':
            return {'provider': provider, 'ok': True, 'message': '本地模式无需校验'}

        base_url = base_url or 'https://xiaoai.plus/v1'
        model = model or 'gpt-4o-mini'
        payload = LLMService._build_openai_payload(LLMService._normalize_messages('ping', None), model=model, temperature=0)
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        with httpx.Client(timeout=30.0) as client:
            response = client.post(f'{base_url.rstrip("/")}/chat/completions', headers=headers, json=payload)
            response.raise_for_status()
        return {'provider': provider, 'ok': True, 'message': '连接测试成功'}
