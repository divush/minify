import ReactMarkdown from 'react-markdown'
import { useChunkContent } from '../hooks/useChunkContent'
import styles from './ReadingPane.module.css'

interface Props {
  chunkId: string | null
  onAsk: () => void
  onToggleSpine: () => void
}

export default function ReadingPane({ chunkId, onAsk, onToggleSpine }: Props) {
  const { data: chunk, isLoading } = useChunkContent(chunkId ?? undefined)

  if (!chunkId) {
    return (
      <main className={styles.pane}>
        <p className={styles.status}>Select a chapter to start reading.</p>
      </main>
    )
  }

  const heading = chunk?.heading ?? `Section ${(chunk?.index ?? 0) + 1}`

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
                · pp. {chunk.page_start}–{chunk.page_end}
              </>
            )}
          </div>
          <h1>{heading}</h1>
        </div>
        <button className={styles.askBtn} onClick={onAsk} type="button" disabled={!chunk?.content}>
          ✎ Ask this chapter
        </button>
      </div>
      {isLoading && <p className={styles.status}>Loading…</p>}
      {chunk?.content ? (
        <div className={styles.prose}>
          <ReactMarkdown>{chunk.content}</ReactMarkdown>
        </div>
      ) : (
        !isLoading && <p className={styles.status}>This chapter hasn't been summarized yet.</p>
      )}
    </main>
  )
}
