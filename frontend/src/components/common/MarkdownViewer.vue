<script setup lang="ts">
import { computed } from 'vue'
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import remarkRehype from 'remark-rehype'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import rehypeStringify from 'rehype-stringify'

const props = withDefaults(
  defineProps<{
    content?: string | null
    emptyText?: string
  }>(),
  {
    content: '',
    emptyText: '-',
  },
)

const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code ?? []), 'className'],
    input: [...(defaultSchema.attributes?.input ?? []), 'type', 'checked', 'disabled'],
    li: [...(defaultSchema.attributes?.li ?? []), 'className'],
    ul: [...(defaultSchema.attributes?.ul ?? []), 'className'],
  },
}

const processor = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkBreaks)
  .use(remarkRehype)
  .use(rehypeSanitize, sanitizeSchema)
  .use(rehypeStringify)

const hasContent = computed(() => Boolean(props.content?.trim()))

const renderedHtml = computed(() => {
  const source = props.content ?? ''

  try {
    return String(processor.processSync(source))
  } catch {
    return ''
  }
})
</script>

<template>
  <div v-if="hasContent" class="markdown-viewer" v-html="renderedHtml"></div>
  <div v-else class="markdown-viewer">{{ emptyText }}</div>
</template>

<style scoped>
.markdown-viewer {
  --md-text: rgb(212 212 216);
  --md-strong: rgb(244 244 245);
  --md-muted: rgb(161 161 170);
  --md-border: rgb(63 63 70);
  --md-border-subtle: rgb(39 39 42);
  --md-inline-code-bg: rgb(39 39 42);
  --md-code-bg: rgb(9 9 11);
  --md-code-text: rgb(226 232 240);
  --md-quote-bg: rgb(39 39 42 / 0.55);
  --md-table-head-bg: rgb(39 39 42);
  --md-table-cell-bg: rgb(24 24 27 / 0.65);
  --md-link: rgb(129 140 248);

  color: var(--md-text);
  line-height: 1.7;
  overflow-wrap: anywhere;
}

:global(html.light .markdown-viewer) {
  --md-text: rgb(51 65 85);
  --md-strong: rgb(15 23 42);
  --md-muted: rgb(71 85 105);
  --md-border: rgb(203 213 225);
  --md-border-subtle: rgb(226 232 240);
  --md-inline-code-bg: rgb(226 232 240);
  --md-code-bg: rgb(15 23 42);
  --md-code-text: rgb(226 232 240);
  --md-quote-bg: rgb(238 242 255);
  --md-table-head-bg: rgb(241 245 249);
  --md-table-cell-bg: rgb(255 255 255 / 0.75);
  --md-link: rgb(67 56 202);
}

.markdown-viewer :deep(*) {
  max-width: 100%;
}

.markdown-viewer :deep(*:first-child) {
  margin-top: 0;
}

.markdown-viewer :deep(*:last-child) {
  margin-bottom: 0;
}

.markdown-viewer :deep(p) {
  margin: 0 0 0.8rem;
}

.markdown-viewer :deep(h1),
.markdown-viewer :deep(h2),
.markdown-viewer :deep(h3),
.markdown-viewer :deep(h4),
.markdown-viewer :deep(h5),
.markdown-viewer :deep(h6) {
  margin: 1.2rem 0 0.55rem;
  color: var(--md-strong);
  font-weight: 700;
  line-height: 1.3;
}

.markdown-viewer :deep(h1) {
  font-size: 1.3rem;
}

.markdown-viewer :deep(h2) {
  font-size: 1.15rem;
  border-bottom: 1px solid var(--md-border-subtle);
  padding-bottom: 0.35rem;
}

.markdown-viewer :deep(h3) {
  font-size: 1.05rem;
}

.markdown-viewer :deep(h4),
.markdown-viewer :deep(h5),
.markdown-viewer :deep(h6) {
  font-size: 0.95rem;
}

.markdown-viewer :deep(ul),
.markdown-viewer :deep(ol) {
  margin: 0 0 0.85rem 1.25rem;
  padding: 0;
}

.markdown-viewer :deep(ul) {
  list-style: disc;
}

.markdown-viewer :deep(ol) {
  list-style: decimal;
}

.markdown-viewer :deep(li) {
  margin: 0.35rem 0;
  padding-left: 0.1rem;
}

.markdown-viewer :deep(li > p) {
  margin: 0.2rem 0;
}

.markdown-viewer :deep(ul.contains-task-list) {
  margin-left: 0;
  list-style: none;
}

.markdown-viewer :deep(li.task-list-item) {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  padding-left: 0;
}

.markdown-viewer :deep(input[type='checkbox']) {
  margin-top: 0.35rem;
  accent-color: var(--md-link);
}

.markdown-viewer :deep(blockquote) {
  margin: 0.85rem 0;
  border-left: 3px solid var(--md-link);
  background: var(--md-quote-bg);
  padding: 0.7rem 0.9rem;
  color: var(--md-text);
}

.markdown-viewer :deep(pre) {
  margin: 0.9rem 0;
  overflow: auto;
  border-radius: 0.55rem;
  border: 1px solid var(--md-border-subtle);
  background: var(--md-code-bg);
  padding: 0.95rem;
}

.markdown-viewer :deep(code) {
  border-radius: 0.35rem;
  background: var(--md-inline-code-bg);
  padding: 0.12rem 0.34rem;
  color: var(--md-strong);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 0.86em;
}

.markdown-viewer :deep(pre code) {
  display: block;
  min-width: max-content;
  background: transparent;
  padding: 0;
  color: var(--md-code-text);
  white-space: pre;
}

.markdown-viewer :deep(table) {
  display: block;
  margin: 0.9rem 0;
  width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
}

.markdown-viewer :deep(th),
.markdown-viewer :deep(td) {
  border: 1px solid var(--md-border);
  padding: 0.55rem 0.65rem;
  text-align: left;
  vertical-align: top;
}

.markdown-viewer :deep(th) {
  background: var(--md-table-head-bg);
  color: var(--md-strong);
  font-weight: 700;
}

.markdown-viewer :deep(td) {
  background: var(--md-table-cell-bg);
}

.markdown-viewer :deep(a) {
  color: var(--md-link);
  text-decoration: underline;
  text-underline-offset: 0.2em;
}

.markdown-viewer :deep(strong) {
  color: var(--md-strong);
  font-weight: 700;
}

.markdown-viewer :deep(em) {
  color: var(--md-text);
}

.markdown-viewer :deep(hr) {
  margin: 1rem 0;
  border: 0;
  border-top: 1px solid var(--md-border);
}
</style>
