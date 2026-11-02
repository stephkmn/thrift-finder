import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UploadPage } from '../pages/UploadPage';
import { makeFile } from './helpers';

function setup() {
  // applyAccept: false lets tests hand the input files the browser picker would filter out.
  const user = userEvent.setup({ applyAccept: false });
  render(<UploadPage />);
  return {
    user,
    submit: () => screen.getByRole('button', { name: 'Analyze item' }),
    fileInput: () => screen.getByLabelText('Photo file'),
    textbox: () => screen.getByRole('textbox', { name: /description/i }),
  };
}

describe('UploadPage', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_USE_MOCKS', 'true');
  });

  it('enables submit only once a photo or text is provided', async () => {
    const { user, submit, fileInput, textbox } = setup();
    expect(submit()).toBeDisabled();

    await user.type(textbox(), '   ');
    expect(submit()).toBeDisabled();

    await user.type(textbox(), 'red parka');
    expect(submit()).toBeEnabled();

    await user.clear(textbox());
    expect(submit()).toBeDisabled();

    await user.upload(fileInput(), makeFile('jacket.png', 'image/png'));
    expect(submit()).toBeEnabled();
    expect(screen.getByText('jacket.png')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Remove' }));
    expect(submit()).toBeDisabled();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });

  it.each([
    [
      'a non-image',
      makeFile('receipt.pdf', 'application/pdf'),
      "That file isn't a JPG, PNG, or WebP image.",
    ],
    [
      'a file over 10 MB',
      makeFile('huge.jpg', 'image/jpeg', 10 * 1024 * 1024 + 1),
      'Please choose an image under 10 MB.',
    ],
  ])('rejects %s with a message and keeps submit disabled', async (_label, file, message) => {
    const { user, submit, fileInput } = setup();

    await user.upload(fileInput(), file);

    expect(screen.getByRole('alert')).toHaveTextContent(message);
    expect(submit()).toBeDisabled();
  });

  it('opens the file picker from the keyboard', async () => {
    const { user, fileInput } = setup();
    const clickSpy = vi.spyOn(fileInput(), 'click');

    screen.getByRole('button', { name: 'Add a photo' }).focus();
    await user.keyboard('{Enter}');
    await user.keyboard(' ');

    expect(clickSpy).toHaveBeenCalledTimes(2);
  });

  it('round-trips text through the mock API and shows all five attributes', async () => {
    vi.stubEnv('VITE_MOCK_DELAY_MS', '30');
    const { user, submit, textbox } = setup();

    await user.type(textbox(), 'black denim jacket');
    await user.click(submit());

    expect(screen.getByText('Analyzing your item…')).toBeInTheDocument();
    expect(textbox()).toBeDisabled();
    expect(submit()).toBeDisabled();

    const card = await screen.findByRole('region', { name: 'What we found' });
    for (const [label, value, percent] of [
      ['Category', 'jacket', '94%'],
      ['Color', 'black', '88%'],
      ['Fabric', 'denim', '71%'],
      ['Fit', 'regular', '55%'],
      ['Hood', 'no hood', '82%'],
    ]) {
      const row = within(card).getByText(label).parentElement!;
      expect(row).toHaveTextContent(value);
      expect(row).toHaveTextContent(percent);
    }
    expect(within(card).getByText(/^mock-/)).toBeInTheDocument();
    expect(screen.queryByText('Analyzing your item…')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Start over' }));
    expect(screen.queryByRole('region', { name: 'What we found' })).not.toBeInTheDocument();
    expect(textbox()).toHaveValue('');
  });

  it('shows an alert for the __error__ scenario and Retry resubmits', async () => {
    vi.stubEnv('VITE_MOCK_DELAY_MS', '30');
    const { user, submit, textbox } = setup();

    await user.type(textbox(), '__error__');
    await user.click(submit());

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Something went wrong');

    await user.click(within(alert).getByRole('button', { name: 'Retry' }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText('Analyzing your item…')).toBeInTheDocument();

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong');
  });
});
