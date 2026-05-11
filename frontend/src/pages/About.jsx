import React from 'react';

const aboutCards = [
  {
    number: '1',
    chip: 'Mission',
    title: 'Empowering Healthcare',
    body: 'Our mission is to simplify the complex world of medical formularies. We provide healthcare professionals with instantaneous, accurate data to make better prescribing decisions.',
    floatStyle: {},
    delayClass: 'delay-1',
  },
  {
    number: '2',
    chip: 'Platform',
    title: 'Precision Engineered',
    body: 'Built on a robust, high-performance architecture, MediFormulary ensures zero-latency searches so you can find critical drug interactions and dosage guides without delay.',
    floatStyle: { borderRadius: '15px', animationDelay: '1s' },
    delayClass: 'delay-2',
  },
  {
    number: '3',
    chip: 'Our Team',
    title: 'Medical & Tech Experts',
    body: 'We are a dedicated group of pharmacists, developers, and designers working synchronously to bridge the gap between complex pharmaceutical data and user-friendly interfaces.',
    floatStyle: { animationDelay: '3s' },
    delayClass: 'delay-3',
  },
  {
    number: '4',
    chip: 'Integrity',
    title: 'Data You Can Trust',
    body: 'Every piece of data on our platform is sourced from verified medical databases and constantly updated to reflect the latest FDA guidelines and formulary changes.',
    floatStyle: { borderRadius: '10px', animationDelay: '1.5s' },
    delayClass: 'delay-4',
  },
];

const About = () => {
  return (
    <main className="about-section">
      <div className="about-header fade-up delay-1">
        <h1>About <span>Us</span></h1>
      </div>

      <div className="about-grid">
        {aboutCards.map((card) => (
          <div key={card.number} className={`about-card fade-up ${card.delayClass}`}>
            <div className="about-card-number">{card.number}</div>
            <div className="float-elem" style={card.floatStyle}></div>
            <div className="about-card-content">
              <div className="chip-title">{card.chip}</div>
              <h3>{card.title}</h3>
              <p>{card.body}</p>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
};

export default About;
