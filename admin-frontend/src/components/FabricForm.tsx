import { FormEvent, useMemo, useState } from 'react';
import {
  AIGeneratedDescription,
  archiveFabric,
  CardCheckResult,
  checkFabricCard,
  createFabric,
  deleteFabricImage,
  Fabric,
  FabricImage,
  FabricPayload,
  hideFabric,
  publishFabric,
  StockStatus,
  updateFabric,
  uploadFabricImage,
} from '../api/fabrics';
import ImageUploader from './ImageUploader';
import StatusBadge from './StatusBadge';
import { generateFabricDescription } from '../api/fabrics';

type FabricFormMode = 'create' | 'edit';
type ImageType = 'main' | 'texture' | 'extra';

type FormState = {
  name: string;
  sku: string;
  category: string;
  short_description: string;
  full_description: string;
  price_per_meter: string;
  currency: string;
  stock_status: StockStatus;
  stock_quantity: string;
  composition: string;
  color: string;
  shade: string;
  pattern: string;
  texture: string;
  density: string;
  stretch: string;
  opacity: string;
  shine: string;
  season: string;
  recommended_for: string;
  not_recommended_for: string;
  tags: string;
  description_for_gpt: string;
};

type SelectedFiles = Record<ImageType, File[]>;

type Props = {
  mode: FabricFormMode;
  fabric?: Fabric;
  onCreated?: (fabricId: string) => void;
  onUpdated?: (fabric: Fabric) => void;
};

const emptyState: FormState = {
  name: '',
  sku: '',
  category: '',
  short_description: '',
  full_description: '',
  price_per_meter: '',
  currency: 'RUB',
  stock_status: 'in_stock',
  stock_quantity: '',
  composition: '',
  color: '',
  shade: '',
  pattern: '',
  texture: '',
  density: '',
  stretch: '',
  opacity: '',
  shine: '',
  season: '',
  recommended_for: '',
  not_recommended_for: '',
  tags: '',
  description_for_gpt: '',
};

const FIELD_LABELS: Record<string, string> = {
  sku: 'Артикул',
  name: 'Название',
  category: 'Категория',
  price_per_meter: 'Цена за метр',
  stock_status: 'Наличие',
  description_for_gpt: 'Описание для GPT',
  'main image': 'Главное фото',
  'texture image': 'Фото фактуры',
};

function toCsv(value?: string[] | null): string {
  return value?.join(', ') ?? '';
}

