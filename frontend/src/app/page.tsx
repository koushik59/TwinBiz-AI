"use client";

import { Button } from "@/components/ui";
import { Logo, ThemeToggle } from "@/components/shell";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Bot,
  Boxes,
  Eye,
  FlaskConical,
  GitCompareArrows,
  HeartHandshake,
  LineChart,
  Quote,
  ShieldAlert,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

/* ------------------------- animated counter ------------------------- */
function Counter({ to, suffix = "", prefix = "" }: { to: number; suffix?: string; prefix?: string }) {
  const [n, setN] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting) return;
        const start = performance.now();
        const tick = (t: number) => {
          const p = Math.min((t - start) / 1400, 1);
          setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
          if (p < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
        obs.disconnect();
      },
      { threshold: 0.4 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [to]);
  return (
    <span ref={ref} className="tabular-nums">
      {prefix}
      {n.toLocaleString("en-IN")}
      {suffix}
    </span>
  );
}

const FEATURES = [
  { icon: FlaskConical, title: "AI Business Simulator", desc: "Move sliders — price, marketing, staffing — and watch revenue, profit and satisfaction react instantly, before you spend a rupee." },
  { icon: GitCompareArrows, title: "Scenario Comparison", desc: "Save competing strategies and compare them side-by-side. TwinBiz highlights the winner on profit, risk and growth." },
  { icon: LineChart, title: "ML Forecasting", desc: "Machine-learning models trained on your history predict sales, demand, cash flow and staffing needs weeks ahead." },
  { icon: Bot, title: "AI Business Advisor", desc: "Ask questions in plain language. Gemini-powered answers grounded in your live business data, with confidence scores." },
  { icon: ShieldAlert, title: "Risk Analyzer", desc: "Continuous scanning for stockouts, cash-flow trouble, churn and overstock — ranked by severity before they hurt." },
  { icon: Boxes, title: "Inventory Intelligence", desc: "Restock predictions, fast/slow-mover detection, and days-to-stockout for every product in your catalog." },
];

const STEPS = [
  { n: "01", title: "Create your twin", desc: "Enter your business profile — type, revenue, team, products. TwinBiz builds a live virtual replica with a year of intelligence." },
  { n: "02", title: "Simulate decisions", desc: "Test price changes, hiring, offers and more inside the twin. Every lever shows its ripple effect on profit and customers." },
  { n: "03", title: "Decide with confidence", desc: "Compare scenarios, read AI recommendations, and roll out only the moves the data supports." },
];

const TESTIMONIALS = [
  { quote: "I tested a ₹2 price increase on milk in the simulator first. It predicted the dip in footfall almost exactly — and saved my margin.", name: "Ramesh Gupta", role: "Supermarket owner, Hyderabad" },
  { quote: "The advisor told me hiring one more baker would pay for itself in 6 weeks. It took 5.", name: "Priya Nair", role: "Bakery owner, Kochi" },
  { quote: "Stockout alerts alone stopped us losing weekend sales on our top 10 SKUs.", name: "Arjun Mehta", role: "Pharmacy chain, Pune" },
];

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.55, ease: "easeOut" as const },
};

