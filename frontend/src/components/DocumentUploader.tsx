import { useCallback, useState } from "react";
import { uploadDocument } from "../lib/api";
import type { ClaimType, ExtractionPreview, UploadedDocument } from "../types";
import { Upload, FileText, CheckCircle2, AlertTriangle, Trash2 } from "lucide-react";

const DOC_TYPES = [
  { value: "prescription", label: "Prescription" },
  { value: "bill", label: "Medical Bill / Invoice" },
  { value: "diagnostic_report", label: "Diagnostic Report" },
  { value: "pharmacy_bill", label: "Pharmacy Bill" },
  { value: "other", label: "Other Document" },
];

interface UploadingFile {
  file: File;
  docType: string;
  status: "uploading" | "done" | "error";
  preview?: ExtractionPreview;
  error?: string;
}

function ExtractionPreviewCard({ preview }: { preview: ExtractionPreview }) {
  const confidence = preview.extraction_confidence;
  const legibility = preview.legibility_score;
  const isGood = confidence >= 0.6 && legibility >= 0.5;

  return (
    <div className={`mt-2 rounded-lg border p-3 text-xs space-y-1.5 ${isGood ? "border-green-200 bg-green-50" : "border-yellow-200 bg-yellow-50"}`}>
      <div className="flex items-center gap-1.5 font-semibold">
        {isGood
          ? <CheckCircle2 size={14} className="text-green-600" />
          : <AlertTriangle size={14} className="text-yellow-600" />}
        <span className={isGood ? "text-green-700" : "text-yellow-700"}>
          {isGood ? "Extracted successfully" : "Low confidence — consider re-uploading a clearer scan"}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-1 text-gray-600">
        {preview.doctor_name && <span>Doctor: <b>{preview.doctor_name}</b></span>}
        {preview.patient_name && <span>Patient: <b>{preview.patient_name}</b></span>}
        {preview.diagnosis && preview.diagnosis.length > 0 && (
          <span className="col-span-2">Diagnosis: <b>{preview.diagnosis.slice(0, 3).join(", ")}</b></span>
        )}
        {preview.total_amount != null && <span>Amount: <b>₹{preview.total_amount.toLocaleString("en-IN")}</b></span>}
        {preview.bill_date && <span>Date: <b>{preview.bill_date}</b></span>}
      </div>
      <div className="flex gap-3 text-gray-500">
        <span>Confidence: {(confidence * 100).toFixed(0)}%</span>
        <span>Legibility: {(legibility * 100).toFixed(0)}%</span>
        {preview.is_handwritten && <span className="text-yellow-600">Handwritten</span>}
      </div>
      {preview.extraction_warnings?.length > 0 && (
        <div className="text-yellow-600">
          {preview.extraction_warnings.map((w, i) => <p key={i}>⚠ {w}</p>)}
        </div>
      )}
    </div>
  );
}

export default function DocumentUploader({
  claimId,
  memberId,
  claimType,
  onUploaded,
}: {
  claimId: string;
  memberId: string;
  claimType: ClaimType;
  onUploaded: (doc: UploadedDocument) => void;
}) {
  const [files, setFiles] = useState<UploadingFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [selectedDocType, setSelectedDocType] = useState(DOC_TYPES[0].value);

  const processFile = useCallback(async (file: File) => {
    const id = file.name + Date.now();
    setFiles((prev) => [...prev, { file, docType: selectedDocType, status: "uploading" }]);

    try {
      const result = await uploadDocument(file, claimId, selectedDocType, memberId);
      setFiles((prev) =>
        prev.map((f) =>
          f.file === file
            ? { ...f, status: "done", preview: result.extraction_preview as ExtractionPreview }
            : f
        )
      );
      onUploaded({
        document_id: result.document_id,
        download_url: result.download_url,
        file_name: file.name,
        doc_type: selectedDocType,
        extraction_preview: result.extraction_preview as ExtractionPreview,
      });
    } catch (err) {
      setFiles((prev) =>
        prev.map((f) => (f.file === file ? { ...f, status: "error", error: "Upload failed" } : f))
      );
    }
  }, [claimId, memberId, selectedDocType, onUploaded]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    Array.from(e.dataTransfer.files).forEach(processFile);
  }, [processFile]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    Array.from(e.target.files || []).forEach(processFile);
    e.target.value = "";
  };

  const removeFile = (file: File) => setFiles((prev) => prev.filter((f) => f.file !== file));

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
      <h2 className="font-semibold text-gray-900">Upload Documents</h2>
      <p className="text-sm text-gray-500">
        Upload your prescription, bills, and any supporting documents. Our AI will extract the details automatically.
      </p>

      {/* Doc type selector */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
        <select value={selectedDocType} onChange={(e) => setSelectedDocType(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-plum-500">
          {DOC_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition cursor-pointer
          ${dragOver ? "border-plum-500 bg-plum-50" : "border-gray-300 hover:border-plum-400 hover:bg-gray-50"}`}
        onClick={() => document.getElementById("file-input")?.click()}>
        <Upload size={28} className={`mx-auto mb-2 ${dragOver ? "text-plum-500" : "text-gray-400"}`} />
        <p className="text-sm font-medium text-gray-700">Drop files here or click to browse</p>
        <p className="text-xs text-gray-400 mt-1">JPEG, PNG, HEIC, PDF · Max 20MB per file</p>
        <input
          id="file-input"
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp,image/heic,application/pdf"
          className="hidden"
          onChange={handleFileInput}
        />
      </div>

      {/* Uploaded files */}
      {files.length > 0 && (
        <div className="space-y-3">
          {files.map((f, i) => (
            <div key={i} className="border border-gray-200 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText size={16} className="text-plum-500 flex-shrink-0" />
                  <span className="text-sm font-medium text-gray-800 truncate">{f.file.name}</span>
                  <span className="text-xs text-gray-400 flex-shrink-0">
                    ({DOC_TYPES.find((t) => t.value === f.docType)?.label})
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {f.status === "uploading" && (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-plum-600" />
                  )}
                  {f.status === "done" && <CheckCircle2 size={16} className="text-green-500" />}
                  {f.status === "error" && <AlertTriangle size={16} className="text-red-500" />}
                  <button onClick={() => removeFile(f.file)} className="text-gray-300 hover:text-red-500 transition">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {f.status === "uploading" && (
                <p className="text-xs text-gray-400 mt-1">Uploading and extracting data…</p>
              )}
              {f.status === "error" && (
                <p className="text-xs text-red-500 mt-1">{f.error}</p>
              )}
              {f.status === "done" && f.preview && (
                <ExtractionPreviewCard preview={f.preview} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
