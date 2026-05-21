import { useEffect, useState } from "react";
import { createBook, updateBook } from "../api/books";

export default function BookForm({   onBookCreated,
  editingBook,
  setEditingBook }) {
  const [form, setForm] = useState({
    title: "",
    author: "",
    description: "",
    language: "en",
  });

  const [loading, setLoading] = useState(false);
  useEffect(() => {
  if (editingBook) {
    setForm({
      title: editingBook.title || "",
      author: editingBook.author || "",
      description: editingBook.description || "",
      language: editingBook.language || "en",
    });
  }
}, [editingBook]);

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

const handleSubmit = async (e) => {
  e.preventDefault();

  try {
    if (editingBook) {
      // UPDATE MODE
      await updateBook(editingBook.id, form);

      setEditingBook(null);
    } else {
      // CREATE MODE
      await createBook(form);

      onBookCreated();
    }

    setForm({
      title: "",
      author: "",
      description: "",
      language: "en",
    });
  } catch (err) {
    console.error(err);
  }
};

  return (
    <form onSubmit={handleSubmit} style={{ marginBottom: "20px" }}>
      <h2>Create Book</h2>

      <input
        name="title"
        placeholder="Title"
        value={form.title}
        onChange={handleChange}
      />

      <br />

      <input
        name="author"
        placeholder="Author"
        value={form.author}
        onChange={handleChange}
      />

      <br />

      <textarea
        name="description"
        placeholder="Description"
        value={form.description}
        onChange={handleChange}
      />

      <br />

    <button type="submit" disabled={loading}>
  {loading ? "Saving..." : editingBook ? "Update Book" : "Add Book"}
</button>
      {editingBook && (
  <button
    type="button"
    onClick={() => {
      setEditingBook(null);
      setForm({
        title: "",
        author: "",
        description: "",
        language: "en",
      });
    }}
  >
    Cancel Edit
  </button>
)}
    </form>
  );
}