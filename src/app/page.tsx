import type { Metadata } from "next";

import { Navbar } from "@/components/marketing/navbar";
import { Hero } from "@/components/marketing/hero";
import { FeaturesSection } from "@/components/marketing/features-section";
import { IndustriesSection } from "@/components/marketing/industries-section";
import { PricingSection } from "@/components/marketing/pricing-section";
import { TestimonialsSection } from "@/components/marketing/testimonials-section";
import { FaqSection } from "@/components/marketing/faq-section";
import { CtaSection } from "@/components/marketing/cta-section";
import { Footer } from "@/components/marketing/footer";

export const metadata: Metadata = {
  title: "LeadMaster AI — Enterprise Lead Intelligence Platform",
  description:
    "Discover, enrich, and convert high-quality leads with AI-powered search, scanning, and intelligence built for modern revenue teams.",
};

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">
        <Hero />
        <FeaturesSection />
        <IndustriesSection />
        <PricingSection />
        <TestimonialsSection />
        <FaqSection />
        <CtaSection />
      </main>
      <Footer />
    </div>
  );
}
