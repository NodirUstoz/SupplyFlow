import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';

interface RegisterFormData {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  confirmPassword: string;
  agreeToTerms: boolean;
}

const RegisterForm: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<RegisterFormData>({
    firstName: '', lastName: '', email: '', password: '', confirmPassword: '', agreeToTerms: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const validateForm = (): boolean => {
    const errs: Record<string, string> = {};
    if (!formData.firstName.trim()) errs.firstName = 'First name is required';
    if (!formData.lastName.trim()) errs.lastName = 'Last name is required';
    if (!formData.email) errs.email = 'Email is required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) errs.email = 'Invalid email format';
    if (!formData.password) errs.password = 'Password is required';
    else if (formData.password.length < 8) errs.password = 'Password must be at least 8 characters';
    else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(formData.password)) errs.password = 'Must contain uppercase, lowercase, and number';
    if (formData.password !== formData.confirmPassword) errs.confirmPassword = 'Passwords do not match';
    if (!formData.agreeToTerms) errs.agreeToTerms = 'You must agree to the terms';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;
    setIsLoading(true);
    try {
      const response = await fetch('/api/v1/auth/register/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: formData.firstName, last_name: formData.lastName,
          email: formData.email, password: formData.password,
        }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Registration failed');
      }
      const data = await response.json();
      localStorage.setItem('auth_tokens', JSON.stringify(data.tokens));
      navigate('/dashboard');
    } catch (error: any) {
      setErrors({ general: error.message });
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const getStrength = () => {
    const p = formData.password;
    if (!p) return { label: '', width: '0%', color: 'bg-gray-200' };
    let s = 0;
    if (p.length >= 8) s++; if (p.length >= 12) s++; if (/[A-Z]/.test(p)) s++;
    if (/[0-9]/.test(p)) s++; if (/[^A-Za-z0-9]/.test(p)) s++;
    if (s <= 2) return { label: 'Weak', width: '33%', color: 'bg-red-500' };
    if (s <= 3) return { label: 'Medium', width: '66%', color: 'bg-yellow-500' };
    return { label: 'Strong', width: '100%', color: 'bg-green-500' };
  };
  const strength = getStrength();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Create your account</h2>
          <p className="mt-2 text-sm text-gray-600">Start your journey with us today</p>
        </div>
        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          {errors.general && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{errors.general}</div>}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">First name</label>
              <input name="firstName" value={formData.firstName} onChange={handleChange}
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 ${errors.firstName ? 'border-red-500' : 'border-gray-300'}`} />
              {errors.firstName && <p className="mt-1 text-sm text-red-600">{errors.firstName}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Last name</label>
              <input name="lastName" value={formData.lastName} onChange={handleChange}
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 ${errors.lastName ? 'border-red-500' : 'border-gray-300'}`} />
              {errors.lastName && <p className="mt-1 text-sm text-red-600">{errors.lastName}</p>}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input name="email" type="email" value={formData.email} onChange={handleChange}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 ${errors.email ? 'border-red-500' : 'border-gray-300'}`} />
            {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input name="password" type="password" value={formData.password} onChange={handleChange}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 ${errors.password ? 'border-red-500' : 'border-gray-300'}`} />
            {formData.password && (
              <div className="mt-2"><div className="h-1.5 bg-gray-200 rounded-full"><div className={`h-full ${strength.color} rounded-full transition-all`} style={{ width: strength.width }} /></div>
              <p className="text-xs mt-1 text-gray-500">Strength: {strength.label}</p></div>
            )}
            {errors.password && <p className="mt-1 text-sm text-red-600">{errors.password}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm password</label>
            <input name="confirmPassword" type="password" value={formData.confirmPassword} onChange={handleChange}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 ${errors.confirmPassword ? 'border-red-500' : 'border-gray-300'}`} />
            {errors.confirmPassword && <p className="mt-1 text-sm text-red-600">{errors.confirmPassword}</p>}
          </div>
          <label className="flex items-start">
            <input type="checkbox" name="agreeToTerms" checked={formData.agreeToTerms} onChange={handleChange} className="h-4 w-4 mt-0.5 text-blue-600 rounded" />
            <span className="ml-2 text-sm text-gray-600">I agree to the Terms of Service and Privacy Policy</span>
          </label>
          <button type="submit" disabled={isLoading}
            className="w-full py-3 px-4 rounded-lg text-white bg-blue-600 hover:bg-blue-700 font-medium disabled:opacity-50">
            {isLoading ? 'Creating account...' : 'Create account'}
          </button>
          <p className="text-center text-sm text-gray-600">Already have an account? <Link to="/login" className="text-blue-600 font-medium">Sign in</Link></p>
        </form>
      </div>
    </div>
  );
};

export default RegisterForm;
