import React, { useState, useEffect } from 'react';

const API_BASE = 'http://localhost:5000/api';

export default function MachineOwnerDashboard({ user, token, onLogout }) {
    const [activeTab, setActiveTab] = useState('home');
    const [dashboardData, setDashboardData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadDashboard();
    }, []);

    const loadDashboard = async () => {
        try {
            const response = await fetch(API_BASE + '/machine/dashboard', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setDashboardData(data);
        } catch (err) {
            console.error('Dashboard load error:', err);
        } finally {
            setLoading(false);
        }
    };

    const updateStatus = async (machineId, newStatus) => {
        try {
            await fetch(API_BASE + `/machine/${machineId}/status`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status: newStatus })
            });
            loadDashboard();
        } catch (err) {
            alert('Failed to update status');
        }
    };

    if (loading) return <div className="loading">Loading...</div>;

    return (
        <>
            <nav className="navbar">
                <div className="navbar-brand">🚜 Machine Owner Portal</div>
                <div className="navbar-menu">
                    <button className={`nav-link ${activeTab === 'home' ? 'active' : ''}`}
                            onClick={() => setActiveTab('home')}>
                        Home
                    </button>
                    <button className={`nav-link ${activeTab === 'register' ? 'active' : ''}`}
                            onClick={() => setActiveTab('register')}>
                        Register Machine
                    </button>
                    <button className={`nav-link ${activeTab === 'profile' ? 'active' : ''}`}
                            onClick={() => setActiveTab('profile')}>
                        Profile
                    </button>
                    <button className="btn-logout" onClick={onLogout}>Logout</button>
                </div>
            </nav>

            {dashboardData && (
            <div className="hero">
                <h2 className="hero-title">Welcome, {user.name}!</h2>
                
                <div className="stats-grid">
                    <div className="stat-card">
                        <h3>{dashboardData.stats?.total_machines || 0}</h3>
                        <p>Total Machines</p>
                    </div>
                    <div className="stat-card">
                        <h3>{dashboardData.stats?.idle_machines || 0}</h3>
                        <p>Available</p>
                    </div>
                    <div className="stat-card">
                        <h3>{dashboardData.stats?.busy_machines || 0}</h3>
                        <p>Working</p>
                    </div>
                </div>

                <div className="data-table">
                    <h3 style={{padding: '1rem'}}>🚜 My Machines</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Machine ID</th>
                                <th>Address</th>
                                <th>District</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(dashboardData.machines || []).map(machine => (
                                <tr key={machine.m_id}>
                                    <td>#{machine.m_id}</td>
                                    <td>{machine.m_address}</td>
                                    <td>{machine.m_district}</td>
                                    <td>
                                        <span className={`badge badge-${
                                            machine.m_status === 'idle' ? 'success' : 
                                            machine.m_status === 'busy' ? 'danger' : 'warning'
                                        }`}>
                                            {machine.m_status}
                                        </span>
                                    </td>
                                    <td>
                                        {machine.m_status === 'busy' && (
                                            <button className="btn-action btn-success"
                                                    onClick={() => updateStatus(machine.m_id, 'idle')}>
                                                Mark as Idle
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="data-table">
                    <h3 style={{padding: '1rem'}}>📋 Assignment History</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Farmer</th>
                                <th>Phone</th>
                                <th>Assigned Date</th>
                                <th>Completion</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(dashboardData.assignments || []).map(assignment => (
                                <tr key={assignment.assignment_id}>
                                    <td>{assignment.farmer_name}</td>
                                    <td>{assignment.farmer_phone}</td>
                                    <td>{assignment.assigned_date}</td>
                                    <td>{assignment.estimated_completion}</td>
                                    <td>
                                        <span className={`badge badge-${
                                            assignment.status === 'completed' ? 'success' : 'info'
                                        }`}>
                                            {assignment.status}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
            )}

            {activeTab === 'register' && (
                <div className="hero">
                    <h2 className="hero-title">Register New Machine</h2>
                    <div style={{maxWidth: '500px', margin: '2rem auto', textAlign: 'left', background: 'white', padding: '2rem', borderRadius: '12px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)'}}>
                        <form onSubmit={(e) => {
                            e.preventDefault();
                            alert('Machine registration submitted successfully!');
                            setActiveTab('home');
                        }}>
                            <div style={{marginBottom: '1rem'}}>
                                <label style={{display: 'block', marginBottom: '0.5rem', fontWeight: 'bold'}}>Machine Name / Model</label>
                                <input type="text" required style={{width: '100%', padding: '0.8rem', border: '1px solid #ccc', borderRadius: '6px'}} />
                            </div>
                            <div style={{marginBottom: '1rem'}}>
                                <label style={{display: 'block', marginBottom: '0.5rem', fontWeight: 'bold'}}>Operating District</label>
                                <input type="text" required style={{width: '100%', padding: '0.8rem', border: '1px solid #ccc', borderRadius: '6px'}} />
                            </div>
                            <div style={{marginBottom: '1rem'}}>
                                <label style={{display: 'block', marginBottom: '0.5rem', fontWeight: 'bold'}}>Base Location Address</label>
                                <textarea required rows="3" style={{width: '100%', padding: '0.8rem', border: '1px solid #ccc', borderRadius: '6px'}}></textarea>
                            </div>
                            <button type="submit" className="btn-primary" style={{width: '100%', marginTop: '1rem', padding: '1rem'}}>Register Machine</button>
                        </form>
                    </div>
                </div>
            )}

            {activeTab === 'profile' && (
                <div className="hero">
                    <h2 className="hero-title">My Profile</h2>
                    <div style={{background: 'white', padding: '2rem', borderRadius: '12px', maxWidth: '400px', margin: '2rem auto', textAlign: 'left', boxShadow: '0 4px 6px rgba(0,0,0,0.1)'}}>
                        <div style={{marginBottom: '1rem'}}><strong style={{color: '#667eea'}}>Name:</strong> <span style={{fontSize: '1.1rem'}}>{user.name}</span></div>
                        <div style={{marginBottom: '1rem'}}><strong style={{color: '#667eea'}}>Phone Number:</strong> <span style={{fontSize: '1.1rem'}}>{user.phone}</span></div>
                        <div style={{marginBottom: '1rem'}}><strong style={{color: '#667eea'}}>Role:</strong> <span style={{fontSize: '1.1rem', textTransform: 'capitalize'}}>{user.role}</span></div>
                    </div>
                </div>
            )}
        </>
    );
}
