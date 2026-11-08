import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { SearchResult } from '../api/types';
import { ResultsGrid } from '../components/ResultsGrid/ResultsGrid';

const ebay: SearchResult = {
  id: 'e-1',
  title: 'Brown suede trucker jacket',
  price: 45,
  image_url: 'data:image/svg+xml,e1',
  listing_url: 'https://example.com/mock-listing/e-1',
  source: 'ebay',
  match_score: 86.6,
};

const local: SearchResult = {
  id: 'l-1',
  title: 'Black wool coat',
  price: null,
  image_url: 'data:image/svg+xml,l1',
  listing_url: null,
  source: 'local',
  match_score: 40,
};

function card(title: string) {
  return screen.getByRole('img', { name: title }).closest('article')!;
}

describe('ResultsGrid', () => {
  it('shows image, title, USD price, score, source, and a new-tab link for eBay items', () => {
    render(<ResultsGrid state={{ status: 'success', results: [ebay, local] }} onRetry={vi.fn()} />);
    const item = within(card(ebay.title));

    expect(item.getByRole('img')).toHaveAttribute('src', ebay.image_url);
    expect(item.getByRole('heading', { name: ebay.title })).toBeInTheDocument();
    expect(item.getByText('$45.00')).toBeInTheDocument();
    expect(item.getByText('87')).toBeInTheDocument();
    expect(item.getByText('eBay')).toBeInTheDocument();

    const link = item.getByRole('link', { name: /view listing.*opens in a new tab/i });
    expect(link).toHaveAttribute('href', ebay.listing_url);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('shows local archive items as not for sale, with no price and no link', () => {
    render(<ResultsGrid state={{ status: 'success', results: [ebay, local] }} onRetry={vi.fn()} />);
    const item = within(card(local.title));

    expect(item.getByText('Price unavailable')).toBeInTheDocument();
    expect(item.getByText('Archive (not for sale)')).toBeInTheDocument();
    expect(item.getByText('40')).toBeInTheDocument();
    expect(item.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getAllByRole('link')).toHaveLength(1);
  });

  it('shows skeleton cards and announces progress while loading', () => {
    render(<ResultsGrid state={{ status: 'loading' }} onRetry={vi.fn()} />);
    expect(screen.getByTestId('results-skeleton')).toBeInTheDocument();
    expect(screen.getByText('Finding matches…')).toHaveAttribute('aria-live', 'polite');
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('shows a friendly message when there are no results', () => {
    render(<ResultsGrid state={{ status: 'success', results: [] }} onRetry={vi.fn()} />);
    expect(screen.getByText(/no matches for these details/i)).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('shows errors in an alert with Retry', async () => {
    const onRetry = vi.fn();
    render(<ResultsGrid state={{ status: 'error', message: 'Search broke.' }} onRetry={onRetry} />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Search broke.');
    await userEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
