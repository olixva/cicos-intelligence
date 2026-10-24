import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ClaimAnalysisPanel } from '@/components/thread/claim-analysis-panel';

describe('ClaimAnalysisPanel', () => {
  it('muestra la parte responsable devuelta por el motor determinista', () => {
    render(
      <ClaimAnalysisPanel
        analysis={{
          applicability: 'applicable',
          convention: 'CIDE',
          decision: 'resolved',
          liable_party: 'B',
          facts: [],
          rules_evaluated: [],
        }}
      />,
    );

    expect(screen.getByText('Responsable: B')).toBeInTheDocument();
  });
});
