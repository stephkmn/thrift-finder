import { useEffect, useReducer, useRef } from 'react';
import type { ReactNode } from 'react';
import { ApiError, extract, search } from '../api/client';
import type { ExtractInput } from '../api/client';
import type { Attributes, ExtractResponse, SearchRequest, SearchResult } from '../api/types';
import { AttributeEditor } from '../components/AttributeEditor/AttributeEditor';
import { ResultsGrid } from '../components/ResultsGrid/ResultsGrid';
import { UploadForm } from '../components/UploadForm/UploadForm';
import { UploadSummary } from '../components/UploadSummary/UploadSummary';
import { sameAttributes } from '../lib/attributes';
import { useRoute } from '../lib/route';
import { DetailsPage } from './DetailsPage';
import styles from './UploadPage.module.css';

type ExtractState =
  | { status: 'idle' }
  | { status: 'loading'; input: ExtractInput }
  | { status: 'error'; input: ExtractInput; message: string };

/** One successful extract: what the user uploaded and what the model found. */
interface Session {
  input: ExtractInput;
  extracted: ExtractResponse;
}

type SearchState =
  | { status: 'idle' }
  | { status: 'loading'; request: SearchRequest }
  | { status: 'success'; request: SearchRequest; results: SearchResult[] }
  | { status: 'error'; request: SearchRequest; message: string };

interface PageState {
  extract: ExtractState;
  session: Session | null;
  /** True while the upload form is re-opened over an existing session. */
  editingUpload: boolean;
  /** The attribute editor's current values. */
  edited: Attributes | null;
  search: SearchState;
  /** `edited_attributes` of the last search that succeeded. */
  lastSearched: Attributes | null;
}

type Action =
  | { type: 'extractStart'; input: ExtractInput }
  | { type: 'extractSucceed'; result: ExtractResponse }
  | { type: 'extractFail'; message: string }
  | { type: 'editUpload' }
  | { type: 'cancelEditUpload' }
  | { type: 'edit'; attributes: Attributes }
  | { type: 'searchStart'; request: SearchRequest }
  | { type: 'searchSucceed'; results: SearchResult[] }
  | { type: 'searchFail'; message: string }
  | { type: 'reset' };

const INITIAL_STATE: PageState = {
  extract: { status: 'idle' },
  session: null,
  editingUpload: false,
  edited: null,
  search: { status: 'idle' },
  lastSearched: null,
};

function reducer(state: PageState, action: Action): PageState {
  switch (action.type) {
    case 'extractStart':
      return { ...state, extract: { status: 'loading', input: action.input } };
    case 'extractSucceed':
      // A new extract replaces the whole session: new query_id, fresh editor, new search.
      return state.extract.status === 'loading'
        ? {
            ...INITIAL_STATE,
            session: { input: state.extract.input, extracted: action.result },
            edited: action.result.attributes,
          }
        : state;
    case 'extractFail':
      return state.extract.status === 'loading'
        ? {
            ...state,
            extract: { status: 'error', input: state.extract.input, message: action.message },
          }
        : state;
    case 'editUpload':
      return { ...state, editingUpload: true, extract: { status: 'idle' } };
    case 'cancelEditUpload':
      return { ...state, editingUpload: false, extract: { status: 'idle' } };
    case 'edit':
      return { ...state, edited: action.attributes };
    case 'searchStart':
      return { ...state, search: { status: 'loading', request: action.request } };
    case 'searchSucceed':
      return state.search.status === 'loading'
        ? {
            ...state,
            search: { status: 'success', request: state.search.request, results: action.results },
            lastSearched: state.search.request.edited_attributes,
          }
        : state;
    case 'searchFail':
      return state.search.status === 'loading'
        ? {
            ...state,
            search: { status: 'error', request: state.search.request, message: action.message },
          }
        : state;
    case 'reset':
      return INITIAL_STATE;
  }
}

/** The description goes along unchanged; omitted when the user gave none. */
/** Same photo (the very File the form was pre-filled with) and the same description. */
function sameInput(a: ExtractInput, b: ExtractInput): boolean {
  return a.image === b.image && (a.text ?? '') === (b.text ?? '');
}

function buildSearchRequest(session: Session, edited: Attributes): SearchRequest {
  const request: SearchRequest = {
    query_id: session.extracted.query_id,
    original_attributes: session.extracted.attributes,
    edited_attributes: edited,
  };
  return session.input.text ? { ...request, text: session.input.text } : request;
}

const EXTRACT_FALLBACK_ERROR = "We couldn't read your item. Try again.";
const SEARCH_FALLBACK_ERROR = "We couldn't load your matches. Try again.";

