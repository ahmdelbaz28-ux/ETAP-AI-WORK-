import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardSection } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useAuth } from '../hooks/useAuth.tsx';

export function Register() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  const navigate = useNavigate();
  const { register } = useAuth();
  
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    
    setError('');
    setLoading(true);
    
    try {
      await register(email, password, name);
      navigate('/login', { state: { from: { pathname: '/' } }, replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <Card className="w-full max-w-md">
        <CardHeader
          title="Create an account"
          subtitle="Enter your details to get started with the engineering platform"
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
              <label htmlFor="name" className="text-sm font-medium text-[var(--text-primary)]">
                Full Name
              </label>
              <input
                id="name"
                type="text"
                placeholder="John Doe"
                value={name}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
                required
                className="w-full rounded-md border border-[var(--border-primary)] px-3 py-2 text-sm bg-transparent"
              />
            </div>

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

            <div className="space-y-2 mt-3">
              <label
                htmlFor="confirmPassword"
                className="text-sm font-medium text-[var(--text-primary)]"
              >
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setConfirmPassword(e.target.value)
                }
                required
                className="w-full rounded-md border border-[var(--border-primary)] px-3 py-2 text-sm bg-transparent"
              />
            </div>
          </CardSection>

          <CardSection className="pt-0 flex flex-col border-t-0">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Creating account...' : 'Create account'}
            </Button>

            <p className="mt-4 text-center text-sm text-gray-600">
              Already have an account?{' '}
              <a
                href="/login"
                className="font-medium text-blue-600 hover:text-blue-500"
              >
                Sign in
              </a>
            </p>
          </CardSection>
        </form>
      </Card>
    </div>
  );
}