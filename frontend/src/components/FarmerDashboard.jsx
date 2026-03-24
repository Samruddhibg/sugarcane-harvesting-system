import React, { useState, useEffect } from 'react';

const API_BASE = 'https://sugarcane-harvesting-system-8.onrender.com/api';

export default function FarmerDashboard({ user, token, onLogout }) {
    const [activeTab, setActiveTab] = useState('home');
    const [dashboardData, setDashboardData] = useState(null);
    const [notifications, setNotifications] = useState([]);
    const [loading, setLoading] = useState(true);
    const [farmerData, setFarmerData] = useState({
        address: "",
        district: "",
        planting_date: "",
        crop_acres: ""
    });

    const handleChange = (e) => {
        setFarmerData({
            ...farmerData,
            [e.target.name]: e.target.value
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        try {
            const res = await fetch(API_BASE + "/farmer/register-crop", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(farmerData)
            });

            if (res.ok) {
                const data = await res.json();
                console.log(data);
                alert("Crop registration submitted successfully! Will be reviewed by factory.");
                setFarmerData({
                    address: "",
                    district: "",
                    planting_date: "",
                    crop_acres: ""
                });
                setActiveTab('home');
                loadDashboard();
            } else {
                const errorData = await res.json();
                alert(`Error: ${errorData.error}`);
            }
        } catch (err) {
            console.error(err);
            alert("Error sending data");
        }
    };


    useEffect(() => {
        loadDashboard();
        loadNotifications();
    }, []);

    const loadDashboard = async () => {
        try {
            const response = await fetch(API_BASE + '/farmer/dashboard', {
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



    //   return (
    //     <div style={{ padding: "20px" }}>
    //       <h2>User Form</h2>

    //       <form onSubmit={handleSubmit}>
    //         <input
    //           type="text"
    //           name="name"
    //           placeholder="Enter Name"
    //           value={formData.name}
    //           onChange={handleChange}
    //         />

    //         <br /><br />

    //         <input
    //           type="email"
    //           name="email"
    //           placeholder="Enter Email"
    //           value={formData.email}
    //           onChange={handleChange}
    //         />

    //         <br /><br />

    //         <button type="submit">Submit</button>
    //       </form>
    //     </div>
    //   );
    // }

    // const loadRegisteredCrop=async ()=>{
    //     try{
    //         const response=await fetch();
    //     }
    //     const data=await response.json();

    // }

    const loadNotifications = async () => {
        try {
            const response = await fetch(API_BASE + '/notifications', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setNotifications(data);
        } catch (err) {
            console.error('Notifications load error:', err);
        }
    };

    const handleAccept = async (requestId) => {
        try {
            await fetch(API_BASE + `/farmer/request/${requestId}/accept`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            loadDashboard();
        } catch (err) {
            alert('Failed to accept request');
        }
    };

    const handleReject = async (requestId) => {
        try {
            await fetch(API_BASE + `/farmer/request/${requestId}/reject`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            loadDashboard();
        } catch (err) {
            alert('Failed to reject request');
        }
    };

    if (loading) return <div className="loading">Loading...</div>;

    return (
        <>
            <nav className="navbar">
                <div className="navbar-brand">Farmer Portal</div>
                <div className="navbar-menu">
                    <button className={`nav-link ${activeTab === 'home' ? 'active' : ''}`}
                        onClick={() => setActiveTab('home')}>
                        Home
                    </button>
                    <button className={`nav-link ${activeTab === 'register' ? 'active' : ''}`}
                        onClick={() => setActiveTab('register')}>
                        Register Crop
                    </button>
                    <button className={`nav-link ${activeTab === 'profile' ? 'active' : ''}`}
                        onClick={() => setActiveTab('profile')}>
                        Profile
                    </button>
                    <button className={`nav-link ${activeTab === 'notifications' ? 'active' : ''}`}
                        onClick={() => setActiveTab('notifications')}>
                        Notifications
                        {notifications.filter(n => !n.read_at).length > 0 && (
                            <span className="notification-badge">
                                {notifications.filter(n => !n.read_at).length}
                            </span>
                        )}
                    </button>
                    <button className="btn-logout" onClick={onLogout}>Logout</button>
                </div>
            </nav>

            {activeTab === 'home' && dashboardData && (
                <div className="hero">
                    <h2 className="hero-title">Welcome, {user.name}!</h2>

                    <div className="stats-grid">
                        <div className="stat-card">
                            <h3>{dashboardData.stats?.total_crops || 0}</h3>
                            <p>Total Crops</p>
                        </div>
                        <div className="stat-card">
                            <h3>{dashboardData.stats?.pending_crops || 0}</h3>
                            <p>Pending</p>
                        </div>
                        <div className="stat-card">
                            <h3>{dashboardData.stats?.assigned_crops || 0}</h3>
                            <p>Assigned</p>
                        </div>
                    </div>

                    {(dashboardData.pending_requests || []).length > 0 && (
                        <div className="data-table">
                            <h3 style={{ padding: '1rem' }}>⏰ Pending Assignment Requests</h3>
                            <table>
                                <thead>
                                    <tr>
                                        <th>Machine Owner</th>
                                        <th>Scheduled Date</th>
                                        <th>Crop (acres)</th>
                                        <th>Expires At</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(dashboardData.pending_requests || []).map(req => (
                                        <tr key={req.assignment_request_id}>
                                            <td>{req.machine_owner}</td>
                                            <td>{req.scheduled_date}</td>
                                            <td>{req.f_crop}</td>
                                            <td>{new Date(req.expires_at).toLocaleString()}</td>
                                            <td>
                                                <button className="btn-action btn-success"
                                                    onClick={() => handleAccept(req.assignment_request_id)}>
                                                    Accept
                                                </button>
                                                <button className="btn-action btn-danger"
                                                    onClick={() => handleReject(req.assignment_request_id)}>
                                                    Reject
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    <div className="data-table">
                        <h3 style={{ padding: '1rem' }}>📋 Assignment History</h3>
                        <table>
                            <thead>
                                <tr>
                                    <th>Machine Owner</th>
                                    <th>Assigned Date</th>
                                    <th>Completion</th>
                                    <th>Crop (acres)</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {(dashboardData.assignments || []).map(assignment => (
                                    <tr key={assignment.assignment_id}>
                                        <td>{assignment.machine_owner}</td>
                                        <td>{assignment.assigned_date}</td>
                                        <td>{assignment.estimated_completion}</td>
                                        <td>{assignment.f_crop}</td>
                                        <td>
                                            <span className={`badge badge-${assignment.status === 'completed' ? 'success' : 'info'
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

            {activeTab === 'notifications' && (
                <div className="hero">
                    <h2 className="hero-title">🔔 Notifications</h2>
                    <div className="data-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Message</th>
                                    <th>Time</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {notifications.map(notif => (
                                    <tr key={notif.notification_id}>
                                        <td>{notif.message}</td>
                                        <td>{new Date(notif.sent_at).toLocaleString()}</td>
                                        <td>
                                            <span className={`badge ${notif.read_at ? 'badge-success' : 'badge-warning'}`}>
                                                {notif.read_at ? 'Read' : 'Unread'}
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
                    <h2 className="hero-title">Register New Crop</h2>
                    <div style={{ maxWidth: '500px', margin: '2rem auto', textAlign: 'left', background: 'white', padding: '2rem', borderRadius: '12px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
                        <form onSubmit={handleSubmit}>
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>Crop Area (in acres)</label>
                                <input type="number" name="crop_acres" value={farmerData.crop_acres} onChange={handleChange} required style={{ width: '100%', padding: '0.8rem', border: '1px solid #ccc', borderRadius: '6px' }} />
                            </div>
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>Planting Date</label>
                                <input type="date" name="planting_date" value={farmerData.planting_date} onChange={handleChange} required style={{ width: '100%', padding: '0.8rem', border: '1px solid #ccc', borderRadius: '6px' }} />
                            </div>
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>District</label>
                                <input type="text" name="district" value={farmerData.district} onChange={handleChange} required style={{ width: '100%', padding: '0.8rem', border: '1px solid #ccc', borderRadius: '6px' }} />
                            </div>
                            <div style={{ marginBottom: '1rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>Farm Address</label>
                                <textarea name="address" value={farmerData.address} onChange={handleChange} required rows="3" style={{ width: '100%', padding: '0.8rem', border: '1px solid #ccc', borderRadius: '6px' }}></textarea>
                            </div>
                            <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '1rem', padding: '1rem' }}>Submit Registration</button>
                        </form>
                    </div>
                </div>
            )}

            {activeTab === 'profile' && (
                <div className="hero">
                    <h2 className="hero-title">My Profile</h2>
                    <div style={{ background: 'white', padding: '2rem', borderRadius: '12px', maxWidth: '400px', margin: '2rem auto', textAlign: 'left', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
                        <div style={{ marginBottom: '1rem' }}><strong style={{ color: '#667eea' }}>Name:</strong> <span style={{ fontSize: '1.1rem' }}>{user.name}</span></div>
                        <div style={{ marginBottom: '1rem' }}><strong style={{ color: '#667eea' }}>Phone Number:</strong> <span style={{ fontSize: '1.1rem' }}>{user.phone}</span></div>
                        <div style={{ marginBottom: '1rem' }}><strong style={{ color: '#667eea' }}>Role:</strong> <span style={{ fontSize: '1.1rem', textTransform: 'capitalize' }}>{user.role}</span></div>
                    </div>
                </div>
            )}
        </>
    );
}
