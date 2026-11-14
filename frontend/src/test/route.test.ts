import { describe, expect, it } from 'vitest';
import { itemPath, parseRoute } from '../lib/route';

describe('route', () => {
  it('round-trips ids through the URL, including eBay ids with "|"', () => {
    for (const id of ['secondhand-000123', 'v1|123456789|0', 'a b/c']) {
      expect(parseRoute(itemPath(id))).toEqual({ page: 'item', id });
    }
    expect(itemPath('v1|1|0')).toBe('/item/v1%7C1%7C0');
  });

  it('treats everything else as the board', () => {
    expect(parseRoute('/')).toEqual({ page: 'board' });
    expect(parseRoute('/item/')).toEqual({ page: 'board' });
    expect(parseRoute('/somewhere')).toEqual({ page: 'board' });
    expect(parseRoute('/item/%E0%A4%A')).toEqual({ page: 'board' }); // malformed escape
  });
});
