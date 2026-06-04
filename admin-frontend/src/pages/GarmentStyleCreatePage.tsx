import GarmentStyleForm from '../components/GarmentStyleForm';

export default function GarmentStyleCreatePage({ navigate }: { navigate: (path: string) => void }) {
  return (
    <div className="space-y-6">
      <div>
        <button className="mb-3 text-sm text-slate-500 hover:underline" onClick={() => navigate('/garment-styles')}>← К списку фасонов</button>
        <h1 className="text-3xl font-bold">Добавить фасон</h1>
        <p className="text-slate-500">Фасоны добавляет только администратор. Загрузите основное изображение и при необходимости mask image.</p>
      </div>
      <GarmentStyleForm mode="create" onSaved={(styleId) => navigate(`/garment-styles/${styleId}`)} />
    </div>
  );
}
