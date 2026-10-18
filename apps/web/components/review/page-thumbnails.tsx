"use client";

import { useEffect, useRef, useState } from "react";

import { Page } from "@/components/review/pdf";
import type { ReviewState } from "@/lib/api/review";
import { countsByPage } from "@/lib/review/derive";
import { useReviewStore } from "@/lib/review/store";
import { cn } from "@/lib/utils";

const THUMB_WIDTH = 104;

export function PageThumbnails({ state }: { state: ReviewState }) {
  const page = useReviewStore((s) => s.page);
  const pageCount = useReviewStore((s) => s.pageCount);
  const goToPage = useReviewStore((s) => s.goToPage);
  const setTab = useReviewStore((s) => s.setTab);
  const counts = countsByPage(state);
  const pages = Array.from({ length: pageCount }, (_, index) => index + 1);

  return (
    <nav aria-label="Pages" className="h-full overflow-y-auto pr-1">
      <ol className="flex flex-col items-center gap-3 py-1">
        {pages.map((pageNumber) => {
          const count = counts.get(pageNumber);
          const size = state.pages.find((item) => item.pageNumber === pageNumber);
          const aspect = size && size.width > 0 ? size.height / size.width : 792 / 612;
          return (
            <li key={pageNumber}>
              <button
                type="button"
                aria-label={`Page ${pageNumber}${count ? `, ${count.detections} items` : ""}`}
                aria-current={pageNumber === page ? "page" : undefined}
                className={cn(
                  "relative block rounded-md border-2 p-0.5 transition-colors",
                  pageNumber === page ? "border-primary" : "border-transparent hover:border-border",
                )}
                onClick={() => {
                  goToPage(pageNumber);
                  setTab("viewer");
                }}
              >
                <LazyThumbnail pageNumber={pageNumber} height={Math.round(THUMB_WIDTH * aspect)} />
                {count ? (
                  <span
                    className={cn(
                      "absolute right-1 top-1 min-w-5 rounded-full px-1.5 text-center text-[11px] font-semibold leading-5",
                      count.redacted > 0 ? "bg-black text-white" : "bg-amber-400 text-black",
                    )}
                  >
                    {count.detections}
                  </span>
                ) : null}
                <span className="mt-1 block text-center text-xs text-muted-foreground">{pageNumber}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** Renders the page canvas only after the thumbnail first scrolls into view. */
function LazyThumbnail({ pageNumber, height }: { pageNumber: number; height: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element || visible) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [visible]);

  return (
    <div ref={ref} className="overflow-hidden bg-white" style={{ width: THUMB_WIDTH, height }}>
      {visible ? (
        <Page
          pageNumber={pageNumber}
          width={THUMB_WIDTH}
          renderTextLayer={false}
          renderAnnotationLayer={false}
          loading={null}
          error={null}
        />
      ) : null}
    </div>
  );
}
