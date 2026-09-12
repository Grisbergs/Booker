import { useEffect, useState } from "react";
import { getBooks, deleteBook } from "../api/books";
import Button from "@ds/button";
import Card from "@ds/card";
import Alert from "@ds/alert";
import Modal from "@ds/modal";
import BookFilesModal from "./BookFilesModal";
import styles from "./BookList.module.css";

export default function BookList({ refreshTrigger, setEditingBook }) {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [deleteError, setDeleteError] = useState(null);
  const [filesBook, setFilesBook] = useState(null);

  useEffect(() => {
    const fetchBooks = async () => {
      try {
        setLoading(true);
        const data = await getBooks();
        setBooks(data);
      } catch (err) {
        console.error("Fetch error:", err);
        setError("Failed to load books.");
      } finally {
        setLoading(false);
      }
    };

    fetchBooks();
  }, [refreshTrigger]);

  const handleDeleteConfirm = async () => {
    try {
      await deleteBook(pendingDeleteId);
      setBooks((prev) => prev.filter((b) => b.id !== pendingDeleteId));
      setPendingDeleteId(null);
    } catch (err) {
      console.error("Delete failed:", err);
      setPendingDeleteId(null);
      setDeleteError("Failed to delete book.");
    }
  };

  if (loading) return <p>Loading books…</p>;
  if (error) return <Alert variant="danger">{error}</Alert>;

  return (
    <div className={styles.list}>
      {deleteError && (
        <Alert variant="danger" onDismiss={() => setDeleteError(null)}>
          {deleteError}
        </Alert>
      )}

      <Modal
        isOpen={!!pendingDeleteId}
        onClose={() => setPendingDeleteId(null)}
        title="Delete Book"
      >
        <p>Are you sure you want to delete this book? This cannot be undone.</p>
        <div className={styles.actions}>
          <Button variant="danger" onClick={handleDeleteConfirm}>Delete</Button>
          <Button variant="secondary" onClick={() => setPendingDeleteId(null)}>Cancel</Button>
        </div>
      </Modal>

      {filesBook && (
        <BookFilesModal book={filesBook} onClose={() => setFilesBook(null)} />
      )}

      {(books ?? []).length === 0 ? (
        <Alert variant="info">No books yet. Add one above.</Alert>
      ) : (
        <div className={styles.grid}>
          {books.map((book) => (
            <Card key={book.id} className={styles.bookCard}>
              <h3>{book.title}</h3>
              <p><strong>Author:</strong> {book.author}</p>
              <p>{book.description}</p>
              <div className={styles.actions}>
                <Button variant="primary" onClick={() => setFilesBook(book)}>
                  Files
                </Button>
                <Button variant="secondary" onClick={() => setEditingBook(book)}>
                  Edit
                </Button>
                <Button variant="danger" onClick={() => setPendingDeleteId(book.id)}>
                  Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
