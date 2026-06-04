import { ReactNode } from 'react';
import { logout } from '../api/client';

export default function Layout({ children, navigate }: { children: ReactNode; navigate: (path: string) => void }) {
  const item = (label: string, path: string) => <button type="button" className="block w-full text-left hover:bg-slate-100" onClick={() => navigate(path)}>{label}</button>;
  return (
    <div className="min-h-screen flex">
      <aside className="w-60 bg-white border-r p-4 space-y-2">
        <h1 className="font-bold text-xl mb-4">Fashion Admin</h1>
        {item('Дашборд', '/dashboard')}
        {item('Ткани', '/fabrics')}
        {item('Фасоны', '/garment-styles')}
        {item('Генерации', '/generations')}
        <button type="button" className="block w-full text-left text-red-600" onClick={logout}>Выйти</button>
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}
