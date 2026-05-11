import React, { useState, useEffect, useCallback } from 'react';
import { 
  uploadPdf, 
  getDatabaseStatus, 
  deleteDatabase, 
  getEmbeddingStatus 
} from '../../api/apiService';
import toast from 'react-hot-toast';

const DatabaseManagement = () => {
  const [databases, setDatabases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const fetchDatabases = useCallback(async () => {
    setLoading(true);
    const res = await getDatabaseStatus();
    if (res.success) {
      setDatabases(res.databases);
    } else {
      toast.error('Failed to load databases');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDatabases();
  }, [fetchDatabases]);

  useEffect(() => {
    const isProcessing = databases.some(db => db.status === 'processing');
    if (!isProcessing) return;

    const timeout = setTimeout(() => {
      fetchDatabases();
    }, 5000);
    return () => clearTimeout(timeout);
  }, [databases, fetchDatabases]);

  const handleFile = async (file) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Please upload a PDF file');
      return;
    }
    setUploading(true);
    const toastId = toast.loading(`Uploading ${file.name}...`);
    try {
      const res = await uploadPdf(file);
      if (res.success) {
        toast.success('Upload successful! Indexing started in background.', { id: toastId });
        fetchDatabases();
      } else {
        toast.error(res.error || 'Upload failed', { id: toastId });
      }
    } catch (err) {
      toast.error('Connection error', { id: toastId });
    } finally {
      setUploading(false);
    }
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setDragActive(true);
  };

  const onDragLeave = () => {
    setDragActive(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleDelete = async (db) => {
    const confirmation = window.prompt(`Type the database name to confirm deletion: ${db.name}`);
    if (confirmation !== db.name) {
      toast.error('Deletion cancelled. Confirmation text did not match.');
      return;
    }
    const toastId = toast.loading('Deleting...');
    const res = await deleteDatabase(db.id);
    if (res.success) {
      toast.success('Deleted successfully', { id: toastId });
      fetchDatabases();
    } else {
      toast.error(res.error || 'Delete failed', { id: toastId });
    }
  };

  return (
    <div className="management-page">
      <div className="management-header">
        <h1>Database Management</h1>
        <p>Manage your formulary PDFs and monitor their indexing status for the RAG engine.</p>
      </div>
      {/* Upload Zone */}
      <div 
        className={`upload-zone ${dragActive ? 'active' : ''} ${uploading ? 'uploading' : ''}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <div className="upload-icon">📄</div>
        <h3>{uploading ? 'Uploading...' : 'Upload Formulary PDF'}</h3>
        <p>Drag and drop your PDF here, or click to browse</p>
        <input 
          type="file" 
          accept=".pdf" 
          onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
          disabled={uploading}
        />
        {uploading && <div className="progress-bar-container"><div className="progress-bar-indefinite"></div></div>}
      </div>
      {/* Database Table */}
      <div className="db-list-section">
        <div className="section-header">
          <h2>Active Databases</h2>
          <button className="refresh-btn" onClick={fetchDatabases} disabled={loading}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M23 4v6h-6M1 20v-6h6"></path>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
            </svg>
          </button>
        </div>
        {loading && databases.length === 0 ? (
          <div className="loading-state">Loading databases...</div>
        ) : databases.length === 0 ? (
          <div className="empty-state">
            <p>No databases found. Upload a PDF to get started.</p>
          </div>
        ) : (
          <table className="management-table">
            <thead>
              <tr>
                <th>Name / Filename</th>
                <th>Status</th>
                <th>Drug Count</th>
                <th>File Size</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {databases.map(db => (
                <tr key={db.id}>
                  <td>
                    <div className="db-name">{db.name}</div>
                    <div className="db-filename">{db.filename}</div>
                  </td>
                  <td>
                    <span className={`status-badge ${String(db.status).toLowerCase()}`}>
                      {db.status === 'processing' && <span className="spinner-small"></span>}
                      {db.status}
                    </span>
                  </td>
                  <td>{db.drugCount ?? '—'}</td>
                  <td>{db.size}</td>
                  <td>{db.uploadedAt ? new Date(db.uploadedAt).toLocaleString() : 'Unknown'}</td>
                  <td>
                    <div className="action-buttons">
                      <button 
                        className="action-btn delete" 
                        onClick={() => handleDelete(db)}
                        title="Delete database"
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="3 6 5 6 21 6"></polyline>
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <style>{`
        .management-page {
          padding: 2rem;
          max-width: 1200px;
          margin: 0 auto;
        }
        .management-header {
          margin-bottom: 2rem;
        }
        .management-header h1 {
          font-size: 2.5rem;
          font-weight: 700;
          color: #1e293b;
          margin-bottom: 0.5rem;
        }
        .management-header p {
          color: #64748b;
          font-size: 1.1rem;
        }
        .upload-zone {
          border: 2px dashed #cbd5e1;
          border-radius: 1rem;
          padding: 3rem;
          text-align: center;
          background: #f8fafc;
          transition: all 0.3s ease;
          position: relative;
          cursor: pointer;
          margin-bottom: 3rem;
        }
        .upload-zone:hover, .upload-zone.active {
          border-color: #10b981;
          background: #f0fdf4;
        }
        .upload-zone input {
          position: absolute;
          top: 0; left: 0; width: 100%; height: 100%;
          opacity: 0;
          cursor: pointer;
        }
        .upload-icon {
          font-size: 3rem;
          margin-bottom: 1rem;
        }
        .upload-zone.uploading {
          pointer-events: none;
          opacity: 0.7;
        }
        .progress-bar-container {
          width: 100%;
          height: 4px;
          background: #e2e8f0;
          border-radius: 2px;
          margin-top: 1.5rem;
          overflow: hidden;
        }
        .progress-bar-indefinite {
          width: 30%;
          height: 100%;
          background: #10b981;
          animation: move 1.5s infinite linear;
        }
        @keyframes move {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(400%); }
        }
        .db-list-section {
          background: white;
          border-radius: 1rem;
          box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
          padding: 2rem;
        }
        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1.5rem;
        }
        .refresh-btn {
          background: none;
          border: none;
          color: #64748b;
          cursor: pointer;
          padding: 0.5rem;
          border-radius: 0.5rem;
          transition: background 0.2s;
        }
        .refresh-btn:hover { background: #f1f5f9; }
        .management-table {
          width: 100%;
          border-collapse: collapse;
        }
        .management-table th {
          text-align: left;
          padding: 1rem;
          border-bottom: 2px solid #f1f5f9;
          color: #475569;
          font-weight: 600;
        }
        .management-table td {
          padding: 1rem;
          border-bottom: 1px solid #f1f5f9;
        }
        .db-name { font-weight: 600; color: #1e293b; }
        .db-filename { font-size: 0.85rem; color: #64748b; }
        .status-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.25rem 0.75rem;
          border-radius: 9999px;
          font-size: 0.85rem;
          font-weight: 600;
        }
        .status-badge.ready { background: #dcfce7; color: #166534; }
        .status-badge.processing { background: #fef9c3; color: #854d0e; }
        .status-badge.not.processed { background: #f1f5f9; color: #475569; }
        .spinner-small {
          width: 12px;
          height: 12px;
          border: 2px solid #854d0e;
          border-top-color: transparent;
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .action-btn {
          background: none;
          border: none;
          padding: 0.5rem;
          border-radius: 0.5rem;
          cursor: pointer;
          transition: all 0.2s;
        }
        .action-btn.delete { color: #ef4444; }
        .action-btn.delete:hover { background: #fef2f2; }
      `}</style>
    </div>
  );
};

export default DatabaseManagement;
