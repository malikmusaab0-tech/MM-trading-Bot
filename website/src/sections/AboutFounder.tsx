import { useEffect, useRef, useState } from 'react';
import { 
  Award, 
  Briefcase, 
  GraduationCap, 
  Linkedin, 
  Mail, 
  MapPin, 
  TrendingUp,
  BadgeCheck,
  Trophy,
  FileCheck
} from 'lucide-react';

interface Achievement {
  icon: React.ElementType;
  title: string;
  subtitle: string;
  date?: string;
}

const achievements: Achievement[] = [
  {
    icon: BadgeCheck,
    title: 'CFA Level 1',
    subtitle: 'Chartered Financial Analyst',
    date: 'Jan 2025',
  },
  {
    icon: FileCheck,
    title: 'Alteryx Designer Core',
    subtitle: 'Certified Professional',
    date: 'Jan 2026',
  },
  {
    icon: Trophy,
    title: 'Business Excellence Award',
    subtitle: 'eClerx',
    date: 'Feb 2025',
  },
  {
    icon: Award,
    title: 'Fixed Income Fundamentals',
    subtitle: 'NASBA Certified',
    date: 'Feb 2026',
  },
];

const AboutFounder = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
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

  return (
    <section 
      ref={sectionRef}
      className="relative w-full py-24 lg:py-32 bg-prima-dark overflow-hidden"
    >
      {/* Background */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-0 w-[500px] h-[500px] bg-prima-green/5 rounded-full blur-[150px] -translate-y-1/2" />
        <div className="absolute inset-0 grid-pattern opacity-20" />
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
            <Briefcase className="w-4 h-4 text-prima-green" />
            <span className="text-sm font-medium text-prima-muted">Leadership</span>
          </div>
          
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-prima-text mb-6">
            Meet the{' '}
            <span className="text-gradient">Founder</span>
          </h2>
        </div>

        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left: Profile Image */}
          <div 
            className="relative"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateX(0)' : 'translateX(-30px)',
              transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s',
            }}
          >
            <div className="relative max-w-md mx-auto lg:mx-0">
              {/* Decorative elements */}
              <div className="absolute -top-4 -left-4 w-24 h-24 border-l-2 border-t-2 border-prima-green/30 rounded-tl-3xl" />
              <div className="absolute -bottom-4 -right-4 w-24 h-24 border-r-2 border-b-2 border-prima-green/30 rounded-br-3xl" />
              
              {/* Image container */}
              <div className="relative rounded-2xl overflow-hidden border border-prima-border group">
                {/* Glow */}
                <div className="absolute -inset-px rounded-2xl bg-gradient-to-r from-prima-green/20 to-prima-blue/20 opacity-50 blur-sm" />
                
                <div className="relative aspect-[3/4] overflow-hidden">
                  <img 
                    src="/founder-profile.jpg" 
                    alt="Malik (Musa'b) Musaib"
                    className={`
                      w-full h-full object-cover transition-all duration-700
                      ${imageLoaded ? 'opacity-100 scale-100' : 'opacity-0 scale-105'}
                      group-hover:scale-105
                    `}
                    onLoad={() => setImageLoaded(true)}
                  />
                  
                  {/* Gradient overlay */}
                  <div className="absolute inset-0 bg-gradient-to-t from-prima-dark/80 via-transparent to-transparent" />
                  
                  {/* Name badge */}
                  <div className="absolute bottom-4 left-4 right-4">
                    <div className="p-4 rounded-xl bg-prima-dark/90 backdrop-blur-sm border border-prima-border">
                      <h3 className="text-xl font-bold text-prima-text">Malik (Musa'b) Musaib</h3>
                      <p className="text-sm text-prima-green">Founder & CEO, PRIMA PRO</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Social links */}
              <div className="flex gap-3 mt-6 justify-center lg:justify-start">
                <a 
                  href="https://www.linkedin.com/in/malik-musaib-9ab6931bb" 
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-12 h-12 rounded-xl bg-prima-dark-secondary border border-prima-border flex items-center justify-center hover:border-prima-green/50 hover:bg-prima-green/10 transition-all duration-300 group"
                >
                  <Linkedin className="w-5 h-5 text-prima-muted group-hover:text-prima-green transition-colors" />
                </a>
                <a 
                  href="mailto:malik.musaib@email.com"
                  className="w-12 h-12 rounded-xl bg-prima-dark-secondary border border-prima-border flex items-center justify-center hover:border-prima-green/50 hover:bg-prima-green/10 transition-all duration-300 group"
                >
                  <Mail className="w-5 h-5 text-prima-muted group-hover:text-prima-green transition-colors" />
                </a>
              </div>
            </div>
          </div>

          {/* Right: Bio & Achievements */}
          <div 
            className="space-y-8"
            style={{
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateX(0)' : 'translateX(30px)',
              transition: 'all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.3s',
            }}
          >
            {/* Bio */}
            <div>
              <div className="flex items-center gap-2 text-prima-muted mb-4">
                <MapPin className="w-4 h-4" />
                <span className="text-sm">Mumbai, Maharashtra, India</span>
              </div>
              
              <p className="text-lg text-prima-text leading-relaxed mb-4">
                Dedicated Financial Analyst with over a year of professional experience in 
                trade reconciliations, capital markets, and regulatory reporting at{' '}
                <span className="text-prima-green font-semibold">eClerx</span>.
              </p>
              
              <p className="text-prima-muted leading-relaxed mb-4">
                Cleared CFA Level 1 in January 2025, demonstrating a strong foundation in 
                financial analysis, investment management, and ethical standards. Proficient 
                in data analysis, business consulting, and process automation with a proven 
                track record of streamlining workflows and enhancing operational efficiency.
              </p>

              <div className="flex items-center gap-2 text-prima-muted">
                <GraduationCap className="w-4 h-4" />
                <span className="text-sm">BFM, Finance & Financial Management Services - Jai Hind College, Mumbai</span>
              </div>
            </div>

            {/* Current Role */}
            <div className="p-5 rounded-xl bg-prima-dark-secondary/50 border border-prima-border">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-prima-green/10 flex items-center justify-center flex-shrink-0">
                  <TrendingUp className="w-6 h-6 text-prima-green" />
                </div>
                <div>
                  <div className="text-sm text-prima-muted mb-1">Current Role</div>
                  <div className="text-lg font-semibold text-prima-text">Senior Analyst</div>
                  <div className="text-prima-green">eClerx - Capital Markets Division</div>
                  <p className="text-sm text-prima-muted mt-2">
                    Specializing in trade reconciliations, automation initiatives, and 
                    process optimization for major financial institutions.
                  </p>
                </div>
              </div>
            </div>

            {/* Achievements Grid */}
            <div>
              <h4 className="text-sm font-semibold text-prima-muted uppercase tracking-wider mb-4">
                Certifications & Awards
              </h4>
              <div className="grid grid-cols-2 gap-3">
                {achievements.map((achievement, index) => {
                  const Icon = achievement.icon;
                  return (
                    <div
                      key={achievement.title}
                      className="group p-4 rounded-xl bg-prima-dark-secondary/50 border border-prima-border hover:border-prima-green/30 transition-all duration-300"
                      style={{
                        opacity: isVisible ? 1 : 0,
                        transform: isVisible ? 'translateY(0) scale(1)' : 'translateY(20px) scale(0.95)',
                        transition: `all 0.5s cubic-bezier(0.16, 1, 0.3, 1) ${0.5 + index * 0.1}s`,
                      }}
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-lg bg-prima-green/10 flex items-center justify-center flex-shrink-0 group-hover:bg-prima-green/20 transition-colors">
                          <Icon className="w-5 h-5 text-prima-green" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-prima-text truncate">
                            {achievement.title}
                          </div>
                          <div className="text-xs text-prima-muted truncate">
                            {achievement.subtitle}
                          </div>
                          {achievement.date && (
                            <div className="text-xs text-prima-green font-mono mt-1">
                              {achievement.date}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default AboutFounder;