export function UploadPage() {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const { route, openItem, backToBoard } = useRoute();
  // Ignore responses from requests superseded by "Start over" or a newer request.
  const extractRequestId = useRef(0);
  const searchRequestId = useRef(0);

  const runSearch = async (request: SearchRequest) => {
    const id = ++searchRequestId.current;
    dispatch({ type: 'searchStart', request });
    try {
      const { results } = await search(request);
      if (id === searchRequestId.current) dispatch({ type: 'searchSucceed', results });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : SEARCH_FALLBACK_ERROR;
      if (id === searchRequestId.current) dispatch({ type: 'searchFail', message });
    }
  };

  const cancelEditUpload = () => {
    extractRequestId.current++;
    dispatch({ type: 'cancelEditUpload' });
  };

  const runExtract = async (input: ExtractInput) => {
    // Resubmitting an unchanged upload would only wipe the user's edits: keep the session.
    if (state.editingUpload && state.session && sameInput(input, state.session.input)) {
      cancelEditUpload();
      return;
    }
    const id = ++extractRequestId.current;
    dispatch({ type: 'extractStart', input });
    let result: ExtractResponse;
    try {
      result = await extract(input);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : EXTRACT_FALLBACK_ERROR;
      if (id === extractRequestId.current) dispatch({ type: 'extractFail', message });
      return;
    }
    if (id !== extractRequestId.current) return;
    dispatch({ type: 'extractSucceed', result });
    // Search once straight away with the model's attributes; later searches wait for the button.
    void runSearch(buildSearchRequest({ input, extracted: result }, result.attributes));
  };

  const startOver = () => {
    extractRequestId.current++;
    searchRequestId.current++;
    dispatch({ type: 'reset' });
  };

  const { session, edited, editingUpload } = state;
  const showForm = !session || editingUpload;

  // Keep keyboard focus on what just appeared when the page switches between form and summary.
  const summaryHeadingRef = useRef<HTMLHeadingElement>(null);
  const formHeadingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!session) return;
    if (editingUpload) formHeadingRef.current?.focus();
    else summaryHeadingRef.current?.focus();
  }, [session, editingUpload]);

  // Opening a polaroid remembers where the board was, so Back returns to the same spot.
  const lastOpened = useRef<{ id: string; scrollY: number } | null>(null);
  const openDetails = (id: string) => {
    lastOpened.current = { id, scrollY: window.scrollY };
    openItem(id);
  };
  useEffect(() => {
    const opened = lastOpened.current;
    if (route.page !== 'board' || !opened) return;
    lastOpened.current = null;
    window.scrollTo({ top: opened.scrollY });
    // Keyboard users land back on the photo they opened, not at the top of the page.
    const photo = [...document.querySelectorAll<HTMLElement>('[data-listing-id]')].find(
      (element) => element.dataset.listingId === opened.id,
    );
    photo?.focus({ preventScroll: true });
  }, [route.page]);

  // On phones an extract error renders below the fold; bring it into view when it arrives.
  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (state.extract.status !== 'error') return;
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    errorRef.current?.scrollIntoView?.({
      block: 'nearest',
      behavior: reduceMotion ? 'auto' : 'smooth',
    });
  }, [state.extract.status]);

  let board: ReactNode;
  if (showForm) {
    const extractState = state.extract;
    const isLoading = extractState.status === 'loading';
    board = (
      <UploadForm
        onSubmit={runExtract}
        disabled={isLoading}
        initialInput={editingUpload ? session?.input : undefined}
        intro={
          <>
            <h2 ref={formHeadingRef} tabIndex={-1} className={styles.heading}>
              {editingUpload ? 'Change your upload' : 'Find that jacket secondhand'}
            </h2>
            <p className={styles.lede}>
              Add a photo, a description, or both. We&rsquo;ll pick out details like color and
              fabric, and you can change any of them before we search.
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

        {extractState.status === 'error' && (
          <div ref={errorRef} className={styles.error} role="alert">
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
              {extractState.message}
            </p>
            <button
              type="button"
              className={styles.retry}
              onClick={() => runExtract(extractState.input)}
            >
              Retry
            </button>
          </div>
        )}

        {editingUpload && (
          <button type="button" className={styles.secondary} onClick={cancelEditUpload}>
            Cancel
          </button>
        )}
      </UploadForm>
    );
  } else {
    // The form is hidden only once a session exists, so session and edited are set here.
    const activeSession = session!;
    const attributes = edited!;
    const searchState = state.search;
    const searching = searchState.status === 'loading' || searchState.status === 'idle';
    const hasChanges =
      state.lastSearched === null || !sameAttributes(attributes, state.lastSearched);

    board = (
      <div className={styles.session}>
        {/* Right-hand column on wide screens: what you gave us, then what we found. */}
        <div className={styles.sidebar}>
          <UploadSummary
            input={activeSession.input}
            queryId={activeSession.extracted.query_id}
            onEdit={() => dispatch({ type: 'editUpload' })}
            onStartOver={startOver}
            headingRef={summaryHeadingRef}
          />

          <AttributeEditor
            extracted={activeSession.extracted}
            value={attributes}
            onChange={(next) => dispatch({ type: 'edit', attributes: next })}
          >
            <button
              type="button"
              className={styles.update}
              disabled={searching || !hasChanges}
              onClick={() => runSearch(buildSearchRequest(activeSession, attributes))}
            >
              Update results
            </button>
            {/* After a failed search there are no results on screen for this note to describe. */}
            {!searching &&
              searchState.status !== 'error' &&
              hasChanges &&
              state.lastSearched !== null && (
                <p className={styles.pending}>Your results don&rsquo;t include these edits yet.</p>
              )}
          </AttributeEditor>
        </div>

        <ResultsGrid
          state={searchState.status === 'idle' ? { status: 'loading' } : searchState}
          onRetry={() => {
            if (searchState.status === 'error') void runSearch(searchState.request);
          }}
          onOpenDetails={openDetails}
        />
      </div>
    );
  }

  const results = state.search.status === 'success' ? state.search.results : [];
  return (
    <>
      {/* The board stays mounted while a listing is open, so Back returns to the same results. */}
      <div hidden={route.page === 'item'}>{board}</div>
      {route.page === 'item' && (
        <DetailsPage
          key={route.id}
          id={route.id}
          result={results.find((result) => result.id === route.id)}
          searched={state.lastSearched}
          onBack={backToBoard}
        />
      )}
    </>
  );
}
