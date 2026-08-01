import { Link } from 'react-router-dom'
import type { BookSummary } from '../api/types'
import styles from './BookCard.module.css'

export default function BookCard({ book }: { book: BookSummary }) {
  const title = book.title || book.source_filename
  const isClickable = book.status === 'ready' || book.status === 'failed'
  const showProgress = book.status === 'processing' || book.status === 'queued'

  const meta =
    book.status === 'ready'
      ? `${book.total_chunks} chapter${book.total_chunks === 1 ? '' : 's'}`
      : book.status === 'failed'
        ? 'Processing failed'
        : `${book.ready_chunks} of ${book.total_chunks} chapters ready`

  const inner = (
    <>
      <div className={styles.main}>
        <div className={styles.title}>{title}</div>
        <div className={styles.meta}>{meta}</div>
        {showProgress && book.total_chunks > 0 && (
          <span className={styles.track}>
            <span style={{ width: `${(book.ready_chunks / book.total_chunks) * 100}%` }} />
          </span>
        )}
      </div>
      <div className={`${styles.status} ${styles[book.status]}`}>
        <span className={styles.pip} />
        {book.status === 'ready' ? 'Ready' : book.status === 'failed' ? 'Failed' : 'Processing'}
      </div>
    </>
  )

  if (isClickable) {
    return (
      <Link to={`/books/${book.id}`} className={`${styles.card} ${styles.clickable}`}>
        {inner}
      </Link>
    )
  }

  return (
    <div className={styles.card} title="Still processing — check back soon">
      {inner}
    </div>
  )
}
