import styles from "./card.module.css";

export default function Card({ children, className = "", ...props }) {
  return (
    <div className={`${styles.card}${className ? ` ${className}` : ""}`} {...props}>
      {children}
    </div>
  );
}
