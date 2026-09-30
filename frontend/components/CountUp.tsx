"use client";

import { animate, useMotionValue, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

interface Props {
  value: number;
  /** Same formatter the static figure used; the final text is exactly format(value). */
  format: (n: number) => string;
}

/**
 * Counts up to `value`. The exact final figure is always in the DOM for screen readers and
 * copy/paste (visually hidden text); the counting digits are decoration (aria-hidden, unselectable).
 * Under reduced motion the final figure is rendered at once.
 */
export default function CountUp({ value, format }: Props) {
  const reduce = useReducedMotion();
  const motionValue = useMotionValue(reduce ? value : 0);
  const [text, setText] = useState(() => format(reduce ? value : 0));

  useEffect(() => {
    if (reduce) {
      motionValue.set(value);
      setText(format(value));
      return;
    }
    const stop = motionValue.on("change", (v) => setText(format(v)));
    const controls = animate(motionValue, value, {
      duration: 0.6,
      ease: "easeOut",
      onComplete: () => setText(format(value)),
    });
    return () => { controls.stop(); stop(); };
  }, [value, reduce, motionValue, format]);

  return (
    <>
      <span className="count" aria-hidden="true">{text}</span>
      <span className="sr-only">{format(value)}</span>
    </>
  );
}
