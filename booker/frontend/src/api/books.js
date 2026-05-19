import axios from "axios";

const API_URL = "http://localhost/api/books";

// GET
export const getBooks = async () => {
  const res = await axios.get(API_URL);
  return res.data.data;
};

// POST
export const createBook = async (book) => {
  const res = await axios.post(API_URL, book);
  return res.data;
};