import { useEffect, useRef, useState } from 'react';
import { 
  Cpu, 
  ScanLine, 
  Shield, 
  Wallet, 
  BarChart3, 
  Power,
  ArrowRight
} from 'lucide-react';

interface Feature {
  icon: React.ElementType;
  title: string;
  description: string;
  color: string;
}

const features: Feature[] = [
  {
    icon: Cpu,
    title: 'Multi-Strategy Engine',
    description: 'Deploy 8 proven strategies from VWAP Momentum to Bollinger Reversals. Auto-select the best strategy based on market conditions.',
    color: 'from-prima-green/20 to-prima-green/5',
  },
  {
    icon: ScanLine,
    title: 'Real-Time Scanner',
    description: 'Scans the entire NSE market for liquid opportunities every second. Never miss a trading opportunity again.',
    color: 'from-prima-blue/20 to-prima-blue/5',
  },
  {
    icon: Shield,
    title: 'Risk Management',
    description: 'Intelligent stop-loss, take-profit, and position sizing. Protects your capital with trailing stops and risk limits.',
    color: 'from-prima-yellow/20 to-prima-yellow/5',
  },
  {
    icon: Wallet,
    title: 'Paper Trading',
    description: 'Test strategies risk-free with virtual capital. Validate your approach before deploying real money.',
    color: 'from-purple-500/20 to-purple-500/5',
  },
  {
    icon: BarChart3,
    title: 'Live P&L Tracking',
    description: 'Real-time portfolio analytics and performance metrics. Track every trade with detailed insights.',
    color: 'from-pink-500/20 to-pink-500/5',
  },
  {
    icon: Power,
    title: 'Kill Switch',
    description: 'Instantly close all positions with one click. Emergency protection when you need it most.',
    color: 'from-prima-red/20 to-prima-red/5',
  },
];

const Features = () => {
  const [visibleCards, setVisibleCards] = useState<Set<number>>(new Set());
  const [hoveredCard, setHoveredCard] = useState<number | null>(null);
  const sectionRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const index = cardRefs.current.indexOf(entry.target as HTMLDivElement);
          if (entry.isIntersecting && index !== -1) {
            setVisibleCards((prev) => new Set([...prev, index]));
          }
        });
      },
      { threshold: 0.2, rootMargin: '0px 0px -50px 0px' }
    );

    cardRefs.current.forEach((ref) => {
      if (ref) observer.observe(ref);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <section 
      ref={sectionRef}
      className="relative w-full py-24 lg:py-32 bg-prima-dark"
    >
      {/* Background elements */}
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-prima-green/5 rounded-full blur-[120px]" />
        <div className="absolute inset-0 grid-pattern opacity-20" />
      </div>

      <div className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 xl:px-12">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16 lg:mb-20">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-prima-dark-secondary border border-prima-border mb-6">
            <Cpu className="w-4 h-4 text-prima-green" />
            <span className="text-sm font-medium text-prima-muted">Powerful Features</span>
          </div>
          
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-prima-text mb-6">
            Everything You Need to{' '}
            <span className="text-gradient">Trade with Confidence</span>
          </h2>
          
          <p className="text-lg text-prima-muted leading-relaxed">
            Professional-grade tools designed for speed, precision, and profitability. 
            Built by traders, for traders.
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            const isVisible = visibleCards.has(index);
            const isHovered = hoveredCard === index;
            
            // Staggered offset for masonry effect
            const offsetY = index % 3 === 1 ? 'lg:mt-10' : index % 3 === 2 ? 'lg:mt-20' : '';
            
            return (
              <div
                key={feature.title}
                ref={(el) => { cardRefs.current[index] = el; }}
                className={`group relative ${offsetY}`}
                onMouseEnter={() => setHoveredCard(index)}
                onMouseLeave={() => setHoveredCard(null)}
                style={{
                  opacity: isVisible ? 1 : 0,
                  transform: isVisible ? 'translateY(0) rotateX(0)' : 'translateY(40px) rotateX(15deg)',
                  transition: `all 0.8s cubic-bezier(0.16, 1, 0.3, 1) ${index * 0.1}s`,
                }}
              >
                <div 
                  className={`
                    relative h-full p-6 lg:p-8 rounded-2xl 
                    bg-gradient-to-b from-prima-dark-secondary/80 to-prima-dark-secondary/40
                    border border-prima-border backdrop-blur-sm
                    transition-all duration-500
                    ${isHovered ? 'border-prima-green/50 shadow-glow' : ''}
                  `}
                >
                  {/* Holographic sheen effect on hover */}
                  <div 
                    className={`
                      absolute inset-0 rounded-2xl overflow-hidden pointer-events-none
                      transition-opacity duration-500
                      ${isHovered ? 'opacity-100' : 'opacity-0'}
                    `}
                  >
                    <div 
                      className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000"
                    />
                  </div>

                  {/* Icon */}
                  <div 
                    className={`
                      relative w-14 h-14 rounded-xl mb-6 flex items-center justify-center
                      bg-gradient-to-br ${feature.color} border border-white/10
                      transition-all duration-500
                      ${isHovered ? 'scale-110 rotate-3' : ''}
                    `}
                  >
                    <Icon 
                      className={`
                        w-7 h-7 transition-all duration-500
                        ${isHovered ? 'text-prima-green' : 'text-prima-text'}
                      `} 
                    />
                  </div>

                  {/* Content */}
                  <h3 className="text-xl font-bold text-prima-text mb-3 group-hover:text-prima-green transition-colors duration-300">
                    {feature.title}
                  </h3>
                  
                  <p className="text-prima-muted leading-relaxed mb-4">
                    {feature.description}
                  </p>

                  {/* Learn more link */}
                  <div 
                    className={`
                      flex items-center gap-2 text-sm font-medium
                      transition-all duration-300
                      ${isHovered ? 'text-prima-green translate-x-2' : 'text-prima-muted'}
                    `}
                  >
                    <span>Learn more</span>
                    <ArrowRight className="w-4 h-4" />
                  </div>

                  {/* Corner accent */}
                  <div 
                    className={`
                      absolute top-0 right-0 w-20 h-20 
                      bg-gradient-to-br ${feature.color} rounded-bl-full opacity-20
                      transition-opacity duration-500
                      ${isHovered ? 'opacity-40' : ''}
                    `}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default Features;
