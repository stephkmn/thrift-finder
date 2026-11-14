import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import type { Attributes, ExtractResponse } from '../api/types';
import { AttributeEditor } from '../components/AttributeEditor/AttributeEditor';
import { VOCABULARY } from '../lib/vocabulary';

const extracted: ExtractResponse = {
  attributes: {
    category: 'jacket',
    color: 'black',
    fabric: 'denim',
    fit: 'regular fit',
    others: ['hood'],
  },
  confidences: {
    category: 0.94,
    color: 0.88,
    fabric: 0.71,
    fit: 0.55,
    others: { hood: 0.82 },
  },
  query_id: 'q-1',
};

function setup(result: ExtractResponse = extracted) {
  const onChange = vi.fn();
  function Harness() {
    const [value, setValue] = useState<Attributes>(result.attributes);
    return (
      <AttributeEditor
        extracted={result}
        value={value}
        onChange={(next) => {
          onChange(next);
          setValue(next);
        }}
      />
    );
  }
  render(<Harness />);
  const user = userEvent.setup();
  const latest = (): Attributes => onChange.mock.lastCall![0];
  const row = (name: string) =>
    screen.getByRole('group', { name: new RegExp(`^${name}`) }) as HTMLElement;
  return { user, latest, row };
}

describe('AttributeEditor', () => {
  it('shows each attribute with vocabulary options and no confidence numbers', () => {
    setup();
    expect(screen.getByRole('combobox', { name: /category/i })).toHaveValue('jacket');
    expect(screen.getByRole('combobox', { name: /fabric/i })).toHaveValue('denim');
    expect(screen.getByRole('combobox', { name: /^fit/i })).toHaveValue('regular fit');
    expect(screen.getByRole('radio', { name: 'black' })).toBeChecked();
    expect(screen.getAllByRole('radio')).toHaveLength(VOCABULARY.color.length);
    expect(
      within(screen.getByRole('combobox', { name: /fabric/i })).getAllByRole('option'),
    ).toHaveLength(VOCABULARY.fabric.length);
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it('edits color with a swatch, marks it "was black", and resets it', async () => {
    const { user, latest } = setup();
    expect(screen.queryByText('was black')).not.toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: 'brown' }));
    expect(latest().color).toBe('brown');
    expect(screen.getByText('was black')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Reset color' }));
    expect(latest().color).toBe('black');
    expect(screen.queryByText('was black')).not.toBeInTheDocument();
  });

  it('moves between colors with the arrow keys', async () => {
    const { user, latest } = setup();
    screen.getByRole('radio', { name: 'black' }).focus();
    await user.keyboard('{ArrowRight}');
    expect(latest().color).toBe(VOCABULARY.color[1]);
  });

  it('flags a low-confidence attribute only while it holds the model value', async () => {
    const { user } = setup({
      ...extracted,
      confidences: { ...extracted.confidences, fabric: 0.52 },
    });
    const fabricLabel = () => screen.getByText('Fabric').closest('label')!;
    expect(screen.getAllByText('Double-check')).toHaveLength(1);
    expect(fabricLabel()).toHaveTextContent('Double-check');

    await user.selectOptions(screen.getByRole('combobox', { name: /^fabric/i }), 'leather');
    expect(screen.queryByText('Double-check')).not.toBeInTheDocument();
    expect(screen.getByText('was denim')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Reset fabric' }));
    expect(fabricLabel()).toHaveTextContent('Double-check');
  });

  it("doesn't flag the default fit, whose confidence is low by design", () => {
    // extracted has fit "regular fit" (the attributes.yaml default) at 0.55.
    setup();
    expect(screen.queryByText('Double-check')).not.toBeInTheDocument();
  });

  it('still flags a low-confidence fit that is not the default', () => {
    setup({
      ...extracted,
      attributes: { ...extracted.attributes, fit: 'cropped' },
    });
    expect(screen.getByText('Fit').closest('label')).toHaveTextContent('Double-check');
  });

  it('removes the last feature as null, never []', async () => {
    const { user, latest, row } = setup();
    await user.click(screen.getByRole('button', { name: 'Remove hood' }));
    expect(latest().others).toBeNull();
    expect(within(row('Other features')).getByText('None')).toBeInTheDocument();
    expect(screen.getByText('was hood')).toBeInTheDocument();
  });

  it('adds features and stops offering the ones already present', async () => {
    const { user, latest } = setup();
    const picker = () => screen.getByRole('combobox', { name: 'Add feature' });
    const offered = () =>
      within(picker())
        .getAllByRole('option')
        .map((o) => o.textContent);

    expect(offered()).not.toContain('hood');
    expect(screen.getByRole('button', { name: 'Add' })).toBeDisabled();

    await user.selectOptions(picker(), 'zipper');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    expect(latest().others).toEqual(['hood', 'zipper']);
    expect(screen.getByRole('button', { name: 'Remove zipper' })).toBeInTheDocument();
    expect(offered()).not.toContain('zipper');
    expect(picker()).toHaveValue('');
  });

  it('Reset all restores every model value and clears the markers', async () => {
    const { user, latest } = setup();
    const resetAll = screen.getByRole('button', { name: 'Reset all' });
    expect(resetAll).toBeDisabled();

    await user.click(screen.getByRole('radio', { name: 'brown' }));
    await user.selectOptions(screen.getByRole('combobox', { name: /fabric/i }), 'suede');
    await user.click(screen.getByRole('button', { name: 'Remove hood' }));
    expect(screen.getAllByText(/^was /)).toHaveLength(3);

    await user.click(resetAll);
    expect(latest()).toEqual(extracted.attributes);
    expect(screen.queryByText(/^was /)).not.toBeInTheDocument();
    expect(resetAll).toBeDisabled();
  });

  it('keeps values that are not in the vocabulary instead of replacing them', () => {
    setup({
      ...extracted,
      attributes: { ...extracted.attributes, fabric: 'mesh', color: 'teal', others: ['pockets'] },
      confidences: { ...extracted.confidences, others: { pockets: 0.7 } },
    });
    expect(screen.getByRole('combobox', { name: /fabric/i })).toHaveValue('mesh');
    expect(screen.getByRole('radio', { name: 'teal' })).toBeChecked();
    expect(screen.getByRole('button', { name: 'Remove pockets' })).toBeInTheDocument();
  });

  it('flags low-confidence features as chips until the features are edited', async () => {
    const { user } = setup({
      ...extracted,
      attributes: { ...extracted.attributes, others: ['hood', 'zipper'] },
      confidences: { ...extracted.confidences, fit: 0.9, others: { hood: 0.82, zipper: 0.4 } },
    });
    const chip = () => screen.getByRole('button', { name: 'Remove zipper' }).closest('li')!;
    expect(chip()).toHaveTextContent('Double-check');

    await user.click(screen.getByRole('button', { name: 'Remove hood' }));
    expect(chip()).not.toHaveTextContent('Double-check');
  });
});

describe('AttributeEditor — keyboard focus', () => {
  const picker = () => screen.getByRole('combobox', { name: 'Add feature' });

  it('moves focus to the Add-feature select after removing a chip', async () => {
    const { user } = setup();
    await user.click(screen.getByRole('button', { name: 'Remove hood' }));
    expect(picker()).toHaveFocus();
  });

  it('still lands on the Add-feature select when every feature was selected', async () => {
    const { user } = setup({
      ...extracted,
      attributes: { ...extracted.attributes, others: [...VOCABULARY.features] },
      confidences: {
        ...extracted.confidences,
        others: Object.fromEntries(VOCABULARY.features.map((f) => [f, 0.9])),
      },
    });
    expect(screen.queryByRole('combobox', { name: 'Add feature' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Remove hood' }));
    expect(picker()).toHaveFocus();
    expect(document.body).not.toHaveFocus();
  });

  it('falls back to the first chip when the select cannot appear', async () => {
    const { user } = setup({
      ...extracted,
      attributes: { ...extracted.attributes, others: [...VOCABULARY.features, 'pockets'] },
      confidences: {
        ...extracted.confidences,
        others: Object.fromEntries([...VOCABULARY.features, 'pockets'].map((f) => [f, 0.9])),
      },
    });
    await user.click(screen.getByRole('button', { name: 'Remove pockets' }));
    expect(screen.getByRole('button', { name: `Remove ${VOCABULARY.features[0]}` })).toHaveFocus();
  });

  it('moves focus to the attribute control after its Reset button disappears', async () => {
    const { user } = setup();

    await user.selectOptions(screen.getByRole('combobox', { name: /fabric/i }), 'suede');
    await user.click(screen.getByRole('button', { name: 'Reset fabric' }));
    expect(screen.getByRole('combobox', { name: /fabric/i })).toHaveFocus();

    await user.click(screen.getByRole('radio', { name: 'brown' }));
    await user.click(screen.getByRole('button', { name: 'Reset color' }));
    expect(screen.getByRole('radio', { name: 'black' })).toHaveFocus();

    await user.click(screen.getByRole('button', { name: 'Remove hood' }));
    await user.click(screen.getByRole('button', { name: 'Reset other features' }));
    expect(picker()).toHaveFocus();
  });

  it('moves focus to the editor heading after Reset all', async () => {
    const { user } = setup();
    await user.click(screen.getByRole('radio', { name: 'brown' }));
    await user.click(screen.getByRole('button', { name: 'Reset all' }));
    expect(screen.getByRole('heading', { name: 'What we found' })).toHaveFocus();
  });
});
