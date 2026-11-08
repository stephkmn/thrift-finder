import { useEffect, useState } from 'react';

/**
 * A temporary object URL for showing `file`, revoked when the file changes or the component
 * unmounts, so a photo never outlives the part of the page that shows it.
 */
export function useObjectUrl(file: File | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file) return;
    const next = URL.createObjectURL(file);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing with an external resource
    setUrl(next);
    return () => {
      URL.revokeObjectURL(next);
      setUrl(null);
    };
  }, [file]);

  return url;
}
