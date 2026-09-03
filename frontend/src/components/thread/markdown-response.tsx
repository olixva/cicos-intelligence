import { Fragment, useMemo, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * MarkdownResponse — render de respuestas del asistente en markdown.
 *
 * Sin dependencias externas: implementa un parser CommonMark muy acotado al
 * subconjunto que el backend del manual CIDE/ASCIDE puede generar (texto
 * narrativo, no tablas). El streaming se sigue mostrando con
 * `TextGenerateEffect` (palabra por palabra); cuando el mensaje está
 * completo, se monta este componente para que el texto ya cerrado pase
 * por el parser.
 *
 * Soporta:
 *   - Párrafos (líneas en blanco como separador)
 *   - Headings `#`, `##`, `###` (h1/h2/h3)
 *   - Negrita `**x**` y cursiva `*x*` / `_x_`
 *   - Código inline `` `x` `` y bloques ``` ```x``` ```
 *   - Listas desordenadas `-` y ordenadas `1.`
 *   - Citas `>`
 *   - Links `[text](url)`
 *   - Reglas horizontales `---`
 *   - Línea dura con dos espacios al final de línea
 *
 * Lo que NO soporta (a propósito, porque suma mucho código y el backend
 * no lo emite en sus respuestas): tablas GFM, listas de tareas, tachado,
 * HTML crudo, imágenes, escapes avanzados. Si en el futuro hace falta,
 * lo natural sería migrar a `react-markdown`.
 */
export interface MarkdownResponseProps {
  text: string;
  className?: string;
}

// ---------------------------------------------------------------------------
// Parsing
// ---------------------------------------------------------------------------

type InlineToken =
  | { kind: 'text'; value: string }
  | { kind: 'bold'; value: string }
  | { kind: 'italic'; value: string }
  | { kind: 'code'; value: string }
  | { kind: 'link'; text: string; href: string };

type Block =
  | { kind: 'heading'; level: 1 | 2 | 3; children: InlineToken[] }
  | { kind: 'paragraph'; children: InlineToken[] }
  | { kind: 'list'; ordered: boolean; items: InlineToken[][] }
  | { kind: 'quote'; lines: string[] }
  | { kind: 'code-block'; value: string; lang?: string }
  | { kind: 'hr' };

/** Etiqueta un patrón de bloque al inicio de línea. */
function detectBlock(line: string): Block | null {
  if (/^\s*---\s*$/.test(line)) return { kind: 'hr' };
  const heading = /^(#{1,3})\s+(.*)$/.exec(line);
  if (heading) {
    return {
      kind: 'heading',
      level: heading[1]!.length as 1 | 2 | 3,
      children: parseInline(heading[2] ?? ''),
    };
  }
  return null;
}

/** Parsea inline markdown (**bold**, *italic*, `code`, [text](url)). */
function parseInline(input: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let remaining = input;

  while (remaining.length > 0) {
    // Link: [text](url) — antes que bold/italic para que los `**` dentro del
    // texto del link no se rendericen como marcador de negrita.
    const linkMatch = /^\[([^\]]+)\]\(([^)\s]+)\)/.exec(remaining);
    if (linkMatch) {
      tokens.push({ kind: 'link', text: linkMatch[1]!, href: linkMatch[2]! });
      remaining = remaining.slice(linkMatch[0].length);
      continue;
    }
    // Código inline: `contenido` (no acepta ` adentro, simplificación
    // aceptable para el output del backend).
    const codeMatch = /^`([^`]+)`/.exec(remaining);
    if (codeMatch) {
      tokens.push({ kind: 'code', value: codeMatch[1]! });
      remaining = remaining.slice(codeMatch[0].length);
      continue;
    }
    // Negrita: **x**
    const boldMatch = /^\*\*([^*]+)\*\*/.exec(remaining);
    if (boldMatch) {
      tokens.push({ kind: 'bold', value: boldMatch[1]! });
      remaining = remaining.slice(boldMatch[0].length);
      continue;
    }
    // Cursiva: *x* o _x_
    const italicMatch = /^\*([^*\s][^*]*?)\*|^_([^_\s][^_]*?)_/.exec(remaining);
    if (italicMatch) {
      tokens.push({ kind: 'italic', value: (italicMatch[1] ?? italicMatch[2])! });
      remaining = remaining.slice(italicMatch[0].length);
      continue;
    }
    // Texto plano: tomamos hasta el próximo marcador.
    const plainMatch = /^([^*_`[]+)/.exec(remaining);
    if (plainMatch) {
      tokens.push({ kind: 'text', value: plainMatch[1]! });
      remaining = remaining.slice(plainMatch[0].length);
      continue;
    }
    // Carácter suelto sin patrón (por ejemplo un `*` o `[` huérfano que
    // no abre nada). Lo emitimos como texto y avanzamos uno para evitar
    // bucle infinito.
    tokens.push({ kind: 'text', value: remaining[0]! });
    remaining = remaining.slice(1);
  }

  return tokens;
}

