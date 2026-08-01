import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useBookStatus } from '../hooks/useBook'
import ChapterReviewPanel from '../components/ChapterReviewPanel'
import ProcessingPanel from '../components/ProcessingPanel'
import ChapterSpine from '../components/ChapterSpine'
import ReadingPane from '../components/ReadingPane'
import MarginaliaPanel from '../components/MarginaliaPanel'
import styles from './BookView.module.css'

export default function BookView() {
  const { bookId } = useParams<{ bookId: string }>()
  const { data: status, isLoading, error } = useBookStatus(bookId!)
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)
  const [showMarginalia, setShowMarginalia] = useState(false)
  const [mobileSpineOpen, setMobileSpineOpen] = useState(false)

  const selectChunk = (id: string) => {
    setSelectedChunkId(id)
    setMobileSpineOpen(false)
  }

  if (isLoading) {
    return <div className={styles.centered}>Loading…</div>
  }
  if (error || !status) {
    return (
      <div className={styles.centered}>
        <p>Can't reach the backend — is it running?</p>
        <Link to="/">← Back to library</Link>
      </div>
    )
  }
  if (status.status === 'failed') {
    return (
      <div className={styles.centered}>
        <p>This book failed to process.</p>
        <Link to="/">← Back to library</Link>
      </div>
    )
  }
  if (status.status === 'awaiting_confirmation') {
    return <ChapterReviewPanel bookId={bookId!} />
  }
  if (status.status !== 'ready') {
    return <ProcessingPanel bookId={bookId!} />
  }

  return (
    <div className={styles.reading}>
      <ChapterSpine
        bookId={bookId!}
        selectedChunkId={selectedChunkId}
        onSelect={selectChunk}
        isOpenOnMobile={mobileSpineOpen}
      />
      <ReadingPane
        bookId={bookId!}
        chunkId={selectedChunkId}
        onSelect={selectChunk}
        onAsk={() => setShowMarginalia(true)}
        onToggleSpine={() => setMobileSpineOpen((open) => !open)}
      />
      {showMarginalia && selectedChunkId && (
        <MarginaliaPanel chunkId={selectedChunkId} onClose={() => setShowMarginalia(false)} />
      )}
    </div>
  )
}
