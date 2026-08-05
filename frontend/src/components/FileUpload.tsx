import { useState } from "react";
import { api } from "../api/client";

export default function FileUpload({ onUploaded }: { onUploaded: (docId: string) => void }) {
  const [uploading, setUploading] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const { data } = await api.post("/ingest/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onUploaded(data.document_id);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="border-dashed border-2 rounded-lg p-4 text-center text-sm text-gray-500">
      <input type="file" accept=".pdf,.docx,.csv" onChange={handleFileChange} disabled={uploading} />
      {uploading && <p className="mt-2">Uploading & processing...</p>}
    </div>
  );
}