"use client";

import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react";

const CompareCanvas = lazy(() =>
  import("./CompareCanvas").then((m) => ({ default: m.CompareCanvas }))
);

export function CompareLazy({ placeholder }: { placeholder: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (shown || !ref.current) return;
    if (!("IntersectionObserver" in window)) {
      setShown(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [shown]);

  return (
    <div ref={ref}>
      {shown ? (
        <Suspense fallback={placeholder}>
          <CompareCanvas />
        </Suspense>
      ) : (
        placeholder
      )}
    </div>
  );
}
