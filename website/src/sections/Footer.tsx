import { useEffect, useRef, useState } from 'react';
import { 
  TrendingUp, 
  Github, 
  Linkedin, 
  Twitter, 
  Mail,
  ExternalLink,
  Heart
} from 'lucide-react';

const footerLinks = {
  product: [
    { label: 'Features', href: '#features' },
    { label: 'Strategies', href: '#strategies' },
    { label: 'Performance', href: '#performance' },
    { label: 'Dashboard', href: 'http://localhost:5000' },
  ],
  company: [
    { label: 'About', href: '#about' },
    { label: 'Founder', href: '#founder' },
    { label: 'Careers', href: '#' },
    { label: 'Contact', href: '#' },
  ],
  resources: [
    { label: 'Documentation', href: '#' },
    { label: 'API Reference', href: '#' },
    { label: 'Blog', href: '#' },
    { label: 'Support', href: '#' },
  ],
  legal: [
    { label: 'Privacy Policy', href: '#' },
    { label: 'Terms of Service', href: '#' },
    { label: 'Disclaimer', href: '#' },
  ],
};

const Footer = () => {
  const [typedText, setTypedText] = useState('');
  const [isVisible, setIsVisible] = useState(false);
  const footerRef = useRef<HTMLDivElement>(null);
  
  const statusText = 'System Status: Operational | Version 2.4.0 | Last Update: 2026-02-25';

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.2 }
    );

    if (footerRef.current) {
      observer.observe(footerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  // Typing effect for status line
  useEffect(() => {
    if (!isVisible) return;

    let index = 0;
    const timer = setInterval(() => {
      if (index <= statusText.length) {
        setTypedText(statusText.slice(0, index));
        index++;
      } else {
        clearInterval(timer);
      }
    }, 30);

    return () => clearInterval(timer);
  }, [isVisible]);

  return (
    <footer 
      ref={footerRef}
      className="relative w-full bg-prima-dark border-t border-prima-border"
    >
      {/* Main Footer */}
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 xl:px-12 py-16">
        <div 
          className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8 lg:gap-12"
          style={{
            opacity: isVisible ? 1 : 0,
            transform: isVisible ? 'translateY(0)' : 'translateY(20px)',
            transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          {/* Brand Column */}
          <div className="col-span-2 md:col-span-4 lg:col-span-1">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-prima-green/10 flex items-center justify-center border border-prima-green/30">
                <TrendingUp className="w-5 h-5 text-prima-green" />
              </div>
              <div>
                <div className="text-lg font-bold text-prima-text tracking-wide">PRIMA PRO</div>
                <div className="text-xs text-prima-muted">Algorithmic Trading Bot</div>
              </div>
            </div>
            <p className="text-sm text-prima-muted mb-6 max-w-xs">
              Professional-grade algorithmic trading for the NSE market. 
              Built with precision, speed, and reliability.
            </p>
            
            {/* Social Links */}
            <div className="flex gap-3">
              {[
                { icon: Github, href: '#' },
                { icon: Linkedin, href: 'https://www.linkedin.com/in/malik-musaib-9ab6931bb' },
                { icon: Twitter, href: '#' },
                { icon: Mail, href: 'mailto:malik.musaib@email.com' },
              ].map(({ icon: Icon, href }, index) => (
                <a
                  key={index}
                  href={href}
                  target={href.startsWith('http') ? '_blank' : undefined}
                  rel={href.startsWith('http') ? 'noopener noreferrer' : undefined}
                  className="w-10 h-10 rounded-lg bg-prima-dark-secondary border border-prima-border flex items-center justify-center hover:border-prima-green/50 hover:bg-prima-green/10 transition-all duration-300 group"
                >
                  <Icon className="w-4 h-4 text-prima-muted group-hover:text-prima-green transition-colors" />
                </a>
              ))}
            </div>
          </div>

          {/* Link Columns */}
          {Object.entries(footerLinks).map(([category, links], categoryIndex) => (
            <div 
              key={category}
              style={{
                opacity: isVisible ? 1 : 0,
                transform: isVisible ? 'translateY(0)' : 'translateY(20px)',
                transition: `all 0.6s cubic-bezier(0.16, 1, 0.3, 1) ${0.1 + categoryIndex * 0.05}s`,
              }}
            >
              <h4 className="text-sm font-semibold text-prima-text uppercase tracking-wider mb-4">
                {category}
              </h4>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      target={link.href.startsWith('http') ? '_blank' : undefined}
                      rel={link.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                      className="group flex items-center text-sm text-prima-muted hover:text-prima-green transition-colors duration-300"
                    >
                      <span className="relative">
                        {link.label}
                        <span className="absolute -bottom-0.5 left-0 w-0 h-px bg-prima-green transition-all duration-300 group-hover:w-full" />
                      </span>
                      {link.href.startsWith('http') && (
                        <ExternalLink className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                      )}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Status Bar */}
      <div className="border-t border-prima-border">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 xl:px-12 py-4">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
            {/* Typed Status */}
            <div className="font-mono text-xs text-prima-muted flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-prima-green animate-pulse" />
              <span>{typedText}</span>
              <span className="w-2 h-4 bg-prima-green/50 animate-pulse" />
            </div>

            {/* Copyright */}
            <div className="flex items-center gap-1 text-xs text-prima-muted">
              <span>© 2026 PRIMA PRO. Made with</span>
              <Heart className="w-3 h-3 text-prima-red fill-prima-red" />
              <span>in Mumbai</span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
