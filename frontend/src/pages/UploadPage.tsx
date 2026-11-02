import { useEffect, useReducer, useRef } from 'react';
import { ApiError, extract } from '../api/client';
import type { ExtractInput } from '../api/client';
import type { ExtractResponse } from '../api/types';
import { AttributeCard } from '../components/AttributeCard/AttributeCard';
import { UploadForm } from '../components/UploadForm/UploadForm';
import styles from './UploadPage.module.css';

type RequestState =
  | { status: 'idle' }
  | { status: 'loading'; input: ExtractInput }
  | { status: 'success'; input: ExtractInput; result: ExtractResponse }
  | { status: 'error'; input: ExtractInput; message: string };

type Action =
  | { type: 'submit'; input: ExtractInput }
  | { type: 'succeed'; result: ExtractResponse }
  | { type: 'fail'; message: string }
  | { type: 'reset' };

function reducer(state: RequestState, action: Action): RequestState {
  switch (action.type) {
    case 'submit':
      return { status: 'loading', input: action.input };
    case 'succeed':
      return state.status === 'loading'
        ? { status: 'success', input: state.input, result: action.result }
        : state;
    case 'fail':
      return state.status === 'loading'
        ? { status: 'error', input: state.input, message: action.message }
        : state;
    case 'reset':
      return { status: 'idle' };
  }
}

const FALLBACK_ERROR = 'Something went wrong while analyzing your item. Please try again.';

export function UploadPage() {
  const [state, dispatch] = useReducer(reducer, { status: 'idle' });
  // Bumped on "Start over" to remount the form with empty inputs.
  const [formKey, bumpFormKey] = useReducer((key: number) => key + 1, 0);
  // Ignore responses from a request superseded by "Start over" or a newer submit.
  const requestId = useRef(0);

  const run = async (input: ExtractInput) => {
    const id = ++requestId.current;
    dispatch({ type: 'submit', input });
    try {
      const result = await extract(input);
      if (id === requestId.current) dispatch({ type: 'succeed', result });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : FALLBACK_ERROR;
      if (id === requestId.current) dispatch({ type: 'fail', message });
    }
  };

  const startOver = () => {
    requestId.current++;
    dispatch({ type: 'reset' });
    bumpFormKey();
  };

  // On phones the outcome renders below the fold; bring it into view when it arrives.
  const outcomeRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (state.status !== 'success' && state.status !== 'error') return;
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    outcomeRef.current?.scrollIntoView?.({
      block: 'nearest',
      behavior: reduceMotion ? 'auto' : 'smooth',
    });
  }, [state.status]);

  const isLoading = state.status === 'loading';

  return (
    <UploadForm
      key={formKey}
      onSubmit={run}
      disabled={isLoading}
      intro={
        <>
          <h2 className={styles.heading}>Found a jacket you love?</h2>
          <p className={styles.lede}>
            Add a photo, a description, or both. We&rsquo;ll read its details so you can find it
            secondhand.
          </p>
        </>
      }
    >
      <div className={styles.status} aria-live="polite">
        {isLoading && (
          <p className={styles.loading}>
            <span className={styles.spinner} aria-hidden="true" />
            Analyzing your item…
          </p>
        )}
      </div>

      {state.status === 'error' && (
        <div ref={outcomeRef} className={styles.error} role="alert">
          <p className={styles.errorMessage}>
            <svg
              className={styles.errorIcon}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7.5v5.5" />
              <path d="M12 16.5h.01" />
            </svg>
            {state.message}
          </p>
          <button type="button" className={styles.retry} onClick={() => run(state.input)}>
            Retry
          </button>
        </div>
      )}

      {state.status === 'success' && (
        <div ref={outcomeRef} className={styles.result}>
          <AttributeCard result={state.result} />
          <button type="button" className={styles.startOver} onClick={startOver}>
            Start over
          </button>
        </div>
      )}
    </UploadForm>
  );
}
