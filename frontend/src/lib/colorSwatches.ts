/**
 * Approximate display colors for each vocabulary color in attributes.yaml.
 * Used by the color picker and the mock listing images. Names are always shown
 * next to a swatch, so these only need to be recognisable, not exact.
 */
export const COLOR_SWATCHES: Record<string, string> = {
  black: '#1c1c1c',
  white: '#f7f7f5',
  gray: '#8a8d91',
  navy: '#1f2f56',
  blue: '#2f6fd0',
  brown: '#6b4226',
  tan: '#c8a674',
  cream: '#f1e6cc',
  green: '#2e7d4f',
  olive: '#6b6b2a',
  red: '#c62828',
  burgundy: '#7a1f35',
  pink: '#f2a5bf',
  purple: '#6a3d9a',
  yellow: '#f2c230',
  orange: '#ec7a1c',
  multicolor: '#c62828', // first gradient stop; see MULTICOLOR_STOPS
};

/** Multicolor has no single hex: swatches draw these stops as a gradient. */
export const MULTICOLOR_STOPS = ['#c62828', '#f2c230', '#2e7d4f', '#2f6fd0', '#6a3d9a'];

/** Neutral fill for a color the vocabulary does not know, e.g. from a newer model. */
export const UNKNOWN_SWATCH = '#d9dee5';

/** A CSS `background` value for the swatch of `color`. */
export function swatchBackground(color: string): string {
  if (color === 'multicolor') return `linear-gradient(135deg, ${MULTICOLOR_STOPS.join(', ')})`;
  return COLOR_SWATCHES[color] ?? UNKNOWN_SWATCH;
}