function parseBlocks(input: string): Block[] {
  // Normalizamos saltos de línea y recortamos.
  const normalized = input.replace(/\r\n?/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  if (!normalized) return [];

  const lines = normalized.split('\n');
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i]!;
    const trimmed = line.trim();

    // Bloque de código fenceado ```lang ... ```
    if (/^```/.test(trimmed)) {
      const langMatch = /^```\s*([\w-]+)?\s*$/.exec(trimmed);
      const lang = langMatch?.[1];
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i]!.trim())) {
        codeLines.push(lines[i]!);
        i += 1;
      }
      if (i < lines.length) i += 1; // skip cierre
      blocks.push({ kind: 'code-block', value: codeLines.join('\n'), lang });
      continue;
    }

    // HR.
    if (/^\s*---\s*$/.test(trimmed)) {
      blocks.push({ kind: 'hr' });
      i += 1;
      continue;
    }

    // Heading.
    const heading = detectBlock(trimmed);
    if (heading) {
      blocks.push(heading);
      i += 1;
      continue;
    }

    // Cita: líneas consecutivas que empiezan por `>`.
    if (/^>\s?/.test(trimmed)) {
      const quoteLines: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i]!.trim())) {
        quoteLines.push(lines[i]!.trim().replace(/^>\s?/, ''));
        i += 1;
      }
      blocks.push({ kind: 'quote', lines: quoteLines });
      continue;
    }

    // Lista.
    const isUnordered = /^\s*[-*]\s+/.test(line);
    const isOrdered = /^\s*\d+\.\s+/.test(line);
    if (isUnordered || isOrdered) {
      const ordered = isOrdered;
      const items: InlineToken[][] = [];
      while (i < lines.length) {
        const current = lines[i]!;
        const currentTrim = current.trim();
        if (ordered) {
          if (!/^\s*\d+\.\s+/.test(current)) break;
          items.push(parseInline(currentTrim.replace(/^\d+\.\s+/, '')));
        } else {
          if (!/^\s*[-*]\s+/.test(current)) break;
          items.push(parseInline(currentTrim.replace(/^[-*]\s+/, '')));
        }
        i += 1;
      }
      blocks.push({ kind: 'list', ordered, items });
      continue;
    }

    // Párrafo: consume líneas consecutivas hasta línea en blanco, fin de
    // bloque o fin de input. Las unimos con un espacio (líneas del
    // mismo párrafo).
    if (trimmed.length > 0) {
      const paraLines: string[] = [line.replace(/\s+$/, '')];
      i += 1;
      while (i < lines.length) {
        const next = lines[i]!;
        const nextTrim = next.trim();
        if (nextTrim.length === 0) break;
        if (detectBlock(nextTrim)) break;
        if (/^```/.test(nextTrim)) break;
        if (/^>\s?/.test(nextTrim)) break;
        if (/^\s*[-*]\s+/.test(next) || /^\s*\d+\.\s+/.test(next)) break;
        paraLines.push(next.replace(/\s+$/, ''));
        i += 1;
      }
      // Si la línea anterior termina con dos espacios o `\` la
      // interpretamos como hard-break; en otro caso unimos con espacio.
      const joined = paraLines
        .map((ln, idx) => {
          if (idx === 0) return ln;
          if (/(?: {2,}|\\)$/.test(paraLines[idx - 1] ?? '')) {
            return '\n' + ln;
          }
          return ' ' + ln;
        })
        .join('');
      blocks.push({ kind: 'paragraph', children: parseInline(joined) });
      continue;
    }

    i += 1;
  }

  return blocks;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function renderInline(tokens: InlineToken[]): ReactNode[] {
  return tokens.map((token, idx) => {
    switch (token.kind) {
      case 'text':
        return <Fragment key={idx}>{token.value}</Fragment>;
      case 'bold':
        return (
          <strong key={idx} className="font-semibold text-foreground">
            {renderInline(parseInline(token.value))}
          </strong>
        );
      case 'italic':
        return (
          <em key={idx} className="italic">
            {renderInline(parseInline(token.value))}
          </em>
        );
      case 'code':
        return (
          <code
            key={idx}
            className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
          >
            {token.value}
          </code>
        );
      case 'link':
        return (
          <a
            key={idx}
            href={token.href}
            target="_blank"
            rel="noreferrer"
            className="text-primary underline-offset-2 hover:underline"
          >
            {token.text}
          </a>
        );
    }
  });
}

function renderBlock(block: Block, idx: number): ReactNode {
  switch (block.kind) {
    case 'heading': {
      const className = 'font-semibold tracking-tight';
      if (block.level === 1) {
        return (
          <h1 key={idx} className={cn(className, 'text-base')}>
            {renderInline(block.children)}
          </h1>
        );
      }
      if (block.level === 2) {
        return (
          <h2 key={idx} className={cn(className, 'text-sm')}>
            {renderInline(block.children)}
          </h2>
        );
      }
      return (
        <h3 key={idx} className={cn(className, 'text-sm')}>
          {renderInline(block.children)}
        </h3>
      );
    }
    case 'paragraph':
      return (
        <p key={idx} className="my-1.5 leading-relaxed">
          {renderInline(block.children)}
        </p>
      );
    case 'list': {
      const Tag = block.ordered ? 'ol' : 'ul';
      return (
        <Tag
          key={idx}
          className={cn(
            'my-1.5 pl-5',
            block.ordered ? 'list-decimal' : 'list-disc',
          )}
        >
          {block.items.map((item, i) => (
            <li key={i} className="my-0.5">
              {renderInline(item)}
            </li>
          ))}
        </Tag>
      );
    }
    case 'quote':
      return (
        <blockquote
          key={idx}
          className="my-1.5 border-l-2 border-muted-foreground/30 pl-3 text-muted-foreground"
        >
          {block.lines.map((line, i) => (
            <p key={i} className="my-0.5">
              {renderInline(parseInline(line))}
            </p>
          ))}
        </blockquote>
      );
    case 'code-block':
      return (
        <pre
          key={idx}
          className="my-1.5 overflow-x-auto rounded-md bg-muted p-2 font-mono text-[0.8em]"
        >
          <code>{block.value}</code>
        </pre>
      );
    case 'hr':
      return <hr key={idx} className="my-2 border-border" />;
  }
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export function MarkdownResponse({ text, className }: MarkdownResponseProps) {
  const blocks = useMemo(() => parseBlocks(text), [text]);

  if (blocks.length === 0) {
    return <p className="text-muted-foreground">Sin contenido.</p>;
  }

  return (
    <div className={cn('text-sm leading-relaxed', className)}>
      {blocks.map((block, idx) => renderBlock(block, idx))}
    </div>
  );
}
