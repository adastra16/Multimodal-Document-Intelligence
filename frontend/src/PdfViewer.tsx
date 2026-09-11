import { useEffect, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

import { sourceFileUrl } from "./api";
import type { CitationRegion } from "./types";

GlobalWorkerOptions.workerSrc = workerUrl;

interface PdfViewerProps {
  documentId: string;
  highlightedRegions: CitationRegion[];
  pageNumber: number;
  onPageChange: (pageNumber: number) => void;
}

function PdfViewer({ documentId, highlightedRegions, pageNumber, onPageChange }: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [pageCount, setPageCount] = useState(0);
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const [error, setError] = useState<string | null>(null);
  const regions = highlightedRegions.filter((region) => region.page_number === pageNumber);

  useEffect(() => {
    let cancelled = false;
    const loadingTask = getDocument({ url: sourceFileUrl(documentId) });
    async function renderPage() {
      try {
        setError(null);
        const pdf = await loadingTask.promise;
        if (cancelled) return;
        setPageCount(pdf.numPages);
        const safePage = Math.min(Math.max(pageNumber, 1), pdf.numPages);
        if (safePage !== pageNumber) onPageChange(safePage);
        const page = await pdf.getPage(safePage);
        const viewport = page.getViewport({ scale: 1.35 });
        const canvas = canvasRef.current;
        if (!canvas || cancelled) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        setPageSize({ width: viewport.width, height: viewport.height });
        const context = canvas.getContext("2d");
        if (!context) return;
        await page.render({ canvas, canvasContext: context, viewport }).promise;
      } catch {
        if (!cancelled) setError("Unable to render this PDF page.");
      }
    }
    void renderPage();
    return () => {
      cancelled = true;
      void loadingTask.destroy();
    };
  }, [documentId, onPageChange, pageNumber]);

  if (error) return <div className="empty-state">{error}</div>;

  return (
    <div className="pdf-canvas-viewer">
      <div className="page-controls">
        <button disabled={pageNumber <= 1} onClick={() => onPageChange(pageNumber - 1)} type="button">
          Previous
        </button>
        <span>Page {pageNumber} of {pageCount || "..."}</span>
        <button disabled={pageCount === 0 || pageNumber >= pageCount} onClick={() => onPageChange(pageNumber + 1)} type="button">
          Next
        </button>
      </div>
      <div className="page-stage" style={{ width: pageSize.width || undefined }}>
        <canvas ref={canvasRef} />
        {regions.map((region) => region.bbox && pageSize.width > 0 && (
          <div
            aria-label={`Highlighted ${region.block_type} region`}
            className="region-highlight"
            key={region.block_id}
            style={{
              left: `${(region.bbox.x0 / (pageSize.width / 1.35)) * 100}%`,
              top: `${(region.bbox.y0 / (pageSize.height / 1.35)) * 100}%`,
              width: `${((region.bbox.x1 - region.bbox.x0) / (pageSize.width / 1.35)) * 100}%`,
              height: `${((region.bbox.y1 - region.bbox.y0) / (pageSize.height / 1.35)) * 100}%`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default PdfViewer;