export default function Landing() {
  return (
    <div className="min-h-screen bg-bg">
      {/* nav */}
      <header className="sticky top-0 z-50 border-b border-line bg-bg/75 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Logo />
          <nav className="hidden items-center gap-6 text-sm text-ink-2 md:flex">
            <a href="#features" className="hover:text-ink transition-colors">Features</a>
            <a href="#how" className="hover:text-ink transition-colors">How it works</a>
            <a href="#about" className="hover:text-ink transition-colors">About us</a>
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link href="/login"><Button variant="ghost" size="sm">Sign in</Button></Link>
            <Link href="/register"><Button size="sm">Get Started</Button></Link>
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="aurora relative overflow-hidden">
        <div className="mx-auto max-w-6xl px-4 pb-20 pt-20 text-center md:pt-28">
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-brand/30 bg-brand-soft px-3 py-1 text-xs font-semibold text-brand">
              <Sparkles size={13} /> Digital Twin + Decision Intelligence for SMEs
            </span>
            <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-bold leading-[1.08] tracking-tight md:text-6xl">
              Predict before <span className="gradient-text">you decide.</span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-base text-ink-2 md:text-lg">
              TwinBiz AI builds a living virtual replica of your business. Test price changes, hiring,
              offers and inventory moves inside the twin — see profit, risk and customer impact
              <em> before</em> spending real money.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link href="/register"><Button size="lg">Get Started Free <ArrowRight size={16} /></Button></Link>
              <Link href="/login"><Button variant="outline" size="lg">View Live Demo</Button></Link>
            </div>
            <p className="mt-3 text-xs text-muted">Demo login: demo@twinbiz.ai · demo1234</p>
          </motion.div>

          {/* hero mock: what-if */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.25 }}
            className="glass mx-auto mt-14 max-w-3xl rounded-3xl p-6 text-left shadow-2xl shadow-brand/10"
          >
            <p className="text-xs font-semibold uppercase tracking-widest text-muted">Live simulation</p>
            <p className="mt-1.5 text-lg font-semibold">&ldquo;What happens if I increase milk price by ₹2?&rdquo;</p>
            <div className="mt-4 grid grid-cols-3 gap-3">
              {[
                { label: "Sales", value: "−6.2%", bad: true },
                { label: "Profit", value: "+3.1%", bad: false },
                { label: "Satisfaction", value: "−4.8%", bad: true },
              ].map((m) => (
                <div key={m.label} className="rounded-2xl border border-line bg-surface/60 p-4">
                  <p className="text-xs text-muted">{m.label}</p>
                  <p className={`mt-1 text-xl font-bold tabular-nums ${m.bad ? "text-critical" : "text-[var(--delta-good)]"}`}>{m.value}</p>
                </div>
              ))}
            </div>
            <p className="mt-4 flex items-center gap-2 rounded-xl bg-brand-soft px-4 py-3 text-sm text-ink-2">
              <Bot size={16} className="shrink-0 text-brand" />
              Recommendation: raise price on low-elasticity items only — projected net profit +2.4% with minimal churn.
            </p>
          </motion.div>
        </div>
      </section>

      {/* stats */}
      <section className="border-y border-line bg-surface/50">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-4 py-12 md:grid-cols-4">
          {[
            { to: 12800, suffix: "+", label: "Decisions simulated" },
            { to: 94, suffix: "%", label: "Forecast accuracy" },
            { to: 27, prefix: "₹", suffix: "L", label: "Avg. losses prevented / yr" },
            { to: 365, suffix: " days", label: "Of twin intelligence" },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-3xl font-bold tracking-tight md:text-4xl">
                <Counter to={s.to} suffix={s.suffix} prefix={s.prefix} />
              </p>
              <p className="mt-1 text-xs text-muted">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* features */}
      <section id="features" className="mx-auto max-w-6xl px-4 py-20">
        <motion.div {...fadeUp} className="text-center">
          <h2 className="text-3xl font-bold tracking-tight md:text-4xl">Your business, twice.</h2>
          <p className="mx-auto mt-3 max-w-xl text-ink-2">One that runs in the real world — and one where mistakes are free.</p>
        </motion.div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.div key={f.title} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.06 }} className="glass group rounded-2xl p-6 transition-transform hover:-translate-y-1">
              <div className="inline-flex rounded-xl bg-brand-soft p-3 text-brand transition-transform group-hover:scale-110">
                <f.icon size={20} />
              </div>
              <h3 className="mt-4 font-semibold">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* how it works */}
      <section id="how" className="border-y border-line bg-surface/50 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <motion.h2 {...fadeUp} className="text-center text-3xl font-bold tracking-tight md:text-4xl">How it works</motion.h2>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <motion.div key={s.n} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.1 }} className="relative rounded-2xl border border-line p-6">
                <span className="gradient-text text-4xl font-bold">{s.n}</span>
                <h3 className="mt-3 font-semibold">{s.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* about us */}
      <section id="about" className="mx-auto max-w-6xl px-4 py-20">
        <motion.div {...fadeUp} className="text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-brand/30 bg-brand-soft px-3 py-1 text-xs font-semibold text-brand">
            <HeartHandshake size={13} /> About us
          </span>
          <h2 className="mt-4 text-3xl font-bold tracking-tight md:text-4xl">
            Big-company intelligence, <span className="gradient-text">corner-shop simple.</span>
          </h2>
          <p className="mx-auto mt-4 max-w-3xl leading-relaxed text-ink-2">
            India runs on millions of small businesses — supermarkets, kiranas, restaurants, pharmacies —
            and every one of them makes high-stakes decisions on gut feeling alone. Enterprises have
            analysts, dashboards and simulations; the shop owner gets a notebook and a prayer.
            <strong className="text-ink"> We built TwinBiz AI to close that gap.</strong>
          </p>
        </motion.div>

        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {[
            {
              icon: Target,
              title: "Our goal",
              desc: "Make decision intelligence — the kind only large enterprises could afford — available to every small business owner, in plain language, at kirana-scale prices. No analysts required, no jargon, just answers.",
            },
            {
              icon: Eye,
              title: "Our vision",
              desc: "A future where no shop owner loses a season to a guessable mistake. Every price change, every hire, every product launch tested in a digital twin first — so mistakes stay virtual and profits stay real.",
            },
            {
              icon: HeartHandshake,
              title: "What we promise",
              desc: "Honest AI. Every prediction shows its reasoning, its assumptions and a confidence score — always labeled “Predicted, not guaranteed.” Demo data is never passed off as real, and nothing changes without your approval.",
            },
          ].map((v, i) => (
            <motion.div key={v.title} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.08 }} className="glass rounded-2xl p-6">
              <div className="inline-flex rounded-xl bg-brand-soft p-3 text-brand"><v.icon size={20} /></div>
              <h3 className="mt-4 font-semibold">{v.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{v.desc}</p>
            </motion.div>
          ))}
        </div>

        <motion.p {...fadeUp} className="mx-auto mt-10 max-w-2xl text-center text-sm italic leading-relaxed text-muted">
          &ldquo;Pilots train on flight simulators. Banks stress-test on models. We believe the corner
          store — the riskiest business of all — deserves the same superpower.&rdquo;
        </motion.p>
      </section>

      {/* testimonials */}
      <section className="border-y border-line bg-surface/50 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <motion.h2 {...fadeUp} className="text-center text-3xl font-bold tracking-tight md:text-4xl">Owners who predicted first</motion.h2>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {TESTIMONIALS.map((t, i) => (
              <motion.figure key={t.name} {...fadeUp} transition={{ ...fadeUp.transition, delay: i * 0.08 }} className="glass rounded-2xl p-6">
                <Quote size={20} className="text-brand" />
                <blockquote className="mt-3 text-sm leading-relaxed text-ink-2">{t.quote}</blockquote>
                <figcaption className="mt-4">
                  <p className="text-sm font-semibold">{t.name}</p>
                  <p className="text-xs text-muted">{t.role}</p>
                </figcaption>
              </motion.figure>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-4 py-20 text-center">
        <motion.div {...fadeUp} className="aurora glass rounded-3xl px-6 py-16">
          <TrendingUp size={28} className="mx-auto text-brand" />
          <h2 className="mt-4 text-3xl font-bold tracking-tight md:text-4xl">Stop guessing. Start simulating.</h2>
          <p className="mx-auto mt-3 max-w-lg text-ink-2">Create your digital twin in under two minutes — with a full year of intelligence generated instantly.</p>
          <Link href="/register" className="mt-7 inline-block">
            <Button size="lg">Create Your Twin <ArrowRight size={16} /></Button>
          </Link>
        </motion.div>
      </section>

      {/* footer */}
      <footer className="border-t border-line py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 md:flex-row">
          <Logo />
          <p className="text-xs text-muted">© 2026 TwinBiz AI — Predict Before You Decide. Built for the Ideathon.</p>
        </div>
      </footer>
    </div>
  );
}
