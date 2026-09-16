import { useEffect, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy } from "pdfjs-dist";
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
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [scale, setScale] = useState(1.35);
  const [pageSize, setPageSize] = useState({
    width: 0,
    height: 0,
    unscaledWidth: 1,
    unscaledHeight: 1,
  });
  const [error, setError] = useState<string | null>(null);

  // Filter regions that apply to current page
  const regions = highlightedRegions.filter((region) => region.page_number === pageNumber);

  // Load PDF document when documentId changes
  useEffect(() => {
    let cancelled = false;
    const loadingTask = getDocument({ url: sourceFileUrl(documentId) });

    async function loadPdf() {
      try {
        setError(null);
        const pdf = await loadingTask.promise;
        if (cancelled) return;
        setPdfDoc(pdf);
        setPageCount(pdf.numPages);
      } catch {
        if (!cancelled) {
          setError("Unable to load the PDF document.");
          setPdfDoc(null);
          setPageCount(0);
        }
      }
    }

    void loadPdf();

    return () => {
      cancelled = true;
      void loadingTask.destroy();
    };
  }, [documentId]);

  // Render current page onto canvas whenever pdfDoc, pageNumber, or scale changes
  useEffect(() => {
    if (!pdfDoc) return;

    let cancelled = false;
    const safePage = Math.min(Math.max(pageNumber, 1), pdfDoc.numPages);
    if (safePage !== pageNumber) {
      onPageChange(safePage);
      return;
    }

    let activeRenderTask: any = null;

    async function renderPage() {
      try {
        setError(null);
        const page = await pdfDoc!.getPage(safePage);
        if (cancelled) return;

        const viewport = page.getViewport({ scale });
        const unscaledViewport = page.getViewport({ scale: 1.0 });
        const canvas = canvasRef.current;
        if (!canvas || cancelled) return;

        canvas.width = viewport.width;
        canvas.height = viewport.height;

        setPageSize({
          width: viewport.width,
          height: viewport.height,
          unscaledWidth: unscaledViewport.width,
          unscaledHeight: unscaledViewport.height,
        });

        const context = canvas.getContext("2d");
        if (!context) return;

        activeRenderTask = page.render({ canvas, canvasContext: context, viewport });
        await activeRenderTask.promise;
      } catch (renderError: any) {
        if (!cancelled && renderError?.name !== "RenderingCancelledException") {
          setError("Unable to render this PDF page.");
        }
      }
    }

    void renderPage();

    return () => {
      cancelled = true;
      if (activeRenderTask) {
        try {
          activeRenderTask.cancel();
        } catch {
          // Ignore cancellation errors
        }
      }
    };
  }, [pdfDoc, pageNumber, scale, onPageChange]);

  if (error) return <div className="empty-state">{error}</div>;

  return (
    <div className="pdf-canvas-viewer">
      <div className="page-controls">
        <button
          disabled={pageNumber <= 1}
          onClick={() => onPageChange(pageNumber - 1)}
          type="button"
        >
          Previous
        </button>
        <span className="page-indicator">
          Page {pageNumber} of {pageCount || "..."}
        </span>
        <button
          disabled={pageCount === 0 || pageNumber >= pageCount}
          onClick={() => onPageChange(pageNumber + 1)}
          type="button"
        >
          Next
        </button>

        <div className="zoom-controls">
          <button
            disabled={scale <= 0.8}
            onClick={() => setScale((current) => Math.max(0.75, Math.round((current - 0.2) * 100) / 100))}
            title="Zoom Out"
            type="button"
          >
            -
          </button>
          <button
            onClick={() => setScale(1.35)}
            title="Reset Zoom"
            type="button"
          >
            {Math.round(scale * 100 / 1.35)}%
          </button>
          <button
            disabled={scale >= 2.5}
            onClick={() => setScale((current) => Math.min(2.5, Math.round((current + 0.2) * 100) / 100))}
            title="Zoom In"
            type="button"
          >
            +
          </button>
        </div>

        {regions.length > 0 && (
          <span className="citation-badge">
            {regions.length} cited region{regions.length > 1 ? "s" : ""} on this page
          </span>
        )}
      </div>

      <div className="page-stage">
        <canvas ref={canvasRef} />
        {regions.map((region) => region.bbox && pageSize.unscaledWidth > 0 && (
          <div
            aria-label={`Highlighted ${region.block_type} region`}
            className="region-highlight"
            key={region.block_id}
            style={{
              left: `${(region.bbox.x0 / pageSize.unscaledWidth) * 100}%`,
              top: `${(region.bbox.y0 / pageSize.unscaledHeight) * 100}%`,
              width: `${((region.bbox.x1 - region.bbox.x0) / pageSize.unscaledWidth) * 100}%`,
              height: `${((region.bbox.y1 - region.bbox.y0) / pageSize.unscaledHeight) * 100}%`,
            }}
          >
            <span className="region-tag">{region.block_type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default PdfViewer;
