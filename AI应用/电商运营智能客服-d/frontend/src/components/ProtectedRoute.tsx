import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const { token } = useAuth();
  if (!token) return <Navigate to="/" replace />;
  return children;
};