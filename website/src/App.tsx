import Navigation from './sections/Navigation';
import Hero from './sections/Hero';
import Features from './sections/Features';
import Strategies from './sections/Strategies';
import Performance from './sections/Performance';
import CTA from './sections/CTA';
import Footer from './sections/Footer';
import './App.css';

function App() {
  return (
    <div className="min-h-screen bg-prima-dark text-prima-text">
      <Navigation />
      
      <main>
        <Hero />
        
        <div id="features">
          <Features />
        </div>
        
        <div id="strategies">
          <Strategies />
        </div>
        
        <div id="performance">
          <Performance />
        </div>
        
        <CTA />
      </main>
      
      <Footer />
    </div>
  );
}

export default App;
