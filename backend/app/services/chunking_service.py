import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StructuredChunk:
    # 结构化切片结果，保留标题、层级和切片类型，方便调试和回溯。
    text: str
    heading: str | None = None
    heading_path: list[str] | None = None
    level: int | None = None
    chunk_type: str = 'text'


class ChunkingService:
    # 切片服务：负责普通文本与 Markdown 的标题感知分块。
    @staticmethod
    def _is_heading(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False

        heading_patterns = [
            r'^#{1,6}\s+.+$',
            r'^第[一二三四五六七八九十百千0-9]+[章节篇部分]\s*.*$',
            r'^[0-9]+(\.[0-9]+){0,3}[\s、.．]+.+$',
            r'^[（(]?[一二三四五六七八九十百千0-9]+[）)]\s*.+$',
            r'^[一二三四五六七八九十百千0-9]+[、.．]\s*.+$',
            r'^第[一二三四五六七八九十百千0-9]+条\s*.+$',
            r'^\d+\s+[A-Za-z\u4e00-\u9fa5].+$',
        ]
        if any(re.match(pattern, stripped) for pattern in heading_patterns):
            return True

        if re.match(r'^.+[.．·…]{3,}\s*\d+$', stripped):
            return True

        if len(stripped) <= 22 and not re.search(r'[。！？.!?；;:]$', stripped):
            return True
        return False

    @staticmethod
    def _split_by_sentences(text: str) -> list[str]:
        parts = [s.strip() for s in re.split(r'(?<=[。！？.!?；;])\s*', text) if s.strip()]
        return parts or [text]

    @staticmethod
    def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
        sentence_parts = ChunkingService._split_by_sentences(text)
        chunks: list[str] = []
        buffer = ''
        for part in sentence_parts:
            candidate = f'{buffer}{part}' if buffer else part
            if len(candidate) <= chunk_size:
                buffer = candidate
                continue

            if buffer:
                chunks.append(buffer)

            if len(part) > chunk_size:
                start = 0
                while start < len(part):
                    end = start + chunk_size
                    sub = part[start:end].strip()
                    if sub:
                        chunks.append(sub)
                    if end >= len(part):
                        break
                    start = max(end - overlap, start + 1)
                buffer = ''
            else:
                buffer = part

        if buffer:
            chunks.append(buffer)
        return chunks

    @staticmethod
    def _split_directory_like_text(text: str) -> list[str]:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) < 2:
            return []
        if sum(1 for line in lines if re.search(r'[.．·…]{3,}\s*\d+$', line)) >= max(2, len(lines) // 2):
            return lines
        return []

    @staticmethod
    def _normalize_heading(line: str) -> str:
        stripped = line.strip()
        stripped = re.sub(r'^#{1,6}\s*', '', stripped)
        return stripped.strip()

    @staticmethod
    def _make_section_chunks(heading: str | None, body: str, chunk_size: int, overlap: int) -> list[str]:
        body = body.strip()
        if not body:
            return []

        body_chunks = ChunkingService._split_long_text(body, chunk_size, overlap)
        if not heading:
            return body_chunks

        wrapped: list[str] = []
        for idx, chunk in enumerate(body_chunks):
            prefix = heading if idx == 0 else f'{heading}（续）'
            wrapped.append(f'{prefix}\n{chunk}'.strip())
        return wrapped

    @staticmethod
    def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        cleaned = re.sub(r'\r\n', '\n', text).strip()
        if not cleaned:
            logger.info('chunking skipped because text is empty')
            return []

        directory_chunks = ChunkingService._split_directory_like_text(cleaned)
        if directory_chunks:
            logger.info('directory-like text detected chunks=%s', len(directory_chunks))
            return [chunk for chunk in directory_chunks if len(chunk.strip()) >= 4]

        lines = [line.strip() for line in cleaned.split('\n')]
        chunks: list[str] = []
        current_heading: str | None = None
        section_buffer = ''

        def flush_section_buffer() -> None:
            nonlocal section_buffer
            if not section_buffer.strip():
                section_buffer = ''
                return
            chunks.extend(ChunkingService._make_section_chunks(current_heading, section_buffer, chunk_size, overlap))
            section_buffer = ''

        for line in lines:
            if not line:
                flush_section_buffer()
                continue

            if ChunkingService._is_heading(line):
                flush_section_buffer()
                current_heading = ChunkingService._normalize_heading(line)
                continue

            if not section_buffer:
                section_buffer = line
                continue

            candidate = f'{section_buffer}\n\n{line}'.strip()
            if len(candidate) <= chunk_size:
                section_buffer = candidate
            else:
                flush_section_buffer()
                section_buffer = line

        flush_section_buffer()
        chunks = [chunk.strip() for chunk in chunks if chunk.strip() and len(chunk.strip()) >= 8]
        logger.info('chunking finished chunks=%s', len(chunks))
        return chunks

    @staticmethod
    def _parse_markdown_heading(line: str) -> tuple[int, str] | None:
        match = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', line.strip())
        if not match:
            return None
        return len(match.group(1)), match.group(2).strip()

    @staticmethod
    def split_markdown(text: str, chunk_size: int = 500, overlap: int = 50) -> list[StructuredChunk]:
        cleaned = re.sub(r'\r\n', '\n', text).strip()
        if not cleaned:
            logger.info('markdown chunking skipped because text is empty')
            return []

        lines = cleaned.split('\n')
        chunks: list[StructuredChunk] = []
        heading_stack: list[tuple[int, str]] = []
        buffer: list[str] = []

        def current_heading() -> str | None:
            return heading_stack[-1][1] if heading_stack else None

        def current_path() -> list[str]:
            return [item[1] for item in heading_stack]

        def current_level() -> int | None:
            return heading_stack[-1][0] if heading_stack else None

        def flush_buffer() -> None:
            nonlocal buffer
            body = '\n'.join(buffer).strip()
            if not body:
                buffer = []
                return

            path = current_path()
            heading = current_heading()
            level = current_level()
            body_chunks = ChunkingService._split_long_text(body, chunk_size, overlap)
            for idx, piece in enumerate(body_chunks):
                text_prefix = ' > '.join(path)
                if text_prefix:
                    prefix = text_prefix if idx == 0 else f'{text_prefix}（续）'
                    chunk_text = f'{prefix}\n{piece}'.strip()
                else:
                    chunk_text = piece.strip()
                chunks.append(
                    StructuredChunk(
                        text=chunk_text,
                        heading=heading,
                        heading_path=path or None,
                        level=level,
                        chunk_type='markdown_section' if path else 'markdown_text',
                    )
                )
            buffer = []

        for raw_line in lines:
            line = raw_line.rstrip()
            parsed = ChunkingService._parse_markdown_heading(line)
            if parsed:
                flush_buffer()
                level, title = parsed
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                continue

            if not line.strip() and buffer:
                buffer.append('')
                continue

            if line.strip() or buffer:
                buffer.append(line)

        flush_buffer()

        if not chunks:
            logger.info('markdown chunking fallback to generic text chunking')
            return [StructuredChunk(text=item, chunk_type='markdown_fallback') for item in ChunkingService.split_text(cleaned, chunk_size, overlap)]

        logger.info('markdown chunking finished chunks=%s', len(chunks))
        return [chunk for chunk in chunks if chunk.text.strip() and len(chunk.text.strip()) >= 8]
