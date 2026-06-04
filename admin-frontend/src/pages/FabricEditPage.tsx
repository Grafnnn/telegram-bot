import { useEffect, useState } from 'react';
import { Fabric, getFabric } from '../api/fabrics';
import FabricForm from '../components/FabricForm';

export default function FabricEditPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const [fabric, setFabric] = useState<Fabric | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getFabric(id)
      .then(setFabric)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Не удалось загрузить ткань.'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p>Загрузка ткани...</p>;
  if (error) return <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>;
  if (!fabric) return <p>Ткань не найдена.</p>;

  return (
    <div className="space-y-6">
      <div>
        <button className="mb-3 text-sm text-slate-500 hover:underline" onClick={() => navigate('/fabrics')}>← К списку тканей</button>
        <h1 className="text-3xl font-bold">Редактирование ткани</h1>
        <p className="text-slate-500">Измените поля, загрузите изображения, проверьте карточку и опубликуйте ткань.</p>
      </div>
      <FabricForm mode="edit" fabric={fabric} onUpdated={setFabric} />
    </div>
  );
}
