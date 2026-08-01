import { useState } from 'react'
import { useBooks } from '../hooks/useBooks'
import { useProfile } from '../hooks/useProfile'
import BookCard from '../components/BookCard'
import UploadRow from '../components/UploadRow'
import ProfileModal from '../components/ProfileModal'
import styles from './LibraryView.module.css'

export default function LibraryView() {
  const { data: books, isLoading, error } = useBooks()
  const { data: profile } = useProfile()
  const [showProfileModal, setShowProfileModal] = useState(false)

  return (
    <div className={styles.inner}>
      <div className={styles.header}>
        <div className={styles.brandMark}>Minify</div>
        <button className={styles.profileChip} onClick={() => setShowProfileModal(true)} type="button">
          <span className={styles.dot} />
          <span>{profile?.label ?? 'Reader'}</span>
          <span className={styles.editHint}>Edit</span>
        </button>
      </div>

      <div>
        <div className={styles.libraryLabel}>Your library</div>
        {isLoading && <p className={styles.status}>Loading your library…</p>}
        {error && <p className={styles.error}>Can't reach the backend — is it running?</p>}
        {books && books.length === 0 && (
          <p className={styles.status}>No books yet — upload your first PDF below.</p>
        )}
        {books && books.length > 0 && (
          <div className={styles.bookList}>
            {books.map((book) => (
              <BookCard key={book.id} book={book} />
            ))}
          </div>
        )}
      </div>

      <UploadRow />

      {showProfileModal && <ProfileModal onClose={() => setShowProfileModal(false)} />}
    </div>
  )
}
