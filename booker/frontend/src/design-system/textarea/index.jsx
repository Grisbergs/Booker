import styles from "./textarea.module.css";

export default function Textarea({ label, id, ...props }) {
  return (
    <div className={styles.field}>
      {label && (
        <label className={styles.label} htmlFor={id}>
          {label}
        </label>
      )}
      <textarea id={id} className={styles.textarea} {...props} />
    </div>
  );
}
