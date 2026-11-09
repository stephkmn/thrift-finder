import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from '../api/mocks/extract.json';
import { rankListings } from '../api/mocks/mockApi';
import { MOCK_POOL } from '../api/mocks/searchPool';
import type { SearchRequest, SearchResponse } from '../api/types';
import { UploadPage } from '../pages/UploadPage';
import { makeFile } from './helpers';

function setup() {
  // applyAccept: false lets tests hand the input files the browser picker would filter out.
  const user = userEvent.setup({ applyAccept: false });
  render(<UploadPage />);
  return {
    user,
    submit: () => screen.getByRole('button', { name: 'Read the details' }),
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

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

/**
 * Live mode against a fake backend: /api/extract returns the mock fixture with a numbered
 * query_id, /api/search ranks the mock pool unless `onSearch` answers instead.
 */
function fakeBackend(onSearch?: (request: SearchRequest) => Response) {
  vi.stubEnv('VITE_USE_MOCKS', 'false');
  const searches: SearchRequest[] = [];
  let extracts = 0;
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    if (url === '/api/extract') return json({ ...fixture, query_id: `q-${++extracts}` });
    const request = JSON.parse(init!.body as string) as SearchRequest;
    searches.push(request);
    return onSearch?.(request) ?? json(rankListings(MOCK_POOL, request.edited_attributes));
  });
  return searches;
}

async function extractText(text: string) {
  const ui = setup();
  await ui.user.type(ui.textbox(), text);
  await ui.user.click(ui.submit());
  await screen.findByRole('region', { name: 'Your upload' });
  return ui;
}

const resultTitles = () =>
  screen.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent);
const updateButton = () => screen.getByRole('button', { name: 'Update results' });

