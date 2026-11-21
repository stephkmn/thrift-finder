import { useCallback, useEffect, useState } from 'react';

/**
 * Two views, no router library (S3-6): the board at `/` and a listing's details at
 * `/item/<id>`. Opening a listing pushes a history entry, so the browser's Back button and
 * the page's Back link both return to the board, which stays in memory the whole time.
 */
export type Route = { page: 'board' } | { page: 'item'; id: string };

const ITEM_PREFIX = '/item/';

/** Marks history entries pushed from the board, so Back knows it can go back to it. */
interface HistoryState {
  fromBoard?: boolean;
}

export function itemPath(id: string): string {
  // eBay ids contain "|"; encode so every id round-trips through the URL.
  return ITEM_PREFIX + encodeURIComponent(id);
}

export function parseRoute(pathname: string): Route {
  if (!pathname.startsWith(ITEM_PREFIX)) return { page: 'board' };
  const raw = pathname.slice(ITEM_PREFIX.length);
  try {
    const id = decodeURIComponent(raw);
    return id ? { page: 'item', id } : { page: 'board' };
  } catch {
    return { page: 'board' }; // malformed escape sequence
  }
}

export function useRoute() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname));

  useEffect(() => {
    const onPopState = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const openItem = useCallback((id: string) => {
    window.history.pushState({ fromBoard: true } satisfies HistoryState, '', itemPath(id));
    setRoute({ page: 'item', id });
  }, []);

  const backToBoard = useCallback(() => {
    if ((window.history.state as HistoryState | null)?.fromBoard) {
      window.history.back(); // the popstate listener updates the route
    } else {
      // Opened straight from a link or a reload: there is no board entry to go back to.
      window.history.replaceState(null, '', '/');
      setRoute({ page: 'board' });
    }
  }, []);

  return { route, openItem, backToBoard };
}
