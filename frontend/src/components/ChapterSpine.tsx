import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useBookChunks } from '../hooks/useBook'
import { useProfile } from '../hooks/useProfile'
import styles from './ChapterSpine.module.css'

interface Props {
  bookId: string
  selectedChunkId: string | null
  onSelect: (chunkId: string) => void
  isOpenOnMobile: boolean
}

export default function ChapterSpine({ bookId, selectedChunkId, onSelect, isOpenOnMobile }: Props) {
  const { data: chunks } = useBookChunks(bookId)
  const { data: profile } = useProfile()

  useEffect(() => {
    if (chunks && chunks.length > 0 && !selectedChunkId) {
      onSelect(chunks[0].id)
    }
  }, [chunks, selectedChunkId, onSelect])

  const readyCount = chunks?.filter((c) => c.status === 'ready').length ?? 0

  return (
    <aside className={`${styles.spine} ${isOpenOnMobile ? styles.open : ''}`}>
      <Link to="/" className={styles.backLink}>
        ← Library
      </Link>
      <div className={styles.profileChip}>
        <span className={styles.dot} />
        {profile?.label ?? 'Reader'}
      </div>

      <div>
        <div className={styles.tocLabel}>Chapters</div>
        <ul className={styles.toc}>
          {chunks?.map((chunk) => (
            <li key={chunk.id}>
              <button
                type="button"
                className={chunk.is_read ? styles.read : undefined}
                aria-current={chunk.id === selectedChunkId}
                onClick={() => onSelect(chunk.id)}
              >
                <span className={`${styles.pip} ${chunk.is_read ? styles.read : ''}`} />
                <span className={styles.tocText}>
                  <span>{chunk.heading ?? `Section ${chunk.index + 1}`}</span>
                  <span className={styles.tocPages}>
                    pp. {chunk.page_start}-{chunk.page_end}
                    {chunk.is_read && ' · read'}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {chunks && (
        <div className={styles.footer}>
          {readyCount} of {chunks.length} chapters ready
        </div>
      )}
    </aside>
  )
}
