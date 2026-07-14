/**
 * ProtectedRoute — gates access to routes that require authentication.
 *
 * Behavior:
 *   - While the auth state is loading (initial token validation), shows a
 *     full-screen spinner so we don't flash the login page before the
 *     token check completes.
 *   - If the user is not authenticated, redirects to /login with the
 *     intended destination preserved in the `from` search param so the
 *     login page can send them back after a successful login.
 *   - If the user is authenticated, renders the matched child route.
 *
 * This component MUST wrap every route that should not be publicly
 * accessible. Before this component existed, /dashboard, /studies,
 * /settings, etc. were all reachable without login — a real security
 * hole because those pages can trigger backend operations.
 */
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

interface ProtectedRouteProps {
  readonly children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  // While validating the token on initial mount, show a loading screen.
  // This prevents a flash of /login for users who have a valid token.
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[var(--text-muted)]">Loading session…</p>
        </div>
      </div>
    );
  }

  // Not authenticated → redirect to /login, preserving the intended URL.
  if (!isAuthenticated) {
    const from = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?from=${from}`} replace />;
  }

  // Authenticated → render the protected route.
  return <>{children}</>;
}
