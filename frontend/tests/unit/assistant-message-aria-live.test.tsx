import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { AssistantMessage } from '@/components/thread/assistant-message';
import type { MessageAssistant } from '@/lib/thread-state';

const streamingMessage: MessageAssistant = {
  id: 'a-1',
  role: 'assistant',
  status: 'streaming',
  streamedText: 'Texto en streaming',
  toolCalls: [],
  citations: [],
  createdAt: Date.now(),
};

describe('AssistantMessage aria-live (Finding G3 #2 — WCAG 4.1.3)', () => {
  it('el bubble de texto streameado es una live region polite y no atómica', () => {
    const { container } = render(<AssistantMessage message={streamingMessage} />);
    const liveRegion = container.querySelector('[aria-live="polite"][aria-atomic="false"]');
    expect(liveRegion).not.toBeNull();
    expect(liveRegion?.textContent).toContain('Texto en streaming');
  });

  it('el span sr-only de TextGenerateEffect está aria-hidden (evita duplicación)', () => {
    const { container } = render(
      <AssistantMessage message={{ ...streamingMessage, status: 'done' }} />,
    );
    const srOnly = container.querySelector('span.sr-only');
    expect(srOnly).not.toBeNull();
    expect(srOnly).toHaveAttribute('aria-hidden', 'true');
  });
});
