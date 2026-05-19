import { useState } from "react";
import { createBook } from "../api/books";

export default function BookForm({ onBookCreated }) {
  const [form, setForm] = useState({
    title: "",
    author: "",
    description: "",
    language: "en",
  });

  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

 const handleSubmit = async (e) => {
  e.preventDefault();
  setLoading(true);

  try {
    const newBook = await createBook(form);

    // 👇 THIS is where it goes
    onBookCreated();

    setForm({
      title: "",
      author: "",
      description: "",
      language: "en",
    });

  } catch (err) {
    console.error("Error creating book:", err);
  } finally {
    setLoading(false);
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
        {loading ? "Saving..." : "Add Book"}
      </button>
    </form>
  );
}