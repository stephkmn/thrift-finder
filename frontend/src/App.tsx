import styles from './App.module.css';

function App() {
  return (
    <>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <svg
            className={styles.mark}
            viewBox="0 0 32 32"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.25"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M13 9a3 3 0 1 1 4.2 2.75c-.75.33-1.2 1.05-1.2 1.87V14" />
            <path d="M16 14 3.6 22.4A1.5 1.5 0 0 0 4.45 25h23.1a1.5 1.5 0 0 0 .85-2.6Z" />
          </svg>
          <h1 className={styles.title}>Thrift Searcher</h1>
        </div>
      </header>
      <main className={styles.main} />
    </>
  );
}

export default App;
