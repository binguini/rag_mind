<template>
  <div class="markdown-body" v-html="rendered"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps<{
  content: string
}>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
})

const normalizedContent = computed(() => {
  const source = props.content || ''
  const lines = source
    .replace(/\r\n/g, '\n')
    .replace(/[\t ]+\n/g, '\n')
    .trim()
    .split('\n')
    .map((line) => line.trimEnd())

  const normalizedLines: string[] = []
  let nestedBulletIndent = ''
  let inNestedBulletList = false

  const normalizeInlineListSyntax = (value: string) => value
    .replace(/^(\d+)\.(\S)/, '$1. $2')
    .replace(/^([-*+])(\S)/, '$1 $2')

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim()

    if (!line) {
      const previousLine = normalizedLines[normalizedLines.length - 1] || ''
      const nextNonEmptyLine = lines.slice(index + 1).find((item) => item.trim())?.trim() || ''
      const previousIsListMarker = /^(?:\d+\.|[-*+])$/.test(previousLine.trim())
      const nextStartsListContent = /^(?:事件视界|奇点|类型|[-*+]\s*\S|\d+\.\s*\S)/.test(nextNonEmptyLine)
      const nextIsNestedBullet = Boolean(nestedBulletIndent) && /^[-*+]\s*\S/.test(normalizeInlineListSyntax(nextNonEmptyLine))

      if (previousIsListMarker || nextStartsListContent || nextIsNestedBullet) {
        continue
      }

      nestedBulletIndent = ''
      inNestedBulletList = false

      if (previousLine) {
        normalizedLines.push('')
      }
      continue
    }

    const normalizedLine = normalizeInlineListSyntax(line)

    if (/^(?:\d+\.|[-*+])$/.test(normalizedLine)) {
      const nextNonEmptyLine = lines.slice(index + 1).find((item) => item.trim())?.trim()
      if (nextNonEmptyLine) {
        const mergedLine = `${normalizedLine} ${normalizeInlineListSyntax(nextNonEmptyLine)}`
        normalizedLines.push(mergedLine)
        inNestedBulletList = /^\d+\.\s+.*[:：]$/.test(mergedLine)
        nestedBulletIndent = inNestedBulletList ? '    ' : ''
        while (index + 1 < lines.length && !lines[index + 1].trim()) {
          index += 1
        }
        index += 1
      } else {
        normalizedLines.push(normalizedLine)
        nestedBulletIndent = ''
        inNestedBulletList = false
      }
      continue
    }

    if (normalizedLines[normalizedLines.length - 1] === '') {
      while (normalizedLines[normalizedLines.length - 2] === '') {
        normalizedLines.pop()
      }
    }

    if (nestedBulletIndent && /^[-*+]\s+\S/.test(normalizedLine)) {
      normalizedLines.push(`${nestedBulletIndent}${normalizedLine}`)
      inNestedBulletList = true
      continue
    }

    if (inNestedBulletList && !/^[-*+]\s+\S/.test(normalizedLine)) {
      normalizedLines.push('')
      inNestedBulletList = false
      nestedBulletIndent = ''
    }

    normalizedLines.push(normalizedLine)
    inNestedBulletList = false
    nestedBulletIndent = /^\d+\.\s+.*[:：]$/.test(normalizedLine) ? '    ' : ''
  }

  return normalizedLines.join('\n').replace(/\n{3,}/g, '\n\n')
})

const rendered = computed(() => md.render(normalizedContent.value))
</script>

<style scoped>
.markdown-body {
  line-height: 1.3;
  font-size: 14px;
  color: #1f2937;
  letter-spacing: 0;
  word-break: break-word;
}

.markdown-body :deep(*:first-child) {
  margin-top: 0;
}

.markdown-body :deep(*:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(p) {
  margin: 0 0 3px;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 10px 0 4px;
  line-height: 1.25;
  font-weight: 700;
  color: #111827;
}

.markdown-body :deep(h1) {
  font-size: 22px;
}

.markdown-body :deep(h2) {
  font-size: 18px;
}

.markdown-body :deep(h3) {
  font-size: 16px;
}

.markdown-body :deep(h4) {
  font-size: 15px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0 0 6px;
  padding-left: 1.6em;
}

.markdown-body :deep(ol) {
  list-style: decimal;
  list-style-position: outside;
}

.markdown-body :deep(ul) {
  list-style-position: outside;
}

.markdown-body :deep(li) {
  margin: 0 0 4px;
  line-height: 1.6;
}

.markdown-body :deep(li::marker) {
  color: inherit;
  font-variant-numeric: tabular-nums;
}

.markdown-body :deep(li > p) {
  margin: 0;
}

.markdown-body :deep(li > p + p) {
  margin-top: 4px;
}

.markdown-body :deep(li > ol),
.markdown-body :deep(li > ul) {
  margin: 6px 0 0;
  padding-left: 1.4em;
}

.markdown-body :deep(ol > li > ul),
.markdown-body :deep(ol > li > ol) {
  margin-left: 0;
}

.markdown-body :deep(pre) {
  margin: 6px 0;
  padding: 10px 12px;
  border-radius: 12px;
  overflow: auto;
  background: #0f172a;
  color: #f8fafc;
  line-height: 1.55;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
}

.markdown-body :deep(code) {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 0.92em;
}

.markdown-body :deep(p code),
.markdown-body :deep(li code),
.markdown-body :deep(td code),
.markdown-body :deep(blockquote code) {
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.14);
}

.markdown-body :deep(blockquote) {
  margin: 6px 0;
  padding: 6px 10px;
  border-left: 4px solid #93c5fd;
  border-radius: 0 10px 10px 0;
  background: #eff6ff;
  color: #1e3a8a;
}

.markdown-body :deep(blockquote p) {
  margin-bottom: 4px;
}

.markdown-body :deep(hr) {
  margin: 10px 0;
  border: none;
  border-top: 1px solid #e5e7eb;
}

.markdown-body :deep(a) {
  color: #409eff;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(table) {
  width: 100%;
  margin: 6px 0;
  border-collapse: collapse;
  font-size: 13px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 7px 9px;
  border: 1px solid #e5e7eb;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f8fafc;
  font-weight: 600;
}
</style>
