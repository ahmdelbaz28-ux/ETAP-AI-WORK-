import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Card, CardHeader, CardSection } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth.tsx'

export function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  
  const from = location.state?.from?.pathname || '/';

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader
          title="Sign in to your account"
          subtitle="Enter your credentials to access the engineering platform"
          className="space-y-1"
        />
        <form onSubmit={handleSubmit} className="space-y-4">
          <CardSection>
            {error && (
              <div className="bg-red-50 text-red-700 p-3 rounded-md text-sm">
                {error}
              </div>
            )}

            <div className="space-y-2 mt-3">
              <label htmlFor="email" className="text-sm font-medium text-[var(--text-primary)]">
                Email
              </label>
              <input
                id="email"
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                required
                className="w-full rounded-md border border-[var(--border-primary)] px-3 py-2 text-sm bg-transparent"
              />
            </div>

            <div className="space-y-2 mt-3">
              <label htmlFor="password" className="text-sm font-medium text-[var(--text-primary)]">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
                required
                className="w-full rounded-md border border-[var(--border-primary)] px-3 py-2 text-sm bg-transparent"
              />
            </div>
          </CardSection>

          <CardSection className="pt-0 flex flex-col border-t-0">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign in'}
            </Button>

            <p className="mt-4 text-center text-sm text-gray-600">
              Don't have an account?{' '}
              <a href="/register" className="font-medium text-blue-600 hover:text-blue-500">
                Sign up
              </a>
            </p>
          </CardSection>
        </form>
      </Card>
    </div>
  );
}