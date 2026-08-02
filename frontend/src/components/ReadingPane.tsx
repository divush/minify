import ReactMarkdown from 'react-markdown'
import { useBookChunks, useMarkChunkRead } from '../hooks/useBook'
import { useChunkContent } from '../hooks/useChunkContent'
import styles from './ReadingPane.module.css'

interface Props {
  bookId: string
  chunkId: string | null
  onSelect: (chunkId: string) => void
  onAsk: () => void
  onToggleSpine: () => void
}

export default function ReadingPane({ bookId, chunkId, onSelect, onAsk, onToggleSpine }: Props) {
  const { data: chunk, isLoading } = useChunkContent(chunkId ?? undefined)
  const { data: chunks } = useBookChunks(bookId)
  const markRead = useMarkChunkRead(bookId)

  if (!chunkId) {
    return (
      <main className={styles.pane}>
        <p className={styles.status}>Select a chapter to start reading.</p>
      </main>
    )
  }

  const heading = chunk?.heading ?? `Section ${(chunk?.index ?? 0) + 1}`
  const currentIndex = chunks?.findIndex((c) => c.id === chunkId) ?? -1
  const previousChunk = currentIndex > 0 ? chunks?.[currentIndex - 1] : undefined
  const nextChunk =
    chunks && currentIndex >= 0 && currentIndex < chunks.length - 1 ? chunks[currentIndex + 1] : undefined
  const isRead = chunks?.[currentIndex]?.is_read ?? false

  return (
    <main className={styles.pane}>
      <button className={styles.mobileToggle} type="button" onClick={onToggleSpine}>
        ☰ Chapters
      </button>
      <div className={styles.head}>
        <div>
          <div className={styles.eyebrow}>
            Chapter {(chunk?.index ?? 0) + 1}
            {chunk && (
              <>
                {' '}
                · pp. {chunk.page_start}-{chunk.page_end}
              </>
            )}
          </div>
          <h1>{heading}</h1>
        </div>
        <div className={styles.actions}>
          <button
            className={`${styles.readToggle} ${isRead ? styles.isRead : ''}`}
            onClick={() => markRead.mutate({ chunkId, isRead: !isRead })}
            type="button"
          >
            {isRead ? '✓ Read' : 'Mark as read'}
          </button>
          <button className={styles.askBtn} onClick={onAsk} type="button" disabled={!chunk?.content}>
            ✎ Ask this chapter
          </button>
        </div>
      </div>
      {isLoading && <p className={styles.status}>Loading…</p>}
      {chunk?.content ? (
        <div className={styles.prose}>
          <ReactMarkdown>{chunk.content}</ReactMarkdown>
        </div>
      ) : (
        !isLoading && <p className={styles.status}>This chapter hasn't been summarized yet.</p>
      )}
      <div className={styles.navRow}>
        <button
          className={styles.navBtn}
          type="button"
          disabled={!previousChunk}
          onClick={() => previousChunk && onSelect(previousChunk.id)}
        >
          ← Previous
        </button>
        <button
          className={styles.navBtn}
          type="button"
          disabled={!nextChunk}
          onClick={() => nextChunk && onSelect(nextChunk.id)}
        >
          Next →
        </button>
      </div>
    </main>
  )
}
