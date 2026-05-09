import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { ArrowRight, ExternalLink, Play, TrendingUp, Monitor, Tablet, Smartphone } from 'lucide-react';

const Hero = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const heroRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!heroRef.current) return;
      const rect = heroRef.current.getBoundingClientRect();
      const x = (e.clientX - rect.left - rect.width / 2) / rect.width;
      const y = (e.clientY - rect.top - rect.height / 2) / rect.height;
      setMousePosition({ x, y });
    };

    const hero = heroRef.current;
    if (hero) {
      hero.addEventListener('mousemove', handleMouseMove, { passive: true });
    }

    return () => {
      if (hero) {
        hero.removeEventListener('mousemove', handleMouseMove);
      }
    };
  }, []);

  return (
    <section
      ref={heroRef}
      className="relative min-h-screen w-full overflow-hidden bg-prima-dark"
    >
      {/* Animated Background */}
      <div className="absolute inset-0">
        {/* Gradient orbs */}
        <div 
          className="absolute top-1/4 left-1/4 w-[600px] h-[600px] rounded-full opacity-20"
          style={{
            background: 'radial-gradient(circle, rgba(0, 229, 160, 0.15) 0%, transparent 70%)',
            filter: 'blur(80px)',
            transform: `translate(${mousePosition.x * -30}px, ${mousePosition.y * -30}px)`,
          }}
        />
        <div 
          className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] rounded-full opacity-15"
          style={{
            background: 'radial-gradient(circle, rgba(14, 165, 233, 0.12) 0%, transparent 70%)',
            filter: 'blur(60px)',
            transform: `translate(${mousePosition.x * 20}px, ${mousePosition.y * 20}px)`,
          }}
        />
        
        {/* Grid pattern */}
        <div className="absolute inset-0 grid-pattern opacity-30" />
        
        {/* Floating particles */}
        <div className="absolute inset-0 overflow-hidden">
          {[...Array(20)].map((_, i) => (
            <div
              key={i}
              className="absolute w-1 h-1 bg-prima-green/30 rounded-full animate-float"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                animationDelay: `${Math.random() * 6}s`,
                animationDuration: `${6 + Math.random() * 4}s`,
              }}
            />
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 xl:px-12 min-h-screen flex items-center">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-8 items-center w-full py-20">
          {/* Left: Text Content */}
          <div className={`space-y-8 transition-all duration-1000 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
            {/* Badge */}
            <div 
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-prima-green/10 border border-prima-green/30"
              style={{ transitionDelay: '0.1s' }}
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-prima-green opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-prima-green"></span>
              </span>
              <span className="text-sm font-medium text-prima-green font-mono">v2.4.0 Now Live</span>
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-bold leading-tight">
              <span className="text-prima-text">Trade Smarter with</span>
              <br />
              <span className="text-gradient">PRIMA PRO</span>
            </h1>

            {/* Subheading */}
            <p className="text-lg sm:text-xl text-prima-muted max-w-xl leading-relaxed">
              Advanced algorithmic trading bot with multi-strategy execution, 
              real-time market scanning, and intelligent risk management for the NSE market.
            </p>

            {/* Stats */}
            <div className="flex flex-wrap gap-6 sm:gap-10">
              {[
                { value: '8', label: 'Strategies' },
                { value: '<50ms', label: 'Latency' },
                { value: '24/7', label: 'Monitoring' },
              ].map((stat, index) => (
                <div 
                  key={stat.label}
                  className="text-center"
                  style={{ 
                    opacity: isVisible ? 1 : 0, 
                    transform: isVisible ? 'translateY(0)' : 'translateY(20px)',
                    transition: `all 0.6s cubic-bezier(0.16, 1, 0.3, 1) ${0.4 + index * 0.1}s`
                  }}
                >
                  <div className="text-2xl sm:text-3xl font-bold text-prima-green font-mono">{stat.value}</div>
                  <div className="text-sm text-prima-muted">{stat.label}</div>
                </div>
              ))}
            </div>

            {/* CTAs */}
            <div 
              className="flex flex-wrap gap-4"
              style={{ 
                opacity: isVisible ? 1 : 0, 
                transform: isVisible ? 'translateY(0)' : 'translateY(20px)',
                transition: 'all 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.6s'
              }}
            >
              <Button 
                size="lg"
                className="bg-prima-green text-prima-dark hover:bg-prima-green/90 font-semibold px-8 py-6 text-base group glow-green transition-all duration-300"
                onClick={() => window.open('http://localhost:5000', '_blank')}
              >
                <TrendingUp className="w-5 h-5 mr-2" />
                Launch Dashboard
                <ExternalLink className="w-4 h-4 ml-2 transition-transform group-hover:translate-x-1" />
              </Button>
              <Button 
                size="lg"
                variant="outline"
                className="border-prima-border text-prima-text hover:bg-prima-dark-secondary hover:border-prima-green/50 px-8 py-6 text-base group transition-all duration-300"
              >
                <Play className="w-5 h-5 mr-2 text-prima-green" />
                View Documentation
                <ArrowRight className="w-4 h-4 ml-2 transition-transform group-hover:translate-x-1" />
              </Button>
            </div>
          </div>

          {/* Right: Multi-Device Preview */}
          <div 
            className={`relative transition-all duration-1000 ${isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-12'}`}
            style={{ 
              transitionDelay: '0.5s',
              perspective: '1000px',
            }}
          >
            {/* Device Showcase Container */}
            <div className="relative">
              {/* Glow effect behind devices */}
              <div className="absolute -inset-8 bg-gradient-to-r from-prima-green/15 to-prima-blue/15 rounded-3xl blur-3xl opacity-60" />
              
              {/* Devices Composition */}
              <div 
                className="relative"
                style={{
                  transform: `perspective(1200px) rotateY(${mousePosition.x * -5}deg) rotateX(${mousePosition.y * 5}deg)`,
                  transition: 'transform 0.1s ease-out',
                }}
              >
                {/* Laptop (Main) */}
                <div className="relative z-30 animate-float" style={{ animationDuration: '6s' }}>
                  <div className="relative rounded-xl overflow-hidden border border-prima-border shadow-2xl">
                    <img 
                      src="/hero-laptop.jpg" 
                      alt="PRIMA PRO on Laptop"
                      className="w-full h-auto"
                    />
                  </div>
                </div>

                {/* Tablet (Behind, Left) */}
                <div 
                  className="absolute -bottom-8 -left-16 w-2/3 z-20 animate-float"
                  style={{ 
                    animationDuration: '7s',
                    animationDelay: '0.5s',
                    transform: `translateZ(-50px) rotateY(15deg)`,
                  }}
                >
                  <div className="relative rounded-xl overflow-hidden border border-prima-border shadow-xl">
                    <img 
                      src="/hero-tablet.jpg" 
                      alt="PRIMA PRO on Tablet"
                      className="w-full h-auto"
                    />
                  </div>
                </div>

                {/* Mobile (Behind, Right) */}
                <div 
                  className="absolute -bottom-4 -right-12 w-1/3 z-20 animate-float"
                  style={{ 
                    animationDuration: '5s',
                    animationDelay: '1s',
                    transform: `translateZ(-30px) rotateY(-10deg)`,
                  }}
                >
                  <div className="relative rounded-xl overflow-hidden border border-prima-border shadow-xl">
                    <img 
                      src="/hero-mobile.jpg" 
                      alt="PRIMA PRO on Mobile"
                      className="w-full h-auto"
                    />
                  </div>
                </div>
              </div>

              {/* Device Labels */}
              <div className="flex justify-center gap-6 mt-8">
                {[
                  { icon: Monitor, label: 'Desktop' },
                  { icon: Tablet, label: 'Tablet' },
                  { icon: Smartphone, label: 'Mobile' },
                ].map(({ icon: Icon, label }) => (
                  <div 
                    key={label}
                    className="flex items-center gap-2 px-4 py-2 rounded-full bg-prima-dark-secondary/80 border border-prima-border"
                  >
                    <Icon className="w-4 h-4 text-prima-green" />
                    <span className="text-sm text-prima-muted">{label}</span>
                  </div>
                ))}
              </div>

              {/* Floating stats cards */}
              <div 
                className="absolute top-1/2 -left-8 px-4 py-3 rounded-lg bg-prima-dark-secondary/95 backdrop-blur-sm border border-prima-border shadow-xl z-40"
                style={{
                  transform: `translate(${mousePosition.x * -20}px, ${mousePosition.y * -20}px)`,
                }}
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-prima-green/10 flex items-center justify-center">
                    <TrendingUp className="w-5 h-5 text-prima-green" />
                  </div>
                  <div>
                    <div className="text-xs text-prima-muted">Today's P&L</div>
                    <div className="text-lg font-bold text-prima-green font-mono">+₹12,450</div>
                  </div>
                </div>
              </div>

              <div 
                className="absolute top-1/4 -right-6 px-4 py-3 rounded-lg bg-prima-dark-secondary/95 backdrop-blur-sm border border-prima-border shadow-xl z-40"
                style={{
                  transform: `translate(${mousePosition.x * 15}px, ${mousePosition.y * 15}px)`,
                }}
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-prima-blue/10 flex items-center justify-center">
                    <div className="w-5 h-5 rounded-full border-2 border-prima-blue border-t-transparent animate-spin" />
                  </div>
                  <div>
                    <div className="text-xs text-prima-muted">Scanning</div>
                    <div className="text-sm font-semibold text-prima-text">1,847 stocks</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom gradient fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-prima-dark to-transparent" />
    </section>
  );
};

export default Hero;
