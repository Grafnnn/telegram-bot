import { ChangeEvent, FormEvent, useEffect, useState } from 'react';
import { GarmentStyle, resolveImageUrl } from '../api/client';
import { createGarmentStyle, updateGarmentStyle, uploadGarmentStyleImage } from '../api/garmentStyles';
import { optionalTrimmed, requiredTrimmed, splitCsv } from '../utils/formValidation';

type Props = {
  mode: 'create' | 'edit';
  initialStyle?: GarmentStyle | null;
  onSaved: (styleId: string) => void;
};

type FormState = {
  name: string;
  category: string;
  description: string;
  compatible_fabric_categories: string;
};

const EMPTY_FORM: FormState = { name: '', category: '', description: '', compatible_fabric_categories: '' };
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function toFormState(style?: GarmentStyle | null): FormState {
  if (!style) return EMPTY_FORM;
  return {
    name: style.name ?? '',
    category: style.category ?? '',
    description: style.description ?? '',
    compatible_fabric_categories: (style.compatible_fabric_categories ?? []).join(', '),
  };
}

export default function GarmentStyleForm({ mode, initialStyle, onSaved }: Props) {
  const [form, setForm] = useState<FormState>(() => toFormState(initialStyle));
  const [baseFile, setBaseFile] = useState<File | null>(null);
  const [maskFile, setMaskFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => { setForm(toFormState(initialStyle)); }, [initialStyle]);

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function pickFile(event: ChangeEvent<HTMLInputElement>, setter: (file: File | null) => void) {
    const file = event.target.files?.[0] ?? null;
    if (file && !ACCEPTED_TYPES.includes(file.type)) {
      setError('Неподдерживаемый формат. Выберите JPG, PNG или WEBP.');
      event.target.value = '';
      setter(null);
      return;
    }
    setError('');
    setter(file);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = {
        name: requiredTrimmed(form.name, 'Название'),
        category: requiredTrimmed(form.category, 'Категория'),
        description: optionalTrimmed(form.description),
        compatible_fabric_categories: splitCsv(form.compatible_fabric_categories),
      };
      const style = mode === 'create' ? await createGarmentStyle(payload) : await updateGarmentStyle(initialStyle?.id ?? '', payload);
      if (baseFile) await uploadGarmentStyleImage(style.id, baseFile, 'base');
      if (maskFile) await uploadGarmentStyleImage(style.id, maskFile, 'mask');
      onSaved(style.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка сохранения фасона');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-6 max-w-3xl">
      {error && <p className="rounded bg-red-50 p-3 text-red-700">{error}</p>}
      <div className="grid gap-4 rounded-xl bg-white p-5 shadow md:grid-cols-2">
        <label className="space-y-1">
          <span className="font-semibold">Название *</span>
          <input required value={form.name} onChange={(event) => updateField('name', event.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="font-semibold">Категория *</span>
          <input required value={form.category} onChange={(event) => updateField('category', event.target.value)} />
        </label>
        <label className="space-y-1 md:col-span-2">
          <span className="font-semibold">Описание</span>
          <textarea rows={4} value={form.description} onChange={(event) => updateField('description', event.target.value)} />
        </label>
        <label className="space-y-1 md:col-span-2">
          <span className="font-semibold">Совместимые категории тканей</span>
          <input placeholder="cotton, silk, linen" value={form.compatible_fabric_categories} onChange={(event) => updateField('compatible_fabric_categories', event.target.value)} />
          <p className="text-sm text-slate-500">Введите значения через запятую.</p>
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl bg-white p-5 shadow">
          <label className="block font-semibold" htmlFor="style-base-image">Основное изображение фасона</label>
          {initialStyle?.base_image_url && <img src={resolveImageUrl(initialStyle.base_image_url)} alt="Основное изображение фасона" className="my-3 h-40 w-full rounded object-cover" />}
          <input id="style-base-image" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => pickFile(event, setBaseFile)} />
          {baseFile && <p className="mt-2 text-sm text-slate-500">Будет загружено: {baseFile.name}</p>}
        </div>
        <div className="rounded-xl bg-white p-5 shadow">
          <label className="block font-semibold" htmlFor="style-mask-image">Mask image (опционально)</label>
          {initialStyle?.mask_image_url && <img src={resolveImageUrl(initialStyle.mask_image_url)} alt="Mask image" className="my-3 h-40 w-full rounded object-cover" />}
          <input id="style-mask-image" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => pickFile(event, setMaskFile)} />
          {maskFile && <p className="mt-2 text-sm text-slate-500">Будет загружено: {maskFile.name}</p>}
        </div>
      </div>

      <button disabled={saving} className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50">{saving ? 'Сохраняем…' : 'Сохранить фасон'}</button>
    </form>
  );
}