describe('UploadPage — editor and results', () => {
  it('collapses the form, searches once automatically, and re-searches with edits', async () => {
    const searches = fakeBackend();
    await extractText('black denim jacket');

    const summary = screen.getByRole('region', { name: 'Your upload' });
    expect(summary).toHaveTextContent('black denim jacket');
    expect(summary).toHaveTextContent('q-1');
    expect(screen.queryByRole('textbox', { name: /description/i })).not.toBeInTheDocument();

    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(10));
    expect(searches).toEqual([
      {
        query_id: 'q-1',
        original_attributes: fixture.attributes,
        edited_attributes: fixture.attributes,
        text: 'black denim jacket',
      },
    ]);
    const before = resultTitles();
    expect(updateButton()).toBeDisabled();

    const user = userEvent.setup();
    await user.click(screen.getByRole('radio', { name: 'brown' }));
    expect(screen.getByText('was black')).toBeInTheDocument();
    expect(updateButton()).toBeEnabled();

    await user.click(updateButton());
    await waitFor(() => expect(resultTitles()).not.toEqual(before));
    expect(searches).toHaveLength(2);
    expect(searches[1]).toEqual({
      ...searches[0],
      edited_attributes: { ...fixture.attributes, color: 'brown' },
    });
    expect(updateButton()).toBeDisabled();
  });

  it('sends others: null after removing the hood, and offers added features only once', async () => {
    const searches = fakeBackend();
    await extractText('jacket');
    await screen.findAllByRole('article');
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: 'Remove hood' }));
    await user.click(updateButton());
    await waitFor(() => expect(searches).toHaveLength(2));
    expect(searches[1].edited_attributes.others).toBeNull();
    expect(searches[1].original_attributes.others).toEqual(['hood']);

    const picker = screen.getByRole('combobox', { name: 'Add feature' });
    await user.selectOptions(picker, 'zipper');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    expect(screen.getByRole('button', { name: 'Remove zipper' })).toBeInTheDocument();
    expect(within(picker).queryByRole('option', { name: 'zipper' })).not.toBeInTheDocument();
  });

  it('omits text from the search when there was no description', async () => {
    const searches = fakeBackend();
    const { user, fileInput, submit } = setup();
    await user.upload(fileInput(), makeFile('jacket.png', 'image/png'));
    await user.click(submit());

    await waitFor(() => expect(searches).toHaveLength(1));
    expect(searches[0]).not.toHaveProperty('text');
    expect(screen.getByRole('img', { name: 'Your photo' })).toBeInTheDocument();
  });

  it('Reset all and per-attribute resets restore model values and disable Update results', async () => {
    fakeBackend();
    await extractText('jacket');
    await screen.findAllByRole('article');
    const user = userEvent.setup();

    await user.click(screen.getByRole('radio', { name: 'brown' }));
    await user.selectOptions(screen.getByRole('combobox', { name: /fabric/i }), 'suede');
    expect(updateButton()).toBeEnabled();

    await user.click(screen.getByRole('button', { name: 'Reset fabric' }));
    expect(screen.getByRole('combobox', { name: /fabric/i })).toHaveValue('denim');
    expect(screen.queryByText('was denim')).not.toBeInTheDocument();
    expect(screen.getByText('was black')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Reset all' }));
    expect(screen.getByRole('radio', { name: 'black' })).toBeChecked();
    expect(screen.queryByText(/^was /)).not.toBeInTheDocument();
    expect(updateButton()).toBeDisabled();
  });

  it('flags the low-confidence fit until it is edited, and again after reset', async () => {
    fakeBackend();
    await extractText('jacket');
    const user = userEvent.setup();
    const fitLabel = () => screen.getByText('Fit').closest('label')!;

    expect(screen.getAllByText('Double-check')).toHaveLength(1);
    expect(fitLabel()).toHaveTextContent('Double-check');

    await user.selectOptions(screen.getByRole('combobox', { name: /^fit/i }), 'slim fit');
    expect(screen.queryByText('Double-check')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Reset fit' }));
    expect(fitLabel()).toHaveTextContent('Double-check');
  });

  it('shows skeletons while searching, then the results', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'true');
    vi.stubEnv('VITE_MOCK_DELAY_MS', '30');
    await extractText('black denim jacket');

    expect(screen.getByTestId('results-skeleton')).toBeInTheDocument();
    expect(screen.getByText('Finding matches…')).toBeInTheDocument();
    expect(updateButton()).toBeDisabled();

    expect(await screen.findAllByRole('article')).toHaveLength(10);
    expect(screen.queryByTestId('results-skeleton')).not.toBeInTheDocument();
  });

  it('shows the empty state when the search returns no results', async () => {
    fakeBackend(() => json({ results: [] } satisfies SearchResponse));
    await extractText('jacket');
    expect(await screen.findByText(/no matches for these details/i)).toBeInTheDocument();
  });

  it('shows the __search_error__ alert, and Retry resends the same request', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'true');
    await extractText('__search_error__');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Something went wrong while finding matches');

    const searches = fakeBackend();
    await userEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    await screen.findAllByRole('article');
    expect(searches).toHaveLength(1);
    expect(searches[0]).toMatchObject({
      text: '__search_error__',
      edited_attributes: fixture.attributes,
    });
    expect(searches[0].query_id).toMatch(/^mock-/);
  });

  it('Edit upload restores the photo and text, and resubmitting a change starts a new session', async () => {
    const searches = fakeBackend();
    const { user, fileInput, textbox, submit } = setup();
    await user.upload(fileInput(), makeFile('jacket.png', 'image/png'));
    await user.type(textbox(), 'black denim jacket');
    await user.click(submit());
    await screen.findAllByRole('article');

    await user.click(screen.getByRole('radio', { name: 'brown' }));
    await user.click(screen.getByRole('button', { name: 'Edit upload' }));

    expect(textbox()).toHaveValue('black denim jacket');
    expect(screen.getByText('jacket.png')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('radio', { name: 'brown' })).toBeChecked();

    await user.click(screen.getByRole('button', { name: 'Edit upload' }));
    await user.type(textbox(), ', cropped');
    await user.click(submit());
    await waitFor(() => expect(searches).toHaveLength(2));
    expect(screen.getByRole('region', { name: 'Your upload' })).toHaveTextContent('q-2');
    expect(screen.getByRole('radio', { name: 'black' })).toBeChecked();
    expect(searches[1]).toMatchObject({
      query_id: 'q-2',
      edited_attributes: fixture.attributes,
      text: 'black denim jacket, cropped',
    });
  });

  it('resubmitting an unchanged upload keeps the session, edits, and results', async () => {
    const searches = fakeBackend();
    const extracts = () =>
      vi.mocked(globalThis.fetch).mock.calls.filter(([url]) => url === '/api/extract').length;
    const { user, fileInput, textbox, submit } = setup();
    await user.upload(fileInput(), makeFile('jacket.png', 'image/png'));
    await user.type(textbox(), 'black denim jacket');
    await user.click(submit());
    await screen.findAllByRole('article');

    await user.click(screen.getByRole('radio', { name: 'brown' }));
    await user.click(updateButton());
    await waitFor(() => expect(searches).toHaveLength(2));
    const results = resultTitles();
    await user.click(screen.getByRole('radio', { name: 'green' }));

    await user.click(screen.getByRole('button', { name: 'Edit upload' }));
    await user.click(submit());

    const summary = await screen.findByRole('region', { name: 'Your upload' });
    expect(summary).toHaveTextContent('q-1');
    expect(summary.querySelector('h2')).toHaveFocus();
    expect(screen.getByRole('radio', { name: 'green' })).toBeChecked();
    expect(screen.getByText('was black')).toBeInTheDocument();
    expect(resultTitles()).toEqual(results);
    expect(updateButton()).toBeEnabled();
    expect(extracts()).toBe(1);
    expect(searches).toHaveLength(2);
  });

  it('hides the pending-edits note when the search for those edits failed', async () => {
    const searches = fakeBackend((request) =>
      request.edited_attributes.color === 'brown'
        ? json({ detail: 'boom' }, 500)
        : json(rankListings(MOCK_POOL, request.edited_attributes)),
    );
    await extractText('black denim jacket');
    await screen.findAllByRole('article');
    const user = userEvent.setup();
    const note = () => screen.queryByText(/your results don.t include these edits yet/i);

    await user.click(screen.getByRole('radio', { name: 'brown' }));
    expect(note()).toBeInTheDocument();

    await user.click(updateButton());
    expect(await screen.findByRole('alert')).toHaveTextContent('finding matches');
    expect(searches).toHaveLength(2);
    expect(note()).not.toBeInTheDocument();
  });

  it('Start over clears everything back to an empty form', async () => {
    fakeBackend();
    const { user, fileInput, textbox, submit } = setup();
    await user.upload(fileInput(), makeFile('jacket.png', 'image/png'));
    await user.type(textbox(), 'black denim jacket');
    await user.click(submit());
    await screen.findAllByRole('article');

    await user.click(screen.getByRole('button', { name: 'Start over' }));
    expect(screen.queryByRole('region', { name: 'Your upload' })).not.toBeInTheDocument();
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
    expect(textbox()).toHaveValue('');
    expect(screen.queryByText('jacket.png')).not.toBeInTheDocument();
    expect(submit()).toBeDisabled();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
  });
});
