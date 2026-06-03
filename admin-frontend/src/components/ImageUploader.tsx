import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import { FabricImage } from '../api/fabrics';
import { resolveImageUrl } from '../api/client';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

export type SelectedImage = { file: File; previewUrl: string };

type Props = {
  label: string;
  currentImages: FabricImage[];
  selectedFiles?: File[];
  multiple?: boolean;
  disabled?: boolean;
  onFileSelect: (files: File[]) => void;
  onDeleteImage: (image: FabricImage) => void;
};

export default function ImageUploader({ label, currentImages, selectedFiles = [], multiple = false, disabled = false, onFileSelect, onDeleteImage }: Props) {
  const [error, setError] = useState('');
  const [previews, setPreviews] = useState<SelectedImage[]>([]);

  useEffect(() => {
    const nextPreviews = selectedFiles.map((file) => ({ file, previewUrl: URL.createObjectURL(file) }));
    setPreviews(nextPreviews);
    return () => nextPreviews.forEach((preview) => URL.revokeObjectURL(preview.previewUrl));
  }, [selectedFiles]);

  const inputId = useMemo(() => `upload-${label.replace(/\s+/g, '-').toLowerCase()}`, [label]);

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    const invalid = files.find((file) => !ACCEPTED_TYPES.includes(file.type));
    if (invalid) {
      setError('Неподдерживаемый формат. Выберите JPG, PNG или WEBP.');
      event.target.value = '';
      return;
    }
    setError('');
    onFileSelect(multiple ? files : files.slice(0, 1));
  }

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
      <div>
        <label className="block font-semibold text-slate-900" htmlFor={inputId}>{label}</label>
        <p className="text-sm text-slate-500">JPG, PNG или WEBP, до 10 MB</p>
      </div>
      <input id={inputId} type="file" accept="image/jpeg,image/png,image/webp" multiple={multiple} disabled={disabled} onChange={handleChange} />
      {error && <p className="text-sm text-red-600">{error}</p>}
      {(currentImages.length > 0 || previews.length > 0) && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {currentImages.map((image) => (
            <div key={image.id} className="rounded-lg border bg-slate-50 p-2">
              <img src={resolveImageUrl(image.image_url)} alt={image.image_type} className="h-28 w-full rounded object-cover" />
              <div className="mt-2 flex items-center justify-between gap-2 text-xs">
                <span className="text-slate-500">Загружено</span>
                <button type="button" className="text-red-600 hover:underline disabled:opacity-50" disabled={disabled} onClick={() => onDeleteImage(image)}>Удалить</button>
              </div>
            </div>
          ))}
          {previews.map((preview) => (
            <div key={`${preview.file.name}-${preview.file.lastModified}`} className="rounded-lg border border-dashed bg-blue-50 p-2">
              <img src={preview.previewUrl} alt={preview.file.name} className="h-28 w-full rounded object-cover" />
              <p className="mt-2 truncate text-xs text-slate-600">Будет загружено: {preview.file.name}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
