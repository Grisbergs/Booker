import { useEffect, useState } from "react";
import { getBooks, deleteBook } from "../api/books";
import Button from "@ds/button";
import Card from "@ds/card";
import styles from "./BookList.module.css";

export default function BookList({ refreshTrigger, setEditingBook }) {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchBooks = async () => {
      try {
        setLoading(true);
        const data = await getBooks();
        setBooks(data);
      } catch (err) {
        console.error("Fetch error:", err);
        setError("Failed to load books");
      } finally {
        setLoading(false);
      }
    };

    fetchBooks();
  }, [refreshTrigger]);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this book?")) return;
    try {
      await deleteBook(id);
      setBooks((prev) => prev.filter((b) => b.id !== id));
    } catch (err) {
      console.error("Delete failed:", err);
      alert("Failed to delete book");
    }
  };

  if (loading) return <p>Loading books…</p>;
  if (error) return <p>{error}</p>;

  return (
    <div className={styles.list}>
      {(books ?? []).length === 0 ? (
        <p>No books found.</p>
      ) : (
        <div className={styles.grid}>
          {books.map((book) => (
            <Card key={book.id} className={styles.bookCard}>
              <h3>{book.title}</h3>
              <p><strong>Author:</strong> {book.author}</p>
              <p>{book.description}</p>
              <div className={styles.actions}>
                <Button variant="danger" onClick={() => handleDelete(book.id)}>
                  Delete
                </Button>
                <Button variant="secondary" onClick={() => setEditingBook(book)}>
                  Edit
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
