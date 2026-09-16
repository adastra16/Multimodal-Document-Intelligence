import { useEffect, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

import { sourceFileUrl } from "./api";
import type { CitationRegion } from "./types";

GlobalWorkerOptions.workerSrc = workerUrl;

const MIN_ZOOM = 1;
const MAX_ZOOM = 2.5;
const ZOOM_STEP = 0.2;

interface PdfViewerProps {
  documentId: string;
  highlightedRegions: CitationRegion[];
  pageNumber: number;
  onPageChange: (pageNumber: number) => void;
}

function PdfViewer({ documentId, highlightedRegions, pageNumber, onPageChange }: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [zoomFactor, setZoomFactor] = useState(1);
  const [containerWidth, setContainerWidth] = useState(0);
  const [pageSize, setPageSize] = useState({
    width: 0,
    height: 0,
    unscaledWidth: 1,
    unscaledHeight: 1,
  });
  const [error, setError] = useState<string | null>(null);

  const regions = highlightedRegions.filter((region) => region.page_number === pageNumber);

  useEffect(() => {
    setZoomFactor(1);
  }, [documentId]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      const width = Math.floor(entries[0]?.contentRect.width ?? 0);
      if (width > 0) {
        setContainerWidth(width);
      }
    });
    observer.observe(stage);
    setContainerWidth(Math.floor(stage.clientWidth));
    return () => observer.disconnect();
  }, []);

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

  useEffect(() => {
    if (!pdfDoc || containerWidth <= 0) return;

    let cancelled = false;
    const safePage = Math.min(Math.max(pageNumber, 1), pdfDoc.numPages);
    if (safePage !== pageNumber) {
      onPageChange(safePage);
      return;
    }

    let activeRenderTask: { cancel: () => void; promise: Promise<unknown> } | null = null;

    async function renderPage() {
      try {
        setError(null);
        const page = await pdfDoc!.getPage(safePage);
        if (cancelled) return;

        const unscaledViewport = page.getViewport({ scale: 1.0 });
        const fitScale = containerWidth / unscaledViewport.width;
        const scale = fitScale * zoomFactor;
        const viewport = page.getViewport({ scale });
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
      } catch (renderError: unknown) {
        const name = typeof renderError === "object" && renderError && "name" in renderError
          ? String((renderError as { name: string }).name)
          : "";
        if (!cancelled && name !== "RenderingCancelledException") {
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
  }, [pdfDoc, pageNumber, zoomFactor, containerWidth, onPageChange]);

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
            disabled={zoomFactor <= MIN_ZOOM}
            onClick={() => setZoomFactor((current) => Math.max(MIN_ZOOM, roundZoom(current - ZOOM_STEP)))}
            title="Zoom Out"
            type="button"
          >
            -
          </button>
          <button onClick={() => setZoomFactor(1)} title="Fit width" type="button">
            {Math.round(zoomFactor * 100)}%
          </button>
          <button
            disabled={zoomFactor >= MAX_ZOOM}
            onClick={() => setZoomFactor((current) => Math.min(MAX_ZOOM, roundZoom(current + ZOOM_STEP)))}
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

      <div className={`page-stage${zoomFactor > 1 ? " is-zoomed" : ""}`} ref={stageRef}>
        <div
          className="page-frame"
          style={
            pageSize.width > 0
              ? { width: pageSize.width, height: pageSize.height }
              : undefined
          }
        >
          <canvas ref={canvasRef} />
          {regions.map((region) => region.bbox && pageSize.unscaledWidth > 0 && (
            <div
              aria-label="Cited region"
              className="region-highlight"
              key={region.block_id}
              style={{
                left: `${(region.bbox.x0 / pageSize.unscaledWidth) * 100}%`,
                top: `${(region.bbox.y0 / pageSize.unscaledHeight) * 100}%`,
                width: `${((region.bbox.x1 - region.bbox.x0) / pageSize.unscaledWidth) * 100}%`,
                height: `${((region.bbox.y1 - region.bbox.y0) / pageSize.unscaledHeight) * 100}%`,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function roundZoom(value: number): number {
  return Math.round(value * 100) / 100;
}

export default PdfViewer;
