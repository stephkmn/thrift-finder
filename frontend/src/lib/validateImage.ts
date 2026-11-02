export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const;
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

// Browsers often report an empty MIME type for HEIC, so check the extension too.
function isHeic(file: File): boolean {
  return /^image\/hei[cf]$/.test(file.type) || /\.hei[cf]$/i.test(file.name);
}

/** Returns a user-facing error message, or null when the file can be uploaded. */
export function validateImage(file: File): string | null {
  if (isHeic(file)) {
    return "iPhone HEIC photos aren't supported yet — export as JPG.";
  }
  if (!(ACCEPTED_IMAGE_TYPES as readonly string[]).includes(file.type)) {
    return "That file isn't a JPG, PNG, or WebP image.";
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return 'Please choose an image under 10 MB.';
  }
  return null;
}
