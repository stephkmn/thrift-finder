/**
 * The first image in a paste, or null when the clipboard holds no image (e.g. plain text).
 * Screenshots and copied images arrive as an unnamed "image.png"; give them a name the
 * upload form can show.
 */
export function imageFromClipboard(data: DataTransfer | null): File | null {
  if (!data) return null;
  const fromFiles = Array.from(data.files ?? []).find((file) => file.type.startsWith('image/'));
  const fromItems = Array.from(data.items ?? [])
    .find((item) => item.kind === 'file' && item.type.startsWith('image/'))
    ?.getAsFile();
  const image = fromFiles ?? fromItems ?? null;
  if (!image) return null;
  const extension = image.type.split('/')[1]?.replace('jpeg', 'jpg') || 'png';
  return new File([image], `Pasted image.${extension}`, {
    type: image.type,
    lastModified: Date.now(),
  });
}
