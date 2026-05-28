import React, { useState, useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';

const API_BASE = 'http://localhost:5000/api';

export default function FactoryDashboard({ user, token, onLogout }) {
    const [activeTab, setActiveTab] = useState('home');
    const [dashboardData, setDashboardData] = useState(null);
    const [loading, setLoading] = useState(true);
    const chartRef = useRef(null);

    useEffect(() => {
        loadDashboard();
    }, []);

    const loadDashboard = async () => {
        try {
            const response = await fetch(API_BASE + '/factory/dashboard', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setDashboardData(data);

            // Create chart after data loads if on home tab
            if (activeTab === 'home' && data.chart_data) {
                setTimeout(() => createChart(data.chart_data), 100);
            }
        } catch (err) {
            console.error('Dashboard load error:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'home' && dashboardData?.chart_data) {
            createChart(dashboardData.chart_data);
        }
    }, [activeTab]);

    const createChart = (chartData) => {
        const ctx = document.getElementById('assignmentChart');
        if (!ctx) return;

        if (chartRef.current) {
            chartRef.current.destroy();
        }

        chartRef.current = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: chartData.map(d => d.assigned_date),
                datasets: [{
                    label: 'Assignments',
                    data: chartData.map(d => d.assignments),
                    backgroundColor: 'rgba(102, 126, 234, 0.5)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    };

    if (loading) return <div className="loading">Loading...</div>;

    return (
        <>
            <nav className="navbar">
                <div className="navbar-brand">🏭 Factory Dashboard</div>
                <div className="navbar-menu">
                    <button className={`nav-link ${activeTab === 'home' ? 'active' : ''}`}
                        onClick={() => setActiveTab('home')}>
                        Home
                    </button>
                    <button className={`nav-link ${activeTab === 'farmers' ? 'active' : ''}`}
                        onClick={() => setActiveTab('farmers')}>
                        All Farmers
                    </button>
                    <button className={`nav-link ${activeTab === 'machines' ? 'active' : ''}`}
                        onClick={() => setActiveTab('machines')}>
                        All Machines
                    </button>
                    <button className={`nav-link ${activeTab === 'profile' ? 'active' : ''}`}
                        onClick={() => setActiveTab('profile')}>
                        Profile
                    </button>
                    <button className="btn-logout" onClick={onLogout}>Logout</button>
                </div>
            </nav>

            {activeTab === 'home' && dashboardData && (
                <div className="hero">
                    <h2 className="hero-title">{dashboardData.factory?.name || 'Factory'}</h2>

                    <div className="stats-grid">
                        <div className="stat-card">
                            <h3>{dashboardData.stats?.total_farmers || 0}</h3>
                            <p>Total Farmers</p>
                        </div>
                        <div className="stat-card">
                            <h3>{dashboardData.stats?.pending_farmers || 0}</h3>
                            <p>Pending</p>
                        </div>
                        <div className="stat-card">
                            <h3>{dashboardData.stats?.total_machines || 0}</h3>
                            <p>Total Machines</p>
                        </div>
                        <div className="stat-card">
                            <h3>{dashboardData.stats?.today_assignments || 0}</h3>
                            <p>Today's Assignments</p>
                        </div>
                    </div>

                    <div className="data-table">
                        <h3 style={{ padding: '1rem' }}>
                            📊 Capacity: {dashboardData.stats?.capacity_used_percent?.toFixed(1) || 0}% Used
                        </h3>
                        <div style={{ padding: '1rem' }}>
                            <div style={{ background: '#f0f0f0', borderRadius: '10px', height: '30px', overflow: 'hidden' }}>
                                <div style={{
                                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                    height: '100%',
                                    width: `${dashboardData.stats?.capacity_used_percent || 0}%`,
                                    transition: 'width 0.3s'
                                }}></div>
                            </div>
                            <p style={{ marginTop: '0.5rem', color: '#666' }}>
                                {(dashboardData.stats?.today_production || 0).toLocaleString()} kg / {(dashboardData.stats?.capacity || 0).toLocaleString()} kg
                            </p>
                        </div>
                    </div>

                    <div className="chart-container">
                        <h3>Last 7 Days Assignments</h3>
                        <canvas id="assignmentChart"></canvas>
                    </div>

                    <div className="data-table">
                        <h3 style={{ padding: '1rem' }}>📋 Today's Assignments</h3>
                        <table>
                            <thead>
                                <tr>
                                    <th>Farmer</th>
                                    <th>Machine Owner</th>
                                    <th>Crop (acres)</th>
                                    <th>Production (kg)</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(dashboardData.today_assignments || []).map(assignment => (
                                    <tr key={assignment.assignment_id}>
                                        <td>{assignment.farmer_name}</td>
                                        <td>{assignment.machine_owner}</td>
                                        <td>{assignment.f_crop}</td>
                                        <td>{(assignment.production_kg || 0).toLocaleString()}</td>
                                        <td>
                                            <span className="badge badge-info">{assignment.status}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {activeTab === 'farmers' && dashboardData && (
                <div className="hero">
                    <h2 className="hero-title">All Farmers</h2>
                    <div className="data-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Phone</th>
                                    <th>Crop (acres)</th>
                                    <th>Planting Date</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(dashboardData.farmers || []).map(farmer => (
                                    <tr key={farmer.f_id}>
                                        <td>{farmer.f_name}</td>
                                        <td>{farmer.f_phone_number}</td>
                                        <td>{farmer.f_crop}</td>
                                        <td>{farmer.f_planting_date}</td>
                                        <td>
                                            <span className={`badge badge-${farmer.status === 'assigned' ? 'success' : 'warning'
                                                }`}>
                                                {farmer.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {activeTab === 'machines' && dashboardData && (
                <div className="hero">
                    <h2 className="hero-title">All Machines</h2>
                    <div className="data-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Machine ID</th>
                                    <th>Owner</th>
                                    <th>Phone</th>
                                    <th>District</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(dashboardData.machines || []).map(machine => (
                                    <tr key={machine.m_id}>
                                        <td>#{machine.m_id}</td>
                                        <td>{machine.owner_name}</td>
                                        <td>{machine.m_phone_number}</td>
                                        <td>{machine.m_district}</td>
                                        <td>
                                            <span className={`badge badge-${machine.m_status === 'idle' ? 'success' : 'danger'
                                                }`}>
                                                {machine.m_status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {activeTab === 'profile' && (
                <div className="hero">
                    <h2 className="hero-title">Admin Profile</h2>
                    <div style={{ background: 'white', padding: '2rem', borderRadius: '12px', maxWidth: '400px', margin: '2rem auto', textAlign: 'left', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
                        <div style={{ marginBottom: '1rem' }}><strong style={{ color: '#667eea' }}>Admin Name:</strong> <span style={{ fontSize: '1.1rem' }}>{user.name}</span></div>
                        <div style={{ marginBottom: '1rem' }}><strong style={{ color: '#667eea' }}>Phone Number:</strong> <span style={{ fontSize: '1.1rem' }}>{user.phone}</span></div>
                        <div style={{ marginBottom: '1rem' }}><strong style={{ color: '#667eea' }}>Role:</strong> <span style={{ fontSize: '1.1rem', textTransform: 'capitalize' }}>{user.role}</span></div>
                        <div style={{ marginBottom: '1rem' }}><strong style={{ color: '#667eea' }}>Managed Factory ID:</strong> <span style={{ fontSize: '1.1rem' }}>{user.factory_id}</span></div>
                    </div>
                </div>
            )}
        </>
    );
}
