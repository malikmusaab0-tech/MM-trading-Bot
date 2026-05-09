import { useEffect, useRef, useState } from 'react';
import { TrendingUp, Activity, Zap, Target, BarChart2, Volume2, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';

interface Strategy {
  name: string;
  fullName: string;
  description: string;
  icon: React.ElementType;
  type: 'momentum' | 'reversal' | 'trend' | 'breakout';
  signal: 'buy' | 'sell' | 'neutral';
  performance: string;
}

const strategies: Strategy[] = [
  {
    name: 'VWAP_MOMENTUM',
    fullName: 'VWAP Momentum',
    description: 'Trades when price breaks above/below VWAP with volume confirmation. Best for intraday trends.',
    icon: TrendingUp,
    type: 'momentum',
    signal: 'buy',
    performance: '+12.4%',
  },
  {
    name: 'EMA_CROSSOVER',
    fullName: 'EMA Crossover',
    description: 'Classic moving average crossover strategy using 9/21 EMA for trend identification.',
    icon: Activity,
    type: 'trend',
    signal: 'buy',
    performance: '+8.7%',
  },
  {
    name: 'SUPERTREND',
    fullName: 'Supertrend',
    description: 'Follows the supertrend indicator for directional trades with ATR-based stops.',
    icon: Zap,
    type: 'trend',
    signal: 'neutral',
    performance: '+15.2%',
  },
  {
    name: 'BOLLINGER_REVERSAL',
    fullName: 'Bollinger Reversal',
    description: 'Mean reversion strategy trading bounces off Bollinger Bands.',
    icon: Target,
    type: 'reversal',
    signal: 'sell',
    performance: '+6.3%',
  },
  {
    name: 'RSI_REVERSAL',
    fullName: 'RSI Reversal',
    description: 'Identifies overbought/oversold conditions using RSI for counter-trend entries.',
    icon: BarChart2,
    type: 'reversal',
    signal: 'buy',
    performance: '+9.1%',
  },
  {
    name: 'MACD_MOMENTUM',
    fullName: 'MACD Momentum',
    description: 'Uses MACD histogram and signal line crossovers for momentum trades.',
    icon: Activity,
    type: 'momentum',
    signal: 'neutral',
    performance: '+11.8%',
  },
  {
    name: 'VOLUME_BREAKOUT',
    fullName: 'Volume Breakout',
    description: 'Detects breakouts confirmed by above-average volume spikes.',
    icon: Volume2,
    type: 'breakout',
    signal: 'buy',
    performance: '+14.6%',
  },
  {
    name: 'ATR_BREAKOUT',
    fullName: 'ATR Breakout',
    description: 'Volatility-based breakout strategy using Average True Range.',
    icon: ArrowUpRight,
    type: 'breakout',
    signal: 'sell',
    performance: '+7.9%',
  },
];

const typeColors = {
  momentum: 'text-prima-green bg-prima-green/10 border-prima-green/30',
  reversal: 'text-prima-blue bg-prima-blue/10 border-prima-blue/30',
  trend: 'text-prima-yellow bg-prima-yellow/10 border-prima-yellow/30',
  breakout: 'text-purple-400 bg-purple-400/10 border-purple-400/30',
};

const Strategies = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.2 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  // Auto-rotate active strategy
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % strategies.length);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const getSignalIcon = (signal: string) => {
    switch (signal) {
      case 'buy':
        return <ArrowUpRight className="w-4 h-4 text-prima-green" />;
      case 'sell':
        return <ArrowDownRight className="w-4 h-4 text-prima-red" />;
      default:
        return <Minus className="w-4 h-4 text-prima-muted" />;
    }
  };

  return (
    <section 
      ref={sectionRef}
      className="relative w-full py-24 lg:py-32 bg-prima-dark overflow-hidden"
    >
      {/* Background */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1000px] h-[600px] bg-prima-green/5 rounded-full blur-[150px]" />
        
        {/* Horizontal scrolling grid lines */}
        <div className="absolute inset-0 overflow-hidden opacity-10">
          <div 
            className="absolute inset-0"
            style={{
              backgroundImage: 'repeating-linear-gradient(90deg, #30363d 0px, #30363d 1px, transparent 1px, transparent 100px)',
              animation: 'slide-left 20s linear infinite',
            }}
          />
        </div>
      </div>

      <div className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-8 xl:px-12">
        {/* Section Header */}
        <div 
          className="text-center max-w-3xl mx-auto mb-16"
          style={{
            opacity: isVisible ? 1 : 0,
            transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
            transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-prima-dark-secondary border border-prima-border mb-6">
            <Zap className="w-4 h-4 text-prima-green" />
            <span className="text-sm font-medium text-prima-muted">Trading Strategies</span>
          </div>
          
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-prima-text mb-6">
            8{' '}
            <span className="text-gradient">Battle-Tested</span>{' '}
            Strategies
          </h2>
          
          <p className="text-lg text-prima-muted leading-relaxed">
            From momentum breaks to mean reversions, deploy the right strategy 
            for any market condition. Auto-selection based on real-time analysis.
          </p>
        </div>

        {/* Strategies Display */}
        <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">
          {/* Left: Active Strategy Detail */}
          <div 
            className="order-2 lg:order-1"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateX(0)' : 'translateX(-30px)',
              transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s',
            }}
          >
            <div className="relative p-8 rounded-2xl bg-gradient-to-br from-prima-dark-secondary to-prima-dark border border-prima-border">
              {/* Glow effect */}
              <div className="absolute -inset-px rounded-2xl bg-gradient-to-r from-prima-green/20 via-prima-blue/20 to-prima-green/20 opacity-50 blur-sm" />
              
              <div className="relative">
                {/* Strategy header */}
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`px-3 py-1 rounded-full text-xs font-mono border ${typeColors[strategies[activeIndex].type]}`}>
                        {strategies[activeIndex].type.toUpperCase()}
                      </span>
                      <span className="text-prima-muted font-mono text-sm">
                        {strategies[activeIndex].name}
                      </span>
                    </div>
                    <h3 className="text-2xl lg:text-3xl font-bold text-prima-text">
                      {strategies[activeIndex].fullName}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-prima-green/10 border border-prima-green/30">
                    {getSignalIcon(strategies[activeIndex].signal)}
                    <span className="text-prima-green font-mono font-bold">
                      {strategies[activeIndex].performance}
                    </span>
                  </div>
                </div>

                {/* Description */}
                <p className="text-prima-muted leading-relaxed mb-8">
                  {strategies[activeIndex].description}
                </p>

                {/* Strategy metrics */}
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: 'Win Rate', value: '68%' },
                    { label: 'Avg Hold', value: '4.2h' },
                    { label: 'Trades/Day', value: '12' },
                  ].map((metric) => (
                    <div 
                      key={metric.label}
                      className="p-4 rounded-xl bg-prima-dark/50 border border-prima-border"
                    >
                      <div className="text-xs text-prima-muted mb-1">{metric.label}</div>
                      <div className="text-lg font-bold text-prima-text font-mono">{metric.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Right: Strategy Grid */}
          <div 
            className="order-1 lg:order-2"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateX(0)' : 'translateX(30px)',
              transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.3s',
            }}
          >
            <div className="grid grid-cols-2 gap-3">
              {strategies.map((strategy, index) => {
                const Icon = strategy.icon;
                const isActive = index === activeIndex;
                
                return (
                  <button
                    key={strategy.name}
                    onClick={() => setActiveIndex(index)}
                    className={`
                      relative p-4 rounded-xl text-left transition-all duration-300
                      ${isActive 
                        ? 'bg-prima-dark-secondary border-2 border-prima-green shadow-glow' 
                        : 'bg-prima-dark-secondary/50 border border-prima-border hover:border-prima-green/30'
                      }
                    `}
                  >
                    {/* Active indicator */}
                    {isActive && (
                      <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-prima-green animate-pulse" />
                    )}
                    
                    <div className="flex items-start gap-3">
                      <div 
                        className={`
                          w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0
                          ${isActive ? 'bg-prima-green/20' : 'bg-prima-dark'}
                        `}
                      >
                        <Icon 
                          className={`w-5 h-5 ${isActive ? 'text-prima-green' : 'text-prima-muted'}`} 
                        />
                      </div>
                      
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-prima-text truncate">
                          {strategy.fullName}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          {getSignalIcon(strategy.signal)}
                          <span className="text-xs text-prima-green font-mono">{strategy.performance}</span>
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Animation keyframes */}
      <style>{`
        @keyframes slide-left {
          from { transform: translateX(0); }
          to { transform: translateX(-100px); }
        }
      `}</style>
    </section>
  );
};

export default Strategies;
