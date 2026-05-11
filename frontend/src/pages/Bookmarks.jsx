import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import DrugCard from '../components/DrugCard';
import QuickFormularyModal from '../components/QuickFormularyModal';

const getBookmarks = () => {
  try {
    return JSON.parse(localStorage.getItem('mediformulary_bookmarks') || '[]');
  } catch {
    return [];
  }
};

const saveBookmarks = (bm) => {
  localStorage.setItem('mediformulary_bookmarks', JSON.stringify(bm));
  window.dispatchEvent(new Event('bookmarksChange'));
};

const Bookmarks = () => {
  const [bookmarks, setBookmarks] = useState(getBookmarks());
  const [selectedModalDrug, setSelectedModalDrug] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handleStorageChange = () => setBookmarks(getBookmarks());
    window.addEventListener('bookmarksChange', handleStorageChange);
    return () => window.removeEventListener('bookmarksChange', handleStorageChange);
  }, []);

  const removeBookmark = (name) => {
    const updated = bookmarks.filter(b => b.name !== name);
    saveBookmarks(updated);
    setBookmarks(updated);
  };

  const handleView = (drugName) => {
    const drugObj = bookmarks.find(b => b.name === drugName);
    if (drugObj) {
      setSelectedModalDrug(drugObj);
    }
  };

  const handleBookmarkToggle = (drug) => {
    removeBookmark(drug.name);
  };

  return (
    <div className="bookmarks-page">
      <div className="bookmarks-header">
        <div className="container">
          <div className="header-flex">
            <div>
              <nav className="breadcrumb">
                <Link to="/">Home</Link>
                <span>/</span>
                <span className="active">Saved Items</span>
              </nav>
              <h1>Your Saved Medications</h1>
              <p>Quick access to your most important formulary data.</p>
            </div>
            <div className="bookmarks-stats">
              <div className="stat-pill">
                <strong>{bookmarks.length}</strong> Items
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="container">
        {bookmarks.length === 0 ? (
          <div className="empty-bookmarks">
            <div className="empty-icon">🔖</div>
            <h2>No saved medications yet</h2>
            <p>You can add drugs to your bookmarks directly from the Search page.</p>
            <Link to="/search" className="btn-primary-pill">
              Go to Search
            </Link>
          </div>
        ) : (
          <div className="bookmarks-grid">
            {bookmarks.map((drug, index) => (
              <DrugCard
                key={`${drug.name}-${index}`}
                drug={drug}
                bookmarked={true}
                onView={handleView}
                onBookmark={handleBookmarkToggle}
                onRemove={removeBookmark}
              />
            ))}
          </div>
        )}
      </div>
      <QuickFormularyModal 
        open={!!selectedModalDrug} 
        drug={selectedModalDrug} 
        onClose={() => setSelectedModalDrug(null)} 
      />
    </div>
  );
};

export default Bookmarks;
