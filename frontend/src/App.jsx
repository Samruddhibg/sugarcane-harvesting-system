import React, { useState, useEffect } from 'react';
import LandingPage from './components/LandingPage';
import AuthPage from './components/AuthPage';
import FarmerDashboard from './components/FarmerDashboard';
import MachineOwnerDashboard from './components/MachineOwnerDashboard';
import FactoryDashboard from './components/FactoryDashboard';

const API_BASE = 'http://localhost:5000/api';

export default function App() {
    const [currentPage, setCurrentPage] = useState('home');
    const [authMode, setAuthMode] = useState('login');
    const [role, setRole] = useState('farmer');
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);

    useEffect(() => {
        // Check if already logged in
        const savedToken = localStorage.getItem('token');
        const savedUser = localStorage.getItem('user');
        if (savedToken && savedUser) {
            setToken(savedToken);
            setUser(JSON.parse(savedUser));
            setCurrentPage('dashboard');
        }
    }, []);

    const handleNavigate = (page, userRole) => {
        setCurrentPage(page);
        if (userRole) setRole(userRole);
        if (page === 'login' || page === 'signup') {
            setAuthMode(page);
        }
    };

    const handleAuth = (userData) => {
        setUser(userData);
        setToken(userData.token);
        setCurrentPage('dashboard');
    };

    const handleLogout = async () => {
        try {
            await fetch(API_BASE + '/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
        } catch(e) {
            console.error('Logout error', e);
        }
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setUser(null);
        setToken(null);
        setCurrentPage('home');
    };

    if (currentPage === 'home') {
        return <LandingPage onNavigate={handleNavigate} />;
    }

    if (currentPage === 'login' || currentPage === 'signup') {
        return <AuthPage 
            mode={authMode} 
            role={role} 
            onAuth={handleAuth}
            onNavigate={handleNavigate}
        />;
    }

    if (currentPage === 'dashboard' && user) {
        if (user.role === 'farmer') {
            return <FarmerDashboard user={user} token={token} onLogout={handleLogout} />;
        } else if (user.role === 'machine_owner') {
            return <MachineOwnerDashboard user={user} token={token} onLogout={handleLogout} />;
        } else if (user.role === 'factory_admin') {
            return <FactoryDashboard user={user} token={token} onLogout={handleLogout} />;
        }
    }

    return <div className="loading">Loading...</div>;
}
