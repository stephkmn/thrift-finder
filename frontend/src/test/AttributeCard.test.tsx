import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ExtractResponse } from '../api/types';
import { AttributeCard } from '../components/AttributeCard/AttributeCard';

const base: ExtractResponse = {
  attributes: { category: 'coat', color: 'brown', fabric: 'wool', fit: 'oversized', others: null },
  confidences: { category: 0.9, color: 0.8, fabric: 0.7, fit: 0.65, others: null },
  query_id: 'q-1',
};

function othersRow() {
  const card = screen.getByRole('region', { name: 'What we found' });
  return within(card).getByText('Other features').parentElement!;
}

describe('AttributeCard — others', () => {
  it('shows "None detected" when others is null', () => {
    render(<AttributeCard result={base} />);
    expect(othersRow()).toHaveTextContent('None detected');
    expect(within(othersRow()).queryByRole('listitem')).not.toBeInTheDocument();
  });

  it('treats an empty list the same as null', () => {
    render(
      <AttributeCard
        result={{
          ...base,
          attributes: { ...base.attributes, others: [] },
          confidences: { ...base.confidences, others: {} },
        }}
      />,
    );
    expect(othersRow()).toHaveTextContent('None detected');
  });

  it('lists each feature with its own score and flags low ones', () => {
    render(
      <AttributeCard
        result={{
          ...base,
          attributes: { ...base.attributes, others: ['hood', 'pockets'] },
          confidences: { ...base.confidences, others: { hood: 0.82, pockets: 0.41 } },
        }}
      />,
    );
    const items = within(othersRow()).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('hood');
    expect(items[0]).toHaveTextContent('82%');
    expect(items[0]).not.toHaveAttribute('data-low');
    expect(items[1]).toHaveTextContent('pockets');
    expect(items[1]).toHaveTextContent('41%');
    expect(items[1]).toHaveAttribute('data-low');
    expect(items[1]).toHaveTextContent('double-check');
  });
});
