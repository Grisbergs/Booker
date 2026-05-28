import axios from "axios";

const API_URL = "http://localhost/api/books";

export const getBooks = async () => {
  const res = await axios.get(API_URL);
  return res.data.data;
};

export const createBook = async (book) => {
  const res = await axios.post(API_URL, book);
  return res.data;
};

export const updateBook = async (id, bookData) => {
  const res = await axios.put(`${API_URL}/${id}`, bookData);
  return res.data;
};

export const deleteBook = async (id) => {
  await axios.delete(`${API_URL}/${id}`);
};

export const getBookFiles = async (bookId) => {
  const res = await axios.get(`${API_URL}/${bookId}/files`);
  return res.data;
};

export const uploadBookFile = async (bookId, file, onProgress) => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await axios.post(`${API_URL}/${bookId}/files`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
    },
  });
  return res.data;
};

export const deleteBookFile = async (fileId) => {
  await axios.delete(`http://localhost/api/book-files/${fileId}`);
};
