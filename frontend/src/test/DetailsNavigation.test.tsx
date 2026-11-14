import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UploadPage } from '../pages/UploadPage';

const titles = () =>
  screen.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent);

/** Mock mode: search "black denim jacket" and wait for the board. */
async function showBoard() {
  const user = userEvent.setup();
  render(<UploadPage />);
  await user.type(screen.getByRole('textbox', { name: /description/i }), 'black denim jacket');
  await user.click(screen.getByRole('button', { name: 'Identify details' }));
  await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(10));
  return user;
}

describe('S3-6 navigation', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_USE_MOCKS', 'true');
    vi.stubEnv('VITE_MOCK_DELAY_MS', '0');
    window.history.replaceState(null, '', '/');
  });

  it('opens a polaroid at /item/<id> and the Back link returns to the same board', async () => {
    const user = await showBoard();
    const before = titles();
    const photo = screen.getAllByRole('button', { name: /^See details: / })[2];
    const title = photo.getAttribute('aria-label')!.replace('See details: ', '');
    const id = photo.dataset.listingId!;

    await user.click(photo);
    expect(window.location.pathname).toBe(`/item/${encodeURIComponent(id)}`);
    const heading = screen.getByRole('heading', { level: 2, name: title });
    expect(heading).toHaveFocus();
    // The board is still there, just hidden, so nothing is searched again.
    expect(screen.queryByRole('region', { name: 'Your upload' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Back to results' }));
    await waitFor(() => expect(window.location.pathname).toBe('/'));
    expect(titles()).toEqual(before);
    expect(screen.getByRole('button', { name: `See details: ${title}` })).toHaveFocus();
  });

  it("the browser's Back button returns to the board too", async () => {
    const user = await showBoard();
    await user.click(screen.getAllByRole('button', { name: /^See details: / })[0]);
    expect(window.location.pathname).toMatch(/^\/item\//);

    window.history.back();
    await waitFor(() => expect(window.location.pathname).toBe('/'));
    await waitFor(() => expect(screen.getByRole('region', { name: 'Your upload' })).toBeVisible());
  });

  it('a details URL opened directly has a way back to the start', async () => {
    window.history.replaceState(null, '', '/item/secondhand-000123');
    const user = userEvent.setup();
    render(<UploadPage />);
    expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^Back/ }));
    expect(window.location.pathname).toBe('/');
    expect(screen.getByRole('button', { name: 'Identify details' })).toBeInTheDocument();
  });
});
