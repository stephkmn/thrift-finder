import { describe, expect, it } from 'vitest';
import { MAX_IMAGE_BYTES, validateImage } from '../lib/validateImage';
import { makeFile } from './helpers';

describe('validateImage', () => {
  it.each([
    ['photo.jpg', 'image/jpeg'],
    ['photo.png', 'image/png'],
    ['photo.webp', 'image/webp'],
  ])('accepts %s', (name, type) => {
    expect(validateImage(makeFile(name, type))).toBeNull();
  });

  it('rejects non-image files', () => {
    expect(validateImage(makeFile('receipt.pdf', 'application/pdf'))).toBe(
      "That file isn't a JPG, PNG, or WebP image.",
    );
  });

  it('rejects files over 10 MB and accepts exactly 10 MB', () => {
    expect(validateImage(makeFile('big.jpg', 'image/jpeg', MAX_IMAGE_BYTES + 1))).toBe(
      'Please choose an image under 10 MB.',
    );
    expect(validateImage(makeFile('edge.jpg', 'image/jpeg', MAX_IMAGE_BYTES))).toBeNull();
  });

  it('gives HEIC photos a specific hint, even with no MIME type', () => {
    const hint = "iPhone HEIC photos aren't supported yet. Export it as a JPG first.";
    expect(validateImage(makeFile('IMG_0001.heic', 'image/heic'))).toBe(hint);
    expect(validateImage(makeFile('IMG_0002.HEIC', ''))).toBe(hint);
  });
});
