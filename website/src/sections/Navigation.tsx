import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { TrendingUp, Menu, X, ExternalLink } from 'lucide-react';

const navLinks = [
  { label: 'Features', href: '#features' },
  { label: 'Strategies', href: '#strategies' },
  { label: 'Performance', href: '#performance' },
  { label: 'About', href: '#founder' },
];

const Navigation = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (href: string) => {
    setIsMobileMenuOpen(false);
    if (href.startsWith('#')) {
      const element = document.querySelector(href);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  return (
    <>
      <nav 
        className={`
          fixed top-0 left-0 right-0 z-50 transition-all duration-500
          ${isScrolled 
            ? 'bg-prima-dark/90 backdrop-blur-xl border-b border-prima-border' 
            : 'bg-transparent'
          }
        `}
      >
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 xl:px-12">
          <div className="flex items-center justify-between h-16 lg:h-20">
            {/* Logo */}
            <a 
              href="#" 
              className="flex items-center gap-3 group"
              onClick={(e) => {
                e.preventDefault();
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            >
              <div className="w-10 h-10 rounded-xl bg-prima-green/10 flex items-center justify-center border border-prima-green/30 group-hover:bg-prima-green/20 transition-colors">
                <TrendingUp className="w-5 h-5 text-prima-green" />
              </div>
              <div className="hidden sm:block">
                <div className="text-lg font-bold text-prima-text tracking-wide group-hover:text-prima-green transition-colors">
                  PRIMA PRO
                </div>
                <div className="text-xs text-prima-muted">Algorithmic Trading</div>
              </div>
            </a>

            {/* Desktop Navigation */}
            <div className="hidden lg:flex items-center gap-8">
              {navLinks.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  onClick={(e) => {
                    e.preventDefault();
                    scrollToSection(link.href);
                  }}
                  className="relative text-sm font-medium text-prima-muted hover:text-prima-text transition-colors group"
                >
                  {link.label}
                  <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-prima-green transition-all duration-300 group-hover:w-full" />
                </a>
              ))}
            </div>

            {/* CTA Button */}
            <div className="hidden lg:flex items-center gap-4">
              <Button 
                size="sm"
                className="bg-prima-green text-prima-dark hover:bg-prima-green/90 font-semibold group"
                onClick={() => window.open('http://localhost:5000', '_blank')}
              >
                Launch Dashboard
                <ExternalLink className="w-4 h-4 ml-2 transition-transform group-hover:translate-x-0.5" />
              </Button>
            </div>

            {/* Mobile Menu Button */}
            <button
              className="lg:hidden w-10 h-10 rounded-lg bg-prima-dark-secondary border border-prima-border flex items-center justify-center"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? (
                <X className="w-5 h-5 text-prima-text" />
              ) : (
                <Menu className="w-5 h-5 text-prima-text" />
              )}
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile Menu */}
      <div 
        className={`
          fixed inset-0 z-40 lg:hidden transition-all duration-500
          ${isMobileMenuOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}
        `}
      >
        {/* Backdrop */}
        <div 
          className="absolute inset-0 bg-prima-dark/95 backdrop-blur-xl"
          onClick={() => setIsMobileMenuOpen(false)}
        />
        
        {/* Menu Content */}
        <div 
          className={`
            absolute top-20 left-4 right-4 p-6 rounded-2xl bg-prima-dark-secondary border border-prima-border
            transition-all duration-500
            ${isMobileMenuOpen ? 'translate-y-0 opacity-100' : '-translate-y-4 opacity-0'}
          `}
        >
          <div className="space-y-4">
            {navLinks.map((link, index) => (
              <a
                key={link.label}
                href={link.href}
                onClick={(e) => {
                  e.preventDefault();
                  scrollToSection(link.href);
                }}
                className="block py-3 px-4 rounded-xl text-lg font-medium text-prima-text hover:bg-prima-dark hover:text-prima-green transition-all"
                style={{
                  transitionDelay: `${index * 50}ms`,
                }}
              >
                {link.label}
              </a>
            ))}
            
            <div className="pt-4 border-t border-prima-border">
              <Button 
                className="w-full bg-prima-green text-prima-dark hover:bg-prima-green/90 font-semibold py-6"
                onClick={() => {
                  setIsMobileMenuOpen(false);
                  window.open('http://localhost:5000', '_blank');
                }}
              >
                Launch Dashboard
                <ExternalLink className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default Navigation;