function toNumber(value: string): number | null {
  const normalized = value.trim().replace(',', '.');
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function toArray(value: string): string[] | null {
  const items = value.split(',').map((item) => item.trim()).filter(Boolean);
  return items.length > 0 ? items : null;
}

function fromFabric(fabric?: Fabric): FormState {
  if (!fabric) return emptyState;
  return {
    name: fabric.name ?? '',
    sku: fabric.sku ?? '',
    category: fabric.category ?? '',
    short_description: fabric.short_description ?? '',
    full_description: fabric.full_description ?? '',
    price_per_meter: fabric.price_per_meter == null ? '' : String(fabric.price_per_meter),
    currency: fabric.currency ?? 'RUB',
    stock_status: fabric.stock_status ?? 'in_stock',
    stock_quantity: fabric.stock_quantity == null ? '' : String(fabric.stock_quantity),
    composition: fabric.composition ?? '',
    color: fabric.color ?? '',
    shade: fabric.shade ?? '',
    pattern: fabric.pattern ?? '',
    texture: fabric.texture ?? '',
    density: fabric.density ?? '',
    stretch: fabric.stretch ?? '',
    opacity: fabric.opacity ?? '',
    shine: fabric.shine ?? '',
    season: toCsv(fabric.season),
    recommended_for: toCsv(fabric.recommended_for),
    not_recommended_for: toCsv(fabric.not_recommended_for),
    tags: toCsv(fabric.tags),
    description_for_gpt: fabric.description_for_gpt ?? '',
  };
}

function payloadFromState(state: FormState, status?: 'draft'): FabricPayload {
  return {
    name: state.name.trim(),
    sku: state.sku.trim(),
    category: state.category.trim(),
    short_description: state.short_description.trim() || null,
    full_description: state.full_description.trim() || null,
    price_per_meter: toNumber(state.price_per_meter),
    currency: state.currency.trim() || 'RUB',
    stock_status: state.stock_status,
    stock_quantity: toNumber(state.stock_quantity),
    composition: state.composition.trim() || null,
    color: state.color.trim() || null,
    shade: state.shade.trim() || null,
    pattern: state.pattern.trim() || null,
    texture: state.texture.trim() || null,
    density: state.density.trim() || null,
    stretch: state.stretch.trim() || null,
    opacity: state.opacity.trim() || null,
    shine: state.shine.trim() || null,
    season: toArray(state.season),
    recommended_for: toArray(state.recommended_for),
    not_recommended_for: toArray(state.not_recommended_for),
    tags: toArray(state.tags),
    description_for_gpt: state.description_for_gpt.trim() || null,
    ...(status ? { status } : {}),
  };
}

function imagesOfType(images: FabricImage[], type: ImageType): FabricImage[] {
  return images.filter((image) => image.image_type === type);
}

export default function FabricForm({ mode, fabric, onCreated, onUpdated }: Props) {
  const [form, setForm] = useState<FormState>(() => fromFabric(fabric));
  const [images, setImages] = useState<FabricImage[]>(fabric?.images ?? []);
  const [createdFabricId, setCreatedFabricId] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<SelectedFiles>({ main: [], texture: [], extra: [] });
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [checkResult, setCheckResult] = useState<CardCheckResult | null>(null);
  const [aiPreview, setAiPreview] = useState<AIGeneratedDescription | null>(null);

  const effectiveFabricId = fabric?.id ?? createdFabricId;
  const hasMainImage = useMemo(() => images.some((image) => image.image_type === 'main') || selectedFiles.main.length > 0, [images, selectedFiles.main.length]);
  const hasTextureImage = useMemo(() => images.some((image) => image.image_type === 'texture') || selectedFiles.texture.length > 0, [images, selectedFiles.texture.length]);
  const disabled = loadingAction !== null;

  function updateField<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function setFiles(type: ImageType, files: File[]) {
    setSelectedFiles((current) => ({ ...current, [type]: files }));
  }

  async function uploadSelectedImages(fabricId: string): Promise<FabricImage[]> {
    const uploaded: FabricImage[] = [];
    for (const type of ['main', 'texture', 'extra'] as const) {
      for (let index = 0; index < selectedFiles[type].length; index += 1) {
        uploaded.push(await uploadFabricImage(fabricId, selectedFiles[type][index], type, index));
      }
    }
    if (uploaded.length > 0) {
      setSuccess('Фото загружено.');
      setSelectedFiles({ main: [], texture: [], extra: [] });
      setImages((current) => [...current, ...uploaded]);
    }
    return uploaded;
  }

  async function saveDraft(redirectAfterCreate = true): Promise<Fabric> {
    const payload = payloadFromState(form, mode === 'create' ? 'draft' : undefined);
    const saved = effectiveFabricId ? await updateFabric(effectiveFabricId, payload) : await createFabric(payload);
    if (!fabric) setCreatedFabricId(saved.id);
    const uploaded = await uploadSelectedImages(saved.id);
    const nextFabric = uploaded.length > 0 ? { ...saved, images: [...(saved.images ?? []), ...uploaded] } : saved;
    setImages(nextFabric.images ?? []);
    onUpdated?.(nextFabric);
    if (!fabric && redirectAfterCreate) onCreated?.(saved.id);
    setSuccess('Ткань сохранена.');
    return nextFabric;
  }

  async function runSave(event?: FormEvent) {
    event?.preventDefault();
    setLoadingAction('save');
    setError('');
    try {
      await saveDraft();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить ткань.');
    } finally {
      setLoadingAction(null);
    }
  }

  async function saveAndPublish() {
    setLoadingAction('publish');
    setError('');
    const missingBeforeSave = localMissingFields();
    if (missingBeforeSave.length > 0) {
      setError(`Нельзя опубликовать ткань. Не хватает: ${missingBeforeSave.map((field) => FIELD_LABELS[field] ?? field).join(', ')}`);
      setLoadingAction(null);
      return;
    }
    try {
      const saved = await saveDraft(false);
      const published = await publishFabric(saved.id);
      setImages(published.images ?? []);
      onUpdated?.(published);
      setSuccess('Ткань опубликована.');
      if (!fabric) onCreated?.(published.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось опубликовать ткань.');
    } finally {
      setLoadingAction(null);
    }
  }

  async function changeStatus(action: 'publish' | 'hide' | 'archive') {
    if (!fabric) return;
    if (action === 'archive' && !confirm('Архивировать ткань?')) return;
    setLoadingAction(action);
    setError('');
    try {
      const updated = action === 'publish' ? await publishFabric(fabric.id) : action === 'hide' ? await hideFabric(fabric.id) : await archiveFabric(fabric.id);
      setImages(updated.images ?? []);
      onUpdated?.(updated);
      setSuccess(action === 'publish' ? 'Ткань опубликована.' : action === 'hide' ? 'Ткань скрыта.' : 'Ткань отправлена в архив.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось изменить статус.');
    } finally {
      setLoadingAction(null);
    }
  }

  async function deleteImage(image: FabricImage) {
    if (!effectiveFabricId || !confirm('Удалить изображение?')) return;
    setLoadingAction(`delete-image-${image.id}`);
    setError('');
    try {
      await deleteFabricImage(effectiveFabricId, image.id);
      setImages((current) => current.filter((item) => item.id !== image.id));
      setSuccess('Фото удалено.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось удалить фото.');
    } finally {
      setLoadingAction(null);
    }
  }

  function localMissingFields(): string[] {
    const payload = payloadFromState(form);
    const missing = ['sku', 'name', 'category', 'price_per_meter', 'stock_status', 'description_for_gpt'].filter((field) => !payload[field as keyof FabricPayload]);
    if (!hasMainImage) missing.push('main image');
    if (!hasTextureImage) missing.push('texture image');
    return missing;
  }

  async function runCheckCard() {
    setLoadingAction('check');
    setError('');
    setCheckResult(null);
    try {
      const payload = { ...payloadFromState(form), images, has_main_image: hasMainImage, has_texture_image: hasTextureImage };
      const result = await checkFabricCard(payload);
      const localMissing = localMissingFields();
      const mergedMissing = Array.from(new Set([...(result.missing_fields ?? []), ...localMissing]));
      setCheckResult({
        ...result,
        is_ready: mergedMissing.length === 0,
        ok: mergedMissing.length === 0,
        missing_fields: mergedMissing,
        recommendations: mergedMissing.map((field) => `Заполните: ${FIELD_LABELS[field] ?? field}`),
        message: mergedMissing.length === 0 ? 'Карточка готова к публикации.' : 'Заполните обязательные поля перед публикацией.',
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось проверить карточку.');
    } finally {
      setLoadingAction(null);
    }
  }

  async function runGenerateDescription() {
    setLoadingAction('ai');
    setError('');
    setAiPreview(null);
    try {
      const result = await generateFabricDescription(payloadFromState(form));
      if (result.error || result.ok === false) {
        setError('OpenAI API key не настроен. Сейчас AI-описание недоступно.');
        return;
      }
      setAiPreview(result);
      setSuccess('AI-описание сгенерировано. Проверьте preview и примите его при необходимости.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сгенерировать описание.');
    } finally {
      setLoadingAction(null);
    }
  }

  function acceptAiDescription() {
    if (!aiPreview) return;
    setForm((current) => ({
      ...current,
      short_description: aiPreview.short_description ?? current.short_description,
      full_description: aiPreview.full_description ?? current.full_description,
      description_for_gpt: aiPreview.description_for_gpt ?? current.description_for_gpt,
      tags: aiPreview.tags?.join(', ') ?? current.tags,
      recommended_for: aiPreview.recommended_for?.join(', ') ?? current.recommended_for,
      not_recommended_for: aiPreview.not_recommended_for?.join(', ') ?? current.not_recommended_for,
    }));
    setAiPreview(null);
    setSuccess('Описание принято и перенесено в форму.');
  }

  const buttonLabel = (key: string, label: string) => (loadingAction === key ? 'Подождите...' : label);

  return (
    <form className="space-y-6" onSubmit={runSave}>
      {fabric && <div className="flex items-center gap-3 rounded-xl bg-white p-4 shadow-sm"><span className="text-sm text-slate-500">Текущий статус:</span><StatusBadge status={fabric.status} /></div>}
      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
      {success && <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-green-700">{success}</div>}

      <section className="rounded-xl bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-xl font-semibold">Основное</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <label>Название ткани *<input required value={form.name} onChange={(event) => updateField('name', event.target.value)} /></label>
          <label>Артикул *<input required value={form.sku} onChange={(event) => updateField('sku', event.target.value)} /></label>
          <label>Категория *<input required value={form.category} onChange={(event) => updateField('category', event.target.value)} /></label>
          <label>Цена за метр *<input required type="number" min="0" step="0.01" value={form.price_per_meter} onChange={(event) => updateField('price_per_meter', event.target.value)} /></label>
          <label>Валюта<input value={form.currency} onChange={(event) => updateField('currency', event.target.value)} /></label>
          <label>Наличие *<select required value={form.stock_status} onChange={(event) => updateField('stock_status', event.target.value as StockStatus)}><option value="in_stock">В наличии</option><option value="preorder">Под заказ</option><option value="out_of_stock">Нет в наличии</option></select></label>
          <label>Количество на складе<input type="number" min="0" step="0.01" value={form.stock_quantity} onChange={(event) => updateField('stock_quantity', event.target.value)} /></label>
        </div>
        <div className="mt-4 grid gap-4">
          <label>Краткое описание<textarea rows={3} value={form.short_description} onChange={(event) => updateField('short_description', event.target.value)} /></label>
          <label>Подробное описание<textarea rows={5} value={form.full_description} onChange={(event) => updateField('full_description', event.target.value)} /></label>
        </div>
      </section>

      <section className="rounded-xl bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-xl font-semibold">Характеристики</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <label>Состав<input value={form.composition} onChange={(event) => updateField('composition', event.target.value)} /></label>
          <label>Цвет<input value={form.color} onChange={(event) => updateField('color', event.target.value)} /></label>
          <label>Оттенок<input value={form.shade} onChange={(event) => updateField('shade', event.target.value)} /></label>
          <label>Узор<input value={form.pattern} onChange={(event) => updateField('pattern', event.target.value)} /></label>
          <label>Фактура<input value={form.texture} onChange={(event) => updateField('texture', event.target.value)} /></label>
          <label>Плотность<input value={form.density} onChange={(event) => updateField('density', event.target.value)} /></label>
          <label>Эластичность<input value={form.stretch} onChange={(event) => updateField('stretch', event.target.value)} /></label>
          <label>Прозрачность<input value={form.opacity} onChange={(event) => updateField('opacity', event.target.value)} /></label>
          <label>Блеск<input value={form.shine} onChange={(event) => updateField('shine', event.target.value)} /></label>
        </div>
        <label className="mt-4 block">Сезон <span className="text-sm text-slate-500">(через запятую)</span><input value={form.season} onChange={(event) => updateField('season', event.target.value)} /></label>
      </section>

      <section className="rounded-xl bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-xl font-semibold">Назначение</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <label>Подходит для <span className="text-sm text-slate-500">(через запятую)</span><input value={form.recommended_for} onChange={(event) => updateField('recommended_for', event.target.value)} /></label>
          <label>Не рекомендуется для <span className="text-sm text-slate-500">(через запятую)</span><input value={form.not_recommended_for} onChange={(event) => updateField('not_recommended_for', event.target.value)} /></label>
          <label>Теги <span className="text-sm text-slate-500">(через запятую)</span><input value={form.tags} onChange={(event) => updateField('tags', event.target.value)} /></label>
        </div>
        <label className="mt-4 block">Описание для GPT *<textarea required rows={5} value={form.description_for_gpt} onChange={(event) => updateField('description_for_gpt', event.target.value)} /></label>
      </section>

      <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">Фото</h2>
        {!fabric && <p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-700">На странице создания фото будут загружены сразу после сохранения черновика. Для полной проверки фото сначала сохраните ткань.</p>}
        <ImageUploader label="Главное фото ткани *" currentImages={imagesOfType(images, 'main')} selectedFiles={selectedFiles.main} disabled={disabled} onFileSelect={(files) => setFiles('main', files)} onDeleteImage={deleteImage} />
        <ImageUploader label="Фото фактуры ткани *" currentImages={imagesOfType(images, 'texture')} selectedFiles={selectedFiles.texture} disabled={disabled} onFileSelect={(files) => setFiles('texture', files)} onDeleteImage={deleteImage} />
        <ImageUploader label="Дополнительные фото" currentImages={imagesOfType(images, 'extra')} selectedFiles={selectedFiles.extra} multiple disabled={disabled} onFileSelect={(files) => setFiles('extra', files)} onDeleteImage={deleteImage} />
      </section>

      {checkResult && (
        <section className={`rounded-xl p-4 ${checkResult.is_ready ? 'bg-green-50 text-green-800' : 'bg-yellow-50 text-yellow-900'}`}>
          <h2 className="font-semibold">Результат проверки</h2>
          <p>{checkResult.is_ready ? 'Карточка готова к публикации.' : checkResult.message}</p>
          {!checkResult.is_ready && <ul className="mt-2 list-disc pl-5">{checkResult.missing_fields.map((field) => <li key={field}>{FIELD_LABELS[field] ?? field}</li>)}</ul>}
          {!fabric && <p className="mt-2 text-sm">Для полной проверки фото сначала сохраните ткань.</p>}
        </section>
      )}

      {aiPreview && (
        <section className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-blue-950">
          <h2 className="font-semibold">Preview AI-описания</h2>
          {aiPreview.short_description && <p><b>Краткое:</b> {aiPreview.short_description}</p>}
          {aiPreview.full_description && <p><b>Подробное:</b> {aiPreview.full_description}</p>}
          {aiPreview.description_for_gpt && <p><b>Для GPT:</b> {aiPreview.description_for_gpt}</p>}
          {aiPreview.tags && <p><b>Теги:</b> {aiPreview.tags.join(', ')}</p>}
          <button type="button" className="mt-3 bg-blue-700 text-white" onClick={acceptAiDescription}>Принять описание</button>
        </section>
      )}

      <div className="sticky bottom-0 flex flex-wrap gap-3 rounded-xl border bg-white p-4 shadow-lg">
        <button type="submit" disabled={disabled} className="bg-slate-900 text-white disabled:opacity-50">{mode === 'create' ? buttonLabel('save', 'Сохранить черновик') : buttonLabel('save', 'Сохранить')}</button>
        {mode === 'create' && <button type="button" disabled={disabled} className="bg-green-700 text-white disabled:opacity-50" onClick={saveAndPublish}>{buttonLabel('publish', 'Сохранить и опубликовать')}</button>}
        <button type="button" disabled={disabled} className="border bg-white disabled:opacity-50" onClick={runCheckCard}>{buttonLabel('check', 'Проверить карточку')}</button>
        <button type="button" disabled={disabled} className="border bg-white disabled:opacity-50" onClick={runGenerateDescription}>{buttonLabel('ai', 'Сгенерировать описание GPT')}</button>
        {mode === 'edit' && <button type="button" disabled={disabled} className="bg-green-700 text-white disabled:opacity-50" onClick={() => changeStatus('publish')}>{buttonLabel('publish', 'Опубликовать')}</button>}
        {mode === 'edit' && <button type="button" disabled={disabled} className="bg-yellow-600 text-white disabled:opacity-50" onClick={() => changeStatus('hide')}>{buttonLabel('hide', 'Скрыть')}</button>}
        {mode === 'edit' && <button type="button" disabled={disabled} className="bg-red-700 text-white disabled:opacity-50" onClick={() => changeStatus('archive')}>{buttonLabel('archive', 'Архивировать')}</button>}
      </div>
    </form>
  );
}
