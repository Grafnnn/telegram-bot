import FabricForm from '../components/FabricForm';

export default function FabricCreatePage({ navigate }: { navigate: (path: string) => void }) {
  return (
    <div className="space-y-6">
      <div>
        <button className="mb-3 text-sm text-slate-500 hover:underline" onClick={() => navigate('/fabrics')}>← К списку тканей</button>
        <h1 className="text-3xl font-bold">Добавить ткань</h1>
        <p className="text-slate-500">Заполните карточку, добавьте главное фото и фото фактуры, затем сохраните черновик или опубликуйте ткань.</p>
      </div>
      <FabricForm mode="create" onCreated={(fabricId) => navigate(`/fabrics/${fabricId}`)} />
    </div>
  );
}
