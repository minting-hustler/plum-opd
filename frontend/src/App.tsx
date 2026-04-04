import { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { onAuth, type User } from "./lib/auth";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import ClaimNew from "./pages/ClaimNew";
import ClaimDetail from "./pages/ClaimDetail";
import Admin from "./pages/Admin";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    const unsub = onAuth((u) => setUser(u));
    return unsub;
  }, []);

  if (user === undefined) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-plum-600" />
      </div>
    );
  }

  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route
        path="/dashboard"
        element={<PrivateRoute><Dashboard /></PrivateRoute>}
      />
      <Route
        path="/claims/new"
        element={<PrivateRoute><ClaimNew /></PrivateRoute>}
      />
      <Route
        path="/claims/:id"
        element={<PrivateRoute><ClaimDetail /></PrivateRoute>}
      />
      <Route
        path="/admin"
        element={<PrivateRoute><Admin /></PrivateRoute>}
      />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
