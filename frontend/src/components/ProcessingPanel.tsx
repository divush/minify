import { Link } from 'react-router-dom'
import { useBookChunks, useBookStatus } from '../hooks/useBook'
import { useProfile } from '../hooks/useProfile'
import styles from './ProcessingPanel.module.css'

export default function ProcessingPanel({ bookId }: { bookId: string }) {
  const { data: status } = useBookStatus(bookId)
  const { data: chunks } = useBookChunks(bookId)
  const { data: profile } = useProfile()

  const total = status?.total_chunks ?? 0
  const ready = status?.ready_chunks ?? 0

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <Link to="/" className={styles.backLink}>
          ← Library
        </Link>
        <div className={styles.eyebrow}>Reading as: {profile?.label ?? 'Reader'}</div>
        <h1>Processing your book…</h1>

        {chunks && chunks.length > 0 ? (
          <ul className={styles.list}>
            {chunks.map((chunk) => (
              <li key={chunk.id} data-status={chunk.status}>
                <span className={styles.pip} />
                <span className={styles.chapTitle}>{chunk.heading ?? `Section ${chunk.index + 1}`}</span>
                <span className={styles.chapPages}>
                  pp. {chunk.page_start}-{chunk.page_end}
                </span>
                <span className={styles.chapState}>
                  {chunk.status === 'ready' ? 'Ready' : chunk.status === 'processing' ? 'Processing…' : 'Queued'}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.status}>Extracting chapters…</p>
        )}

        <div className={styles.footer}>
          <span className={styles.counter}>
            {ready} / {total} chapters ready
          </span>
          <span className={styles.track}>
            <span style={{ width: total ? `${(ready / total) * 100}%` : '0%' }} />
          </span>
        </div>
      </div>
    </div>
  )
}
