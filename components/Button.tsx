import type { ButtonHTMLAttributes } from "react";
import styles from "./Button.module.css";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "subtle";
  fullWidth?: boolean;
}

/**
 * Three weights of the same control. There is no accent colour in this system,
 * so "primary" is expressed as the maximum contrast it allows — solid ink with
 * paper-coloured type — and the quieter variants step down to a hairline and
 * then to nothing at all.
 */
export function Button({ variant = "primary", fullWidth, className, children, ...rest }: ButtonProps) {
  const classes = [styles.btn, styles[variant], fullWidth ? styles.full : "", className ?? ""]
    .filter(Boolean)
    .join(" ");
  return (
    <button type="button" className={classes} {...rest}>
      {children}
    </button>
  );
}
