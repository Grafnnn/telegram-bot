import { useEffect, useState } from 'react';
import { getToken } from './api/client';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import FabricCreatePage from './pages/FabricCreatePage';
import FabricEditPage from './pages/FabricEditPage';
import FabricImportReviewPage from './pages/FabricImportReviewPage';
import FabricsListPage from './pages/FabricsListPage';
import GarmentStyleCreatePage from './pages/GarmentStyleCreatePage';
import GarmentStyleEditPage from './pages/GarmentStyleEditPage';
import GarmentStylesListPage from './pages/GarmentStylesListPage';
import GenerationsPage from './pages/GenerationsPage';
import LoginPage from './pages/LoginPage';

function useHashRoute() {
  const [route, setRoute] = useState(window.location.hash.slice(1) || '/');
  useEffect(() => { const onHash = () => setRoute(window.location.hash.slice(1) || '/'); window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash); }, []);
  const navigate = (path: string) => { window.location.hash = `#${path}`; setRoute(path); };
  return { route, navigate };
}

export default function App() {
  const { route, navigate } = useHashRoute();
  if (!getToken() && route !== '/login') return <LoginPage navigate={navigate} />;
  if (route === '/login') return <LoginPage navigate={navigate} />;
  let page = <DashboardPage navigate={navigate} />;
  if (route === '/dashboard') page = <DashboardPage navigate={navigate} />;
  if (route === '/fabrics') page = <FabricsListPage navigate={navigate} />;
  if (route === '/fabrics/import') page = <FabricImportReviewPage navigate={navigate} />;
  if (route === '/fabrics/new') page = <FabricCreatePage navigate={navigate} />;
  if (route.startsWith('/fabrics/') && !['/fabrics/new', '/fabrics/import'].includes(route)) page = <FabricEditPage id={route.split('/')[2] ?? ''} navigate={navigate} />;
  if (route === '/garment-styles') page = <GarmentStylesListPage navigate={navigate} />;
  if (route === '/garment-styles/new') page = <GarmentStyleCreatePage navigate={navigate} />;
  if (route.startsWith('/garment-styles/') && route !== '/garment-styles/new') page = <GarmentStyleEditPage id={route.split('/')[2] ?? ''} navigate={navigate} />;
  if (route === '/generations') page = <GenerationsPage />;
  return <Layout navigate={navigate}>{page}</Layout>;
}
