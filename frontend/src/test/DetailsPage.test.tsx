import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Attributes, ItemDetails, SearchResult } from '../api/types';
import { DetailsPage } from '../pages/DetailsPage';

const searched: Attributes = {
  category: 'jacket',
  color: 'black',
  fabric: 'denim',
  fit: 'regular fit',
  others: ['hood'],
};

const archiveResult: SearchResult = {
  id: 'secondhand-000123',
  title: 'Brown Jacket',
  price: null,
  image_url: '/api/local-images/secondhand-000123',
  listing_url: null,
  source: 'local',
  match_score: 81.6,
};

const ebayResult: SearchResult = {
  id: 'v1|123|0',
  title: 'Black denim jacket',
  price: 48,
  image_url: 'https://i.ebayimg.com/images/g/abc/s-l500.jpg',
  listing_url: 'https://www.ebay.com/itm/123',
  source: 'ebay',
  match_score: 86,
};

const details: ItemDetails = {
  id: 'secondhand-000123',
  title: 'Brown Jacket',
  image_url: '/api/local-images/secondhand-000123',
  source: 'local',
  dataset_labels: {
    type: 'Jacket',
    category: 'Ladies',
    colors: ['Brown'],
    material: '100% bomull',
    cut: 'Regular',
    pattern: null,
    brand: null,
  },
  comparison: [
    { attribute: 'category', yours: 'jacket', listing: 'jacket', match: true },
    { attribute: 'color', yours: 'black', listing: 'brown', match: false },
    { attribute: 'fabric', yours: 'denim', listing: null, match: null },
  ],
  credit: {
    text: 'Second-Hand Fashion dataset, Nauman (2024), CC BY 4.0. Photo resized.',
    url: 'https://huggingface.co/datasets/fnauman/fashion-second-hand-front-only-rgb',
  },
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function backend(...responses: Response[]) {
  const fetchMock = vi.spyOn(globalThis, 'fetch');
  for (const response of responses) fetchMock.mockResolvedValueOnce(response);
  return fetchMock;
}

describe('DetailsPage', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_USE_MOCKS', 'false');
  });

  it('loads an archive item with the searched attributes and shows why it matched', async () => {
    const fetchMock = backend(json(details));
    render(
      <DetailsPage
        id={archiveResult.id}
        result={archiveResult}
        searched={searched}
        onBack={vi.fn()}
      />,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/item/secondhand-000123?category=jacket&color=black&fabric=denim&fit=regular+fit',
      { method: 'GET' },
    );
    expect(screen.getByRole('heading', { level: 2, name: 'Brown Jacket' })).toHaveFocus();
    expect(screen.getByText('Archive (not for sale)')).toBeInTheDocument();
    expect(screen.getByText('Price unavailable')).toBeInTheDocument();
    expect(screen.getByText('82')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /view listing/i })).not.toBeInTheDocument();

    const table = await screen.findByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => row.textContent)).toEqual([
      'Categoryjacketjacket✓ Matches',
      'Colorblackbrown✗ Different',
      'Fabricdenim—Not labeled',
    ]);
    expect(screen.getByText('100% bomull')).toBeInTheDocument();
    expect(screen.queryByText('Pattern')).not.toBeInTheDocument(); // missing labels are left out

    const credit = screen.getByRole('link', { name: /Second-Hand Fashion dataset/ });
    expect(credit).toHaveAttribute('href', details.credit.url);
    expect(credit).toHaveAttribute('target', '_blank');
    expect(credit).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('builds an eBay item from the search result, without calling the backend', () => {
    const fetchMock = backend();
    render(
      <DetailsPage id={ebayResult.id} result={ebayResult} searched={searched} onBack={vi.fn()} />,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText('$48.00')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /view listing on ebay/i });
    expect(link).toHaveAttribute('href', ebayResult.listing_url);
    expect(link).toHaveAttribute('target', '_blank');
    expect(screen.getByRole('img', { name: ebayResult.title })).toHaveAttribute(
      'src',
      ebayResult.image_url,
    );
    expect(screen.queryByText('Why it matched')).not.toBeInTheDocument();
  });

  it('says a reloaded or shared listing the archive lacks is no longer available', async () => {
    backend(json({ detail: 'Listing not found' }, 404));
    const onBack = vi.fn();
    render(<DetailsPage id="v1|123|0" searched={null} onBack={onBack} />);

    expect(
      await screen.findByRole('heading', { name: 'This listing isn’t available' }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Back to search' }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('asks to search again when there is nothing to compare', async () => {
    const fetchMock = backend(json({ ...details, comparison: [] }));
    render(<DetailsPage id={details.id} searched={null} onBack={vi.fn()} />);

    expect(fetchMock).toHaveBeenCalledWith('/api/item/secondhand-000123', { method: 'GET' });
    expect(
      await screen.findByText('Search again to compare this listing with your attributes.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Brown Jacket' })).toBeInTheDocument();
  });

  it('shows a friendly error with Retry when the details fail to load', async () => {
    const fetchMock = backend(json({ detail: 'Listing details unavailable' }, 503), json(details));
    render(
      <DetailsPage
        id={archiveResult.id}
        result={archiveResult}
        searched={searched}
        onBack={vi.fn()}
      />,
    );

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent("We couldn't load this listing");
    await userEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
