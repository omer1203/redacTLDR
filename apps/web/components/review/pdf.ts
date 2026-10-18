"use client";

import { Document, Page, pdfjs } from "react-pdf";

// The worker must be configured in the module that re-exports react-pdf's components;
// every review component imports Document/Page from here so the setting always applies.
pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

/**
 * Fetch the whole file in one GET. With range requests pdf.js would keep fetching
 * chunks after the presigned URL (5 minutes) has expired.
 */
export const PDF_OPTIONS = { disableRange: true, disableStream: true } as const;

export { Document, Page };
