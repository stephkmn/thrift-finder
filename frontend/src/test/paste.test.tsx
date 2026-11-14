import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { imageFromClipboard } from '../lib/clipboardImage';
import { UploadPage } from '../pages/UploadPage';

/** A minimal stand-in for the clipboard's DataTransfer (jsdom has none). */
function clipboard({ files = [] as File[], text = '' } = {}) {
  return {
    files,
    items: files.map((file) => ({ kind: 'file', type: file.type, getAsFile: () => file })),
    types: [...(files.length ? ['Files'] : []), ...(text ? ['text/plain'] : [])],
    getData: (type: string) => (type === 'text/plain' ? text : ''),
  };
}

const screenshot = () => new File(['png-bytes'], 'image.png', { type: 'image/png' });

function paste(target: Element | Document, data: ReturnType<typeof clipboard>) {
  // fireEvent returns false when a handler called preventDefault().
  return fireEvent.paste(target, { clipboardData: data });
}

describe('pasting a photo', () => {
  beforeEach(() => {
    vi.stubEnv('VITE_USE_MOCKS', 'true');
    window.history.replaceState(null, '', '/');
  });

  it('adds a pasted screenshot as the photo, named so the form can show it', () => {
    render(<UploadPage />);
    const handled = !paste(document.body, clipboard({ files: [screenshot()] }));

    expect(handled).toBe(true);
    expect(screen.getByText('Pasted image.png')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Preview of the selected photo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Find its details' })).toBeEnabled();
  });

  it('takes an image pasted into the description box (how phones paste)', () => {
    render(<UploadPage />);
    paste(
      screen.getByRole('textbox', { name: /description/i }),
      clipboard({ files: [screenshot()] }),
    );
    expect(screen.getByText('Pasted image.png')).toBeInTheDocument();
  });

  it('leaves pasted text alone', () => {
    render(<UploadPage />);
    const textbox = screen.getByRole('textbox', { name: /description/i });
    const handled = !paste(textbox, clipboard({ text: 'brown suede jacket' }));

    expect(handled).toBe(false); // the browser inserts the text as usual
    expect(screen.queryByText(/Pasted image/)).not.toBeInTheDocument();
  });

  it('checks a pasted image like a picked one', () => {
    render(<UploadPage />);
    paste(
      document.body,
      clipboard({ files: [new File(['gif'], 'image.gif', { type: 'image/gif' })] }),
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      "That file isn't a JPG, PNG, or WebP image.",
    );
    expect(screen.queryByText('Pasted image.gif')).not.toBeInTheDocument();
  });

  it('replaces a photo that was already chosen', () => {
    render(<UploadPage />);
    paste(document.body, clipboard({ files: [screenshot()] }));
    paste(
      document.body,
      clipboard({ files: [new File(['jpg'], 'x.jpg', { type: 'image/jpeg' })] }),
    );
    expect(screen.getByText('Pasted image.jpg')).toBeInTheDocument();
    expect(screen.queryByText('Pasted image.png')).not.toBeInTheDocument();
  });
});

describe('imageFromClipboard', () => {
  it('finds an image in the items list when files is empty', () => {
    const file = screenshot();
    const data = {
      files: [],
      items: [
        { kind: 'string', type: 'text/html', getAsFile: () => null },
        { kind: 'file', type: 'image/png', getAsFile: () => file },
      ],
    } as unknown as DataTransfer;
    expect(imageFromClipboard(data)?.name).toBe('Pasted image.png');
  });

  it('returns null without an image', () => {
    expect(imageFromClipboard(null)).toBeNull();
    expect(imageFromClipboard({ files: [], items: [] } as unknown as DataTransfer)).toBeNull();
  });
});
