import axios from "axios";

const API_URL = "http://localhost/api/books";

// GET
export const getBooks = async () => {
  const res = await axios.get(API_URL);

  console.log("RAW API RESPONSE:", res.data);

  return res.data.data;
};

// POST
export const createBook = async (book) => {
  const res = await axios.post(API_URL, book);
  return res.data;
};
export const deleteBook = async (id) => {
  await axios.delete(`${API_URL}/${id}`);
};
export const updateBook = async (id, bookData) => {
  const res = await axios.put(`${API_URL}/${id}`, bookData);
  return res.data;
};