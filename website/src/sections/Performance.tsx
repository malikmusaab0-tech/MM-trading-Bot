import { useEffect, useRef, useState } from 'react';
import { TrendingUp, Clock, Activity, Shield, Zap, BarChart3 } from 'lucide-react';

interface Stat {
  icon: React.ElementType;
  value: string;
  label: string;
  suffix?: string;
  color: string;
}

const stats: Stat[] = [
  {
    icon: Shield,
    value: '99.9',
    suffix: '%',
    label: 'Uptime',
    color: 'text-prima-green',
  },
  {
    icon: Zap,
    value: '<50',
    suffix: 'ms',
    label: 'Execution Latency',
    color: 'text-prima-blue',
  },
  {
    icon: Clock,
    value: '24/7',
    label: 'Market Monitoring',
    color: 'text-prima-yellow',
  },
  {
    icon: Activity,
    value: '1,847',
    label: 'Stocks Scanned',
    color: 'text-purple-400',
  },
];

const Performance = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [counters, setCounters] = useState<number[]>(stats.map(() => 0));
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

  // Animate counters
  useEffect(() => {
    if (!isVisible) return;

    const duration = 2000;
    const steps = 60;
    const interval = duration / steps;

    let step = 0;
    const timer = setInterval(() => {
      step++;
      const progress = step / steps;
      const easeOut = 1 - Math.pow(1 - progress, 3);

      setCounters(
        stats.map((stat) => {
          const numValue = parseFloat(stat.value.replace(/[^0-9.]/g, ''));
          if (isNaN(numValue)) return 0;
          return Math.floor(numValue * easeOut);
        })
      );

      if (step >= steps) {
        clearInterval(timer);
        setCounters(stats.map((stat) => parseFloat(stat.value.replace(/[^0-9.]/g, '')) || 0));
      }
    }, interval);

    return () => clearInterval(timer);
  }, [isVisible]);

  const formatCounter = (index: number, stat: Stat) => {
    if (stat.value === '24/7') return '24/7';
    if (stat.value.startsWith('<')) return `<${counters[index]}${stat.suffix || ''}`;
    return `${counters[index].toLocaleString()}${stat.suffix || ''}`;
  };

  return (
    <section 
      ref={sectionRef}
      className="relative w-full py-24 lg:py-32 bg-prima-dark overflow-hidden"
    >
      {/* Background */}
      <div className="absolute inset-0">
        <div className="absolute bottom-0 right-0 w-[600px] h-[600px] bg-prima-blue/5 rounded-full blur-[150px]" />
        <div className="absolute inset-0 grid-pattern opacity-20" />
      </div>

      <div className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 xl:px-12">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left: Content */}
          <div 
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
              transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-prima-dark-secondary border border-prima-border mb-6">
              <BarChart3 className="w-4 h-4 text-prima-green" />
              <span className="text-sm font-medium text-prima-muted">Performance</span>
            </div>
            
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-prima-text mb-6">
              Performance That{' '}
              <span className="text-gradient">Speaks</span>
            </h2>
            
            <p className="text-lg text-prima-muted leading-relaxed mb-8">
              Real-time metrics and historical performance tracking. Our bot operates 
              with institutional-grade reliability and speed, ensuring you never miss 
              an opportunity in the market.
            </p>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-4">
              {stats.map((stat, index) => {
                const Icon = stat.icon;
                return (
                  <div
                    key={stat.label}
                    className="group p-5 rounded-xl bg-prima-dark-secondary/50 border border-prima-border hover:border-prima-green/30 transition-all duration-300"
                    style={{
                      opacity: isVisible ? 1 : 0,
                      transform: isVisible ? 'translateY(0)' : 'translateY(20px)',
                      transition: `all 0.6s cubic-bezier(0.16, 1, 0.3, 1) ${0.2 + index * 0.1}s`,
                    }}
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-lg bg-prima-dark flex items-center justify-center group-hover:bg-prima-green/10 transition-colors">
                        <Icon className={`w-5 h-5 ${stat.color}`} />
                      </div>
                    </div>
                    <div className={`text-2xl lg:text-3xl font-bold font-mono ${stat.color}`}>
                      {formatCounter(index, stat)}
                    </div>
                    <div className="text-sm text-prima-muted mt-1">{stat.label}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Chart Visualization */}
          <div 
            className="relative"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateX(0)' : 'translateX(30px)',
              transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.3s',
            }}
          >
            <div className="relative rounded-2xl overflow-hidden border border-prima-border">
              {/* Glow */}
              <div className="absolute -inset-px rounded-2xl bg-gradient-to-r from-prima-green/20 to-prima-blue/20 opacity-50 blur-sm" />
              
              {/* Chart image */}
              <img 
                src="/performance-chart.jpg" 
                alt="Performance Chart"
                className="w-full h-auto relative z-10"
              />
              
              {/* Overlay stats */}
              <div className="absolute bottom-4 left-4 right-4 z-20">
                <div className="p-4 rounded-xl bg-prima-dark/90 backdrop-blur-sm border border-prima-border">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs text-prima-muted mb-1">Total Returns (YTD)</div>
                      <div className="text-2xl font-bold text-prima-green font-mono">+47.8%</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-prima-muted mb-1">Sharpe Ratio</div>
                      <div className="text-2xl font-bold text-prima-blue font-mono">2.34</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-prima-muted mb-1">Max Drawdown</div>
                      <div className="text-2xl font-bold text-prima-yellow font-mono">-8.2%</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Floating badge */}
            <div 
              className="absolute -top-4 -right-4 px-4 py-2 rounded-lg bg-prima-green/10 border border-prima-green/30 backdrop-blur-sm"
              style={{
                animation: 'float 4s ease-in-out infinite',
              }}
            >
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-prima-green" />
                <span className="text-sm font-semibold text-prima-green">Beating Nifty 50</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Performance;
