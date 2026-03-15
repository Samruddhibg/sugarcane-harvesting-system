import React from 'react';

export default function LandingPage({ onNavigate }) {
    return (
        <div className="landing-container">
            <div className="landing-hero">
                <h1>🌾 Sugarcane Harvesting System</h1>
                <p>Efficient resource allocation for sugarcane farmers and machine owners</p>
            </div>
            <div className="landing-cards">
                <div className="landing-card">
                    <h2>👨‍🌾 Farmers</h2>
                    <p>Register your crops and get matched with harvesting machines automatically</p>
                    <button className="btn-primary" onClick={() => onNavigate('login', 'farmer')}>
                        Farmer Portal
                    </button>
                </div>
                <div className="landing-card">
                    <h2>🚜 Machine Owners</h2>
                    <p>Register your machines and receive assignment requests from farmers</p>
                    <button className="btn-primary" onClick={() => onNavigate('login', 'machine_owner')}>
                        Machine Owner Portal
                    </button>
                </div>
                <div className="landing-card">
                    <h2>🏭 Factory Admin</h2>
                    <p>Manage operations, view analytics, and monitor assignments</p>
                    <button className="btn-primary" onClick={() => onNavigate('login', 'factory_admin')}>
                        Admin Dashboard
                    </button>
                </div>
            </div>
        </div>
    );
}
