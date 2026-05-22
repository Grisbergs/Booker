import { useEffect, useState } from "react";
import { createBook, updateBook } from "../api/books";
import Button from "@ds/button";
import Input from "@ds/input";
import Textarea from "@ds/textarea";
import Card from "@ds/card";
import styles from "./BookForm.module.css";

export default function BookForm({ onBookCreated, editingBook, setEditingBook }) {
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
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleCancel = () => {
    setEditingBook(null);
    setForm({ title: "", author: "", description: "", language: "en" });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (editingBook) {
        await updateBook(editingBook.id, form);
        setEditingBook(null);
      } else {
        await createBook(form);
        onBookCreated();
      }
      setForm({ title: "", author: "", description: "", language: "en" });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <form onSubmit={handleSubmit}>
        <h2>{editingBook ? "Edit Book" : "Add Book"}</h2>

        <Input
          label="Title"
          name="title"
          placeholder="Title"
          value={form.title}
          onChange={handleChange}
        />
        <Input
          label="Author"
          name="author"
          placeholder="Author"
          value={form.author}
          onChange={handleChange}
        />
        <Textarea
          label="Description"
          name="description"
          placeholder="Description"
          value={form.description}
          onChange={handleChange}
        />

        <div className={styles.actions}>
          <Button type="submit" loading={loading}>
            {editingBook ? "Update Book" : "Add Book"}
          </Button>
          {editingBook && (
            <Button type="button" variant="secondary" onClick={handleCancel}>
              Cancel
            </Button>
          )}
        </div>
      </form>
    </Card>
  );
}
