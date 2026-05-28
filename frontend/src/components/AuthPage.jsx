import React, { useState } from 'react';

const API_BASE = 'http://localhost:5000/api';

export default function AuthPage({ mode, role, onAuth, onNavigate }) {
    const [formData, setFormData] = useState({
        name: '',
        phone: '',
        password: '',
        factory_id: '1'
    });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const endpoint = mode === 'signup' ? '/auth/signup' : '/auth/login';
            const payload = mode === 'signup'
                ? { ...formData, role }
                : { phone: formData.phone, password: formData.password };

            const response = await fetch(API_BASE + endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok) {
                localStorage.setItem('token', data.token);
                localStorage.setItem('user', JSON.stringify(data));
                onAuth(data);
            } else {
                setError(data.error || 'Authentication failed');
            }
        } catch (err) {
            setError('Connection error. Please check if backend is running.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-container">
            <div className="auth-box">
                <h2>{mode === 'signup' ? 'Sign Up' : 'Login'} - {role.replace('_', ' ').toUpperCase()}</h2>
                {error && <div className="error-message">{error}</div>}
                <form onSubmit={handleSubmit}>
                    {mode === 'signup' && (
                        <>
                            <div className="form-group">
                                <label htmlFor="auth-name">Full Name</label>
                                <input
                                    id="auth-name"
                                    name="name"
                                    type="text"
                                    required
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                />
                            </div>
                            <div className="form-group">
                                <label htmlFor="auth-factory">Factory</label>
                                <select
                                    id="auth-factory"
                                    name="factory_id"
                                    value={formData.factory_id}
                                    onChange={(e) => setFormData({ ...formData, factory_id: e.target.value })}
                                >
                                    <option value="1">Factory Alpha (North Zone)</option>
                                    <option value="2">Factory Beta (South Zone)</option>
                                    <option value="3">Factory Gamma (East Zone)</option>
                                    <option value="4">Factory Delta (West Zone)</option>
                                    <option value="5">Factory Epsilon (Central Zone)</option>
                                    <option value="6">Factory Zeta (North-East Zone)</option>
                                    <option value="7">Factory Eta (South-West Zone)</option>
                                </select>
                            </div>
                        </>
                    )}
                    <div className="form-group">
                        <label htmlFor="auth-phone">Phone Number</label>
                        <input
                            id="auth-phone"
                            name="phone"
                            type="tel"
                            required
                            value={formData.phone}
                            onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                        />
                    </div>
                    <div className="form-group">
                        <label htmlFor="auth-password">Password</label>
                        <input
                            id="auth-password"
                            name="password"
                            type="password"
                            required
                            value={formData.password}
                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        />
                    </div>
                    <button type="submit" className="btn-submit" disabled={loading}>
                        {loading ? 'Please wait...' : (mode === 'signup' ? 'Sign Up' : 'Login')}
                    </button>
                </form>
                <div className="auth-switch">
                    {mode === 'signup' ? (
                        <>
                            Already have an account?{' '}
                            <button onClick={() => onNavigate('login', role)}>Login</button>
                        </>
                    ) : (
                        <>
                            Don't have an account?{' '}
                            <button onClick={() => onNavigate('signup', role)}>Sign Up</button>
                        </>
                    )}
                </div>
                <div className="auth-switch">
                    <button onClick={() => onNavigate('home')}>← Back to Home</button>
                </div>
            </div>
        </div>
    );
}
