import { useEffect, useState } from "react";
import { getBookFiles, uploadBookFile, deleteBookFile } from "../api/books";
import Modal from "@ds/modal";
import Button from "@ds/button";
import Alert from "@ds/alert";
import Badge from "@ds/badge";
import styles from "./BookFilesModal.module.css";

export default function BookFilesModal({ book, onClose }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

  useEffect(() => {
    getBookFiles(book.id)
      .then(setFiles)
      .catch(() => setError("Failed to load files."))
      .finally(() => setLoading(false));
  }, [book.id]);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setProgress(0);
    try {
      const newFile = await uploadBookFile(book.id, file, setProgress);
      setFiles((prev) => [...prev, newFile]);
    } catch {
      setError("Upload failed. Only EPUB and PDF files up to 50 MB are allowed.");
    } finally {
      setUploading(false);
      setProgress(0);
      e.target.value = "";
    }
  };

  const handleDelete = async (fileId) => {
    try {
      await deleteBookFile(fileId);
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    } catch {
      setError("Failed to remove file.");
    }
  };

  return (
    <Modal isOpen onClose={onClose} title={`Files — ${book.title}`}>
      {error && (
        <Alert variant="danger" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading ? (
        <p>Loading…</p>
      ) : files.length === 0 ? (
        <p className={styles.empty}>No files uploaded yet.</p>
      ) : (
        <div className={styles.fileList}>
          {files.map((f) => (
            <div key={f.id} className={styles.fileRow}>
              <Badge variant="primary">{f.format.toUpperCase()}</Badge>
              <span className={styles.size}>{formatBytes(f.file_size)}</span>
              <Button variant="danger" onClick={() => handleDelete(f.id)}>
                Remove
              </Button>
            </div>
          ))}
        </div>
      )}

      <div className={styles.upload}>
        {uploading ? (
          <div className={styles.progress}>
            <div className={styles.progressTrack}>
              <div className={styles.bar} style={{ width: `${progress}%` }} />
            </div>
            <span className={styles.progressLabel}>{progress}%</span>
          </div>
        ) : (
          <label className={styles.uploadLabel}>
            Upload EPUB or PDF
            <input
              type="file"
              accept=".epub,.pdf"
              onChange={handleUpload}
              className={styles.fileInput}
            />
          </label>
        )}
      </div>
    </Modal>
  );
}

function formatBytes(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
