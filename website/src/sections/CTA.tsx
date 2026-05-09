import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { ExternalLink, Sparkles, ArrowRight } from 'lucide-react';

const CTA = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.3 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <section 
      ref={sectionRef}
      className="relative w-full py-24 lg:py-32 bg-prima-dark overflow-hidden"
    >
      {/* Animated Background */}
      <div className="absolute inset-0">
        {/* Pulsing radial gradient */}
        <div 
          className="absolute inset-0"
          style={{
            background: 'radial-gradient(ellipse at center, rgba(0, 229, 160, 0.15) 0%, transparent 60%)',
            animation: 'pulse-scale 4s ease-in-out infinite',
          }}
        />
        
        {/* Secondary glow */}
        <div 
          className="absolute inset-0"
          style={{
            background: 'radial-gradient(ellipse at center, rgba(14, 165, 233, 0.1) 0%, transparent 50%)',
            animation: 'pulse-scale 4s ease-in-out infinite 2s',
          }}
        />
        
        {/* Grid pattern */}
        <div className="absolute inset-0 grid-pattern opacity-30" />
        
        {/* Floating particles */}
        <div className="absolute inset-0 overflow-hidden">
          {[...Array(15)].map((_, i) => (
            <div
              key={i}
              className="absolute w-1 h-1 bg-prima-green/40 rounded-full"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                animation: `float ${5 + Math.random() * 5}s ease-in-out infinite`,
                animationDelay: `${Math.random() * 5}s`,
              }}
            />
          ))}
        </div>
      </div>

      <div className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 xl:px-12">
        <div 
          className="max-w-4xl mx-auto text-center"
          style={{
            opacity: isVisible ? 1 : 0,
            transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
            transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          {/* Badge */}
          <div 
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-prima-green/10 border border-prima-green/30 mb-8"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'scale(1)' : 'scale(0.9)',
              transition: 'all 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.2s',
            }}
          >
            <Sparkles className="w-4 h-4 text-prima-green" />
            <span className="text-sm font-medium text-prima-green">Start Trading Today</span>
          </div>

          {/* Headline */}
          <h2 
            className="text-4xl sm:text-5xl lg:text-6xl font-bold text-prima-text mb-6"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateY(0)' : 'translateY(20px)',
              transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.3s',
            }}
          >
            Ready to Start{' '}
            <span className="text-gradient">Trading?</span>
          </h2>

          {/* Subheading */}
          <p 
            className="text-lg sm:text-xl text-prima-muted max-w-2xl mx-auto mb-10 leading-relaxed"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateY(0)' : 'translateY(20px)',
              transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.4s',
            }}
          >
            Launch the dashboard and experience the future of algorithmic trading. 
            Professional-grade tools, now at your fingertips.
          </p>

          {/* CTA Button */}
          <div 
            className="flex flex-col sm:flex-row gap-4 justify-center items-center"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateY(0)' : 'translateY(20px)',
              transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.5s',
            }}
          >
            <div
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => setIsHovered(false)}
              className="relative"
            >
              {/* Button glow effect */}
              <div 
                className={`
                  absolute -inset-1 rounded-xl bg-gradient-to-r from-prima-green to-prima-blue
                  opacity-0 blur-lg transition-opacity duration-500
                  ${isHovered ? 'opacity-60' : ''}
                `}
              />
              
              <Button 
                size="lg"
                className="relative bg-prima-green text-prima-dark hover:bg-prima-green/90 font-bold px-10 py-7 text-lg group transition-all duration-300"
                onClick={() => window.open('http://localhost:5000', '_blank')}
              >
                <ExternalLink className="w-5 h-5 mr-3" />
                Launch Dashboard
                <ArrowRight className="w-5 h-5 ml-3 transition-transform group-hover:translate-x-1" />
              </Button>
            </div>

            <p className="text-sm text-prima-muted">
              Free to use • Paper trading mode available
            </p>
          </div>

          {/* Trust indicators */}
          <div 
            className="flex flex-wrap justify-center gap-6 mt-12"
            style={{
              opacity: isVisible ? 1 : 0,
              transition: 'opacity 0.8s ease 0.7s',
            }}
          >
            {[
              'NSE Market Data',
              'Real-time Execution',
              'Risk Management',
            ].map((item) => (
              <div key={item} className="flex items-center gap-2 text-prima-muted">
                <div className="w-2 h-2 rounded-full bg-prima-green" />
                <span className="text-sm">{item}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Animation keyframes */}
      <style>{`
        @keyframes pulse-scale {
          0%, 100% {
            transform: scale(1);
            opacity: 0.5;
          }
          50% {
            transform: scale(1.2);
            opacity: 0.8;
          }
        }
      `}</style>
    </section>
  );
};

export default CTA;
